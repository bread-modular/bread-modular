/**
 * Spike 7.1 — Lifecycle + slice/stitch semantics (blank module).
 *
 * Steps (mirrors §7.1 / §4.3):
 *  1. Load routing-disabled circuit.json (produced by
 *     `tsci build --routing-disabled src/blank/blank.circuit.tsx`).
 *  2. Build full SimpleRouteJson via core's getSimpleRouteJsonFromCircuitJson.
 *  3. Preload one explicit trace as "locked" (simulates a completed section),
 *     slice a rect with getRerouteSimpleRouteJson, and check whether
 *     out-of-rect locked traces survive as obstacles + connectivity.
 *  4. Route one rect slice with the capacity-autorouter pipeline
 *     (AutoroutingPipelineSolver9_PreloadedTraceGraph == beta_pipeline9),
 *     stitch back with reconnectReroutedSimpleRouteJsonRegion.
 *  5. Emit verdicts for the §4.0 lifecycle decision.
 *
 * Usage:
 *   node spikes-agent-router/spike-7-1-lifecycle.mjs \
 *     [dist/src/blank/blank/circuit.json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const circuitJsonPath =
  process.argv[2] ??
  path.join(__dirname, "../dist/src/blank/blank/circuit.json");

const core = await import("@tscircuit/core");
const cap = await import("@tscircuit/capacity-autorouter");

const {
  getSimpleRouteJsonFromCircuitJson,
  unrouteCircuitJson,
} = core;
const {
  getRerouteSimpleRouteJson,
  reconnectReroutedSimpleRouteJsonRegion,
  AutoroutingPipelineSolver9_PreloadedTraceGraph,
} = cap;

console.log("== Spike 7.1: lifecycle + slice/stitch ==");
console.log("circuit.json:", circuitJsonPath);
console.log(
  "exports present:",
  [
    ["getSimpleRouteJsonFromCircuitJson", typeof getSimpleRouteJsonFromCircuitJson],
    ["getRerouteSimpleRouteJson", typeof getRerouteSimpleRouteJson],
    ["reconnectReroutedSimpleRouteJsonRegion", typeof reconnectReroutedSimpleRouteJsonRegion],
    ["AutoroutingPipelineSolver9_PreloadedTraceGraph", typeof AutoroutingPipelineSolver9_PreloadedTraceGraph],
  ]
    .map(([n, t]) => `${n}=${t}`)
    .join(" "),
);

const circuitJson = JSON.parse(fs.readFileSync(circuitJsonPath, "utf8"));
console.log(
  `circuit.json elements: ${circuitJson.length}, pcb_trace=${
    circuitJson.filter((e) => e.type === "pcb_trace").length
  }`,
);

// --- 1. Full SRJ from the routing-disabled eval -------------------------------
// NOTE: core in-render calls this WITH subcircuit_id (Group_doInitialPcbTraceRender).
// Without it, connections=0 (all 8 PowerRail traces carry source_trace_id and
// are treated as preserved; only net-level connections for the routed subcircuit
// are emitted). We mirror the in-render call exactly.
const subcircuitId = "subcircuit_source_group_0";
const { simpleRouteJson: fullSrj } = getSimpleRouteJsonFromCircuitJson({
  circuitJson,
  subcircuit_id: subcircuitId,
});
console.log(
  `full SRJ: connections=${fullSrj.connections.length} obstacles=${fullSrj.obstacles.length} ` +
    `traces=${(fullSrj.traces ?? []).length} bounds=${JSON.stringify(fullSrj.bounds)}`,
);
for (const c of fullSrj.connections.slice(0, 12)) {
  const pts = c.pointsToConnect ?? c.points ?? [];
  console.log(
    `  conn ${c.name} pointsToConnect=${pts.length} connectedTo=${JSON.stringify(c.connectedTo ?? []).slice(0, 120)}`,
  );
}

// --- 2. Locked-trace slice semantics ------------------------------------------
// The 8 PowerRail pre-routes in this SRJ are ALREADY "locked" traces
// (pcb_trace records with source_trace_id, preserved by
// getSimpleRouteJsonFromCircuitJson). That is exactly the "completed section"
// state — no fabrication needed (a hand-made trace with the wrong shape
// crashes the slicer; real trace shape = { connection_name, route[] }).
// Slice a rect covering only the LEFT half of the board: the right-hand rail
// segments lie outside it.
const srjWithLocked = structuredClone(fullSrj);
const lockedConn = { name: "(8 preserved PowerRail traces)" };
console.log(`\nlocked traces in SRJ: ${(srjWithLocked.traces ?? []).length}`);

// A rect covering only the LEFT half of the board: the locked trace's right
// endpoint lies outside it.
const rect = {
  shape: "rect",
  minX: fullSrj.bounds.minX - 1,
  maxX: (fullSrj.bounds.minX + fullSrj.bounds.maxX) / 2,
  minY: fullSrj.bounds.minY - 1,
  maxY: fullSrj.bounds.maxY + 1,
};
console.log(`slice rect: ${JSON.stringify(rect)}`);
const sliced = getRerouteSimpleRouteJson(srjWithLocked, rect);
console.log(
  `sliced SRJ: connections=${sliced.connections.length} obstacles=${sliced.obstacles.length} ` +
    `traces=${(sliced.traces ?? []).length} bounds=${JSON.stringify(sliced.bounds)}`,
);
console.log(
  `  full obstacles=${fullSrj.obstacles.length} -> sliced obstacles=${sliced.obstacles.length}`,
);
console.log(
  `  full traces=${(srjWithLocked.traces ?? []).length} -> sliced traces=${(sliced.traces ?? []).length}`,
);
for (const t of sliced.traces ?? []) {
  console.log(
    `  kept trace conn=${t.connection_name} pts=${(t.points ?? t.route ?? []).length}`,
  );
}
// Did connection points outside the rect survive (connectivity preserved)?
const outOfRectPts = (sliced.connections ?? []).flatMap((c) =>
  (c.points ?? []).filter(
    (p) => p.x < rect.minX || p.x > rect.maxX || p.y < rect.minY || p.y > rect.maxY,
  ).map(() => c.name),
);
console.log(
  `  connections with points outside rect: ${JSON.stringify([...new Set(outOfRectPts)].slice(0, 10))} (count=${outOfRectPts.length})`,
);

// --- 3. Route one rect slice with the beta_pipeline9 solver -------------------
console.log("\n-- routing sliced SRJ with AutoroutingPipelineSolver9_PreloadedTraceGraph --");
// BaseSolver API is synchronous: solve() then getOutputSimpleRouteJson().
// (Core's CapacityMeshAutorouter wraps this with start()/on(complete|error);
// the CLI can drive solver.step() itself for timeouts — see §4.3.)
const t0 = Date.now();
const solver = new AutoroutingPipelineSolver9_PreloadedTraceGraph(sliced);
solver.solve();
console.log(`solver.solve() done in ${Date.now() - t0}ms`);
const outSrj = solver.getOutputSimpleRouteJson?.();
const routedTraces = outSrj?.traces ?? [];
console.log(
  `output SRJ traces: ${routedTraces.length} (solver errors: ${JSON.stringify(solver.errors ?? solver._errors ?? "n/a").slice(0, 200)})`,
);
const rerouted = { ...structuredClone(sliced), traces: routedTraces ?? [] };

// --- 4. Stitch back ------------------------------------------------------------
const stitched = reconnectReroutedSimpleRouteJsonRegion(fullSrj, rerouted);
console.log(
  `stitched SRJ: connections=${stitched.connections.length} traces=${(stitched.traces ?? []).length} ` +
    `obstacles=${stitched.obstacles.length}`,
);

// Sanity: stitched traces must map back to ROOT connection names
// (reconnect maps `*_reroute_*` -> __rootConnectionNames[0]). Core's in-render
// trace-matching accepts source_trace_id / pcb_trace_id / root names, so
// source_trace_* names are correct — NOT orphans. Verify against the union of
// root names + original trace connection_names.
const rootNames = new Set([
  ...stitched.connections.map((c) => c.name),
  ...(fullSrj.traces ?? []).map((t) => t.connection_name),
  ...(fullSrj.connections ?? []).flatMap((c) => [
    c.name,
    ...(c.__rootConnectionNames ?? []),
  ]),
]);
const orphans = (stitched.traces ?? []).filter((t) => !rootNames.has(t.connection_name));
console.log(`stitched traces with unmapped connection_name: ${orphans.length} (names: ${JSON.stringify([...new Set((stitched.traces ?? []).map((t) => t.connection_name))]).slice(0, 200)})`);

// Persist artifacts for the implementation chat
const outDir = path.join(__dirname, "out-7-1");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "full.srj.json"), JSON.stringify(fullSrj, null, 2));
fs.writeFileSync(path.join(outDir, "sliced.srj.json"), JSON.stringify(sliced, null, 2));
fs.writeFileSync(path.join(outDir, "rerouted.srj.json"), JSON.stringify(rerouted, null, 2));
fs.writeFileSync(path.join(outDir, "stitched.srj.json"), JSON.stringify(stitched, null, 2));
console.log(`artifacts written to ${outDir}/`);

// --- 5. DRC seam check --------------------------------------------------------
// Build a stitched circuit-json: fresh eval, with the original locked traces
// that intersected the rect REPLACED by the stitched traces (mirrors what
// _updatePcbTraceRenderFromPcbTraces does: delete replaced + insert new).
// Then run runAllRoutingChecks (the §6 gate) on it.
const { runAllRoutingChecks } = await import("@tscircuit/checks");
const stitchedCircuit = circuitJson.filter((e) => e.type !== "pcb_trace");
let k = 0;
for (const t of stitched.traces ?? []) {
  stitchedCircuit.push({
    type: "pcb_trace",
    pcb_trace_id: t.pcb_trace_id ?? `stitched_trace_${k++}`,
    subcircuit_id: subcircuitId,
    connection_name: t.connection_name,
    route: t.route,
  });
}
fs.writeFileSync(
  path.join(outDir, "stitched.circuit.json"),
  JSON.stringify(stitchedCircuit),
);
const drcErrors = await runAllRoutingChecks(stitchedCircuit);
console.log(
  `\nDRC (runAllRoutingChecks) on stitched board: ${drcErrors.length} error(s)`,
);
for (const e of drcErrors.slice(0, 20)) {
  console.log(
    `  - ${e.type} ${e.error_type ?? ""} @${JSON.stringify(e.center ?? e.at ?? "").slice(0, 120)} ${(e.message ?? "").slice(0, 160)}`,
  );
}
// Baseline: DRC on the routing-disabled eval itself (locked traces only)
const baseErrors = await runAllRoutingChecks(circuitJson);
console.log(`DRC baseline (unrouted eval, locked traces only): ${baseErrors.length} error(s)`);
for (const e of baseErrors.slice(0, 10)) {
  console.log(`  - ${e.type} ${(e.message ?? "").slice(0, 140)}`);
}
