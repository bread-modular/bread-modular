/**
 * mm ⇄ px transforms for the silkscreen viewer (plan §3.3).
 *
 * circuit-to-svg renders the PCB onto a fixed-size canvas (default 800×600,
 * no viewBox) at a uniform scale with Y flipped. The `<rect class="pcb-boundary">`
 * marks the board outline, so everything derives deterministically from that
 * rect + the board's mm size:
 *
 *   unitsPerMm = boundary.w / board.width          (svg units per mm)
 *   svgX = boundary.x + (mmX + boardW/2) * unitsPerMm
 *   svgY = boundary.y + (boardH/2 − mmY) * unitsPerMm   (Y flip)
 *
 * Display scale maps svg units → CSS px: displayScale = renderedWidth / canvasW.
 * Rotation stays in pcb convention (CCW+); negate when drawing in screen space.
 */

export type BoardSize = { width: number; height: number };

export type SvgMetrics = {
  canvasW: number;
  canvasH: number;
  boundary: { x: number; y: number; w: number; h: number };
  unitsPerMm: number;
  board: BoardSize;
};

export type Mapper = {
  metrics: SvgMetrics;
  /** css px per mm */
  pxPerMm: number;
  mmToPx(x: number, y: number): { px: number; py: number };
  pxToMm(px: number, py: number): { x: number; y: number };
};

/** svg root dimensions — circuit-to-svg defaults to 800×600. */
export function parseSvgCanvasSize(svg: string): { w: number; h: number } {
  const root = svg.match(/<svg[^>]*>/i)?.[0] ?? "";
  const w = Number(root.match(/\swidth="([\d.]+)"/)?.[1] ?? 800);
  const h = Number(root.match(/\sheight="([\d.]+)"/)?.[1] ?? 600);
  return { w, h };
}

/** The pcb-boundary rect (board outline) in svg units. */
export function parseBoundaryRect(svg: string): {
  x: number;
  y: number;
  w: number;
  h: number;
} | null {
  const rect = svg.match(/<rect[^>]*class="pcb-boundary"[^>]*>/i)?.[0] ?? "";
  if (!rect) return null;
  const attr = (name: string) =>
    Number(rect.match(new RegExp(`\\s${name}="(-?[\\d.]+)"`))?.[1] ?? NaN);
  const x = attr("x");
  const y = attr("y");
  const w = attr("width");
  const h = attr("height");
  if ([x, y, w, h].some((n) => !Number.isFinite(n))) return null;
  return { x, y, w, h };
}

export function deriveMetrics(svg: string, board: BoardSize): SvgMetrics {
  const { w: canvasW, h: canvasH } = parseSvgCanvasSize(svg);
  const boundary =
    parseBoundaryRect(svg) ?? { x: 0, y: 0, w: canvasW, h: canvasH };
  const unitsPerMm =
    board.width > 0 && boundary.w > 0 ? boundary.w / board.width : 1;
  return { canvasW, canvasH, boundary, unitsPerMm, board };
}

/**
 * Build a mm⇄px mapper for a specific rendered width (the canvas element's
 * client width). The underlay svg must be displayed with its intrinsic aspect
 * ratio (viewBox 0 0 canvasW canvasH, width 100%, height auto).
 */
export function makeMapper(metrics: SvgMetrics, renderedWidth: number): Mapper {
  const scale = metrics.canvasW > 0 ? renderedWidth / metrics.canvasW : 1;
  const { boundary, unitsPerMm, board } = metrics;
  return {
    metrics,
    pxPerMm: unitsPerMm * scale,
    mmToPx(x: number, y: number) {
      return {
        px: (boundary.x + (x + board.width / 2) * unitsPerMm) * scale,
        py: (boundary.y + (board.height / 2 - y) * unitsPerMm) * scale,
      };
    },
    pxToMm(px: number, py: number) {
      const ux = px / scale - boundary.x;
      const uy = py / scale - boundary.y;
      return {
        x: ux / unitsPerMm - board.width / 2,
        y: board.height / 2 - uy / unitsPerMm,
      };
    },
  };
}
