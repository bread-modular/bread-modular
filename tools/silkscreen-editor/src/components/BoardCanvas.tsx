import { useEffect, useMemo, useRef, useState } from "react";
import type { SilkItem } from "../model";
import { deriveMetrics, makeMapper, type Mapper } from "../transform";

type Props = {
  svg: string;
  board: { width: number; height: number; center: { x: number; y: number } };
  items: SilkItem[];
  selected: string | null;
  onSelect(fingerprint: string | null): void;
};

/**
 * Board canvas (M2): the silkscreen-only underlay SVG + a read-only overlay of
 * item handles positioned via the deterministic mm⇄px mapper. The underlay is
 * never re-rendered per interaction; handles live in a sibling overlay div.
 */
export function BoardCanvas({ svg, board, items, selected, onSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [renderedWidth, setRenderedWidth] = useState(0);

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

  return (
    <div className="board-canvas">
      <div className="underlay-wrap" ref={wrapRef} onClick={() => onSelect(null)} />
      {mapper && (
        <div
          className="overlay"
          style={{ width: renderedWidth, height: (wrapRef.current?.clientHeight ?? 0) }}
        >
          {items.map((item, i) => {
            const { px, py } = mapper.mmToPx(item.x, item.y);
            const isSel = selected === item.fingerprint;
            return (
              <button
                key={`${i}:${item.fingerprint}`}
                className={[
                  "handle",
                  item.kind === "ref" ? "handle-ref" : "handle-label",
                  item.readonly ? "handle-readonly" : "",
                  isSel ? "handle-selected" : "",
                  item.hidden ? "handle-hidden" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={{
                  left: px,
                  top: py,
                  transform: `translate(-50%, -50%) rotate(${item.rotation > 0 ? `-${item.rotation}deg` : "0deg"})`,
                }}
                title={
                  item.readonly
                    ? `${item.text} — position computed by module-frame (readonly)`
                    : item.text
                }
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(item.fingerprint);
                }}
              >
                {item.readonly ? "🔒" : "◆"}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
