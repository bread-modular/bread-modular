/**
 * Spike 7.3 — lock completed sections as explicit geometry (8bit).
 *
 * Mirrors the §3.4/§4.4 production flow WITHOUT touching board sources:
 * build.sh's merge_routes() merges saved pcb_trace/pcb_via records onto a
 * fresh --routing-disabled eval. Here we:
 *  1. Take the 44 section traces routed in 7.1c (top-half section) as the
 *     "completed, locked section".
 *  2. Merge them onto the fresh 8bit routing-disabled eval (exactly like
 *     build.sh merge_routes: fresh eval minus pcb_trace/pcb_via + saved
 *     routing records).
 *  3. Re-derive the full SRJ -> the locked section's nets must be
 *     already-connected (fewer/changed SRJ connections), locked traces
 *     present as srj.traces.
 *  4. Re-run the full-board pipeline and confirm the locked traces are
 *     preserved bit-identical in the output while the remainder routes.
 *
 * Usage: node spikes-agent-router/spike-7-3-lock.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const core = await import("@tscircuit/core");
const cap = await import("@tscircuit/capacity-autorouter");

const SUB = "subcircuit_source_group_0";
const fresh = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../dist/src/8bit/8bit/circuit.json"), "utf8"),
);
const SECTION_SRJ = process.env.SPIKE_SECTION_SRJ ?? "out-7-1c/stitched.circuit.json";
const sectionStitchedFile = SECTION_SRJ.endsWith(".srj.json")
  ? null
  : path.join(__dirname, SECTION_SRJ);
// A section SRJ file (solver output) can be given directly via
// SPIKE_SECTION_SRJ=out-7-1c/section-padded-e100.srj.json — converted to
// lock records below. Default: legacy stitched.circuit.json path.
const sectionSrjDirect = SECTION_SRJ.endsWith(".srj.json")
  ? JSON.parse(fs.readFileSync(path.join(__dirname, SECTION_SRJ), "utf8"))
  : null;
const sectionStitched = sectionStitchedFile
  ? JSON.parse(fs.readFileSync(sectionStitchedFile, "utf8"))
  : null;

// 1-2. build.sh-equivalent merge: locked section traces onto fresh eval.
// The 44 NEW traces from 7.1c are those beyond the 8 rail pre-routes
// (pcb_trace_0..7). NOTE: raw solver output carries connection_name but NO
// source_trace_id; core's in-render insert resolves it via
// getSourceTraceIdForRoutedTrace. We test BOTH shapes:
//  (a) raw (no source_trace_id) — becomes fixed-copper obstacles;
//  (b) resolved — set source_trace_id from the srj connection's source net.
const RAIL_IDS = new Set(
  fresh.filter((e) => e.type === "pcb_trace").map((e) => e.pcb_trace_id),
);
// Locked-trace source: either rows of a circuit-json (default) or raw solver
// SRJ output (SPIKE_SECTION_SRJ=*.srj.json). SRJ traces lack pcb_trace_id —
// mint stable lock ids (lock_<connection>_<k>).
let kLock = 0;
const srjToLockRows = (srj) =>
  (srj.traces ?? []).map((t) => ({
    type: "pcb_trace",
    pcb_trace_id: t.pcb_trace_id ?? `lock_${t.connection_name}_${kLock++}`,
    connection_name: t.connection_name,
    route: t.route,
  }));
const newTraces = sectionSrjDirect
  ? srjToLockRows(sectionSrjDirect).filter((t) => !RAIL_IDS.has(t.pcb_trace_id))
  : sectionStitched.filter(
      (e) => e.type === "pcb_trace" && !RAIL_IDS.has(e.pcb_trace_id),
    );
console.log(`new section traces from 7.1c: ${newTraces.length}`);
const sample = newTraces[0];
console.log(
  `sample: id=${sample.pcb_trace_id} conn=${sample.connection_name} segs=${(sample.route ?? []).length}`,
);

// Variant (a): raw solver-output shape (connection_name, no source_trace_id).
// Variant (b): production shape — resolve source_trace_id. Core's
// getSourceTraceIdForRoutedTrace matches route endpoints to source traces;
// our emulation: the srj connection name IS the source_net id for net
// connections (source_net_N). pcb_trace records with a source_trace_id whose
// subcircuit matches are "preserved" (connectivity + obstacle); without it
// they are fixed-copper obstacles only.
const ROUTE_TYPES = new Set(["pcb_trace", "pcb_via"]);
// Production normalization (mirrors Group._updatePcbTraceRenderFromPcbTraces):
// solver SRJ uses `through_obstacle` segments; circuit-json pcb_trace records
// must carry `through_pad` instead, or getSimpleRouteJsonFromCircuitJson's
// preserved-trace path crashes (reads start_layer/end_layer, throws on
// undefined.layer.name).
const normalizeRoute = (route) =>
  (route ?? []).map((p) => {
    if (p?.route_type !== "through_obstacle") return { ...p };
    return {
      route_type: "through_pad",
      start: p.start,
      end: p.end,
      start_layer: p.from_layer,
      end_layer: p.to_layer,
      width: p.width,
      ...(p.circuitJsonMetadata ? { circuitJsonMetadata: p.circuitJsonMetadata } : {}),
    };
  });
const lockRecords = (traces, extra) =>
  traces.map((t) => ({ ...t, route: normalizeRoute(t.route), ...extra }));
const mergedA = [
  ...fresh.filter((e) => !ROUTE_TYPES.has(e.type)),
  ...fresh.filter((e) => ROUTE_TYPES.has(e.type)),
  ...lockRecords(newTraces, {}),
];
const mergedB = [
  ...fresh.filter((e) => !ROUTE_TYPES.has(e.type)),
  ...fresh.filter((e) => ROUTE_TYPES.has(e.type)),
  // production shape: keep connection_name AND it will be matched; solver
  // traces whose connection is a net get no single source_trace_id — core
  // handles this via subcircuitConnectivityMapKey. We keep them as-is: this
  // variant == variant A plus subcircuit_id stamp (what build.sh merge gives:
  // fresh eval has subcircuit ids on traces? check below).
  ...lockRecords(newTraces, { subcircuit_id: SUB }),
];
console.log(
  `fresh rail traces carry subcircuit_id: ${fresh.filter((e) => e.type === "pcb_trace").every((e) => !!e.subcircuit_id)}`,
);

function summarize(tag, cj) {
  try {
    const srj = core.getSimpleRouteJsonFromCircuitJson({
      circuitJson: cj,
      subcircuit_id: SUB,
    }).simpleRouteJson;
    console.log(
      `${tag}: conns=${srj.connections.length} traces=${(srj.traces ?? []).length} obstacles=${srj.obstacles.length}`,
    );
    return srj;
  } catch (e) {
    console.log(`${tag}: THREW: ${(e.message ?? String(e)).slice(0, 220)}`);
    return null;
  }
}

// 3. Re-derive SRJ
const before = core.getSimpleRouteJsonFromCircuitJson({
  circuitJson: fresh,
  subcircuit_id: SUB,
}).simpleRouteJson;
console.log(
  `BEFORE lock: conns=${before.connections.length} traces=${(before.traces ?? []).length} obstacles=${before.obstacles.length}`,
);
const afterA = summarize("AFTER lock (a) raw", mergedA);
const afterB = summarize("AFTER lock (b) +subcircuit_id", mergedB);

// Variant (c): production-faithful — emulate getSourceTraceIdForRoutedTrace
// (NOT exported from core): for each locked trace, pick a source_trace in the
// same subcircuit on the same net (connection_name is source_net_N for net
// conns). With source_trace_id set, the trace takes the PRESERVED path
// (connectivity + obstacle) instead of the fixed-copper obstacle path that
// rejects diagonals.
const netToSourceTraces = {};
for (const st of fresh.filter((e) => e.type === "source_trace")) {
  for (const nid of st.connected_source_net_ids ?? []) {
    (netToSourceTraces[nid] ??= []).push(st.source_trace_id);
  }
}
let unmapped = 0;
const sourceTraceIds = new Set(
  fresh.filter((e) => e.type === "source_trace").map((e) => e.source_trace_id),
);
const variantC = lockRecords(newTraces, { subcircuit_id: SUB }).map((t) => {
  // connection may itself be a source_trace (direct-trace conns)
  if (sourceTraceIds.has(t.connection_name)) {
    return { ...t, source_trace_id: t.connection_name };
  }
  const cands = netToSourceTraces[t.connection_name] ?? [];
  if (cands.length === 0) {
    unmapped++;
    return t;
  }
  return { ...t, source_trace_id: cands[0] };
});
console.log(`variant C: ${variantC.length} traces, unmapped(net not found)=${unmapped}`);
const mergedC = [
  ...fresh.filter((e) => !ROUTE_TYPES.has(e.type)),
  ...fresh.filter((e) => ROUTE_TYPES.has(e.type)),
  ...variantC,
];
const afterC = summarize("AFTER lock (c) +source_trace_id", mergedC);

// 4. Full-board re-route with locked section present (variant C).
// Requires afterC non-null (variants A/B are expected to throw: diagonal
// fixed-copper can't become obstacles).
const after = afterC;
if (!after) {
  console.log("variant C failed too — cannot proceed to re-route step");
  process.exit(2);
}
const merged = mergedC;
const lockedTraces = variantC;
// Re-route effort: pipelines take { effort } (default 1). The repo builds
// 8bit at 100x (autorouterEffortLevel="100x" in 8bit.circuit.tsx); lock tests
// must use comparable effort or locked traces self-conflict at low effort.
const REROUTE_EFFORT = Number(process.env.SPIKE_REROUTE_EFFORT ?? 10);
const t0 = Date.now();
const solver = new cap.AutoroutingPipelineSolver9_PreloadedTraceGraph(after, {
  effort: REROUTE_EFFORT,
});
solver.solve();
console.log(`full re-route solve() in ${Date.now() - t0}ms (effort=${REROUTE_EFFORT})`);
const out = solver.failed ? null : solver.getOutputSimpleRouteJson?.();
console.log(
  `solver state: solved=${solver.solved} failed=${solver.failed} error=${String(solver.error ?? "").slice(0, 300)}`,
);
if (!out) {
  console.log("pipeline9 full re-route did not solve — trying default pipeline (MultiGraph) + effort 10");
}
const lockedIds = new Set(lockedTraces.map((t) => t.pcb_trace_id));
const outIds = new Set((out?.traces ?? []).map((t) => t.pcb_trace_id));
// Locked traces preserved? Compare surviving locked geometry by connection+route.
const outById = new Map((out?.traces ?? []).map((t) => [t.pcb_trace_id, t]));
let preserved = 0;
for (const t of lockedTraces) {
  const o = outById.get(t.pcb_trace_id);
  if (o && JSON.stringify(o.route) === JSON.stringify(t.route)) preserved++;
}
console.log(
  `locked traces bit-identical in output: ${preserved}/${lockedTraces.length}`,
);
console.log(`output traces total: ${(out?.traces ?? []).length}`);

// Also confirm with the DEFAULT pipeline (what core uses in-render), effort 10
const t1 = Date.now();
const solver2 = new cap.AutoroutingPipelineSolver7_MultiGraph(after, { effort: 10 });
solver2.solve();
console.log(`default-pipeline(effort10) re-route solve() in ${Date.now() - t1}ms`);
console.log(
  `solver2 state: solved=${solver2.solved} failed=${solver2.failed} error=${String(solver2.error ?? "").slice(0, 300)}`,
);
const out2 = solver2.failed ? null : solver2.getOutputSimpleRouteJson?.();
const out2ById = new Map((out2?.traces ?? []).map((t) => [t.pcb_trace_id, t]));
let preserved2 = 0;
for (const t of lockedTraces) {
  const o = out2ById.get(t.pcb_trace_id);
  if (o && JSON.stringify(o.route) === JSON.stringify(t.route)) preserved2++;
}
console.log(
  `default pipeline: locked bit-identical ${preserved2}/${lockedTraces.length}, total traces ${(out2?.traces ?? []).length}`,
);

const outDir = path.join(__dirname, "out-7-3");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "merged.circuit.json"), JSON.stringify(merged));
console.log(`artifacts -> ${outDir}/`);
