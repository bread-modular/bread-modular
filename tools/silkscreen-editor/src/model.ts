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
  | "middle_left"
  | "middle_right";

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
  hidden: boolean;
  dirty: boolean;
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
