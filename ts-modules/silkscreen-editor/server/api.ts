/**
 * Vite middleware plugin — the /api surface of the silkscreen editor.
 *
 * Single-entry mode: the process edits exactly ONE .circuit.tsx (SILK_ENTRY);
 * the UI auto-loads it on boot, so there is no module picker and no ?module=
 * params anywhere.
 *
 *   GET  /api/entry                   → { entry, name, sourcePath }
 *   GET  /api/inventory               → { entry, name, items, counts, board }
 *   GET  /api/compile                 → { …, svg } (silkscreen-only underlay)
 *   POST /api/apply                   → M4 write-back (see below)
 *
 * The heavy lifting happens in the bun child (server/compile-worker.ts) so the
 * vite process never loads tscircuit internals.
 *
 * POST /api/apply { expectedEntryMtimeMs, edits: SilkEdit[] }:
 *   1. guard: refuse if the source file changed since the client's compile
 *      (mtime check) or if another apply is in flight,
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
import { compileEntry } from "./compile";
import { entryDisplayName, resolveEntryPath } from "./paths";
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
    if (!matched) {
      return {
        ok: false,
        detail: `no fresh item at (${exp.x!.toFixed(3)}, ${exp.y!.toFixed(3)}) for "${exp.text}"`,
      };
    }
    return verifyStyle(matched, exp);
  }

  if (exp.hidden === false) {
    // show: the text must be back in the fresh compile
    const back = freshItems.find((it) =>
      it.kind === exp.kind &&
      it.text === exp.text &&
      (exp.kind === "label" || it.ref === exp.ref),
    );
    if (!back) {
      return { ok: false, detail: `text "${exp.text}" still absent after show` };
    }
    return { ok: true, detail: "confirmed present in fresh compile", matchedItem: back };
  }

  // text-only / style-only edits: verify by text match, then style fields
  const matched = freshItems.find((it) => sameOwner(it));
  if (!matched) {
    return { ok: false, detail: `no fresh item matches "${exp.text}"` };
  }
  return verifyStyle(matched, exp);
}

/** rotation/anchor/fontSize expectations against a fresh item (when set). */
function verifyStyle(
  it: any,
  exp: NonNullable<EditOutcome["expect"]>,
): { ok: boolean; detail: string; matchedItem?: any } {
  const styleChecks: [string, number | string | undefined, number | string | undefined, number][] = [
    ["rotation", exp.rotation, it.rotation, 0.01],
    ["fontSize", exp.fontSize, it.fontSize, 0.001],
  ];
  for (const [name, want, got, tol] of styleChecks) {
    if (want !== undefined && Math.abs(Number(got) - Number(want)) > tol) {
      return { ok: false, detail: `${name} mismatch: expected ${want}, fresh compile has ${got}` };
    }
  }
  if (exp.anchor !== undefined && it.anchor !== exp.anchor) {
    return { ok: false, detail: `anchor mismatch: expected "${exp.anchor}", fresh compile has "${it.anchor}"` };
  }
  return { ok: true, detail: "confirmed in fresh compile", matchedItem: it };
}

/** in-flight lock (edits mutate a real source file — one apply at a time) */
let applyInFlight = false;

export function silkApiPlugin(): Plugin {
  // resolve at plugin construction so a missing/invalid SILK_ENTRY fails
  // the dev server boot loudly instead of per-request.
  const entry = resolveEntryPath();
  const name = entryDisplayName(entry);

  return {
    name: "bread-modular-silkscreen-api",
    configureServer(server) {
      server.middlewares.use("/api/entry", (_req, res) =>
        handle(res, async () => ({ ok: true, entry, name, sourcePath: entry })),
      );

      server.middlewares.use("/api/inventory", (_req, res) =>
        handle(res, async () => {
          const r = await compileEntry();
          if (!r.ok) return { ok: false, error: r.error };
          const { svg: _svg, ...rest } = r;
          void _svg;
          return rest; // items + counts + board, no svg
        }),
      );

      server.middlewares.use("/api/compile", (_req, res) =>
        handle(res, async () => {
          const r = await compileEntry();
          return r; // items + counts + board + svg underlay
        }),
      );

      server.middlewares.use("/api/apply", (req, res) => {
        if (req.method !== "POST")
          return json(res, 405, { ok: false, error: "POST only" });
        return handleApply(req, res, entry, name);
      });

      // eslint-disable-next-line no-console
      console.log(
        `[silk-api] entry=${entry} — /api/entry /api/inventory /api/compile /api/apply ready`,
      );
    },
  };
}

async function handleApply(req: any, res: any, entry: string, name: string): Promise<void> {
  const body = await readBody(req);
  if (!body)
    return json(res, 400, { ok: false, error: "invalid JSON body" });

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
    if (e.ops?.hidden === undefined && e.ops?.x === undefined && e.ops?.y === undefined && e.ops?.text === undefined && e.ops?.rotation === undefined && e.ops?.anchor === undefined && e.ops?.fontSize === undefined) {
      return json(res, 400, { ok: false, error: "edit has no ops" });
    }
    if (e.ops?.rotation !== undefined && !Number.isFinite(Number(e.ops.rotation))) {
      return json(res, 400, { ok: false, error: "ops.rotation must be a finite number (degrees)" });
    }
    if (e.ops?.fontSize !== undefined && !Number.isFinite(Number(e.ops.fontSize))) {
      return json(res, 400, { ok: false, error: "ops.fontSize must be a finite number (mm)" });
    }
    if (e.ops?.anchor !== undefined) {
      const anchors = new Set([
        "center", "top_left", "top_center", "top_right",
        "center_left", "center_right", "bottom_left", "bottom_center", "bottom_right",
      ]);
      if (typeof e.ops.anchor !== "string" || !anchors.has(e.ops.anchor)) {
        return json(res, 400, { ok: false, error: `ops.anchor must be one of: ${[...anchors].join(", ")}` });
      }
    }
  }

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

  if (applyInFlight)
    return json(res, 423, {
      ok: false,
      error: "another apply is in flight",
    });
  applyInFlight = true;

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
    const fresh = await compileEntry();
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
      entry: fresh.sourcePath ?? entry,
      module: name,
      name,
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
    applyInFlight = false;
  }
}

async function handle(res: any, fn: () => Promise<unknown>) {
  try {
    json(res, 200, await fn());
  } catch (err: any) {
    json(res, 500, { ok: false, error: err?.message ?? String(err) });
  }
}
