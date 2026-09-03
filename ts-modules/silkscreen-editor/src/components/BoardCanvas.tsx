import { useEffect, useMemo, useRef, useState } from "react";
import type { SilkItem } from "../model";
import { snapMm } from "../model";
import { deriveMetrics, makeMapper, type Mapper } from "../transform";
import { ItemPanel } from "./ItemPanel";

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
  /** reset local edits for one item */
  onReset(fingerprint: string): void;
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
 * Board canvas: the silkscreen-only underlay SVG plus an interactive handle
 * overlay positioned via the deterministic mm⇄px mapper. The underlay is
 * never re-rendered during a drag — handles move in the sibling overlay and
 * the drag ghost shows the live dx/dy readout.
 *
 * Geometry contract (the overlay-alignment fix): the `.overlay` div covers
 * exactly the rendered `<svg>` element's border box — same origin, same
 * size — and handle positions are computed as
 *   mmToPx(item) − svgRect.origin
 * so every handle lands on the silkscreen ink it owns, at any container
 * width. Readonly (frame/lib-owned) items render as ghosts with no
 * drag/hide/edit affordances at all.
 */
export function BoardCanvas({
  svg,
  board,
  items,
  selected,
  onSelect,
  onDragEnd,
  onToggleHidden,
  onReset,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgBoxRef = useRef<{ x: number; y: number; w: number; h: number }>({
    x: 0,
    y: 0,
    w: 0,
    h: 0,
  });
  const [svgBox, setSvgBox] = useState({ x: 0, y: 0, w: 0, h: 0 });
  const [drag, setDrag] = useState<DragState | null>(null);

  // Inject the underlay once per compile; give it a viewBox so it scales with
  // its container while keeping its intrinsic aspect ratio. The svg element
  // fills the wrap exactly (width 100%, height auto), so the wrap's border
  // box IS the svg's border box.
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    wrap.innerHTML = svg;
    const el = wrap.querySelector("svg");
    if (el) {
      const w = Number(el.getAttribute("width") ?? 800);
      const h = Number(el.getAttribute("height") ?? 600);
      el.setAttribute("viewBox", `0 0 ${w} ${h}`);
      el.setAttribute("preserveAspectRatio", "xMidYMid meet");
      el.removeAttribute("width");
      el.removeAttribute("height");
      el.style.width = "100%";
      el.style.height = "auto";
      el.style.display = "block";
    }
  }, [svg]);

  // Track the RENDERED svg box (origin + size, CSS px, relative to the
  // relatively-positioned .board-canvas). The svg fills the wrap, so the
  // wrap's rect is the svg's rect — measured in one place, no drift.
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const update = () => {
      const canvas = wrap.parentElement;
      const cRect = canvas?.getBoundingClientRect();
      const r = wrap.getBoundingClientRect();
      const box = {
        x: r.left - (cRect?.left ?? 0),
        y: r.top - (cRect?.top ?? 0),
        w: r.width,
        h: r.height,
      };
      svgBoxRef.current = box;
      setSvgBox(box);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(wrap);
    if (wrap.parentElement) ro.observe(wrap.parentElement);
    window.addEventListener("resize", update);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [svg]);

  const mapper: Mapper | null = useMemo(() => {
    if (svgBox.w <= 0 || !board.width) return null;
    return makeMapper(deriveMetrics(svg, board), svgBox.w);
  }, [svg, board, svgBox.w]);

  // live item positions: dragged item follows the pointer
  const dragItem = drag ? items.find((i) => i.fingerprint === drag.fingerprint) : null;
  const selectedItem = selected ? (items.find((i) => i.fingerprint === selected) ?? null) : null;

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
      {mapper && svgBox.w > 0 && (
        <div
          className="overlay"
          data-testid="silk-overlay"
          style={{
            left: svgBox.x,
            top: svgBox.y,
            width: svgBox.w,
            height: svgBox.h,
          }}
        >
          {items.map((item, i) => {
            const isDragging = drag?.fingerprint === item.fingerprint;
            const abs = isDragging
              ? mapper.mmToPx(drag!.curX, drag!.curY)
              : mapper.mmToPx(item.x, item.y);
            // mmToPx is svg-element-relative and the overlay's origin is the
            // svg element's origin (the overlay covers the svg box exactly),
            // so no offset conversion is needed here.
            const px = { px: abs.px, py: abs.py };
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
                data-testid={`silk-handle-${item.text}`}
                data-fingerprint={item.fingerprint}
                data-x={item.x}
                data-y={item.y}
                style={{
                  left: px.px,
                  top: px.py,
                  transform: `translate(-50%, -50%) rotate(${item.rotation > 0 ? `-${item.rotation}deg` : "0deg"})`,
                }}
                title={
                  item.readonly
                    ? `${item.text} — lib/frame-owned (read-only ghost)`
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
          {selectedItem && mapper && !drag && (
            <ItemPanel
              item={selectedItem}
              px={mapper.mmToPx(selectedItem.x, selectedItem.y).px}
              py={mapper.mmToPx(selectedItem.x, selectedItem.y).py}
              overlayW={svgBox.w}
              overlayH={svgBox.h}
              onClose={() => onSelect(null)}
              onMove={(x, y) => onDragEnd(selectedItem.fingerprint, x, y)}
              onToggleHidden={() => onToggleHidden(selectedItem.fingerprint)}
              onReset={() => onReset(selectedItem.fingerprint)}
            />
          )}
        </div>
      )}
    </div>
  );
}
