import { classifyLabel, classifyRef } from "./ownership";
import { buildEntryContext } from "./entry-parse";
import type { EntryContext, FrameLabels } from "./entry-parse";


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
  /** true ⇒ not draggable (frame-owned or otherwise not patchable) */
  readonly: boolean;
  /**
   * Write-back ownership (server/ownership.ts). The UI uses this to decide
   * drag vs ghost:
   *   entry/rv09/ref → draggable (patch engine knows the call site),
   *   frame          → read-only ghost (lib/frame-owned or computed).
   * Absent on inventories built without an entry context (M1 CLI compat).
   */
  owner?: import("./entry-parse").SilkOwner;
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

export type { FrameLabels } from "./entry-parse";

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
 *
 * Thin wrapper over server/entry-parse.ts (kept for M1 CLI compat).
 */
export function extractFrameLabels(entryPath: string): FrameLabels {
  return buildEntryContext(entryPath).frameLabels;
}


/**
 * Items from a compiled circuit json.
 *
 * Ownership (server/ownership.ts) decides draggable vs ghost:
 *   - entry/rv09/ref owners → editable (the patch engine knows the call site)
 *   - frame owner           → readonly ghost (lib/frame-owned or computed)
 *
 * Without an entry context (M1 CLI path) the legacy frame-label heuristic
 * applies and `owner` is left undefined.
 */
export function itemsFromCircuitJson(
  circuitJson: any[],
  frameLabels: FrameLabels,
  entryCtx?: import("./entry-parse").EntryContext,
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

  // Ownership (server/ownership.ts): which items the patch engine can write
  // back. Without an entry context (M1 CLI path) the legacy frame-label
  // heuristic below applies and `owner` stays undefined.
  const ownerOf = (
    kind: "label" | "ref",
    item: { text: string; x: number; y: number },
    refName?: string,
  ): import("./entry-parse").SilkOwner | undefined => {
    if (!entryCtx) return undefined;
    if (kind === "ref") {
      return classifyRef(refName ?? item.text, entryCtx);
    }
    return classifyLabel(item, entryCtx, halfW);
  };

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
    const refName =
      kind === "ref"
        ? (sourceNames.get(pcbToSource.get(e.pcb_component_id) ?? "") ?? text)
        : undefined;

    const owner = ownerOf(kind, { text, x, y }, refName);
    let readonly: boolean;
    if (owner) {
      readonly = owner.kind === "frame";
    } else if (kind === "label") {
      if (fixedTexts.has(text)) {
        readonly = true;
      } else if (
        busTexts.has(text) &&
        halfW > 0 &&
        Math.abs(Math.abs(x) - (halfW - BUS_LABEL_INSET_MM)) < 0.02
      ) {
        readonly = true; // sits exactly on the frame's bus label column
      } else {
        readonly = false;
      }
    } else {
      readonly = false;
    }

    items.push({
      fingerprint: fingerprintOf(kind, text, x, y, e.layer ?? "top"),
      kind,
      ref: refName,
      text,
      x,
      y,
      rotation: e.ccw_rotation ?? 0,
      anchor: e.anchor_alignment ?? "center",
      fontSize: e.font_size ?? 1,
      layer: e.layer === "bottom" ? "bottom" : "top",
      readonly,
      ...(owner ? { owner } : {}),
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
