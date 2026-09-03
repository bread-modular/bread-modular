#!/usr/bin/env node
// agent-route run-v2 — owned by the v2 routing work (side-by-side with run.js).
//
//   agent-route run-v2 <board> [--json] [--effort N]
//
// Routes phases from src/<board>/<board>.agent-phases.json in phaseIndex
// order using the CLI-owned net-phase loop (lib/route-v2.js): full SRJ with
// connections filtered to the phase net set + locked traces carried, FULL
// BOARD bounds every solve, cumulative locked x new gates. See run.js for the
// v1 equivalent — v1 files untouched.
import { existsSync } from "node:fs";
import { join } from "node:path";
import { routeBoardV2 } from "./lib/route-v2.js";
import { SRC_DIR } from "./lib/constants.js";

const argv = process.argv.slice(2);

function usage(exit = 1) {
  console.error(`usage:
  agent-route run-v2 <board> [--json] [--effort N]`);
  process.exit(exit);
}

const flags = { json: false, effort: undefined };
const positionals = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--json") flags.json = true;
  else if (a === "--effort") flags.effort = Number(argv[++i]);
  else if (a === "--help" || a === "-h") usage(0);
  else if (a.startsWith("--")) {
    console.error(`unknown flag ${a}`);
    usage(1);
  } else positionals.push(a);
}

const [cmd, board] = positionals;
if (cmd !== "run-v2" || !board) usage(1);

if (!existsSync(join(SRC_DIR, board, `${board}.circuit.tsx`))) {
  console.error(`INPUT_INVALID: unknown board '${board}' (expected src/${board}/${board}.circuit.tsx)`);
  process.exit(2);
}

process.on("uncaughtException", (e) => {
  if (flags.json) console.log(JSON.stringify({ ok: false, error: String(e?.message ?? e) }));
  else console.error(`error: ${String(e?.message ?? e)}`);
  process.exit(1);
});

process.exit(await routeBoardV2(board, flags));
