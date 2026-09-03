import { useEffect, useState } from "react";
import type { SilkItem } from "../model";
import { snapMm } from "../model";

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
  onToggleHidden(): void;
  onReset(): void;
};

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/**
 * Floating control panel for the selected silkscreen item: position X/Y in
 * mm plus a visible/hidden toggle.
 *
 * Deliberately minimal (move + show/hide only): text edits, rotation, anchor
 * and font size live in the module source / lib and are out of scope for
 * this editor — every field shown here round-trips through the write-back.
 * For readonly (lib/frame-owned) items the panel renders read-only info.
 */
export function ItemPanel({
  item,
  px,
  py,
  overlayW,
  overlayH,
  onClose,
  onMove,
  onToggleHidden,
  onReset,
}: Props) {
  const [x, setX] = useState<number | "">(item.x);
  const [y, setY] = useState<number | "">(item.y);

  useEffect(() => {
    setX(item.x);
    setY(item.y);
  }, [item.x, item.y, item.fingerprint]);

  const commitPos = () => {
    if (x === "" || y === "") return; // half-typed input — keep last position
    const nx = Number(x);
    const ny = Number(y);
    if (!Number.isFinite(nx) || !Number.isFinite(ny)) return;
    if (snapMm(nx) !== item.x || snapMm(ny) !== item.y) onMove(snapMm(nx), snapMm(ny));
  };

  // keep the panel on-canvas: prefer right of the handle, flip if cramped
  const PANEL_W = 218;
  const PANEL_H = 220;
  const left = clamp(px + 14, 4, Math.max(4, overlayW - PANEL_W - 4));
  const top = clamp(py - 20, 4, Math.max(4, overlayH - PANEL_H - 4));

  const ownerLabel =
    item.owner?.kind === "rv09"
      ? `pot ${item.owner.pot} ${item.owner.slot}`
      : (item.owner?.kind ?? (item.kind === "ref" ? "ref" : "label"));

  return (
    <div
      className="item-panel"
      data-testid="silk-item-panel"
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
          🔒 lib/frame-owned — not editable here
        </p>
      ) : (
        <>
          <div className="item-panel-grid">
            <label className="item-panel-row">
              <span>x mm</span>
              <input
                className="panel-input"
                data-testid="silk-panel-x"
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
                data-testid="silk-panel-y"
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
          </div>
        </>
      )}

      <div className="item-panel-foot">
        <button
          className={`btn-secondary panel-vis-btn ${item.hidden ? "panel-vis-hidden" : ""}`}
          data-testid="silk-panel-visibility"
          disabled={item.readonly}
          onClick={onToggleHidden}
          title={item.readonly ? "frame-owned item" : item.hidden ? "show on board" : "hide from board"}
        >
          {item.hidden ? "🚫 hidden" : "👁 visible"}
        </button>
        <span className="item-panel-meta">
          {item.layer} · {ownerLabel}
        </span>
      </div>
    </div>
  );
}
