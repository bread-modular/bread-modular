/**
 * Vite middleware plugin — the /api surface of the silkscreen editor (M2).
 *
 *   GET /api/modules                 → { modules: string[] }
 *   GET /api/inventory?module=8bit   → { module, items, counts, board }
 *   GET /api/compile?module=8bit     → { …, svg } (silkscreen-only underlay)
 *
 * The heavy lifting happens in the bun child (server/compile-worker.ts) so the
 * vite process never loads tscircuit internals. Write-back (/api/save) lands
 * in M4 — this server is read-only on purpose.
 */
import type { Plugin } from "vite";
import { compileModule } from "./compile";
import { listModules, moduleExists } from "./paths";

function json(res: any, status: number, payload: unknown) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

async function handle(res: any, fn: () => Promise<unknown>) {
  try {
    json(res, 200, await fn());
  } catch (err: any) {
    json(res, 500, { ok: false, error: err?.message ?? String(err) });
  }
}

function moduleNameFromUrl(url: string | undefined): string | null {
  const q = url?.split("?")[1] ?? "";
  const m = new URLSearchParams(q).get("module");
  return m && moduleExists(m) ? m : null;
}

export function silkApiPlugin(): Plugin {
  return {
    name: "bread-modular-silkscreen-api",
    configureServer(server) {
      server.middlewares.use("/api/modules", (_req, res) =>
        handle(res, async () => ({ ok: true, modules: listModules() })),
      );

      server.middlewares.use("/api/inventory", (req, res) => {
        const moduleName = moduleNameFromUrl(req.url);
        if (!moduleName)
          return json(res, 400, {
            ok: false,
            error: "missing/unknown ?module= (known: /api/modules)",
          });
        return handle(res, async () => {
          const r = await compileModule(moduleName);
          if (!r.ok) return { ok: false, error: r.error };
          const { svg: _svg, ...rest } = r;
          return rest; // items + counts + board, no svg
        });
      });

      server.middlewares.use("/api/compile", (req, res) => {
        const moduleName = moduleNameFromUrl(req.url);
        if (!moduleName)
          return json(res, 400, {
            ok: false,
            error: "missing/unknown ?module= (known: /api/modules)",
          });
        return handle(res, async () => {
          const r = await compileModule(moduleName);
          return r; // items + counts + board + svg underlay
        });
      });

      // eslint-disable-next-line no-console
      console.log("[silk-api] /api/modules /api/inventory /api/compile ready");
    },
  };
}
