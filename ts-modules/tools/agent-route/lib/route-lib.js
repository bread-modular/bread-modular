// Shared routing library for run.js (routeBoard) and retry-section.js.
//
// Proven by spikes-agent-router (do not reinvent):
//  - Hand-built section SRJ: full SRJ, connections restricted to the section's
//    set, ALL locked traces kept, bounds = section rect.
//    (getRerouteSimpleRouteJson drops unrouted conns on never-routed boards.)
//  - Lock (variant C): pcb_trace records need subcircuit_id + source_trace_id
//    + through_obstacle → through_pad normalization.
//  - Solver: new Solver(srj, { effort }), sync solve() or manual step() loop
//    with wall-clock deadline; check failed/error BEFORE getOutputSimpleRouteJson.
//  - PreloadedTraceGraph-family output ECHOES locked traces;
//    new traces = output minus input pcb_trace_ids.
//  - DRC gate: runAllRoutingChecks, minus port_not_connected/trace_missing for
//    section-only eval (other sections' nets are legitimately open mid-run).
import { SUBCIRCUIT_ID } from "./constants.js";

export function srjConnPoints(conn) {
  return conn.pointsToConnect ?? conn.points ?? [];
}

export function pointInRect(p, rect) {
  return (
    p.x >= rect.minX && p.x <= rect.maxX && p.y >= rect.minY && p.y <= rect.maxY
  );
}

export function srjConnInRect(conn, rect) {
  return srjConnPoints(conn).some((p) => pointInRect(p, rect));
}

/**
 * Map scan-level plan connections ("REF.pin > REF.pin", one per connectivity
 * net) to SRJ connection names (source_trace_* fragments + source_net_* nets).
 *
 * Rule (endpoint-based, not port-soup):
 *  - A point-to-point FRAGMENT (no connected_source_net_ids, e.g. rail
 *    pin-to-pin links, R1-pa0) belongs to the scan conn iff BOTH its ports
 *    are in the scan conn's port set.
 *  - A TAP fragment (single port + net id, e.g. V_SUPPLY1-tap, R4-vsup)
 *    belongs iff its port is in the set. The net side is covered by the
 *    source_net_* entry below.
 *  - A source_net_* NET belongs iff ANY of its member ports (union of its
 *    source_traces' ports) is in the set.
 *
 * The scan conn's port set = scan.connEndpoints[conn] matched to source_port
 * ids by (ref,x,y) via scan pads, plus ref.pin fallback for unplaced comps
 * (null coords). Returns { srjNames: [...], uncovered: [...] }.
 */
export function resolveScanConn(scanConn, scan, circuitJson) {
  const eps = scan.connEndpoints?.[scanConn] ?? [];
  // Port identity: source_port ids via scan pads (pcb_port -> source port).
  // scan.pads carry sourcePortId; match endpoints by (ref, x, y).
  const portIds = new Set();
  for (const e of eps) {
    for (const p of scan.pads ?? []) {
      if (
        p.ref === e.ref &&
        typeof e.x === "number" &&
        Math.abs(p.x - e.x) < 1e-6 &&
        Math.abs(p.y - e.y) < 1e-6 &&
        p.sourcePortId
      ) {
        portIds.add(p.sourcePortId);
      }
    }
  }
  // Fallback: endpoints with null coords (unplaced comps, e.g. blank R1/R2/C1)
  // match pads by ref + pin. Parse "REF.pin" ends of the scan conn string.
  const ends = String(scanConn)
    .split(">")
    .map((s) => s.trim());
  const endPins = ends.map((end) => {
    const m = end.match(/^(.+)\.([^.]+)$/);
    return m ? { ref: m[1], pin: m[2] } : null;
  });
  const portsById = new Map(
    circuitJson.filter((e) => e.type === "source_port").map((p) => [p.source_port_id, p]),
  );
  const compName = new Map(
    circuitJson.filter((e) => e.type === "source_component").map((e) => [e.source_component_id, e.name]),
  );
  const pinOf = (p) => String(p.pin_number ?? p.name);
  for (const end of endPins) {
    if (!end) continue;
    for (const [pid, p] of portsById) {
      if (compName.get(p.source_component_id) === end.ref && pinOf(p) === end.pin) {
        portIds.add(pid);
      }
    }
  }
  // Net expansion: a scan conn names only first>last ports, but fragments can
  // chain through MIDDLE ports of the same connectivity net (e.g. drive's
  // INPUT1.2>INPUT1.5 daisy chain .2-.3-.4-.5: only .2/.5 are named, and
  // bus-connector pins have no scan pads so the middle ports never match).
  // Include every port sharing an endpoint's connectivity key. Safe: scan
  // emits exactly one conn per net, so expansion stays within this conn's net.
  const keyOf = (pid) => portsById.get(pid)?.subcircuit_connectivity_map_key;
  const keys = new Set([...portIds].map(keyOf).filter(Boolean));
  if (keys.size > 0) {
    for (const [pid, p] of portsById) {
      if (keys.has(p.subcircuit_connectivity_map_key)) portIds.add(pid);
    }
  }

  const srjNames = new Set();
  const fragPorts = new Map(); // source_trace_id -> { ports: Set, nets: [...] }
  for (const st of circuitJson) {
    if (st.type !== "source_trace") continue;
    fragPorts.set(st.source_trace_id, {
      ports: new Set(st.connected_source_port_ids ?? []),
      nets: st.connected_source_net_ids ?? [],
    });
  }
  // net -> member ports (union of its source_traces' ports)
  const netPorts = new Map();
  for (const st of circuitJson) {
    if (st.type !== "source_trace") continue;
    for (const nid of st.connected_source_net_ids ?? []) {
      if (!netPorts.has(nid)) netPorts.set(nid, new Set());
      for (const pid of st.connected_source_port_ids ?? []) netPorts.get(nid).add(pid);
    }
  }
  const inSet = (pid) => portIds.has(pid);
  for (const [name, { ports, nets }] of fragPorts) {
    if (nets.length === 0) {
      // point-to-point fragment: BOTH endpoints must be in the scan conn.
      if (ports.size > 0 && [...ports].every(inSet)) srjNames.add(name);
    } else if (ports.size === 1) {
      // tap fragment: its single port must be in the scan conn.
      if ([...ports].every(inSet)) srjNames.add(name);
    } else if (ports.size > 1) {
      if ([...ports].every(inSet)) srjNames.add(name);
    }
  }
  for (const [nid, set] of netPorts) {
    if ([...set].some(inSet)) srjNames.add(nid);
  }

  return { srjNames: [...srjNames], uncovered: srjNames.size === 0 ? [scanConn] : [] };
}

/** Resolve a list of scan conns; unions SRJ names, collects uncovered. */
export function resolveSectionConns(scanConns, scan, circuitJson) {
  const srjNames = new Set();
  const uncovered = [];
  for (const c of scanConns ?? []) {
    const r = resolveScanConn(c, scan, circuitJson);
    for (const n of r.srjNames) srjNames.add(n);
    uncovered.push(...r.uncovered);
  }
  return { srjNames: [...srjNames], uncovered };
}

/**
 * Build the section SRJ by hand: full SRJ, connections restricted to the
 * section's SRJ name set, ALL locked traces kept, bounds = section rect.
 */
export function buildSectionSrj(fullSrj, rect, srjNames, { lockedTraces = [] } = {}) {
  const wanted = new Set(srjNames);
  return {
    ...structuredClone(fullSrj),
    bounds: { ...rect },
    connections: structuredClone(fullSrj.connections.filter((c) => wanted.has(c.name))),
    traces: structuredClone(lockedTraces),
  };
}

/** New traces = solver output minus locked input ids (echo semantics). */
export function newTracesFromOutput(outputSrj, lockedTraces) {
  const before = new Set((lockedTraces ?? []).map((t) => t.pcb_trace_id));
  return (outputSrj?.traces ?? []).filter((t) => !before.has(t.pcb_trace_id));
}

/** through_obstacle → through_pad normalization (production shape). */
export function normalizeRoute(route) {
  return (route ?? []).map((p) => {
    if (p?.route_type !== "through_obstacle") return { ...p };
    const { from_layer, to_layer, ...rest } = p;
    return {
      ...rest,
      route_type: "through_pad",
      start_layer: p.from_layer,
      end_layer: p.to_layer,
    };
  });
}

/**
 * Convert fresh solver traces to locked pcb_trace records (variant C): stamp
 * subcircuit_id + resolve source_trace_id from the connection name
 * (source_trace id for direct-trace conns, else first source_trace on the
 * net). Returns { records, unmapped }.
 */
export function toLockRecords({ newTraces, circuitJson, sectionId }) {
  const netToSourceTraces = new Map();
  const sourceTraceIds = new Set();
  for (const e of circuitJson) {
    if (e.type !== "source_trace") continue;
    sourceTraceIds.add(e.source_trace_id);
    for (const nid of e.connected_source_net_ids ?? []) {
      if (!netToSourceTraces.has(nid)) netToSourceTraces.set(nid, []);
      netToSourceTraces.get(nid).push(e.source_trace_id);
    }
  }
  let k = 0;
  let unmapped = 0;
  const records = newTraces.map((t) => {
    let sid;
    if (sourceTraceIds.has(t.connection_name)) {
      sid = t.connection_name;
    } else {
      const cands = netToSourceTraces.get(t.connection_name) ?? [];
      if (cands.length === 0) unmapped++;
      else sid = cands[0];
    }
    return {
      type: "pcb_trace",
      pcb_trace_id: t.pcb_trace_id ?? `${sectionId}_lock_${k++}`,
      subcircuit_id: SUBCIRCUIT_ID,
      connection_name: t.connection_name,
      ...(sid ? { source_trace_id: sid } : {}),
      route: normalizeRoute(t.route),
    };
  });
  return { records, unmapped };
}

/**
 * Merge locked pcb_trace/pcb_via records onto a base circuit-json
 * (build.sh merge_routes equivalent): base non-route + base route + locked.
 */
export function mergeLockedRecords(baseCircuitJson, lockedRecords) {
  const ROUTE_TYPES = new Set(["pcb_trace", "pcb_via"]);
  return [
    ...baseCircuitJson.filter((e) => !ROUTE_TYPES.has(e.type)),
    ...baseCircuitJson.filter((e) => ROUTE_TYPES.has(e.type)),
    ...lockedRecords,
  ];
}

/**
 * Route one section SRJ with a PreloadedTraceGraph-family solver, driven via
 * step() with a wall-clock deadline + iteration cap (§4.3 timeout mechanism).
 * Returns { ok, outputSrj, steps, ms, timedOut?, error? }.
 */
export function solveWithDeadline(
  SolverClass,
  sectionSrj,
  { effort = 10, timeoutMs = 120000, maxSteps = 50000000 } = {},
) {
  const solver = new SolverClass(structuredClone(sectionSrj), { effort });
  const t0 = Date.now();
  let steps = 0;
  try {
    while (!solver.solved && !solver.failed) {
      if (steps >= maxSteps) {
        return {
          ok: false,
          outputSrj: null,
          steps,
          ms: Date.now() - t0,
          timedOut: true,
          error: `iteration cap hit (${steps} steps)`,
        };
      }
      if (Date.now() - t0 > timeoutMs) {
        return {
          ok: false,
          outputSrj: null,
          steps,
          ms: Date.now() - t0,
          timedOut: true,
          error: `wall-clock deadline hit (${timeoutMs}ms, ${steps} steps)`,
        };
      }
      solver.step();
      steps++;
    }
  } catch (e) {
    return {
      ok: false,
      outputSrj: null,
      steps,
      ms: Date.now() - t0,
      timedOut: false,
      error: `solver threw: ${String(e?.message ?? e).slice(0, 300)}`,
    };
  }
  const ms = Date.now() - t0;
  if (solver.failed) {
    return {
      ok: false,
      outputSrj: null,
      steps,
      ms,
      timedOut: false,
      error: String(solver.error ?? "solver failed").slice(0, 500),
    };
  }
  let outputSrj = null;
  try {
    outputSrj = solver.getOutputSimpleRouteJson();
  } catch (e) {
    return {
      ok: false,
      outputSrj: null,
      steps,
      ms,
      timedOut: false,
      error: `getOutputSimpleRouteJson threw: ${String(e?.message ?? e).slice(0, 300)}`,
    };
  }
  return { ok: true, outputSrj, steps, ms };
}

/**
 * STITCH (§4.4): reconnectReroutedSimpleRouteJsonRegion(original, rerouted)
 * maps reroute names → root; for plain net connections it is identity, so the
 * assembled board = full SRJ traces + new section traces. SRJ-level sanity
 * check; the circuit-json merge (mergeLockedRecords) is the persisted stitch.
 */
export function stitchSrj(cap, fullSrj, lockedTraces, newTraces) {
  return cap.reconnectReroutedSimpleRouteJsonRegion(fullSrj, {
    ...structuredClone(fullSrj),
    traces: [...structuredClone(lockedTraces), ...structuredClone(newTraces)],
  });
}

// --- DRC helpers (§6) -------------------------------------------------------

const CONNECTIVITY_TYPES = new Set([
  "pcb_port_not_connected_error",
  "pcb_trace_missing_error",
]);

function srjTraceTouchesRect(trace, rect) {
  // Solver-format traces: route points carry x/y (+ layer/via markers).
  for (const seg of trace.route ?? []) {
    for (const pt of [seg, seg.start, seg.end]) {
      if (pt && typeof pt.x === "number" && pointInRect(pt, rect)) return true;
    }
  }
  return false;
}

function errorTouchesRect(err, rect) {
  const pts = [];
  if (err.center) pts.push(err.center);
  if (err.at) pts.push(err.at);
  if (err.position) pts.push(err.position);
  if (Array.isArray(err.polygon)) pts.push(...err.polygon);
  return pts.some((p) => p && typeof p.x === "number" && pointInRect(p, rect));
}

/**
 * Filter circuit-json to rect ∪ margin: keep all non-copper elements (pads,
 * components, nets — checks need them) but drop pcb_trace/pcb_via records
 * that don't touch the grown rect. Handles BOTH circuit-json trace records
 * (route segments with start/end) and solver-format traces (points with x/y).
 */
export function filterCircuitToRect(circuitJson, rect, margin) {
  const scope = {
    minX: rect.minX - margin,
    maxX: rect.maxX + margin,
    minY: rect.minY - margin,
    maxY: rect.maxY + margin,
  };
  return circuitJson.filter((e) => {
    if (e.type === "pcb_via") {
      return typeof e.x === "number" && pointInRect({ x: e.x, y: e.y }, scope);
    }
    if (e.type !== "pcb_trace") return true;
    for (const seg of e.route ?? []) {
      const pts = [seg, seg.start, seg.end];
      if (pts.some((p) => p && typeof p.x === "number" && pointInRect(p, scope))) return true;
    }
    return false;
  });
}

export function stripConnectivityErrors(errors) {
  return (errors ?? []).filter((e) => !CONNECTIVITY_TYPES.has(e.type));
}

/**
 * Strip FALSE "missing a connection to smtpad[...]" errors from a SECTION
 * gate (rect ∪ margin scope) whose implicated pad belongs to a component
 * OUTSIDE the grown rect.
 *
 * Why: the gate scopes circuit-json to rect ∪ margin, which drops the
 * section's own far branches (e.g. drive S3 routes OUT2-star fragments whose
 * R4/U1 joins sit ~20mm outside the rect). The checker then sees in-scope
 * copper that cannot join the far pad and reports "missing connection" —
 * even though the join exists, just outside scope. Real opens (pad inside
 * scope, copper not reaching it) are KEPT. Whole-board connectivity is still
 * enforced by the final gate (zero-error before promotion).
 *
 * Pad identity is parsed from the message: missing a connection to
 * smtpad[.REF > .PIN]. Unparseable messages are kept (fail-closed).
 */
export function stripFarMissingConnections(errors, circuitJson, rect, margin) {
  const scope = {
    minX: rect.minX - margin,
    maxX: rect.maxX + margin,
    minY: rect.minY - margin,
    maxY: rect.maxY + margin,
  };
  // Pad-precision lookup: smtpad[.REF > .PIN] -> pcb_port x/y via
  // source_component (by name) -> source_port (by pin_number/name) ->
  // pcb_port (by source_port_id). Pad-exact (not component centre) so a
  // large part straddling the scope boundary still gates its in-scope pads.
  const compByName = new Map(
    (circuitJson ?? []).filter((e) => e.type === "source_component").map((e) => [e.name, e.source_component_id]),
  );
  const srcPortsByComp = new Map();
  for (const e of circuitJson ?? []) {
    if (e.type !== "source_port") continue;
    if (!srcPortsByComp.has(e.source_component_id)) srcPortsByComp.set(e.source_component_id, []);
    srcPortsByComp.get(e.source_component_id).push(e);
  }
  const pcbPortBySrc = new Map(
    (circuitJson ?? []).filter((e) => e.type === "pcb_port").map((e) => [e.source_port_id, e]),
  );
  const padPos = (ref, pin) => {
    const cid = compByName.get(ref);
    if (!cid) return null;
    const cands = srcPortsByComp.get(cid) ?? [];
    // The checker names pads by port NAME (e.g. OUT2); scan strings use pin
    // numbers (e.g. U1.7). Accept either.
    const sp = cands.find((p) => String(p.pin_number ?? "") === pin || String(p.name ?? "") === pin) ?? null;
    if (!sp) return null;
    const pp = pcbPortBySrc.get(sp.source_port_id);
    if (!pp || typeof pp.x !== "number") return null;
    return pp;
  };
  return (errors ?? []).filter((e) => {
    const m = /missing a connection to smtpad\[\.?(.+?) > \.?(.+?)\]/.exec(String(e.message ?? ""));
    if (!m) return true; // not a missing-connection error, or unparseable: keep
    const pos = padPos(m[1], m[2]);
    if (!pos) return true; // unresolvable pad: keep (fail-closed)
    return pointInRect(pos, scope); // keep iff the pad itself is in scope
  });
}

/** Classify a routing failure into the §4.5 errorClass taxonomy. */
export function classifyError({ solverError = "", timedOut = false, drcErrors = [] } = {}) {
  const msg = String(solverError ?? "").toLowerCase();
  if (timedOut || /deadline|timeout|iteration cap/.test(msg)) return "TIMEOUT";
  if (/via/.test(msg) && /exhaust|limit|maximum/.test(msg)) return "VIA_EXHAUSTED";
  if (/clearance|overlap|spacing|drc/.test(msg)) return "DRC_CLEARANCE";
  if (/no path|unroutable|could not route|no route/.test(msg)) return "NO_PATH";
  if (/invalid|outside.*bounds|bad input/.test(msg)) return "INPUT_INVALID";
  if (drcErrors && drcErrors.length > 0) return "DRC_CLEARANCE";
  if (/stitch|mismatch|reconnect/.test(msg)) return "STITCH_MISMATCH";
  return "NO_PATH";
}

export function summarizeDrc(errors, limit = 10) {
  return (errors ?? []).slice(0, limit).map((e) => ({
    type: e.type,
    message: (e.message ?? "").slice(0, 220),
    at: e.center ?? e.at ?? e.position ?? undefined,
  }));
}
