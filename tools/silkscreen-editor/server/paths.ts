import { dirname, join, resolve } from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

// Works under bun (compile-worker) AND node (vite middleware).
const here = dirname(fileURLToPath(import.meta.url));

/** tools/silkscreen-editor */
export const pkgDir = resolve(here, "..");
/** repo root (this package lives at <repo>/tools/silkscreen-editor) */
export const repoRoot = resolve(pkgDir, "..", "..");
/**
 * The circuit package whose node_modules (KiCad-font-patched) and src/<m>/
 * modules we eval against. Overridable for out-of-repo checkouts:
 *   SILK_TS_MODULES_DIR=/path/to/bread-modular/ts-modules
 */
export const tsModulesDir =
  process.env.SILK_TS_MODULES_DIR ?? join(repoRoot, "ts-modules");

export const MODULE_NAME_RE = /^[a-zA-Z0-9_-]+$/;

export function moduleEntry(moduleName: string): string {
  return join(tsModulesDir, "src", moduleName, `${moduleName}.circuit.tsx`);
}

export function routedJsonPath(moduleName: string): string {
  return join(tsModulesDir, "src", moduleName, `${moduleName}.routed.json`);
}

export function moduleExists(moduleName: string): boolean {
  if (!MODULE_NAME_RE.test(moduleName)) return false;
  return fs.existsSync(moduleEntry(moduleName));
}

/** All modules under ts-modules/src/<m>/<m>.circuit.tsx, sorted. */
export function listModules(): string[] {
  const srcDir = join(tsModulesDir, "src");
  if (!fs.existsSync(srcDir)) return [];
  return fs
    .readdirSync(srcDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .filter((d) => fs.existsSync(join(srcDir, d.name, `${d.name}.circuit.tsx`)))
    .map((d) => d.name)
    .sort();
}
