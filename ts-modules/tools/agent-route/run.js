#!/usr/bin/env node
// agent-route run / retry-section — owned by the routing chat.
//
//   agent-route run <board> [--keep-going] [--no-bisect] [--json]
//                   [--timeout-ms N] [--effort N] [--max-bisect-depth N]
//   agent-route retry-section <board> <sectionId> [--json] [--timeout-ms N] [--effort N]
//
// Routes plan sections in phaseIndex order using the capacity-autorouter
// pipeline, one section SRJ at a time (hand-built: full SRJ with connections
// filtered + locked traces carried), stitch+lock after each section, per-section
// + final DRC gates. See docs/agent-router-design.md §4.3–§4.6, §5, §6.
//
// Conventions shared with the CLI chat (cli.js / lib/*):
//   - plans: src/<board>/<board>.agent-plan.json, connections are scan-level
//     "REF.pin > REF.pin" strings (lib/scan.js). They map to MANY source_trace_*
//     fragments in circuit-json — never 1:1. See resolveScanConn() below.
//   - sigs: lib/sig.js sigForSection/verifySectionSig over a scan object.
//     .sig files hold the bare hex digest; section files hold locked geometry.
//   - status: <board>.agent-route/status.json per §4.5 schema.
//   - section files: Si.<name>.agent-route.json + .sig (bare hex digest).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { routeBoard } from "./lib/route-board.js";
import { retrySection } from "./lib/retry-section.js";

const argv = process.argv.slice(2);

function usage(exit = 1) {
  console.error(`usage:
  agent-route run <board> [--keep-going] [--no-bisect] [--json]
                  [--timeout-ms N] [--effort N] [--max-bisect-depth N]
  agent-route retry-section <board> <sectionId> [--json] [--timeout-ms N] [--effort N]`);
  process.exit(exit);
}

function parseArgs(list) {
  const flags = {
    keepGoing: false,
    bisect: true,
    json: false,
    timeoutMs: undefined,
    effort: undefined,
    maxBisectDepth: undefined,
  };
  const positionals = [];
  for (let i = 0; i < list.length; i++) {
    const a = list[i];
    if (a === "--keep-going") flags.keepGoing = true;
    else if (a === "--no-bisect") flags.bisect = false;
    else if (a === "--json") flags.json = true;
    else if (a === "--timeout-ms") flags.timeoutMs = Number(list[++i]);
    else if (a === "--effort") flags.effort = Number(list[++i]);
    else if (a === "--max-bisect-depth") flags.maxBisectDepth = Number(list[++i]);
    else if (a === "--help" || a === "-h") usage(0);
    else if (a.startsWith("--")) {
      console.error(`unknown flag ${a}`);
      usage(1);
    } else positionals.push(a);
  }
  return { flags, positionals };
}

const { flags, positionals } = parseArgs(argv);
const [cmd, board, sectionId] = positionals;
if (!cmd || !board) usage(1);

if (!existsSync(join("src", board, `${board}.circuit.tsx`))) {
  console.error(`INPUT_INVALID: unknown board '${board}' (expected src/${board}/${board}.circuit.tsx)`);
  process.exit(2);
}

// cli.js prints JSON errors itself; keep a machine-readable envelope on crashes.
process.on("uncaughtException", (e) => {
  if (flags.json) console.log(JSON.stringify({ ok: false, error: String(e?.message ?? e) }));
  else console.error(`error: ${String(e?.message ?? e)}`);
  process.exit(1);
});

let code = 2;
if (cmd === "run") {
  if (sectionId !== undefined) usage(1);
  code = await routeBoard(board, flags);
} else if (cmd === "retry-section") {
  if (!sectionId) usage(1);
  code = await retrySection(board, sectionId, flags);
} else {
  console.error(`run.js: unknown command '${cmd}' (try: run, retry-section)`);
  process.exit(2);
}
process.exit(code);
