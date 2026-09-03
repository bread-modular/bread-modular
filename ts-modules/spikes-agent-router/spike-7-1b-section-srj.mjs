/**
 * Spike 7.1b — hand-built section SRJ fallback (the §7.1a fallback).
 *
 * getRerouteSimpleRouteJson drops unrouted connections, so the CLI must build
 * the section SRJ itself:
 *   section SRJ = full SRJ, but connections filtered to those with >=1
 *   endpoint inside rect, ALL locked traces kept, bounds = rect.
 * Then route with AutoroutingPipelineSolver9_PreloadedTraceGraph and stitch
 * with reconnectReroutedSimpleRouteJsonRegion.
 *
 * Usage: node spikes-agent-router/spike-7-1b-section-srj.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const core = await import("@tscircuit/core");
const cap = await import("@tscircuit/capacity-autorouter");
const { runAllRoutingChecks } = await import("@tscircuit/checks");

const circuitJson = JSON.parse(
  fs.readFileSync(
    process.argv[2] ??
      path.join(__dirname, "../dist/src/blank/blank/circuit.json"),
    "utf8",
  ),
);
const subcircuitId = "subcircuit_source_group_0";
const { simpleRouteJson: fullSrj } = core.getSimpleRouteJsonFromCircuitJson({
  circuitJson,
  subcircuit_id: subcircuitId,
});

// Section = bottom half of the board (contains the GND rail + its tap net).
// NOTE: cut lines chosen BETWEEN pad columns (x=±2.54, pads at multiples of
// 2.54 offset by 1.27) — rect edges must not pass through pads/traces.
const rect = { minX: -15.24, maxX: 15.24, minY: -34.29, maxY: 0 };
const inRect = (p) =>
  p.x >= rect.minX && p.x <= rect.maxX && p.y >= rect.minY && p.y <= rect.maxY;

const sectionConns = fullSrj.connections.filter((c) =>
  (c.pointsToConnect ?? c.points ?? []).some(inRect),
);
console.log(
  `full conns: ${fullSrj.connections.map((c) => c.name).join(",")} -> section conns: ${sectionConns.map((c) => c.name).join(",")}`,
);

const sectionSrj = {
  ...structuredClone(fullSrj),
  bounds: { ...rect },
  connections: structuredClone(sectionConns),
  // ALL locked traces kept: out-of-rect ones are obstacles+connectivity
  // (PreloadedTraceGraph consumes srj.traces as fixed geometry).
};
console.log(
  `section SRJ: conns=${sectionSrj.connections.length} lockedTraces=${(sectionSrj.traces ?? []).length} obstacles=${sectionSrj.obstacles.length}`,
);

const t0 = Date.now();
const solver = new cap.AutoroutingPipelineSolver9_PreloadedTraceGraph(sectionSrj);
solver.solve();
console.log(`solve() done in ${Date.now() - t0}ms`);
const outSrj = solver.getOutputSimpleRouteJson?.();
console.log(`output traces: ${(outSrj?.traces ?? []).length}`);

// Stitch: reconnect maps reroute names -> root; here there are no reroute
// names (we routed plain net connections), so stitch = original + new traces.
// emulate: full traces + (new traces not already present)
const before = new Set((fullSrj.traces ?? []).map((t) => t.pcb_trace_id));
const newTraces = (outSrj?.traces ?? []).filter((t) => !before.has(t.pcb_trace_id));
console.log(`new traces from section route: ${newTraces.length}`);
for (const t of newTraces)
  console.log(
    `  ${t.connection_name} id=${t.pcb_trace_id} segs=${(t.route ?? []).length}`,
  );

const stitched = cap.reconnectReroutedSimpleRouteJsonRegion(fullSrj, {
  ...structuredClone(fullSrj),
  traces: [...(fullSrj.traces ?? []), ...structuredClone(newTraces)],
});
console.log(`stitched traces: ${(stitched.traces ?? []).length}`);

// DRC on stitched board
const stitchedCircuit = circuitJson.filter((e) => e.type !== "pcb_trace");
for (const t of stitched.traces ?? []) {
  stitchedCircuit.push({
    type: "pcb_trace",
    pcb_trace_id: t.pcb_trace_id ?? `stitched_${Math.random().toString(36).slice(2)}`,
    subcircuit_id: subcircuitId,
    connection_name: t.connection_name,
    route: t.route,
  });
}
const errors = await runAllRoutingChecks(stitchedCircuit);
console.log(`\nDRC on fallback-stitched board: ${errors.length} error(s)`);
for (const e of errors.slice(0, 15))
  console.log(`  - ${e.type} ${(e.message ?? "").slice(0, 150)}`);

const outDir = path.join(__dirname, "out-7-1b");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "section.srj.json"), JSON.stringify(sectionSrj, null, 2));
fs.writeFileSync(path.join(outDir, "stitched.srj.json"), JSON.stringify(stitched, null, 2));
console.log(`artifacts -> ${outDir}/`);
