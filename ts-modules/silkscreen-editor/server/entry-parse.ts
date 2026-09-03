/**
 * Entry-source parsing for the silkscreen editor.
 *
 * The editor can only write back edits whose owning JSX lives in the module's
 * own `.circuit.tsx` entry file. Anything owned by `lib/` (module-frame bus
 * labels, RV09Pot internals) or computed in code must be classified so the UI
 * can show it as a read-only ghost instead of offering a drag that silently
 * fails to save.
 *
 * Runs inside the bun compile worker (inventory) AND in the vite process
 * (write-back, via server/patch.ts) — both import ts-morph, so the readers
 * live here and are shared.
 *
 * Two entry points:
 *   buildEntryContext(entryPath)            — read the file, then parse
 *   parseEntryContext(entryPath, sourceText) — parse in-memory source
 * (patch.ts MUST use the in-memory variant: it classifies the not-yet-saved
 * patched source, never the stale bytes on disk.)
 */

import { readFileSync } from "node:fs";
import { Project, type JsxAttribute, type Node } from "ts-morph";

/* ------------------------------------------------------------------ */
/* public types                                                        */
/* ------------------------------------------------------------------ */

/** Who owns a silkscreen item's source position (write-back dispatch). */
export type SilkOwner =
  | { kind: "entry" }
  | { kind: "rv09"; pot: string; slot: "label" | "designator" | "value" }
  | { kind: "ref"; comp: string }
  | { kind: "frame" };

export type FrameLabels = {
  name?: string;
  version?: string;
  inputLabels: string[];
  outputLabels: string[];
};

export type Rv09CallSite = {
  name: string;
  resistance?: string;
  label?: string;
  /** pot origin in board mm — undefined when pcbX/pcbY are computed/absent */
  pcbX?: number;
  pcbY?: number;
  /** editor-written caption offset (defaults 0,0 when the props are absent) */
  labelDx: number;
  labelDy: number;
  /** true when the offset props exist but are computed (not patchable) */
  labelDxComputed: boolean;
  labelDyComputed: boolean;
};

export type EntrySilkText = {
  text: string;
  x?: number;
  y?: number;
};

export type EntryContext = {
  frameLabels: FrameLabels;
  /** <RV09Pot …/> call sites in the module entry (pot captions are movable) */
  rv09: Rv09CallSite[];
  /** direct <silkscreentext …/> nodes in the module entry */
  silkTexts: EntrySilkText[];
  /** every literal name="…" in the entry (locatable ref-designator owners) */
  namedComponents: Set<string>;
};

/* ------------------------------------------------------------------ */
/* ts-morph readers (mirror server/patch.ts literal semantics)         */
/* ------------------------------------------------------------------ */

function elementsOf(
  source: import("ts-morph").SourceFile,
): Node[] {
  // NOTE: getDescendantsOfKind("JsxOpeningElement") returns nothing in this
  // environment (kind-query quirk) — filter getDescendants() instead.
  return source
    .getDescendants()
    .filter(
      (n) =>
        n.getKindName() === "JsxOpeningElement" ||
        n.getKindName() === "JsxSelfClosingElement",
    );
}

function tagName(el: Node): string {
  return (el as any).getTagNameNode().getText().split(".").pop() as string;
}

function jsxAttr(el: Node, name: string): JsxAttribute | undefined {
  return (el as any)
    .getAttributes()
    .filter((a: Node) => a.getKindName() === "JsxAttribute")
    .find((a: JsxAttribute) => a.getNameNode?.().getText() === name);
}

/** unwrap pcbX={…} / pcbX="…" → the inner expression (or string literal). */
function unwrapInitializer(
  initializer: Node | undefined,
): Node | undefined {
  if (!initializer) return undefined;
  if (initializer.getKindName() === "JsxExpression") {
    return (initializer as any).getExpression() as Node | undefined;
  }
  return initializer;
}

function numericValue(initializer: Node | undefined): number | undefined {
  const inner = unwrapInitializer(initializer);
  if (!inner) return undefined;
  if (inner.getKindName() === "NumericLiteral") {
    const v = Number(inner.getText());
    return Number.isFinite(v) ? v : undefined;
  }
  if (inner.getKindName() === "StringLiteral") {
    const t = (inner as any).getLiteralText() as string;
    if (/^-?\d+(\.\d+)?$/.test(t.trim())) return Number(t);
    return undefined;
  }
  // PrefixUnaryExpression (-9.525) etc. — computed for our purposes here
  // (callers that need negatives use patch.ts's fuller reader).
  if (inner.getKindName() === "PrefixUnaryExpression") {
    const v = Number(inner.getText().replace(/\s+/g, ""));
    return Number.isFinite(v) ? v : undefined;
  }
  return undefined;
}

function stringValue(initializer: Node | undefined): string | undefined {
  const inner = unwrapInitializer(initializer);
  if (!inner) return undefined;
  if (inner.getKindName() === "StringLiteral") {
    return (inner as any).getLiteralText() as string;
  }
  return undefined;
}

/** unwrap {[…]} JsxExpression wrappers around array literals. */
function unwrapJsxExpr(node: Node | undefined): Node | undefined {
  if (node?.getKindName() === "JsxExpression") {
    return (node as any).getExpression() as Node | undefined;
  }
  return node;
}

/* ------------------------------------------------------------------ */
/* frame labels (moved here from server/silkscreen.ts — same logic)    */
/* ------------------------------------------------------------------ */

export function extractFrameLabelsFrom(
  elements: Node[],
): FrameLabels {
  const out: FrameLabels = { inputLabels: [], outputLabels: [] };

  const literalText = (expr: Node | undefined): string | undefined =>
    stringValue(expr as any);

  const literalArray = (expr: Node | undefined): string[] => {
    const inner = unwrapJsxExpr(expr);
    if (inner?.getKindName() !== "ArrayLiteralExpression") return [];
    return (inner as any)
      .getElements()
      .map(literalText)
      .filter((s: string | undefined): s is string => typeof s === "string");
  };

  for (const el of elements) {
    if (tagName(el) !== "BreadModule") continue;
    for (const a of (el as any).getAttributes() as JsxAttribute[]) {
      const attrName = a.getNameNode?.().getText();
      if (typeof attrName !== "string") continue;
      const value = unwrapJsxExpr(a.getInitializer() as Node | undefined);
      if (!value) continue;
      if (attrName === "name") out.name = literalText(value);
      else if (attrName === "version") out.version = literalText(value);
      else if (attrName === "inputLabels")
        out.inputLabels = literalArray(a.getInitializer() as Node);
      else if (attrName === "outputLabels")
        out.outputLabels = literalArray(a.getInitializer() as Node);
    }
    break; // first <BreadModule> call site is the module frame
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* entry points                                                        */
/* ------------------------------------------------------------------ */

export function parseEntryContext(
  entryPath: string,
  sourceText: string,
): EntryContext {
  const project = new Project({ useInMemoryFileSystem: true });
  const source = project.createSourceFile(entryPath, sourceText);
  const elements = elementsOf(source);

  const frameLabels = extractFrameLabelsFrom(elements);

  const rv09: Rv09CallSite[] = [];
  const silkTexts: EntrySilkText[] = [];
  const namedComponents = new Set<string>();

  for (const el of elements) {
    const tag = tagName(el);

    const nameAttr = jsxAttr(el, "name");
    const nameLit = nameAttr
      ? stringValue(nameAttr.getInitializer() as Node)
      : undefined;
    if (nameLit) namedComponents.add(nameLit);

    if (tag === "RV09Pot") {
      if (!nameLit) continue; // cannot address an unnamed pot — skip
      const dxAttr = jsxAttr(el, "labelDx");
      const dyAttr = jsxAttr(el, "labelDy");
      rv09.push({
        name: nameLit,
        resistance: stringValue(
          jsxAttr(el, "resistance")?.getInitializer() as Node,
        ),
        label: stringValue(jsxAttr(el, "label")?.getInitializer() as Node),
        pcbX: numericValue(jsxAttr(el, "pcbX")?.getInitializer() as Node),
        pcbY: numericValue(jsxAttr(el, "pcbY")?.getInitializer() as Node),
        labelDx: numericValue(dxAttr?.getInitializer() as Node) ?? 0,
        labelDy: numericValue(dyAttr?.getInitializer() as Node) ?? 0,
        labelDxComputed:
          !!dxAttr &&
          numericValue(dxAttr?.getInitializer() as Node) === undefined,
        labelDyComputed:
          !!dyAttr &&
          numericValue(dyAttr?.getInitializer() as Node) === undefined,
      });
    } else if (tag === "silkscreentext") {
      const text = stringValue(
        jsxAttr(el, "text")?.getInitializer() as Node,
      );
      if (text === undefined) continue; // computed text — not patchable
      silkTexts.push({
        text,
        x: numericValue(jsxAttr(el, "pcbX")?.getInitializer() as Node),
        y: numericValue(jsxAttr(el, "pcbY")?.getInitializer() as Node),
      });
    }
  }

  return { frameLabels, rv09, silkTexts, namedComponents };
}

export function buildEntryContext(entryPath: string): EntryContext {
  return parseEntryContext(entryPath, readFileSync(entryPath, "utf8"));
}
