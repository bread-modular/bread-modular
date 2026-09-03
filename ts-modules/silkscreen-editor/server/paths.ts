import { dirname, join, resolve, basename } from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

/**
 * Single-entry resolution for the silkscreen editor.
 *
 * The editor works on exactly ONE `.circuit.tsx` file per process, chosen at
 * startup via the SILK_ENTRY env var (absolute path — `silk.sh dev <path>`
 * resolves it before launching vite):
 *
 *   SILK_ENTRY=/path/to/ts-modules/src/drive/drive.circuit.tsx ./silk.sh dev
 *   SILK_ENTRY=./e2e/fixtures/drive/drive.circuit.tsx npx playwright test
 *
 * No module registry, no picker: the UI auto-loads the entry, and the e2e
 * suite copies a real module (drive) into e2e/fixtures/ so tests mutate a
 * disposable fixture instead of real sources.
 *
 * Works under bun (compile-worker) AND node (vite middleware).
 */
const here = dirname(fileURLToPath(import.meta.url));

/** ts-modules/silkscreen-editor */
export const pkgDir = resolve(here, "..");
/** repo root (this package lives at <repo>/ts-modules/silkscreen-editor) */
export const repoRoot = resolve(pkgDir, "..", "..");

/**
 * Absolute path of the single entry .circuit.tsx under edit. Throws with a
 * usage hint when SILK_ENTRY is missing/invalid — every caller (worker, CLI,
 * API) funnels through here so misconfiguration fails fast and loud.
 */
export function resolveEntryPath(): string {
  const raw = process.env.SILK_ENTRY;
  if (!raw) {
    throw new Error(
      "SILK_ENTRY is not set — point the editor at one .circuit.tsx, e.g.:\n" +
        "  ./silk.sh dev ../src/drive/drive.circuit.tsx   # from silkscreen-editor/\n" +
        "  SILK_ENTRY=<abs path to a .circuit.tsx> bun run dev",
    );
  }
  const abs = resolve(raw);
  if (!abs.endsWith(".circuit.tsx")) {
    throw new Error(`SILK_ENTRY must be a .circuit.tsx file, got: ${raw}`);
  }
  if (!fs.existsSync(abs)) {
    throw new Error(`SILK_ENTRY does not exist: ${abs}`);
  }
  return abs;
}

/** Display name for an entry: basename minus `.circuit.tsx` (e.g. "drive"). */
export function entryDisplayName(entryPath: string): string {
  return basename(entryPath, ".circuit.tsx");
}

/**
 * The circuit package whose node_modules (KiCad-font-patched) the worker evals
 * against. Default: three levels above the entry (…/ts-modules/src/<m>/<f> →
 * …/ts-modules). Entries that live elsewhere (e.g. e2e/fixtures/) MUST set
 * SILK_TS_MODULES_DIR explicitly — the e2e webServer does this.
 */
export function tsModulesDirFor(entryPath: string): string {
  if (process.env.SILK_TS_MODULES_DIR) {
    return resolve(process.env.SILK_TS_MODULES_DIR);
  }
  return resolve(dirname(entryPath), "..", "..");
}

/** Directory containing the entry file (fixture copies live here). */
export function entryDir(entryPath: string): string {
  return dirname(entryPath);
}

export { join };
