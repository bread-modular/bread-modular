/**
 * Spike 7.1c — section route on 8bit (real unrouted nets).
 * Hand-built section SRJ (fallback from 7.1a) on a board with 23 unrouted
 * connections: filter conns to section rect, keep locked traces, route with
 * AutoroutingPipelineSolver9_PreloadedTraceGraph, stitch, DRC.
 *
 * Usage: node spikes-agent-router/spike-7-1c-8bit-section.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const core = await import("@tscircuit/core");
const cap = await import("@tscircuit/capacity-autorouter");
const { runAllRoutingChecks } = await import("@tscircuit/checks");

const circuitJson = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../dist/src/8bit/8bit/circuit.json"), "utf8"),
);
const subcircuitId = "subcircuit_source_group_0";
const { simpleRouteJson: fullSrj } = core.getSimpleRouteJsonFromCircuitJson({
  circuitJson,
  subcircuit_id: subcircuitId,
});
console.log(
  `full 8bit SRJ: conns=${fullSrj.connections.length} locked=${(fullSrj.traces ?? []).length} obstacles=${fullSrj.obstacles.length}`,
);

// Section: top half of the board (y > 0). Report endpoint distribution.
const rect = { minX: -15.24, maxX: 15.24, minY: 0, maxY: 34.29 };
const inRect = (p) =>
  p.x >= rect.minX && p.x <= rect.maxX && p.y >= rect.minY && p.y <= rect.maxY;
for (const c of fullSrj.connections) {
  const pts = c.pointsToConnect ?? c.points ?? [];
  const inside = pts.filter(inRect).length;
  if (inside > 0)
    console.log(`  conn ${c.name}: ${inside}/${pts.length} endpoints in rect`);
}
const sectionConns = fullSrj.connections.filter((c) =>
  (c.pointsToConnect ?? c.points ?? []).some(inRect),
);
console.log(`section conns: ${sectionConns.length}/${fullSrj.connections.length}`);

const sectionSrj = {
  ...structuredClone(fullSrj),
  bounds: { ...rect },
  connections: structuredClone(sectionConns),
};
const t0 = Date.now();
const solver = new cap.AutoroutingPipelineSolver9_PreloadedTraceGraph(sectionSrj);
solver.solve();
console.log(`solve() done in ${Date.now() - t0}ms`);
const outSrj = solver.getOutputSimpleRouteJson?.();
const before = new Set((fullSrj.traces ?? []).map((t) => t.pcb_trace_id));
const newTraces = (outSrj?.traces ?? []).filter((t) => !before.has(t.pcb_trace_id));
console.log(`output traces=${(outSrj?.traces ?? []).length}, NEW traces=${newTraces.length}`);
const byConn = {};
for (const t of newTraces) byConn[t.connection_name] = (byConn[t.connection_name] ?? 0) + 1;
for (const [k, v] of Object.entries(byConn)) console.log(`  new: ${k} x${v}`);

const stitched = cap.reconnectReroutedSimpleRouteJsonRegion(fullSrj, {
  ...structuredClone(fullSrj),
  traces: [...(fullSrj.traces ?? []), ...structuredClone(newTraces)],
});

// DRC on stitched board
const stitchedCircuit = circuitJson.filter((e) => e.type !== "pcb_trace");
for (const t of stitched.traces ?? []) {
  stitchedCircuit.push({
    type: "pcb_trace",
    pcb_trace_id: t.pcb_trace_id ?? `st_${Math.random().toString(36).slice(2)}`,
    subcircuit_id: subcircuitId,
    connection_name: t.connection_name,
    route: t.route,
  });
}
const errors = await runAllRoutingChecks(stitchedCircuit);
console.log(`DRC on section-stitched 8bit: ${errors.length} error(s)`);
for (const e of errors.slice(0, 15))
  console.log(`  - ${e.type} ${(e.message ?? "").slice(0, 160)}`);

const outDir = path.join(__dirname, "out-7-1c");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "section.srj.json"), JSON.stringify(sectionSrj, null, 2));
fs.writeFileSync(
  path.join(outDir, "stitched.circuit.json"),
  JSON.stringify(stitchedCircuit),
);
console.log(`artifacts -> ${outDir}/`);
