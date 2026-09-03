import { readFileSync } from "node:fs";
import { Project, type JsxAttribute, type Node } from "ts-morph";


/**
 * Silkscreen view-model + circuit-json filtering (M1/M2).
 *
 * This module is the single adapter for tscircuit circuit-json field access
 * (anchor_position / ccw_rotation / anchor_alignment / font_size), so an
 * upstream field rename only breaks here (plan §8 "API drift").
 *
 * Runs inside the bun compile worker only (imports ts-morph).
 */

/** Circuit-json types kept for the silkscreen-only underlay render (plan §2.2). */
export const SILKSCREEN_KEEP_TYPES: ReadonlySet<string> = new Set([
  "pcb_board",
  "pcb_silkscreen_text",
  "pcb_silkscreen_line",
  "pcb_silkscreen_rect",
  "pcb_silkscreen_circle",
  "pcb_silkscreen_path",
  "pcb_plated_hole",
  "pcb_hole",
]);

export function filterSilkscreenCircuitJson<T extends { type?: string }>(
  circuitJson: T[],
): T[] {
  return circuitJson.filter((e) => SILKSCREEN_KEEP_TYPES.has(e.type ?? ""));
}

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

export type SilkItem = {
  /** stable across recompiles (ids are NOT stable): kind|text|x|y|layer */
  fingerprint: string;
  kind: "label" | "ref";
  /** component designator when kind === "ref" (e.g. "R4") */
  ref?: string;
  text: string;
  /** mm, pcb coords (anchor_position), Y up, board centered at 0,0 */
  x: number;
  y: number;
  /** degrees, CCW */
  rotation: number;
  anchor: AnchorAlignment;
  /** mm */
  fontSize: number;
  layer: "top" | "bottom";
  /** true ⇒ frame-computed position (module-frame / bus labels) — do not drag */
  readonly: boolean;
  /**
   * ref items only: owning pcb_component center (mm) + ccw rotation — needed
   * by the write-back to convert a target board position into the component-
   * local pcbSx silkscreentext offset (text_pos = center + R(rot)·local).
   */
  componentCenter?: { x: number; y: number };
  componentRotation?: number;
  /** editor-side flags; always false in freshly compiled inventory */
  hidden: boolean;
  dirty: boolean;
};

export type SilkBoard = {
  width: number;
  height: number;
  center: { x: number; y: number };
};

/**
 * Content fingerprint (plan §3.2): (kind, text, x@3dp, y@3dp, layer).
 * Plain string, deterministic on both server and frontend — no crypto needed.
 */
export function fingerprintOf(
  kind: string,
  text: string,
  x: number,
  y: number,
  layer: string,
): string {
  return `${kind}|${text}|${x.toFixed(3)}|${y.toFixed(3)}|${layer}`;
}

/* ------------------------------------------------------------------ */
/* Frame-computed label detection (plan §5.3)                          */
/* ------------------------------------------------------------------ */

export type FrameLabels = {
  name?: string;
  version?: string;
  inputLabels: string[];
  outputLabels: string[];
};

/**
 * module-frame's bus pin labels sit exactly at x = ±(halfW − BUS_LABEL_INSET)
 * (lib/module-frame.tsx). Used to tell a bus label like "CV1" (frame-computed)
 * from a same-named module-authored caption (e.g. the RV09Pot "CV1" caption).
 */
export const BUS_LABEL_INSET_MM = 7.2;

/**
 * Parse the <BreadModule …> call site of the module entry with ts-morph to
 * learn which label strings the frame owns (name/version/INPUT/OUTPUT/BREAD/
 * MODULAR + inputLabels/outputLabels literals).
 */
export function extractFrameLabels(entryPath: string): FrameLabels {
  const project = new Project({ useInMemoryFileSystem: true });
  const source = project.createSourceFile(
    "module.circuit.tsx",
    readFileSync(entryPath, "utf8"),
  );

  const out: FrameLabels = { inputLabels: [], outputLabels: [] };

  // NOTE: ts-morph's getDescendantsOfKind("JsxOpeningElement") returns nothing
  // in this environment (kind-query quirk) — filter getDescendants() instead.
  // Opening elements cover both <BreadModule …/> and <BreadModule …>…</…>.
  const openingElements = source
    .getDescendants()
    .filter(
      (n) =>
        n.getKindName() === "JsxOpeningElement" ||
        n.getKindName() === "JsxSelfClosingElement",
    ) as any[];

  const literalText = (expr: Node | undefined): string | undefined => {
    if (expr?.getKindName() === "StringLiteral") {
      return (expr as any).getLiteralText() as string;
    }
    return undefined;
  };
  const literalArray = (expr: Node | undefined): string[] => {
    if (expr?.getKindName() !== "ArrayLiteralExpression") return [];
    return (expr as any)
      .getElements()
      .map(literalText)
      .filter((s: string | undefined): s is string => typeof s === "string");
  };
  // {["MIDI", …]} wraps the array in a JsxExpression — unwrap it.
  const unwrap = (expr: Node | undefined): Node | undefined => {
    if (expr?.getKindName() === "JsxExpression") {
      return (expr as any).getExpression() as Node | undefined;
    }
    return expr;
  };

  for (const el of openingElements) {
    const tagName = el.getTagNameNode().getText().split(".").pop();
    if (tagName !== "BreadModule") continue;

    for (const attr of el.getAttributes() as JsxAttribute[]) {
      // NOTE: ts-morph's JsxAttribute has getNameNode() — NOT getName().
      const attrName = attr.getNameNode?.().getText();
      if (typeof attrName !== "string") continue; // e.g. spread attribute
      const value = unwrap(attr.getInitializer());
      if (!value) continue;
      if (attrName === "name") out.name = literalText(value);
      else if (attrName === "version") out.version = literalText(value);
      else if (attrName === "inputLabels") out.inputLabels = literalArray(value);
      else if (attrName === "outputLabels")
        out.outputLabels = literalArray(value);
    }
    break; // first <BreadModule> call site is the module frame
  }
  return out;
}


/**
 * Items from a compiled circuit json. `frameLabels` marks frame-computed
 * labels readonly; bus labels additionally require the bus column position
 * so a module-authored caption with the same string stays editable.
 */
export function itemsFromCircuitJson(
  circuitJson: any[],
  frameLabels: FrameLabels,
): SilkItem[] {
  const board = circuitJson.find((e) => e?.type === "pcb_board") as
    | { width?: number }
    | undefined;
  const halfW = (board?.width ?? 0) / 2;

  // pcb_component → source_component.name for ref designators (plan §3.1)
  const pcbToSource = new Map<string, string | undefined>();
  const sourceNames = new Map<string, string>();
  for (const e of circuitJson) {
    if (e?.type === "pcb_component")
      pcbToSource.set(e.pcb_component_id, e.source_component_id);
    else if (e?.type === "source_component")
      sourceNames.set(e.source_component_id, e.name);
  }

  const fixedTexts = new Set(
    [
      "INPUT",
      "OUTPUT",
      "BREAD",
      "MODULAR",
      frameLabels.name,
      frameLabels.version,
    ].filter((s): s is string => typeof s === "string"),
  );
  const busTexts = new Set(
    [...frameLabels.inputLabels, ...frameLabels.outputLabels].filter(
      (s): s is string => typeof s === "string",
    ),
  );

  const items: SilkItem[] = [];
  // pcb_component center/rotation for ref write-back math (plan §5.2)
  const pcbComponents = new Map<
    string,
    { center?: { x: number; y: number }; rotation?: number }
  >();
  for (const e of circuitJson) {
    if (e?.type === "pcb_component")
      pcbComponents.set(e.pcb_component_id, {
        center: e.center,
        rotation: e.rotation,
      });
  }
  for (const e of circuitJson) {
    if (e?.type !== "pcb_silkscreen_text") continue;
    const x = e.anchor_position?.x ?? 0;
    const y = e.anchor_position?.y ?? 0;
    const text = String(e.text ?? "");
    const kind: "label" | "ref" = e.pcb_component_id ? "ref" : "label";
    const owning = e.pcb_component_id
      ? pcbComponents.get(e.pcb_component_id)
      : undefined;

    let readonly = false;
    if (kind === "label") {
      if (fixedTexts.has(text)) {
        readonly = true;
      } else if (
        busTexts.has(text) &&
        halfW > 0 &&
        Math.abs(Math.abs(x) - (halfW - BUS_LABEL_INSET_MM)) < 0.02
      ) {
        readonly = true; // sits exactly on the frame's bus label column
      }
    }

    items.push({
      fingerprint: fingerprintOf(kind, text, x, y, e.layer ?? "top"),
      kind,
      ref:
        kind === "ref"
          ? (sourceNames.get(pcbToSource.get(e.pcb_component_id) ?? "") ??
            text)
          : undefined,
      text,
      x,
      y,
      rotation: e.ccw_rotation ?? 0,
      anchor: e.anchor_alignment ?? "center",
      fontSize: e.font_size ?? 1,
      layer: e.layer === "bottom" ? "bottom" : "top",
      readonly,
      ...(kind === "ref" && owning?.center
        ? {
            componentCenter: {
              x: owning.center.x,
              y: owning.center.y,
            },
            componentRotation: owning.rotation ?? 0,
          }
        : {}),
      hidden: false,
      dirty: false,
    });
  }
  return items;
}
