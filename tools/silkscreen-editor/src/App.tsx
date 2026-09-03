import { useEffect, useMemo, useState } from "react";
import {
  applyEdits,
  fetchCompile,
  fetchModules,
  type ApplyEdit,
  type ApplyResponse,
  type CompileResponse,
} from "./api";
import type { SilkItem } from "./model";
import { ordinalOf } from "./model";
import { BoardCanvas } from "./components/BoardCanvas";
import { ItemList } from "./components/ItemList";

type SaveReport = {
  ok: boolean;
  sourcePath?: string;
  diff?: string[];
  verifications?: ApplyResponse["verifications"];
  unpatched?: ApplyResponse["unpatched"];
  error?: string;
  rolledBack?: boolean;
};

export function App() {
  const [modules, setModules] = useState<string[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [compiled, setCompiled] = useState<CompileResponse | null>(null);
  /** session items — may carry local (unsaved) edits on top of `compiled` */
  const [items, setItems] = useState<SilkItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SaveReport | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  /** two-step save: pending holds the edits awaiting in-app confirmation */
  const [pendingSave, setPendingSave] = useState<ApplyEdit[] | null>(null);

  useEffect(() => {
    fetchModules()
      .then((r) => setModules(r.modules ?? []))
      .catch((e) => setError(String(e)));
  }, []);

  const load = (moduleName: string) => {
    setLoading(true);
    setError(null);
    setSelected(null);
    setReport(null);
    fetchCompile(moduleName)
      .then((r) => {
        if (!r.ok) setError(r.error ?? "compile failed");
        setCompiled(r.ok ? r : null);
        setItems(r.items ?? []);
        setCurrent(moduleName);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  /* ---------------- M3 session mutations (local state only) ------------- */

  const patchItem = (fingerprint: string, patch: Partial<SilkItem>) => {
    setItems((prev) =>
      prev.map((it) =>
        it.fingerprint === fingerprint
          ? {
              ...it,
              ...patch,
              originX: patch.x !== undefined ? (it.originX ?? it.x) : it.originX,
              originY: patch.y !== undefined ? (it.originY ?? it.y) : it.originY,
              originText:
                patch.text !== undefined ? (it.originText ?? it.text) : it.originText,
              dirty: true,
            }
          : it,
      ),
    );
  };

  const onDragEnd = (fingerprint: string, x: number, y: number) => {
    const item = items.find((i) => i.fingerprint === fingerprint);
    if (!item || item.readonly) return;
    if (item.x === x && item.y === y) return; // no-op drag
    patchItem(fingerprint, { x, y });
  };

  const onToggleHidden = (fingerprint: string) => {
    const item = items.find((i) => i.fingerprint === fingerprint);
    if (!item || item.readonly) return;
    patchItem(fingerprint, { hidden: !item.hidden });
  };

  const onTextEdit = (fingerprint: string, text: string) => {
    const item = items.find((i) => i.fingerprint === fingerprint);
    if (!item || item.readonly || item.kind !== "label") return;
    patchItem(fingerprint, { text });
  };

  const resetItem = (fingerprint: string) => {
    const item = items.find((i) => i.fingerprint === fingerprint);
    if (!item) return;
    setItems((prev) =>
      prev.map((it) =>
        it.fingerprint === fingerprint
          ? {
              ...it,
              x: it.originX ?? it.x,
              y: it.originY ?? it.y,
              text: it.originText ?? it.text,
              hidden: false,
              dirty: false,
              originX: undefined,
              originY: undefined,
              originText: undefined,
            }
          : it,
      ),
    );
  };

  const resetAll = () => {
    setItems(
      (prev) =>
        prev
          // ghost items existed only because of an applied (persisted) hide —
          // resetAll drops session edits, but ghosts have no live compiled item;
          // keep them unless their hide was purely local (dirty).
          .map((it) =>
            it.dirty
              ? {
                  ...it,
                  x: it.originX ?? it.x,
                  y: it.originY ?? it.y,
                  text: it.originText ?? it.text,
                  hidden: false,
                  dirty: false,
                  originX: undefined,
                  originY: undefined,
                  originText: undefined,
                }
              : it,
          ),
    );
  };

  /* ---------------- M4 write-back --------------------------------------- */

  const dirtyItems = useMemo(() => items.filter((i) => i.dirty), [items]);

  const buildEdits = (): ApplyEdit[] =>
    dirtyItems.map((item) => {
      const ops: ApplyEdit["ops"] = {};
      // only emit a move when we know the compiled origin and it differs
      // (ghost items — applied hides — carry no origin and must not move)
      if (
        (item.originX !== undefined && item.x !== item.originX) ||
        (item.originY !== undefined && item.y !== item.originY)
      ) {
        ops.x = item.x;
        ops.y = item.y;
      }
      if (item.originText !== undefined && item.text !== item.originText && item.kind === "label")
        ops.text = item.text;
      if (item.hidden) ops.hidden = true;
      return {
        fingerprint: item.fingerprint,
        ordinal: ordinalOf(items, item),
        kind: item.kind,
        ref: item.ref,
        text: item.originText ?? item.text, // locate by COMPILE-TIME text
        x: item.originX ?? item.x, // locate by COMPILE-TIME position
        y: item.originY ?? item.y,
        layer: item.layer,
        ops,
        componentCenter: item.componentCenter,
        componentRotation: item.componentRotation,
      };
    });

  const requestSave = () => {
    if (!current || !compiled || dirtyItems.length === 0) return;
    const edits = buildEdits();
    setPendingSave(edits);
  };

  const saveToSource = async (edits: ApplyEdit[]) => {
    if (!current || !compiled || edits.length === 0) return;
    setPendingSave(null);
    setSaving(true);
    setError(null);
    setReport(null);
    try {
      const r = await applyEdits(current, compiled.entryMtimeMs, edits);
      if (r.ok) {
        // merge fresh compile with session ghosts + unpatched leftovers
        const fresh: SilkItem[] = [...(r.items ?? [])];
        const ghostOf = new Map(items.map((it) => [it.fingerprint, it]));
        for (const v of r.verifications ?? []) {
          if (v.ok && v.newFingerprint) {
            // adopt verified new values (keeps nothing dirty)
            const ghost = ghostOf.get(v.fingerprint);
            const idx = fresh.findIndex((it) => it.fingerprint === v.newFingerprint);
            if (idx >= 0 && ghost) {
              fresh[idx] = { ...fresh[idx], dirty: false };
            }
          }
        }
        // re-apply session state for unpatched edits (nothing was written)
        for (const u of r.unpatched ?? []) {
          const session = ghostOf.get(u.fingerprint);
          const idx = fresh.findIndex((it) => it.fingerprint === u.fingerprint);
          if (idx >= 0 && session) fresh[idx] = session;
        }
        // ghost items for applied hides — keep toggleable for un-hide
        for (const v of r.verifications ?? []) {
          if (v.ok && !v.newFingerprint) {
            const ghost = ghostOf.get(v.fingerprint);
            if (ghost && ghost.hidden) {
              fresh.push({ ...ghost, dirty: false });
            }
          }
        }
        setItems(fresh);
        setCompiled({
          ...compiled,
          items: r.items,
          counts: r.counts,
          board: r.board,
          svg: r.svg,
          entryMtimeMs: r.entryMtimeMs,
          sourcePath: r.sourcePath,
        });
        setReport({
          ok: true,
          sourcePath: r.sourcePath,
          diff: r.diff,
          verifications: r.verifications,
          unpatched: r.unpatched,
        });
      } else {
        if (r.stale) {
          // source changed under us — reload the compile
          load(current);
        }
        setReport({
          ok: false,
          error: r.error,
          rolledBack: r.rolledBack,
          verifications: r.verifications,
          unpatched: r.unpatched,
        });
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>🔧 Bread Modular — Silkscreen Editor</h1>
        <nav className="module-picker">
          {modules.map((m) => (
            <button
              key={m}
              className={`module-btn ${m === current ? "module-btn-active" : ""}`}
              onClick={() => load(m)}
            >
              {m}
            </button>
          ))}
        </nav>
        <div className="status">
          {loading && <span className="spinner">⏳ compiling…</span>}
          {compiled?.counts && (
            <span>
              {compiled.counts.silkscreenTexts} texts · {compiled.counts.refs} refs ·{" "}
              {compiled.counts.labels} labels · board {compiled.board?.width}×
              {compiled.board?.height}mm
            </span>
          )}
        </div>
      </header>

      {error && <div className="error-banner">⚠ {error}</div>}

      {!current && !loading && (
        <div className="placeholder">
          <p>Pick a module to compile its silkscreen (routing-disabled eval).</p>
        </div>
      )}

      <main className="workspace">
        {compiled?.svg && compiled.board && current && (
          <>
            <BoardCanvas
              svg={compiled.svg}
              board={compiled.board}
              items={items}
              selected={selected}
              onSelect={setSelected}
              onDragEnd={onDragEnd}
              onToggleHidden={onToggleHidden}
            />
            <ItemList
              items={items}
              selected={selected}
              onSelect={setSelected}
              onToggleHidden={onToggleHidden}
              onTextEdit={onTextEdit}
              onReset={resetItem}
            />
          </>
        )}
      </main>

      {pendingSave && compiled && (
        <div className="modal-backdrop" onClick={() => setPendingSave(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>💾 Write edits to the module source?</h3>
            <p className="modal-path">
              <code>{compiled.sourcePath ?? `ts-modules/src/${current}/${current}.circuit.tsx`}</code>
            </p>
            <ul className="modal-edits">
              {pendingSave.map((e) => {
                const what = [
                  e.ops.x !== undefined ? `move → (${e.ops.x}, ${e.ops.y}) mm` : null,
                  e.ops.text !== undefined ? `text → "${e.ops.text}"` : null,
                  e.ops.hidden !== undefined ? (e.ops.hidden ? "hide" : "show") : null,
                ]
                  .filter(Boolean)
                  .join(", ");
                return (
                  <li key={e.fingerprint}>
                    {e.kind === "ref" ? `ref ${e.ref}` : `"${e.text}"`}: {what}
                  </li>
                );
              })}
            </ul>
            <p className="modal-note">
              The file is patched in place with ts-morph, then recompiled and
              verified (rolled back on any failure). Afterwards run{" "}
              <code>./build.sh {current}</code> to regenerate gerbers/SVGs.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setPendingSave(null)}>
                Cancel
              </button>
              <button className="save-btn" disabled={saving} onClick={() => saveToSource(pendingSave)}>
                {saving ? "⏳ saving…" : "Write to source"}
              </button>
            </div>
          </div>
        </div>
      )}

      {current && (
        <footer className="savebar">
          <span className="savebar-info">
            {dirtyItems.length > 0 ? (
              <>
                ✳ {dirtyItems.length} unsaved edit{dirtyItems.length > 1 ? "s" : ""}{" "}
                <button className="link-btn" onClick={resetAll}>
                  reset all
                </button>
              </>
            ) : (
              <>no local edits — drag, hide or edit items above</>
            )}
          </span>
          {report?.ok && (
            <span className="savebar-ok">
              ✓ saved to <code>{report.sourcePath}</code> — run{" "}
              <code>./build.sh {current}</code> to regenerate outputs
              {report.unpatched && report.unpatched.length > 0 && (
                <> · {report.unpatched.length} edit(s) could not be patched (see log)</>
              )}
              <button className="link-btn" onClick={() => setReport(null)}>
                dismiss
              </button>
            </span>
          )}
          {report && !report.ok && (
            <span className="savebar-error">
              ✗ {report.rolledBack ? "write-back rejected, source restored — " : ""}
              {report.error}
              <button className="link-btn" onClick={() => setReport(null)}>
                dismiss
              </button>
            </span>
          )}
          <button
            className="save-btn"
            disabled={dirtyItems.length === 0 || saving}
            onClick={requestSave}
            title={
              compiled?.sourcePath
                ? `writes to ${compiled.sourcePath}`
                : "write edits to the module source"
            }
          >
            {saving ? "⏳ saving…" : `💾 Save to source (${dirtyItems.length})`}
          </button>
        </footer>
      )}
    </div>
  );
}
