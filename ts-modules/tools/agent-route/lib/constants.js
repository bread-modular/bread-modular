// Shared constants for tools/agent-route.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tsModulesDir = join(here, "..", "..", "..");
const require = createRequire(import.meta.url);

function pkgVersion(name) {
  try {
    return require(`${name}/package.json`).version ?? "unknown";
  } catch {
    return "unknown";
  }
}

export const VERSIONS = {
  tscircuit: pkgVersion("tscircuit"),
  core: pkgVersion("@tscircuit/core"),
  capacityAutorouter: pkgVersion("@tscircuit/capacity-autorouter"),
  checks: pkgVersion("@tscircuit/checks"),
  cli: pkgVersion("@tscircuit/cli"),
  eval: pkgVersion("@tscircuit/eval"),
};

export const PLAN_VERSION = 1;

// Clearance defaults (mm). Rect = cluster bbox + MARGIN; adjacent rects
// overlap by >= OVERLAP (>= 2x max trace pitch per design §4.2).
export const MARGIN = 2.0;
export const OVERLAP = 1.0;

export const ROUTER_PARAMS = {
  router: "capacity-autorouter",
  overlapMarginMm: OVERLAP,
  sectionMarginMm: MARGIN,
};

export const TSMODULES_DIR = tsModulesDir;
export const SRC_DIR = join(tsModulesDir, "src");

export function boardEntry(board) {
  return join(SRC_DIR, board, `${board}.circuit.tsx`);
}

export function planPath(board) {
  return join(SRC_DIR, board, `${board}.agent-plan.json`);
}

export function statusPath(board) {
  return join(SRC_DIR, board, `${board}.agent-route`, "status.json");
}

export function sectionDir(board) {
  return join(SRC_DIR, board, `${board}.agent-route`);
}

export function distCircuit(board) {
  return join(tsModulesDir, "dist", "src", board, board, "circuit.json");
}

export function routedJsonPath(board) {
  return join(SRC_DIR, board, `${board}.routed.json`);
}

export function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}
