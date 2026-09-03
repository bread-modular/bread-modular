import { useEffect, useMemo, useRef, useState } from "react";
import type { SilkItem } from "../model";
import { snapMm } from "../model";
import { deriveMetrics, makeMapper, type Mapper } from "../transform";

type Props = {
  svg: string;
  board: { width: number; height: number; center: { x: number; y: number } };
  items: SilkItem[];
  selected: string | null;
  onSelect(fingerprint: string | null): void;
  /** commit a drag: final board-mm position (already snapped) */
  onDragEnd(fingerprint: string, x: number, y: number): void;
  /** hide/show toggle from the canvas affordance */
  onToggleHidden(fingerprint: string): void;
};

type DragState = {
  fingerprint: string;
  /** pointer position when the drag started (CSS px) */
  startPx: number;
  startPy: number;
  /** item position when the drag started (mm) */
  originX: number;
  originY: number;
  /** live position (mm) */
  curX: number;
  curY: number;
  moved: boolean;
};

/**
 * Board canvas (M2 viewer + M3 interactions): the silkscreen-only underlay SVG
 * plus an interactive handle overlay positioned via the deterministic mm⇄px
 * mapper. The underlay is never re-rendered during a drag — handles move in
 * the sibling overlay and the drag ghost shows the live dx/dy readout.
 *
 * Readonly (frame-computed) items get no drag/hide/edit affordances at all.
 */
export function BoardCanvas({
  svg,
  board,
  items,
  selected,
  onSelect,
  onDragEnd,
  onToggleHidden,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [renderedWidth, setRenderedWidth] = useState(0);
  const [drag, setDrag] = useState<DragState | null>(null);

  // Inject the underlay once per compile; give it a viewBox so it scales with
  // its container while keeping its intrinsic aspect ratio.
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    wrap.innerHTML = svg;
    const el = wrap.querySelector("svg");
    if (el) {
      const w = Number(el.getAttribute("width") ?? 800);
      const h = Number(el.getAttribute("height") ?? 600);
      el.setAttribute("viewBox", `0 0 ${w} ${h}`);
      el.removeAttribute("width");
      el.removeAttribute("height");
      el.style.width = "100%";
      el.style.height = "auto";
      el.style.display = "block";
    }
  }, [svg]);

  // Track rendered width for the px mapper.
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const update = () => setRenderedWidth(wrap.clientWidth);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  const mapper: Mapper | null = useMemo(() => {
    if (renderedWidth <= 0 || !board.width) return null;
    return makeMapper(deriveMetrics(svg, board), renderedWidth);
  }, [svg, board, renderedWidth]);

  // live item positions: dragged item follows the pointer
  const dragItem = drag ? items.find((i) => i.fingerprint === drag.fingerprint) : null;

  const beginDrag = (item: SilkItem, e: React.PointerEvent) => {
    if (item.readonly || !mapper) return;
    e.stopPropagation();
    onSelect(item.fingerprint);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    setDrag({
      fingerprint: item.fingerprint,
      startPx: e.clientX,
      startPy: e.clientY,
      originX: item.x,
      originY: item.y,
      curX: item.x,
      curY: item.y,
      moved: false,
    });
  };

  const moveDrag = (e: React.PointerEvent) => {
    if (!drag || !mapper) return;
    const dxPx = e.clientX - drag.startPx;
    const dyPx = e.clientY - drag.startPy;
    // px delta → mm delta (Y flip): move by delta in board mm, snapped
    const dxMm = dxPx / mapper.pxPerMm;
    const dyMm = -dyPx / mapper.pxPerMm;
    const curX = snapMm(drag.originX + dxMm);
    const curY = snapMm(drag.originY + dyMm);
    const moved =
      drag.moved || Math.abs(curX - drag.originX) > 1e-6 || Math.abs(curY - drag.originY) > 1e-6;
    setDrag({ ...drag, curX, curY, moved });
  };

  const endDrag = (e: React.PointerEvent) => {
    if (!drag) return;
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* pointer already released */
    }
    if (drag.moved) {
      onDragEnd(drag.fingerprint, snapMm(drag.curX), snapMm(drag.curY));
    }
    setDrag(null);
  };

  // Arrow-key nudging for the selected item (plan §4): 0.1 mm steps,
  // Shift = 0.5 mm. Ignored while typing in inputs.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selected) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const step = e.shiftKey ? 0.5 : 0.1;
      const delta =
        e.key === "ArrowUp"
          ? [0, step]
          : e.key === "ArrowDown"
            ? [0, -step]
            : e.key === "ArrowLeft"
              ? [-step, 0]
              : e.key === "ArrowRight"
                ? [step, 0]
                : null;
      if (!delta) return;
      e.preventDefault();
      const item = items.find((i) => i.fingerprint === selected);
      if (!item || item.readonly) return;
      onDragEnd(item.fingerprint, snapMm(item.x + delta[0]), snapMm(item.y + delta[1]));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, items, onDragEnd]);

  return (
    <div className="board-canvas">
      <div className="underlay-wrap" ref={wrapRef} onClick={() => onSelect(null)} />
      {mapper && (
        <div
          className="overlay"
          style={{ width: renderedWidth, height: (wrapRef.current?.clientHeight ?? 0) }}
        >
          {items.map((item, i) => {
            const isDragging = drag?.fingerprint === item.fingerprint;
            const px = isDragging ? mapper.mmToPx(drag!.curX, drag!.curY) : mapper.mmToPx(item.x, item.y);
            const isSel = selected === item.fingerprint;
            const cls = [
              "handle",
              item.kind === "ref" ? "handle-ref" : "handle-label",
              item.readonly ? "handle-readonly" : "",
              isSel ? "handle-selected" : "",
              item.hidden ? "handle-hidden" : "",
              item.dirty ? "handle-dirty" : "",
              isDragging ? "handle-dragging" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <button
                key={`${i}:${item.fingerprint}`}
                className={cls}
                style={{
                  left: px.px,
                  top: px.py,
                  transform: `translate(-50%, -50%) rotate(${item.rotation > 0 ? `-${item.rotation}deg` : "0deg"})`,
                }}
                title={
                  item.readonly
                    ? `${item.text} — position computed by module-frame (readonly)`
                    : item.hidden
                      ? `${item.text} — hidden (eye to show)`
                      : item.text
                }
                onPointerDown={(e) => beginDrag(item, e)}
                onPointerMove={moveDrag}
                onPointerUp={endDrag}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!drag?.moved) onSelect(item.fingerprint);
                }}
              >
                {item.readonly ? "🔒" : item.dirty ? "✳" : item.hidden ? "🚫" : "◆"}
                {isSel && !item.readonly && (
                  <span
                    className="handle-eye"
                    role="button"
                    title={item.hidden ? "Show on board" : "Hide from board"}
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleHidden(item.fingerprint);
                    }}
                  >
                    {item.hidden ? "👁" : "🚫"}
                  </span>
                )}
                {isDragging && drag!.moved && (
                  <span className="drag-readout">
                    Δ {(drag!.curX - drag!.originX >= 0 ? "+" : "") + (drag!.curX - drag!.originX).toFixed(2)},{" "}
                    {(drag!.curY - drag!.originY >= 0 ? "+" : "") + (drag!.curY - drag!.originY).toFixed(2)} mm
                  </span>
                )}
              </button>
            );
          })}
          {dragItem && drag?.moved && (
            <div className="drag-hint">
              {dragItem.text}: ({drag!.curX.toFixed(3)}, {drag!.curY.toFixed(3)}) mm — release to drop
            </div>
          )}
        </div>
      )}
    </div>
  );
}
