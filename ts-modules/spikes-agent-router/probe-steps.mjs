import fs from "node:fs";
const core = await import("@tscircuit/core");
const cap = await import("@tscircuit/capacity-autorouter");

const which = process.argv[2] ?? "blank";
const effort = Number(process.argv[3] ?? 10);
const cj = JSON.parse(
  fs.readFileSync(`dist/src/${which}/${which}/circuit.json`, "utf8"),
);
const { simpleRouteJson: full } = core.getSimpleRouteJsonFromCircuitJson({
  circuitJson: cj,
  subcircuit_id: "subcircuit_source_group_0",
});
console.log(
  `full ${which}: conns=${full.connections.length} traces=${(full.traces ?? []).length} effort=${effort}`,
);

const s = new cap.AutoroutingPipelineSolver9_PreloadedTraceGraph(
  structuredClone(full),
  { effort },
);
const t0 = Date.now();
let n = 0;
let threw = null;
try {
  while (!s.solved && !s.failed && n < 50000000) {
    s.step();
    n++;
    if (Date.now() - t0 > 240000) {
      console.log("WALL-CLOCK 240s hit, bailing");
      break;
    }
  }
} catch (e) {
  threw = String(e?.message ?? e).slice(0, 300);
}
console.log(
  `done: steps=${n} iters=${s.iterations} solved=${s.solved} failed=${s.failed} ms=${Date.now() - t0}`,
);
console.log(`solver.error: ${String(s.error ?? "").slice(0, 300)}`);
console.log(`threw: ${threw}`);
if (!s.failed && s.solved) {
  const out = s.getOutputSimpleRouteJson();
  console.log(`out traces=${out.traces.length}`);
}
