import { useEffect, useState } from "react";
import type { SilkItem } from "../model";
import { ANCHOR_OPTIONS, snapMm } from "../model";

type Props = {
  item: SilkItem;
  /** px position of the item's handle on the overlay (panel is offset from it) */
  px: number;
  py: number;
  /** overlay size, for clamping the panel inside the canvas */
  overlayW: number;
  overlayH: number;
  onClose(): void;
  /** commit a new board-mm position (same path as dragging) */
  onMove(x: number, y: number): void;
  onEditProp(patch: Partial<Pick<SilkItem, "rotation" | "anchor" | "fontSize">>): void;
  onToggleHidden(): void;
  onTextEdit(text: string): void;
  onReset(): void;
};

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/**
 * Floating control panel for the selected silkscreen item (task M3): position
 * X/Y in mm, rotation, 9-point anchor, fontSize, a visible/hidden toggle and
 * an editable text string (labels — a ref's text is its netlist identity).
 *
 * Position fields commit on Enter/blur; style fields commit on change. For
 * readonly (frame-computed) items the panel renders read-only information.
 */
export function ItemPanel({
  item,
  px,
  py,
  overlayW,
  overlayH,
  onClose,
  onMove,
  onEditProp,
  onToggleHidden,
  onTextEdit,
  onReset,
}: Props) {
  const [x, setX] = useState<number | "">(item.x);
  const [y, setY] = useState<number | "">(item.y);
  const [text, setText] = useState(item.text);

  useEffect(() => {
    setX(item.x);
    setY(item.y);
  }, [item.x, item.y, item.fingerprint]);
  useEffect(() => setText(item.text), [item.text, item.fingerprint]);

  const commitPos = () => {
    if (x === "" || y === "") return; // half-typed input — keep last position
    const nx = Number(x);
    const ny = Number(y);
    if (!Number.isFinite(nx) || !Number.isFinite(ny)) return;
    if (snapMm(nx) !== item.x || snapMm(ny) !== item.y) onMove(snapMm(nx), snapMm(ny));
  };

  // keep the panel on-canvas: prefer right of the handle, flip if cramped
  const PANEL_W = 218;
  const PANEL_H = 330;
  const left = clamp(px + 14, 4, Math.max(4, overlayW - PANEL_W - 4));
  const top = clamp(py - 20, 4, Math.max(4, overlayH - PANEL_H - 4));

  return (
    <div
      className="item-panel"
      style={{ left, top }}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="item-panel-head">
        <span className="item-panel-title">
          {item.kind === "ref" ? `ref ${item.ref ?? item.text}` : item.text}
          {item.dirty && <span className="dirty-star"> ✳</span>}
        </span>
        <span className="item-panel-head-actions">
          {item.dirty && (
            <button className="icon-btn" title="reset local edits for this item" onClick={onReset}>
              ↺
            </button>
          )}
          <button className="icon-btn" title="close panel" onClick={onClose}>
            ✕
          </button>
        </span>
      </div>

      {item.readonly ? (
        <p className="item-panel-note">
          🔒 position computed by module-frame — not editable
        </p>
      ) : (
        <>
          <label className="item-panel-row">
            <span>text</span>
            {item.kind === "label" ? (
              <input
                className="panel-input"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
                onBlur={() => {
                  const t = text.trim();
                  if (t && t !== item.text) onTextEdit(t);
                  else setText(item.text);
                }}
              />
            ) : (
              <input className="panel-input" value={item.text} disabled title="a ref designator is its netlist identity — rename not supported" />
            )}
          </label>

          <div className="item-panel-grid">
            <label className="item-panel-row">
              <span>x mm</span>
              <input
                className="panel-input"
                type="number"
                step={0.1}
                value={x}
                onChange={(e) => setX(e.target.value === "" ? "" : Number(e.target.value))}
                onBlur={commitPos}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
              />
            </label>
            <label className="item-panel-row">
              <span>y mm</span>
              <input
                className="panel-input"
                type="number"
                step={0.1}
                value={y}
                onChange={(e) => setY(e.target.value === "" ? "" : Number(e.target.value))}
                onBlur={commitPos}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
              />
            </label>
            <label className="item-panel-row">
              <span>rotation °</span>
              <input
                className="panel-input"
                type="number"
                step={15}
                value={item.rotation}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (Number.isFinite(v)) onEditProp({ rotation: v });
                }}
              />
            </label>
            <label className="item-panel-row">
              <span>font mm</span>
              <input
                className="panel-input"
                type="number"
                step={0.1}
                min={0.2}
                value={item.fontSize}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (Number.isFinite(v) && v > 0) onEditProp({ fontSize: v });
                }}
              />
            </label>
          </div>

          <label className="item-panel-row">
            <span>anchor</span>
            <select
              className="panel-input"
              value={item.anchor}
              onChange={(e) => onEditProp({ anchor: e.target.value as SilkItem["anchor"] })}
            >
              {ANCHOR_OPTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
        </>
      )}

      <div className="item-panel-foot">
        <button
          className={`btn-secondary panel-vis-btn ${item.hidden ? "panel-vis-hidden" : ""}`}
          disabled={item.readonly}
          onClick={onToggleHidden}
          title={item.readonly ? "frame-owned item" : item.hidden ? "show on board" : "hide from board"}
        >
          {item.hidden ? "🚫 hidden" : "👁 visible"}
        </button>
        <span className="item-panel-meta">
          {item.layer} · {item.kind}
        </span>
      </div>
    </div>
  );
}
