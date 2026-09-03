/**
 * Ownership classification — which compiled silkscreen items the editor can
 * write back, and where.
 *
 *   entry  → a literal <silkscreentext> in the module entry (movable as
 *             pcbX/pcbY; hide/show via pcbStyle)
 *   rv09   → an RV09Pot caption/designator/value owned by an <RV09Pot>
 *             call site in the module entry (caption moves via labelDx/
 *             labelDy; hide via hideLabel/hideDesignator/hideValue)
 *   ref    → a ref designator owned by a name="…" component in the entry
 *             (moves via pcbSx, hide/show via pcbStyle)
 *   frame  → lib/frame-owned (module-frame bus labels, RV09 internals when
 *             the pot is NOT in the entry, …) — read-only ghost
 *
 * Slot matching for pot internals uses the known RV09Pot internal offsets
 * (lib/rv09-pot.tsx — keep in sync):
 *   designator  (name)       (pcbX − 0.254, pcbY + 1.27)
 *   value       (resistance) (pcbX − 0.127, pcbY − 0.381)
 *   caption     (label)      (pcbX − 0.026 + labelDx, pcbY − 8.8 + labelDy)
 */

import type { EntryContext, FrameLabels, SilkOwner } from "./entry-parse";
import { BUS_LABEL_INSET_MM } from "./silkscreen";

const RV09_OFFSETS = {
  designator: { dx: -0.254, dy: 1.27 },
  value: { dx: -0.127, dy: -0.381 },
  label: { dx: -0.026, dy: -8.8 },
} as const;

/** mm tolerance — eval float noise (e.g. 6.603999999999999 vs 6.604). */
export const POS_TOL = 0.03;

function near(a: number, b: number, tol = POS_TOL): boolean {
  return Math.abs(a - b) < tol;
}

/** fixed frame texts: INPUT/OUTPUT/BREAD/MODULAR + module name/version. */
export function isFixedFrameText(
  text: string,
  frameLabels: FrameLabels,
): boolean {
  if (
    text === "INPUT" ||
    text === "OUTPUT" ||
    text === "BREAD" ||
    text === "MODULAR"
  ) {
    return true;
  }
  if (frameLabels.name !== undefined && text === frameLabels.name) return true;
  if (frameLabels.version !== undefined && text === frameLabels.version) {
    return true;
  }
  return false;
}

/** bus strings (inputLabels/outputLabels) sitting on the frame label column. */
export function isBusColumnLabel(
  text: string,
  x: number,
  boardHalfW: number,
  frameLabels: FrameLabels,
): boolean {
  if (boardHalfW <= 0) return false;
  const bus = new Set(
    [...frameLabels.inputLabels, ...frameLabels.outputLabels].filter(
      (s): s is string => typeof s === "string",
    ),
  );
  if (!bus.has(text)) return false;
  return Math.abs(Math.abs(x) - (boardHalfW - BUS_LABEL_INSET_MM)) < 0.02;
}

export function classifyLabel(
  item: { text: string; x: number; y: number },
  ctx: EntryContext,
  boardHalfW: number,
): SilkOwner {
  if (isFixedFrameText(item.text, ctx.frameLabels)) return { kind: "frame" };

  // RV09Pot internals — match by exact predicted position first, so a
  // caption like "CV1" wins over a same-named bus label or entry text.
  for (const pot of ctx.rv09) {
    if (pot.pcbX === undefined || pot.pcbY === undefined) continue;
    if (
      pot.label !== undefined &&
      item.text === pot.label &&
      near(item.x, pot.pcbX + RV09_OFFSETS.label.dx + pot.labelDx) &&
      near(item.y, pot.pcbY + RV09_OFFSETS.label.dy + pot.labelDy)
    ) {
      return { kind: "rv09", pot: pot.name, slot: "label" };
    }
    if (
      item.text === pot.name &&
      near(item.x, pot.pcbX + RV09_OFFSETS.designator.dx) &&
      near(item.y, pot.pcbY + RV09_OFFSETS.designator.dy)
    ) {
      return { kind: "rv09", pot: pot.name, slot: "designator" };
    }
    if (
      pot.resistance !== undefined &&
      item.text === pot.resistance &&
      near(item.x, pot.pcbX + RV09_OFFSETS.value.dx) &&
      near(item.y, pot.pcbY + RV09_OFFSETS.value.dy)
    ) {
      return { kind: "rv09", pot: pot.name, slot: "value" };
    }
  }

  // Direct entry <silkscreentext> — match by text, then by position when the
  // entry node carries literal pcbX/pcbY.
  const byText = ctx.silkTexts.filter((s) => s.text === item.text);
  if (byText.length === 1 && byText[0].x === undefined) {
    return { kind: "entry" };
  }
  for (const s of byText) {
    if (
      s.x !== undefined &&
      s.y !== undefined &&
      near(s.x, item.x) &&
      near(s.y, item.y)
    ) {
      return { kind: "entry" };
    }
  }

  // Frame bus-label column (e.g. 8bit's "CV1" bus labels).
  if (isBusColumnLabel(item.text, item.x, boardHalfW, ctx.frameLabels)) {
    return { kind: "frame" };
  }

  // Same-named entry text exists elsewhere but this instance is a lib
  // duplicate (e.g. drive's "AUDIO"/bus strings, RV09 captions whose pot is
  // computed) — ghost it rather than offer an unsavable drag.
  return { kind: "frame" };
}

/** ref owners: only entry-declared name="…" components are patchable. */
export function classifyRef(
  refName: string,
  ctx: EntryContext,
): SilkOwner {
  if (ctx.namedComponents.has(refName)) {
    return { kind: "ref", comp: refName };
  }
  return { kind: "frame" };
}
