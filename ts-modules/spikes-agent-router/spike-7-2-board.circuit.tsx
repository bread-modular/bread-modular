/**
 * Spike 7.2 — trivial algorithmFn delegating to capacity-autorouter.
 *
 * SCRATCH board only (does NOT modify any *.circuit.tsx or build.sh).
 * Renders the same BreadModule+AnalogStarter content as blank, but passes
 * autorouter={{ algorithmFn }} (object form, honoured by
 * getPresetAutoroutingConfig) where algorithmFn wraps the DEFAULT pipeline
 * core would use (AutoroutingPipelineSolver7_MultiGraph == "latest") in the
 * start()/on()/getOutputSimpleRouteJson() interface core expects.
 *
 * PASS = tsci build output has identical routing (pcb_trace/pcb_via sets +
 * DRC-clean) to src/blank/blank.routed.json, and the fn is actually invoked
 * (marker file written).
 */
import { BreadModule, AnalogStarter } from "../lib/index.js";
import { AutoroutingPipelineSolver7_MultiGraph } from "@tscircuit/capacity-autorouter";
import fs from "node:fs";

const MARKER = new URL("./out-7-2-algorithmfn-invoked.json", import.meta.url);

function makeDelegatingAutorouter(simpleRouteJson: any) {
  const solver = new AutoroutingPipelineSolver7_MultiGraph(simpleRouteJson);
  const handlers: Record<string, Function[]> = {
    complete: [],
    error: [],
    progress: [],
  };
  return {
    getOutputSimpleRouteJson: () => solver.getOutputSimpleRouteJson(),
    on: (ev: string, cb: Function) => {
      handlers[ev]?.push(cb);
    },
    start: () => {
      (async () => {
        try {
          fs.writeFileSync(
            MARKER,
            JSON.stringify({
              invokedAt: new Date().toISOString(),
              connections: simpleRouteJson.connections?.length,
              obstacles: simpleRouteJson.obstacles?.length,
            }),
          );
          // Drive step-by-step like CapacityMeshAutorouter.runCycleAndQueueNextCycle
          while (!solver.solved && !solver.failed) {
            if (typeof (solver as any).stepAsync === "function") {
              await (solver as any).stepAsync();
            } else {
              (solver as any).step();
            }
          }
          if (solver.failed) {
            const err = new Error(
              `delegated solver failed: ${(solver as any).error ?? "unknown"}`,
            );
            handlers.error.forEach((h) => h({ error: err }));
          } else {
            handlers.complete.forEach((h) =>
              h({ traces: solver.getOutputSimpleRouteJson().traces ?? [] }),
            );
          }
        } catch (error) {
          handlers.error.forEach((h) => h({ error }));
        }
      })();
    },
  };
}

export default () => (
  <BreadModule
    name="NAME"
    version="0.0.0"
    // @ts-expect-error — BreadModule types autorouter as string; runtime
    // spreads it onto <board>, whose AutorouterProp accepts the object form
    // with algorithmFn (scratch spike only, not a board source change).
    autorouter={{ algorithmFn: async (srj: any) => makeDelegatingAutorouter(srj) }}
  >
    <AnalogStarter />
  </BreadModule>
);
