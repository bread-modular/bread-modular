/**
 * Vite middleware plugin — the /api surface of the silkscreen editor.
 *
 *   GET  /api/modules                 → { modules: string[] }
 *   GET  /api/inventory?module=8bit   → { module, items, counts, board }
 *   GET  /api/compile?module=8bit     → { …, svg } (silkscreen-only underlay)
 *   POST /api/apply                   → M4 write-back (see below)
 *
 * The heavy lifting happens in the bun child (server/compile-worker.ts) so the
 * vite process never loads tscircuit internals.
 *
 * POST /api/apply { module, expectedEntryMtimeMs, edits: SilkEdit[] }:
 *   1. guard: refuse if the source file changed since the client's compile
 *      (mtime check) or if another apply is in flight for this module,
 *   2. patch the TSX in memory with ts-morph (server/patch.ts) — edits that
 *      cannot be located / are computed are reported, never guessed,
 *   3. write the file, recompile, and verify every edit's expected post-edit
 *      position/visibility in the fresh circuit json,
 *   4. ANY failure (patch refused, syntax gate, compile error, verification
 *      mismatch) ⇒ restore the original bytes — no partial writes ever.
 *   On success the response carries the fresh compile result so UI and source
 *   stay in sync in one round trip.
 */
import type { Plugin } from "vite";
import { readFile, stat, writeFile } from "node:fs/promises";
import { compileModule } from "./compile";
import { listModules, moduleExists, moduleEntry } from "./paths";
import {
  applyEditsToSource,
  type ApplyEditsResult,
  type EditOutcome,
  type SilkEdit,
} from "./patch";

function json(res: any, status: number, payload: unknown) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

async function readBody(req: any): Promise<any> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  const raw = Buffer.concat(chunks).toString("utf8");
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** did the fresh circuit json contain the expected post-edit state? */
function verifyOutcome(
  outcome: EditOutcome,
  freshItems: any[],
): { ok: boolean; detail: string; matchedItem?: any } {
  const exp = outcome.expect;
  if (!exp) return { ok: false, detail: "no expectation recorded" };

  const sameOwner = (it: any) =>
    it.kind === exp.kind &&
    (exp.kind === "ref"
      ? it.ref === exp.ref
      : it.text === exp.text || it.text === (exp.text ?? ""));

  if (exp.hidden === true) {
    // the text must be gone from the fresh compile
    const still = freshItems.find(
      (it) =>
        it.kind === exp.kind &&
        it.text === exp.text &&
        (exp.kind === "label" || it.ref === exp.ref),
    );
    return still
      ? { ok: false, detail: `text "${exp.text}" still present after hide` }
      : { ok: true, detail: "confirmed absent from fresh compile" };
  }

  if (exp.x !== undefined && exp.y !== undefined) {
    const tol = 0.002;
    const matched = freshItems.find(
      (it) =>
        sameOwner(it) &&
        Math.abs(it.x - exp.x!) < tol &&
        Math.abs(it.y - exp.y!) < tol,
    );
    if (matched) {
      return {
        ok: true,
        detail: `position confirmed (${matched.x.toFixed(3)}, ${matched.y.toFixed(3)})`,
        matchedItem: matched,
      };
    }
    return {
      ok: false,
      detail: `no fresh item at (${exp.x!.toFixed(3)}, ${exp.y!.toFixed(3)}) for "${exp.text}"`,
    };
  }

  if (exp.hidden === false) {
    // show: un-hiding restores visibility; nothing to verify beyond compile ok
    return { ok: true, detail: "show applied (compile ok)" };
  }

  // text-only edits etc: verify by text match
  const matched = freshItems.find((it) => sameOwner(it));
  return matched
    ? { ok: true, detail: "confirmed in fresh compile", matchedItem: matched }
    : { ok: false, detail: `no fresh item matches "${exp.text}"` };
}

/** per-module in-flight lock (edits mutate real source files) */
const locks = new Set<string>();

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

      server.middlewares.use("/api/apply", (req, res) => {
        if (req.method !== "POST")
          return json(res, 405, { ok: false, error: "POST only" });
        return handleApply(req, res);
      });

      // eslint-disable-next-line no-console
      console.log(
        "[silk-api] /api/modules /api/inventory /api/compile /api/apply ready",
      );
    },
  };
}

async function handleApply(req: any, res: any): Promise<void> {
  const body = await readBody(req);
  if (!body)
    return json(res, 400, { ok: false, error: "invalid JSON body" });

  const moduleName = String(body.module ?? "");
  if (!moduleExists(moduleName))
    return json(res, 400, { ok: false, error: `unknown module "${moduleName}"` });

  const edits: SilkEdit[] = Array.isArray(body.edits) ? body.edits : [];
  if (edits.length === 0)
    return json(res, 400, { ok: false, error: "no edits supplied" });

  // basic shape validation — never trust the client
  for (const e of edits) {
    if (
      (e.kind !== "label" && e.kind !== "ref") ||
      typeof e.text !== "string" ||
      typeof e.fingerprint !== "string"
    ) {
      return json(res, 400, {
        ok: false,
        error: `malformed edit (kind/text/fingerprint required): ${JSON.stringify(e).slice(0, 120)}`,
      });
    }
    if (e.kind === "ref" && typeof e.ref !== "string") {
      return json(res, 400, {
        ok: false,
        error: "ref edits require the owning component ref name",
      });
    }
    if (e.ops?.hidden === undefined && e.ops?.x === undefined && e.ops?.y === undefined && e.ops?.text === undefined) {
      return json(res, 400, { ok: false, error: "edit has no ops" });
    }
  }

  const entry = moduleEntry(moduleName);

  // --- mtime guard: refuse stale saves (source changed since compile) ---
  const currentMtime = (await stat(entry)).mtimeMs;
  const expected = Number(body.expectedEntryMtimeMs);
  if (Number.isFinite(expected) && Math.abs(currentMtime - expected) > 1.5) {
    return json(res, 409, {
      ok: false,
      error:
        "source file changed on disk since the last compile — recompile and re-apply",
      stale: true,
      entryMtimeMs: currentMtime,
    });
  }

  if (locks.has(moduleName))
    return json(res, 423, {
      ok: false,
      error: "another apply is in flight for this module",
    });
  locks.add(moduleName);

  const original = await readFile(entry, "utf8");
  let patched: ApplyEditsResult | null = null;
  try {
    // 1. patch in memory (ts-morph) — no disk write yet
    patched = applyEditsToSource(entry, original, edits);
    if (!patched.ok || !patched.newSource) {
      return json(res, 422, {
        ok: false,
        error: patched.error ?? "patch failed",
        outcomes: patched.outcomes,
      });
    }

    const applied = patched.outcomes.filter((o) => o.ok);
    if (applied.length === 0) {
      return json(res, 422, {
        ok: false,
        error: "no edits could be applied to the source",
        outcomes: patched.outcomes,
      });
    }

    // 2. write + 3. recompile + 4. verify — full rollback on any failure
    await writeFile(entry, patched.newSource);
    const fresh = await compileModule(moduleName);
    if (!fresh.ok) {
      await writeFile(entry, original);
      return json(res, 500, {
        ok: false,
        error: `write-back rejected: recompile failed (source restored) — ${fresh.error}`,
        outcomes: patched.outcomes,
        rolledBack: true,
      });
    }

    const verifications = applied.map((o) => {
      const v = verifyOutcome(o, fresh.items ?? []);
      return {
        fingerprint: o.fingerprint,
        ok: v.ok,
        detail: v.detail,
        change: o.change,
        newText: o.expect?.text,
        newX: v.matchedItem?.x,
        newY: v.matchedItem?.y,
        newFingerprint: v.matchedItem?.fingerprint,
      };
    });
    const failed = verifications.filter((v) => !v.ok);
    if (failed.length > 0) {
      await writeFile(entry, original);
      return json(res, 500, {
        ok: false,
        error: `write-back rejected: ${failed.length}/${verifications.length} edits failed round-trip verification (source restored)`,
        verifications,
        outcomes: patched.outcomes,
        rolledBack: true,
      });
    }

    // success — respond with the fresh compile so the UI updates in place
    return json(res, 200, {
      ok: true,
      module: moduleName,
      sourcePath: fresh.sourcePath ?? entry,
      entryMtimeMs: fresh.entryMtimeMs,
      diff: patched.diff ?? [],
      outcomes: patched.outcomes,
      verifications,
      unpatched: patched.outcomes
        .filter((o) => !o.ok)
        .map((o) => ({ fingerprint: o.fingerprint, reason: o.reason })),
      items: fresh.items,
      counts: fresh.counts,
      board: fresh.board,
      svg: fresh.svg,
      frameLabels: fresh.frameLabels,
    });
  } catch (err: any) {
    // belt & braces: never leave a half-written file behind
    if (patched) {
      const now = await readFile(entry, "utf8").catch(() => null);
      if (now !== null && now !== original) await writeFile(entry, original);
    }
    return json(res, 500, {
      ok: false,
      error: err?.message ?? String(err),
      rolledBack: true,
    });
  } finally {
    locks.delete(moduleName);
  }
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

