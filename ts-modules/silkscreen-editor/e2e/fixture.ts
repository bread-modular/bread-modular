/**
 * e2e fixture wiring — shared between the Playwright config (webServer env)
 * and the spec (snapshot/restore the fixture file).
 *
 * The fixture is a byte-identical copy of ts-modules/src/drive/drive.circuit.tsx
 * living at e2e/fixtures/drive/. Its `../../lib` import resolves via the
 * e2e/lib → ../../lib symlink, so the copy compiles standalone while the
 * worker's user-land imports (react/tscircuit/circuit-to-svg) come from
 * SILK_TS_MODULES_DIR (the real ts-modules).
 *
 * Refresh the copy after drive changes (must be byte-identical):
 *   cp ../../src/drive/drive.circuit.tsx e2e/fixtures/drive/drive.circuit.tsx
 */
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

/** absolute path of the disposable .circuit.tsx the e2e server edits */
export const FIXTURE_ENTRY = join(here, "fixtures", "drive", "drive.circuit.tsx");

/** repo ts-modules dir (user-land node_modules for the worker eval) */
export const TS_MODULES_DIR = resolve(here, "..", "..");

/** env for the Playwright webServer: entry + user-land override */
export function fixtureServerEnv(): Record<string, string> {
  return {
    ...process.env as Record<string, string>,
    SILK_ENTRY: FIXTURE_ENTRY,
    SILK_TS_MODULES_DIR: TS_MODULES_DIR,
    PATH: `${join(TS_MODULES_DIR, "node_modules", ".bin")}:${process.env.PATH ?? ""}`,
  };
}
