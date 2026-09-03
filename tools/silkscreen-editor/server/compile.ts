/**
 * Spawn wrapper around the bun compile worker — used by the vite middleware
 * (server/api.ts) and the inventory CLI (server/inventory-cli.ts).
 *
 * The worker writes its result to a temp FILE; stdout of the eval (tscircuit
 * logs etc.) can never corrupt the JSON payload.
 */
import { spawn } from "node:child_process";
import { readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pkgDir } from "./paths";

export type CompileResult = {
  ok: boolean;
  error?: string;
  module?: string;
  entry?: string;
  board?: { width: number; height: number; center: { x: number; y: number } };
  frameLabels?: {
    name?: string;
    version?: string;
    inputLabels: string[];
    outputLabels: string[];
  };
  items?: import("./silkscreen").SilkItem[];
  counts?: {
    silkscreenTexts: number;
    refs: number;
    labels: number;
    keptElements: number;
    droppedElements: number;
  };
  svg?: string;
};

const BUN = process.env.SILK_BUN ?? "bun";
const COMPILE_TIMEOUT_MS = 120_000;

export function compileModule(moduleName: string): Promise<CompileResult> {
  const outFile = path.join(
    tmpdir(),
    `silk-compile-${moduleName}-${process.pid}-${Date.now()}.json`,
  );
  const worker = path.join(pkgDir, "server", "compile-worker.ts");

  return new Promise<CompileResult>((resolvePromise) => {
    const child = spawn(
      BUN,
      [worker, "--module", moduleName, "--out", outFile],
      {
        cwd: pkgDir,
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
      },
    );

    let stderr = "";
    child.stderr.on("data", (d) => (stderr += d.toString()));

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      stderr = `compile timed out after ${COMPILE_TIMEOUT_MS / 1000}s\n${stderr}`;
    }, COMPILE_TIMEOUT_MS);

    child.on("error", (err) => {
      clearTimeout(timer);
      resolvePromise({
        ok: false,
        error: `failed to spawn bun worker (${BUN}): ${err.message}. Run via ./silk.sh so bun is on PATH.`,
      });
    });

    child.on("close", async (code) => {
      clearTimeout(timer);
      try {
        const raw = await readFile(outFile, "utf8");
        const parsed = JSON.parse(raw) as CompileResult;
        resolvePromise(parsed);
      } catch {
        resolvePromise({
          ok: false,
          error: `worker exited with code ${code}${stderr ? `:\n${stderr}` : " (no stderr)"}`,
        });
      } finally {
        rm(outFile, { force: true }).catch(() => {});
      }
    });
  });
}
