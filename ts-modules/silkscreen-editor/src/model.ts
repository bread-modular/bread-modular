/**
 * Editor data model — the SilkItem shape shared with the server adapter
 * (server/silkscreen.ts is the source of truth; keep the fingerprint rule in
 * sync: kind|text|x@3dp|y@3dp|layer).
 */

export type AnchorAlignment =
  | "center"
  | "top_left"
  | "top_center"
  | "top_right"
  | "bottom_left"
  | "bottom_center"
  | "bottom_right"
  | "center_left"
  | "center_right";

export type SilkOwner =
  | { kind: "entry" }
  | { kind: "rv09"; pot: string; slot: "label" | "designator" | "value" }
  | { kind: "ref"; comp: string }
  | { kind: "frame" };

export type SilkItem = {
  fingerprint: string;
  kind: "label" | "ref";
  ref?: string;
  text: string;
  x: number;
  y: number;
  rotation: number;
  anchor: AnchorAlignment;
  fontSize: number;
  layer: "top" | "bottom";
  readonly: boolean;
  /**
   * Write-back ownership from the server inventory. entry/rv09/ref items are
   * draggable (the patch engine knows the call site); frame items render as
   * read-only ghosts. Absent on old payloads — treat as draggable iff
   * !readonly (legacy heuristic).
   */
  owner?: SilkOwner;
  /**
   * ref items only: owning component geometry — echoed back on /api/apply so
   * the server can convert a target board position into the component-local
   * pcbSx silkscreentext offset (text_pos = center + R(rot)·local).
   */
  componentCenter?: { x: number; y: number };
  componentRotation?: number;
  /** editor-side flags; always false in freshly compiled inventory */
  hidden: boolean;
  dirty: boolean;
  /** session-only: compiled position before local edits (for diff display) */
  originX?: number;
  originY?: number;
  /** session-only: compiled visibility before local edits (ghosts = true) */
  originHidden?: boolean;
};

export function fingerprintOf(
  kind: string,
  text: string,
  x: number,
  y: number,
  layer: string,
): string {
  return `${kind}|${text}|${x.toFixed(3)}|${y.toFixed(3)}|${layer}`;
}

export function groupItems(items: SilkItem[]): {
  labels: SilkItem[];
  refs: SilkItem[];
} {
  const labels: SilkItem[] = [];
  const refs: SilkItem[] = [];
  for (const item of items) (item.kind === "ref" ? refs : labels).push(item);
  return { labels, refs };
}

/** stable, collision-free key for React lists */
export function itemKey(item: SilkItem, ordinal: number): string {
  return `${ordinal}:${item.fingerprint}`;
}

/**
 * Ordinal of an item within its fingerprint collision group (plan §3.2) —
 * sent with each edit so the server can disambiguate identical candidates by
 * document order, the same rule it uses to locate them.
 */
export function ordinalOf(items: SilkItem[], item: SilkItem): number {
  let ordinal = 0;
  for (const it of items) {
    if (it === item) return ordinal;
    if (it.fingerprint === item.fingerprint) ordinal++;
  }
  return 0;
}

/** snap a mm coordinate to the 0.05 mm editor grid (plan §4) */
export const SNAP_MM = 0.05;
export function snapMm(v: number): number {
  // re-round to 3dp — 0.05-grid math accumulates float noise (e.g. -8.200000000000001)
  return Math.round(Math.round(v / SNAP_MM) * SNAP_MM * 1000) / 1000;
}

/** the 9-point anchor alignment enum (tscircuit silkscreentext prop) */
export const ANCHOR_OPTIONS: AnchorAlignment[] = [
  "top_left",
  "top_center",
  "top_right",
  "center_left",
  "center",
  "center_right",
  "bottom_left",
  "bottom_center",
  "bottom_right",
];

/** drag/move delta vs the compiled position, snapped */
export function movedTo(item: SilkItem, x: number, y: number): { x: number; y: number } {
  return { x: snapMm(x), y: snapMm(y) };
}
