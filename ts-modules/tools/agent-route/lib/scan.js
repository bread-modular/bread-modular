// SCAN (§4.1): routing-disabled eval + circuit-json extraction + clustering.
//
// scanBoard(board) -> scan object:
//   {
//     board, circuitJsonPath, distPath,
//     components: [{ ref, sourceId, pcbId, center:{x,y}, w, h, placed }],
//     pads: [{ x, y, ref, sourcePortId, pcbPortId }],
//     holes: [{ x, y, ref, diameter }],
//     board: { width, height, cx, cy, minTraceWidth },
//     nets: [{ key, members: [ref...], global: bool }],
//     connections: ["REF.pin > REF.pin", ...],   // one per connectivity net
//     connEndpoints: { "REF.pin > REF.pin": [{ref,x,y}, {ref,x,y}, ...] },
//     sections: [{ name, members: [ref...] }],   // clustered; whole-board fallback
//   }
//
// Clustering: connected-components of the components×nets bipartite graph
// (non-global nets only; nets touching >40% of components are "global" and
// excluded from affinity), then y-row bucketing split (8mm gap) with small-row
// merge + unplaced attach. Boards with <6 routable connections collapse to a
// single whole-board section (e.g. blank).
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import {
  TSMODULES_DIR,
  boardEntry,
  distCircuit,
  readJson,
} from "./constants.js";

const GLOBAL_NET_FRAC = 0.4;
const ROW_GAP = 8; // mm — y-gap that splits rows
const MIN_CONNS_MULTI = 6; // fewer routable conns -> single section fallback

export function runRoutingDisabledEval(board) {
  const entry = boardEntry(board);
  if (!existsSync(entry)) {
    throw new Error(
      `no entry file for board '${board}' (expected src/${board}/${board}.circuit.tsx)`,
    );
  }
  execFileSync(
    "tsci",
    ["build", "--routing-disabled", entry],
    { cwd: TSMODULES_DIR, stdio: ["ignore", "ignore", "pipe"] },
  );
  const dist = distCircuit(board);
  if (!existsSync(dist) || readJson(dist).length === 0) {
    throw new Error(`routing-disabled eval produced no circuit.json for '${board}'`);
  }
  return dist;
}

export function loadScanFromCircuitJson(board, circuitJsonPath) {
  const els = readJson(circuitJsonPath);
  const byType = (t) => els.filter((e) => e.type === t);

  const boardEl = byType("pcb_board")[0] ?? {};
  const boardInfo = {
    width: boardEl.width ?? 0,
    height: boardEl.height ?? 0,
    cx: boardEl.center?.x ?? 0,
    cy: boardEl.center?.y ?? 0,
    minTraceWidth: boardEl.min_trace_width ?? 0.15,
  };

  const compName = new Map(
    byType("source_component").map((e) => [e.source_component_id, e.name]),
  );
  const pcbBySource = new Map(
    byType("pcb_component").map((e) => [e.source_component_id, e]),
  );
  const portBySource = new Map(
    byType("source_port").map((e) => [e.source_port_id, e]),
  );
  const pcbPortBySource = new Map(
    byType("pcb_port").map((e) => [e.source_port_id, e]),
  );

  const components = [];
  for (const [sid, name] of compName) {
    const p = pcbBySource.get(sid);
    const placed = !!p && !(p.width === 0 && p.height === 0);
    components.push({
      ref: name,
      sourceId: sid,
      pcbId: p?.pcb_component_id ?? null,
      center: p ? { x: p.center.x, y: p.center.y } : { x: 0, y: 0 },
      w: p?.width ?? 0,
      h: p?.height ?? 0,
      placed,
    });
  }
  components.sort((a, b) => a.ref.localeCompare(b.ref));

  // pads: smtpad x/y + plated-hole x/y, resolved to ref via pcb_port -> source_port
  const pads = [];
  const holes = [];
  for (const e of byType("pcb_smtpad")) {
    const sp = portBySource.get(pcbPortBySource.get(e.pcb_port_id)?.source_port_id);
    pads.push({
      x: e.x, y: e.y,
      ref: sp ? compName.get(sp.source_component_id) : null,
      sourcePortId: pcbPortBySource.get(e.pcb_port_id)?.source_port_id ?? null,
      pcbPortId: e.pcb_port_id,
    });
  }
  for (const e of byType("pcb_plated_hole")) {
    const sp = portBySource.get(pcbPortBySource.get(e.pcb_port_id)?.source_port_id);
    const ref = sp ? compName.get(sp.source_component_id) : null;
    pads.push({
      x: e.x, y: e.y, ref,
      sourcePortId: pcbPortBySource.get(e.pcb_port_id)?.source_port_id ?? null,
      pcbPortId: e.pcb_port_id,
    });
    holes.push({ x: e.x, y: e.y, ref, diameter: e.hole_diameter ?? 0 });
  }

  // connectivity nets: group source_ports by subcircuit_connectivity_map_key
  const netPorts = new Map(); // key -> [source_port]
  for (const e of byType("source_port")) {
    if (!e.subcircuit_connectivity_map_key) continue;
    if (!netPorts.has(e.subcircuit_connectivity_map_key)) {
      netPorts.set(e.subcircuit_connectivity_map_key, []);
    }
    netPorts.get(e.subcircuit_connectivity_map_key).push(e);
  }
  const nComps = compName.size;
  const nets = [];
  for (const [key, ports] of netPorts) {
    const members = [...new Set(ports.map((p) => compName.get(p.source_component_id)))].sort();
    nets.push({ key, members, global: members.length > GLOBAL_NET_FRAC * nComps });
  }
  nets.sort((a, b) => b.members.length - a.members.length);

  // connections: one "REF.pin > REF.pin" per non-trivial net (ordered port pairs).
  // pin label: prefer pin_number, else port name.
  const pinOf = (p) => p.pin_number ?? p.name;
  const connections = [];
  const connEndpoints = {};
  for (const net of nets) {
    const ports = (netPorts.get(net.key) ?? [])
      .filter((p) => compName.has(p.source_component_id))
      .sort((a, b) =>
        String(compName.get(a.source_component_id)).localeCompare(
          String(compName.get(b.source_component_id)),
        ) || String(pinOf(a)).localeCompare(String(pinOf(b))),
      );
    if (ports.length < 2) continue;
    const a = ports[0];
    const b = ports[ports.length - 1];
    const conn =
      `${compName.get(a.source_component_id)}.${pinOf(a)} > ` +
      `${compName.get(b.source_component_id)}.${pinOf(b)}`;
    connections.push(conn);
    connEndpoints[conn] = ports.map((p) => {
      const ref = compName.get(p.source_component_id);
      const pp = pcbPortBySource.get(p.source_port_id);
      return { ref, x: pp?.x ?? null, y: pp?.y ?? null };
    });
  }

  const sections = cluster(components, nets);
  return {
    board, boardName: board, circuitJsonPath, components, pads, holes,
    boardDims: boardInfo, nets, connections, connEndpoints, sections,
  };
}

export function scanBoard(board) {
  const dist = runRoutingDisabledEval(board);
  return loadScanFromCircuitJson(board, dist);
}

// --- clustering -----------------------------------------------------------
function cluster(components, nets) {
  const placed = components.filter((c) => c.placed);
  // affinity: union-find over non-global nets
  const parent = new Map(components.map((c) => [c.ref, c.ref]));
  const find = (a) => {
    while (parent.get(a) !== a) {
      parent.set(a, parent.get(parent.get(a)));
      a = parent.get(a);
    }
    return a;
  };
  const union = (a, b) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent.set(rb, ra);
  };
  const aff = new Map(); // "A|B" -> shared-net count
  const bump = (a, b) => {
    const k = [a, b].sort().join("|");
    aff.set(k, (aff.get(k) ?? 0) + 1);
  };
  for (const net of nets) {
    if (net.global) continue;
    for (let i = 0; i < net.members.length; i++) {
      for (let j = i + 1; j < net.members.length; j++) {
        bump(net.members[i], net.members[j]);
        union(net.members[i], net.members[j]);
      }
    }
  }
  const affOf = (a, b) => aff.get([a, b].sort().join("|")) ?? 0;

  // y-row bucketing of placed comps
  const ctr = new Map(placed.map((c) => [c.ref, c.center]));
  const ys = [...ctr.keys()].sort((a, b) => ctr.get(a).y - ctr.get(b).y);
  let rows = [];
  if (ys.length > 0) {
    let cur = [ys[0]];
    for (const m of ys.slice(1)) {
      if (ctr.get(m).y - ctr.get(cur[cur.length - 1]).y > ROW_GAP) {
        rows.push(cur);
        cur = [m];
      } else cur.push(m);
    }
    rows.push(cur);
  }
  rows.sort(
    (a, b) => a.reduce((s, m) => s + ctr.get(m).y, 0) / a.length -
      b.reduce((s, m) => s + ctr.get(m).y, 0) / b.length,
  );
  // merge small rows (<3) into best-affinity neighbour
  let i = 0;
  while (i < rows.length) {
    if (rows[i].length < 3 && rows.length > 1) {
      let best = -1;
      let bestW = -1;
      for (const j of [i - 1, i + 1]) {
        if (j < 0 || j >= rows.length) continue;
        let w = 0;
        for (const a of rows[i]) for (const b of rows[j]) w += affOf(a, b);
        if (w > bestW) { bestW = w; best = j; }
      }
      if (best < 0) best = i > 0 ? 0 : 1;
      rows[best] = [...rows[best], ...rows[i]];
      rows.splice(i, 1);
      continue;
    }
    i++;
  }
  const secs = rows.map((r) => new Set(r));
  if (secs.length === 0) secs.push(new Set());
  // unplaced -> section with max affinity
  for (const c of components) {
    if (ctr.has(c.ref)) continue;
    let best = 0;
    let bestW = -1;
    secs.forEach((s, j) => {
      let w = 0;
      for (const m of s) w += affOf(c.ref, m);
      if (w > bestW) { bestW = w; best = j; }
    });
    secs[best].add(c.ref);
  }

  // whole-board fallback: tiny board (<6 routable nets worth of affinity)
  const routableConns = nets.filter((n) => !n.global && n.members.length >= 2).length;
  if (routableConns < MIN_CONNS_MULTI || secs.length <= 1) {
    return [{
      name: "whole-board",
      members: components.map((c) => c.ref).sort(),
    }];
  }
  return secs.map((s, idx) => ({
    name: `section-${idx + 1}`,
    members: [...s].sort(),
  }));
}

export function scanRouter() {
  return join(TSMODULES_DIR, "node_modules", ".bin", "tsci");
}
