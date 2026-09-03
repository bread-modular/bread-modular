/**
 * M4 write-back engine — patches a module's .circuit.tsx with ts-morph so the
 * silkscreen edits survive the next `build.sh` run (plan §5).
 *
 * Edit → source mapping (all runtime-verified against the pinned tscircuit):
 *
 *   custom <silkscreentext> move   set pcbX/pcbY numeric literals
 *   custom <silkscreentext> text   set the text attribute literal
 *   custom <silkscreentext> style  set pcbRotation / anchorAlignment /
 *                                  fontSize literals (runtime-verified props)
 *   hide (label or ref)            add/merge pcbStyle={{ silkscreenTextVisibility: "hidden" }}
 *   show (label or ref)            remove the silkscreenTextVisibility property
 *                                  (and the pcbStyle attr entirely if it empties)
 *   ref designator move            merge pcbSx={{ "& silkscreentext": { pcbX, pcbY } }}
 *                                  on the owning component.
 *   RV09Pot caption move           set labelDx/labelDy on the <RV09Pot>
 *                                  call site (offset from the pot-relative
 *                                  base anchor — never pcbX/pcbY, which stay
 *                                  derived from the pot position)
 *   RV09Pot hide (any slot)        set hideLabel / hideDesignator / hideValue
 *                                  on the <RV09Pot> call site
 *   RV09Pot show                   remove the hide prop again
 *
 * Owner dispatch: the client echoes the inventory's `owner` claim
 * (server/ownership.ts). `frame` claims are refused outright (ghosts);
 * `rv09` claims patch the pot call site; `entry`/`ref`/absent claims use
 * the legacy location-by-content path.
 *
 *   NOTE on ref positions: tscircuit's pcbStyle.silkscreenTextPosition
 *   {offsetX, offsetY} exists in the props schema but has NO runtime consumer
 *   (verified empirically — it renders exactly like the baseline), so refs are
 *   repositioned with pcbSx instead. pcbSx silkscreentext pcbX/pcbY are
 *   COMPONENT-LOCAL: text_pos = componentCenter + R(componentRotation)·local,
 *   so a target board position is converted with local = R(−θ)·(target−center).
 *
 * Safety rules:
 *   - Only literal-initialized attributes are rewritten. A computed value
 *     (identifier / call / calc string) ⇒ the edit is refused as "computed".
 *   - Node location is by content fingerprint (text + rounded pcbX/pcbY +
 *     document-order ordinal within the collision group) — never global regex
 *     replace. No confident match ⇒ the edit is reported unpatched.
 *   - Only the located spans are rewritten; all other formatting, comments and
 *     props are preserved by ts-morph's targeted manipulation.
 */

import {
  type JsxAttribute,
  type Node,
  type ObjectLiteralElementLike,
  type ObjectLiteralExpression,
  IndentationText,
  Project,
  ScriptKind,
  ts,
} from "ts-morph";
import { parseEntryContext } from "./entry-parse";
import type { SilkOwner } from "./entry-parse";

/* ------------------------------------------------------------------ */
/* public types                                                        */
/* ------------------------------------------------------------------ */

export type SilkEditOp = {
  /** new absolute board position (mm) — omit to keep */
  x?: number;
  y?: number;
  /** new text string (custom labels only — ref renames are refused) */
  text?: string;
  /** true ⇒ hide, false ⇒ show */
  hidden?: boolean;
  /** new CCW rotation in degrees (custom labels only) */
  rotation?: number;
  /** new 9-point anchor alignment (custom labels only) */
  anchor?: string;
  /** new font size in mm (custom labels only) */
  fontSize?: number;
};

export type SilkEdit = {
  /** compile-time fingerprint of the item being edited */
  fingerprint: string;
  /** ordinal of the item within its fingerprint collision group */
  ordinal: number;
  kind: "label" | "ref";
  ref?: string;
  /** compile-time text (used to locate the node) */
  text: string;
  /** compile-time position (used to locate the node) */
  x: number;
  y: number;
  layer: string;
  ops: SilkEditOp;
  /** ref items: owning component geometry (echoed from the inventory) */
  componentCenter?: { x: number; y: number };
  componentRotation?: number;
  /**
   * Write-back ownership the client received with the inventory item
   * (server/ownership.ts). When the client echoes it back, the patch engine
   * dispatches directly to the owning call site instead of guessing:
   *   entry/rv09/ref → patch that call site,
   *   frame          → refuse (ghost — lib/frame-owned or computed).
   * Absent on old clients — falls back to legacy location by content.
   */
  owner?: SilkOwner;
};

export type EditOutcome = {
  fingerprint: string;
  ok: boolean;
  /** expected post-edit item values (for verification against a recompile) */
  expect?: {
    kind: "label" | "ref";
    text: string;
    ref?: string;
    x?: number;
    y?: number;
    hidden?: boolean;
    rotation?: number;
    anchor?: string;
    fontSize?: number;
    layer: string;
  };
  reason?: string;
  /** what changed, for the UI/save log */
  change?: string;
};

export type ApplyEditsResult = {
  ok: boolean;
  error?: string;
  outcomes: EditOutcome[];
  /** full patched source (caller decides whether to write it to disk) */
  newSource?: string;
  /** unified-ish line diff old → new (context-free) */
  diff?: string[];
};

/* ------------------------------------------------------------------ */
/* small helpers                                                       */
/* ------------------------------------------------------------------ */

const PCBSX_SELECTOR = "& silkscreentext";
const VISIBILITY_PROP = "silkscreenTextVisibility";
const round3 = (n: number) => Math.round(n * 1000) / 1000;
const fmtNum = (n: number) => String(round3(n));

/** R(−θ) applied to (dx, dy) — inverse of the pcbSx local→board transform. */
export function boardDeltaToLocal(
  target: { x: number; y: number },
  center: { x: number; y: number },
  rotationDeg: number,
): { x: number; y: number } {
  const theta = ((rotationDeg ?? 0) * Math.PI) / 180;
  const c = Math.cos(theta);
  const s = Math.sin(theta);
  const dx = target.x - center.x;
  const dy = target.y - center.y;
  return { x: dx * c + dy * s, y: -dx * s + dy * c };
}

function isJsxElementNode(n: Node): boolean {
  const k = n.getKindName();
  return k === "JsxOpeningElement" || k === "JsxSelfClosingElement";
}

function tagName(el: Node): string {
  return (el as any).getTagNameNode().getText().split(".").pop() as string;
}

function attrs(el: Node): JsxAttribute[] {
  return (el as any).getAttributes().filter((a: Node) => a.getKindName() === "JsxAttribute");
}

function attr(el: Node, name: string): JsxAttribute | undefined {
  return attrs(el).find((a) => a.getNameNode().getText() === name);
}

/** unwrap pcbX={123} / pcbX={-9.525} → number; also accepts numeric strings. */
function numericLiteralValue(initializer: Node | undefined): number | undefined {
  if (!initializer) return undefined;
  let inner = initializer;
  if (inner.getKindName() === "JsxExpression") {
    inner = (inner as any).getExpression();
    if (!inner) return undefined;
  }
  if (inner.getKindName() === "PrefixUnaryExpression") {
    // negative literal: -9.525 ⇒ MinusToken + NumericLiteral
    // (ts-morph's getOperatorToken() returns the SyntaxKind NUMBER here)
    const op = Number((inner as any).getOperatorToken());
    const operand = (inner as any).getOperand() as Node | undefined;
    if (op === ts.SyntaxKind.MinusToken && operand?.getKindName() === "NumericLiteral") {
      const v = Number(operand.getText());
      return Number.isFinite(v) ? -v : undefined;
    }
    return undefined;
  }
  if (inner.getKindName() === "NumericLiteral") {
    const v = Number(inner.getText());
    return Number.isFinite(v) ? v : undefined;
  }
  if (inner.getKindName() === "StringLiteral") {
    // plain numeric strings like "5" are patchable; calc strings are not
    const t = (inner as any).getLiteralText() as string;
    if (/^-?\d+(\.\d+)?$/.test(t.trim())) return Number(t);
    return undefined;
  }
  return undefined;
}

function stringLiteralValue(initializer: Node | undefined): string | undefined {
  if (!initializer) return undefined;
  let inner = initializer;
  if (inner.getKindName() === "JsxExpression") {
    inner = (inner as any).getExpression();
    if (!inner) return undefined;
  }
  if (inner.getKindName() === "StringLiteral") {
    return (inner as any).getLiteralText() as string;
  }
  return undefined;
}

/** set an existing numeric attribute to a new literal, or add the attribute. */
function setNumericAttr(el: Node, name: string, value: number): void {
  const a = attr(el, name);
  if (a) {
    a.setInitializer(`{${fmtNum(value)}}`);
  } else {
    (el as any).addAttribute({ name, initializer: `{${fmtNum(value)}}` });
  }
}

function setStringAttr(el: Node, name: string, value: string): void {
  const esc = value.includes('"') ? JSON.stringify(value) : `"${value}"`;
  const a = attr(el, name);
  if (a) {
    a.setInitializer(esc);
  } else {
    (el as any).addAttribute({ name, initializer: esc });
  }
}

/** object-literal initializer of a JSX attribute, or undefined. */
function objectLiteralOf(a: JsxAttribute | undefined): ObjectLiteralExpression | undefined {
  const init = a?.getInitializer();
  if (!init) return undefined;
  if (init.getKindName() === "JsxExpression") {
    const inner = (init as any).getExpression() as Node | undefined;
    if (inner?.getKindName() === "ObjectLiteralExpression") return inner as ObjectLiteralExpression;
    return undefined;
  }
  return undefined;
}

/** name text of an object-literal property with quotes stripped. */
function propName(prop: Node): string | undefined {
  if (prop.getKindName() !== "PropertyAssignment") return undefined;
  const nameNode = (prop as any).getNameNode() as Node;
  const t = nameNode.getText();
  return t.replace(/^["'`]|["'`]$/g, "");
}

function numericPropOf(obj: ObjectLiteralExpression, name: string): number | undefined {
  const prop = obj.getProperty(name);
  if (!prop) return undefined;
  return numericLiteralValue((prop as any).getInitializer());
}

function setNumericProp(obj: ObjectLiteralExpression, name: string, value: number): void {
  const prop = obj.getProperty(name);
  if (prop && prop.getKindName() === "PropertyAssignment") {
    (prop as any).setInitializer(fmtNum(value));
  } else if (prop) {
    throw new Error(`pcbSx.${name} is computed (not a literal) — refusing to patch`);
  } else {
    obj.addProperty(`${name}: ${fmtNum(value)}`);
  }
}

/**
 * Merge `pcbStyle={{ [VISIBILITY_PROP]: "hidden" }}` into the element —
 * creating the attribute if absent, keeping any sibling style keys.
 */
function hideViaPcbStyle(el: Node): string {
  const a = attr(el, "pcbStyle");
  if (!a) {
    (el as any).addAttribute({
      name: "pcbStyle",
      initializer: `{{ ${VISIBILITY_PROP}: "hidden" }}`,
    });
    return "added pcbStyle={{ silkscreenTextVisibility: \"hidden\" }}";
  }
  const obj = objectLiteralOf(a);
  if (!obj) {
    throw new Error("pcbStyle is computed (not an object literal) — refusing to patch");
  }
  const prop = obj.getProperty(VISIBILITY_PROP);
  if (prop && prop.getKindName() === "PropertyAssignment") {
    (prop as any).setInitializer('"hidden"');
    return "set pcbStyle.silkscreenTextVisibility = \"hidden\"";
  }
  if (prop) {
    throw new Error("pcbStyle.silkscreenTextVisibility is computed — refusing to patch");
  }
  obj.addProperty(`${VISIBILITY_PROP}: "hidden"`);
  return "added pcbStyle.silkscreenTextVisibility = \"hidden\"";
}

/** restore visibility: drop the visibility prop; drop pcbStyle if it empties. */
function showViaPcbStyle(el: Node): string {
  const a = attr(el, "pcbStyle");
  if (!a) return "already visible (no pcbStyle attr) — no change";
  const obj = objectLiteralOf(a);
  if (!obj) {
    throw new Error("pcbStyle is computed (not an object literal) — refusing to patch");
  }
  const prop = obj.getProperty(VISIBILITY_PROP);
  if (!prop) return "already visible (pcbStyle has no visibility prop) — no change";
  prop.remove();
  if (obj.getProperties().length === 0) {
    a.remove();
    return "removed visibility prop and the now-empty pcbStyle attr";
  }
  return "removed pcbStyle.silkscreenTextVisibility";
}

/* ------------------------------------------------------------------ */
/* node location                                                       */
/* ------------------------------------------------------------------ */

type SourceNodes = { elements: Node[] };

function collectElements(source: import("ts-morph").SourceFile): SourceNodes {
  // NOTE: getDescendantsOfKind("JsxOpeningElement") returns nothing in this
  // environment (same quirk as server/silkscreen.ts) — filter getDescendants().
  const elements = source.getDescendants().filter(isJsxElementNode);
  return { elements };
}

function locateLabelNode(
  nodes: SourceNodes,
  edit: SilkEdit,
): { node: Node } | { error: string } {
  const byText = nodes.elements.filter(
    (el) => tagName(el) === "silkscreentext" && stringLiteralValue(attr(el, "text")?.getInitializer()) === edit.text,
  );
  if (byText.length === 0) {
    return {
      error: `no <silkscreentext text="${edit.text}"> literal in the module source (frame/lib-owned or computed label) — cannot patch`,
    };
  }
  // prefer literal pcbX/pcbY matches, then fall back to document-order ordinal
  let candidates = byText.filter((el) => {
    const px = numericLiteralValue(attr(el, "pcbX")?.getInitializer());
    const py = numericLiteralValue(attr(el, "pcbY")?.getInitializer());
    return (
      px !== undefined &&
      py !== undefined &&
      Math.abs(px - edit.x) < 5e-4 &&
      Math.abs(py - edit.y) < 5e-4
    );
  });
  if (candidates.length === 0) candidates = byText;
  if (candidates.length === 1) return { node: candidates[0] };
  const idx = edit.ordinal;
  if (idx < candidates.length) return { node: candidates[idx] };
  return {
    error: `ambiguous <silkscreentext text="${edit.text}"> (ordinal ${idx} of ${candidates.length}) — refusing to guess`,
  };
}

function locateComponentNode(
  nodes: SourceNodes,
  edit: SilkEdit,
): { node: Node } | { error: string } {
  const byName = nodes.elements.filter(
    (el) => stringLiteralValue(attr(el, "name")?.getInitializer()) === edit.ref,
  );
  if (byName.length === 0) {
    return {
      error: `no JSX element with name="${edit.ref}" in the module source — cannot patch its ref designator`,
    };
  }
  if (byName.length > 1) {
    return {
      error: `ambiguous elements with name="${edit.ref}" (${byName.length}) — refusing to guess`,
    };
  }
  return { node: byName[0] };
}

/** locate an <RV09Pot name="…"> call site in the module entry. */
function locateRv09Node(
  nodes: SourceNodes,
  pot: string,
): { node: Node } | { error: string } {
  const byName = nodes.elements.filter(
    (el) =>
      tagName(el) === "RV09Pot" &&
      stringLiteralValue(attr(el, "name")?.getInitializer()) === pot,
  );
  if (byName.length === 0) {
    return {
      error: `no <RV09Pot name="${pot}"> in the module source — cannot patch its labels`,
    };
  }
  if (byName.length > 1) {
    return {
      error: `ambiguous <RV09Pot name="${pot}"> (${byName.length}) — refusing to guess`,
    };
  }
  return { node: byName[0] };
}

/** set an optional numeric prop (labelDx/labelDy): add or overwrite literal. */
function setOptionalNumericProp(
  el: Node,
  name: string,
  value: number,
): void {
  const a = attr(el, name);
  if (a) {
    const lit = numericLiteralValue(a.getInitializer());
    if (lit === undefined) {
      throw new Error(
        `${name} is computed (not a numeric literal) — refusing to patch`,
      );
    }
    a.setInitializer(`{${fmtNum(value)}}`);
  } else {
    (el as any).addAttribute({ name, initializer: `{${fmtNum(value)}}` });
  }
}

/** set an optional boolean prop (hideLabel/…): add or overwrite literal. */
function setOptionalBooleanProp(
  el: Node,
  name: string,
  value: boolean,
): void {
  const a = attr(el, name);
  if (a) {
    a.setInitializer(`{${value ? "true" : "false"}}`);
  } else {
    (el as any).addAttribute({
      name,
      initializer: `{${value ? "true" : "false"}}`,
    });
  }
}

/* RV09 hide prop per slot: label → hideLabel, designator → hideDesignator,
   value → hideValue. */
const RV09_HIDE_PROP = {
  label: "hideLabel",
  designator: "hideDesignator",
  value: "hideValue",
} as const;

/* ------------------------------------------------------------------ */
/* per-edit application                                                */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/* per-edit application                                                */
/* ------------------------------------------------------------------ */

/**
 * Apply a move/hide edit to an <RV09Pot name="…"> call site:
 *   move caption  → labelDx/labelDy (delta from the compiled position)
 *   hide/show     → hideLabel / hideDesignator / hideValue booleans
 * The recompile verification in server/api.ts is the safety net: a stale
 * owner claim (pot renamed/removed since compile) fails location below or
 * fails verification, and the whole batch rolls back.
 */
function applyRv09Edit(
  nodes: SourceNodes,
  entryCtx: import("./entry-parse").EntryContext,
  edit: SilkEdit,
  rv09: { pot: string; slot: "label" | "designator" | "value" },
  base: EditOutcome,
  expect: NonNullable<EditOutcome["expect"]>,
): EditOutcome {
  const located = locateRv09Node(nodes, rv09.pot);
  if ("error" in located) return { ...base, reason: located.error, expect };
  const el = located.node;
  const potSite = entryCtx.rv09.find((p) => p.name === rv09.pot);

  const changes: string[] = [];
  try {
    if (edit.ops.x !== undefined || edit.ops.y !== undefined) {
      // slot === "label" is enforced by the caller.
      const targetX = edit.ops.x ?? edit.x;
      const targetY = edit.ops.y ?? edit.y;
      if (potSite?.pcbX === undefined || potSite?.pcbY === undefined) {
        return {
          ...base,
          reason: `<RV09Pot name="${rv09.pot}"> has a computed pcbX/pcbY — position owned by code, refusing to patch`,
          expect,
        };
      }
      if (potSite.labelDxComputed || potSite.labelDyComputed) {
        return {
          ...base,
          reason: `labelDx/labelDy on <RV09Pot name="${rv09.pot}"> are computed (not literals) — refusing to patch`,
          expect,
        };
      }
      // caption anchor = (pcbX − 0.026 + labelDx, pcbY − 8.8 + labelDy), so
      // the new offset is the target minus the pot-relative base anchor.
      const dx = targetX - (potSite.pcbX - 0.026);
      const dy = targetY - (potSite.pcbY - 8.8);
      setOptionalNumericProp(el, "labelDx", dx);
      setOptionalNumericProp(el, "labelDy", dy);
      changes.push(
        `caption offset → (labelDx ${fmtNum(dx)}, labelDy ${fmtNum(dy)})`,
      );
    }
    if (edit.ops.hidden === true) {
      setOptionalBooleanProp(el, RV09_HIDE_PROP[rv09.slot], true);
      changes.push(`added ${RV09_HIDE_PROP[rv09.slot]}={true}`);
    } else if (edit.ops.hidden === false) {
      const a = attr(el, RV09_HIDE_PROP[rv09.slot]);
      if (a) {
        a.remove();
        changes.push(`removed ${RV09_HIDE_PROP[rv09.slot]}`);
      } else {
        return { ...base, reason: "already visible — no change", expect };
      }
    }
  } catch (err: any) {
    return { ...base, reason: err?.message ?? String(err), expect };
  }
  return {
    fingerprint: edit.fingerprint,
    ok: changes.length > 0,
    expect,
    reason: changes.length === 0 ? "no-op edit" : undefined,
    change: changes.join("; "),
  };
}

function applyEditToNodes(
  nodes: SourceNodes,
  edit: SilkEdit,
  entryCtx: import("./entry-parse").EntryContext,
): EditOutcome {
  const base: EditOutcome = { fingerprint: edit.fingerprint, ok: false };
  const expect = {
    kind: edit.kind,
    text: edit.ops.text ?? edit.text,
    ref: edit.ref,
    x: edit.ops.x,
    y: edit.ops.y,
    hidden: edit.ops.hidden,
    rotation: edit.ops.rotation,
    anchor: edit.ops.anchor,
    fontSize: edit.ops.fontSize,
    layer: edit.layer,
  };

  // --- owner dispatch --------------------------------------------------
  // The inventory told the client who owns this item (server/ownership.ts);
  // the client echoes it back. Dispatch on the CLAIMED owner (the live call
  // site is located below — a stale claim fails location, and the recompile
  // verification in server/api.ts rolls the batch back on any mismatch).
  const claimed = edit.owner?.kind;
  if (claimed === "frame") {
    return {
      ...base,
      reason:
        "item is lib/frame-owned (read-only ghost) — move it in lib/ or the frame, not here",
      expect,
    };
  }

  if (edit.kind === "ref" && edit.ops.text !== undefined && edit.ops.text !== edit.text) {
    return { ...base, reason: "renaming a ref designator changes netlist identity — not supported (M5)" };
  }
  if (
    edit.kind === "ref" &&
    (edit.ops.rotation !== undefined ||
      edit.ops.anchor !== undefined ||
      edit.ops.fontSize !== undefined)
  ) {
    return {
      ...base,
      reason:
        "ref designators support move + hide only — rotation/anchor/fontSize of an auto ref are owned by the component/frame, not patchable",
      expect,
    };
  }
  // rv09 internals support move (caption only) + hide; text/rotation/anchor/
  // fontSize live inside lib/rv09-pot.tsx, not the module entry.
  const rv09Owner =
    claimed === "rv09"
      ? (edit.owner as {
          kind: "rv09";
          pot: string;
          slot: "label" | "designator" | "value";
        })
      : undefined;
  if (rv09Owner) {
    if (edit.ops.text !== undefined && edit.ops.text !== edit.text) {
      return { ...base, reason: "RV09Pot label text lives in lib/rv09-pot.tsx props (label/resistance/name) — edit the call-site prop text via the module source directly", expect };
    }
    if (
      edit.ops.rotation !== undefined ||
      edit.ops.anchor !== undefined ||
      edit.ops.fontSize !== undefined
    ) {
      return {
        ...base,
        reason: "RV09Pot internals support move + hide only — rotation/anchor/fontSize live in lib/rv09-pot.tsx",
        expect,
      };
    }
    if (
      (edit.ops.x !== undefined || edit.ops.y !== undefined) &&
      rv09Owner.slot !== "label"
    ) {
      return {
        ...base,
        reason: `only the "${rv09Owner.pot}" caption moves (labelDx/labelDy) — the designator/value are fixed body markings in lib/rv09-pot.tsx`,
        expect,
      };
    }
    return applyRv09Edit(nodes, entryCtx, edit, rv09Owner, base, expect);
  }

  const located =
    edit.kind === "ref" ? locateComponentNode(nodes, edit) : locateLabelNode(nodes, edit);
  if ("error" in located) return { ...base, reason: located.error, expect };
  const el = located.node;

  const changes: string[] = [];
  try {
    // --- move ----------------------------------------------------------
    if (edit.ops.x !== undefined || edit.ops.y !== undefined) {
      const targetX = edit.ops.x ?? edit.x;
      const targetY = edit.ops.y ?? edit.y;
      if (edit.kind === "ref") {
        if (!edit.componentCenter) {
          return { ...base, reason: "missing component geometry for ref move", expect };
        }
        const local = boardDeltaToLocal(
          { x: targetX, y: targetY },
          edit.componentCenter,
          edit.componentRotation ?? 0,
        );
        const a = attr(el, "pcbSx");
        if (!a) {
          (el as any).addAttribute({
            name: "pcbSx",
            initializer: `{{ "${PCBSX_SELECTOR}": { pcbX: ${fmtNum(local.x)}, pcbY: ${fmtNum(local.y)} } }}`,
          });
          changes.push(
            `added pcbSx ${PCBSX_SELECTOR} offset (${fmtNum(local.x)}, ${fmtNum(local.y)})`,
          );
        } else {
          const obj = objectLiteralOf(a);
          if (!obj) {
            return { ...base, reason: "pcbSx is computed (not an object literal) — refusing to patch", expect };
          }
          let sel: ObjectLiteralElementLike | undefined = obj.getProperty(
            `"${PCBSX_SELECTOR}"`,
          );
          if (sel && sel.getKindName() !== "PropertyAssignment") {
            return { ...base, reason: `pcbSx."${PCBSX_SELECTOR}" is not a literal object — refusing to patch`, expect };
          }
          if (!sel) {
            sel = obj.addProperty(
              `"${PCBSX_SELECTOR}": { pcbX: ${fmtNum(local.x)}, pcbY: ${fmtNum(local.y)} }`,
            ) as ObjectLiteralElementLike;
            changes.push(`added pcbSx."${PCBSX_SELECTOR}" position`);
          } else {
            const selObj = (sel as any).getInitializer() as Node | undefined;
            if (selObj?.getKindName() !== "ObjectLiteralExpression") {
              return { ...base, reason: `pcbSx."${PCBSX_SELECTOR}" is not an object literal — refusing to patch`, expect };
            }
            setNumericProp(selObj as ObjectLiteralExpression, "pcbX", local.x);
            setNumericProp(selObj as ObjectLiteralExpression, "pcbY", local.y);
            changes.push(`updated pcbSx."${PCBSX_SELECTOR}" position`);
          }
        }
      } else {
        const px = attr(el, "pcbX");
        const py = attr(el, "pcbY");
        for (const [a2, name, val] of [
          [px, "pcbX", targetX],
          [py, "pcbY", targetY],
        ] as const) {
          if (a2 && numericLiteralValue(a2.getInitializer()) === undefined) {
            return {
              ...base,
              reason: `${name} is computed (not a numeric literal) — position owned by code, refusing to patch`,
              expect,
            };
          }
        }
        setNumericAttr(el, "pcbX", targetX);
        setNumericAttr(el, "pcbY", targetY);
        changes.push(`moved to (${fmtNum(targetX)}, ${fmtNum(targetY)})`);
      }
    }

    // --- rotation / anchor / font size (labels only — runtime-verified props) ---
    if (
      edit.ops.rotation !== undefined ||
      edit.ops.anchor !== undefined ||
      edit.ops.fontSize !== undefined
    ) {
      // computed-attribute guard: only literal-initialized attrs are rewritten
      for (const [a2, name, kind] of [
        [attr(el, "pcbRotation"), "pcbRotation", "number"],
        [attr(el, "anchorAlignment"), "anchorAlignment", "string"],
        [attr(el, "fontSize"), "fontSize", "number"],
      ] as const) {
        if (!a2) continue; // absent attr — free to add
        const lit =
          kind === "number"
            ? numericLiteralValue(a2.getInitializer())
            : stringLiteralValue(a2.getInitializer());
        if (lit === undefined) {
          return {
            ...base,
            reason: `${name} is computed (not a literal) — refusing to patch`,
            expect,
          };
        }
      }
      if (edit.ops.rotation !== undefined) {
        setNumericAttr(el, "pcbRotation", edit.ops.rotation);
        changes.push(`rotation → ${fmtNum(edit.ops.rotation)}°`);
      }
      if (edit.ops.anchor !== undefined) {
        setStringAttr(el, "anchorAlignment", edit.ops.anchor);
        changes.push(`anchorAlignment → "${edit.ops.anchor}"`);
      }
      if (edit.ops.fontSize !== undefined) {
        setNumericAttr(el, "fontSize", edit.ops.fontSize);
        changes.push(`fontSize → ${fmtNum(edit.ops.fontSize)}`);
      }
    }

    // --- text ----------------------------------------------------------
    if (edit.ops.text !== undefined && edit.ops.text !== edit.text) {
      const ta = attr(el, "text");
      if (ta && stringLiteralValue(ta.getInitializer()) === undefined) {
        return { ...base, reason: "text is computed (not a string literal) — refusing to patch", expect };
      }
      setStringAttr(el, "text", edit.ops.text);
      changes.push(`text "${edit.text}" → "${edit.ops.text}"`);
    }

    // --- hide / show -----------------------------------------------------
    if (edit.ops.hidden === true) {
      changes.push(hideViaPcbStyle(el));
    } else if (edit.ops.hidden === false) {
      changes.push(showViaPcbStyle(el));
    }
  } catch (err: any) {
    return { ...base, reason: err?.message ?? String(err), expect };
  }

  return {
    fingerprint: edit.fingerprint,
    ok: changes.length > 0,
    expect,
    reason: changes.length === 0 ? "no-op edit" : undefined,
    change: changes.join("; "),
  };
}

/* ------------------------------------------------------------------ */
/* entry point                                                         */
/* ------------------------------------------------------------------ */

/**
 * Apply edits to the module entry's source file WITHOUT writing to disk.
 * Returns the patched source + per-edit outcomes; the caller writes +
 * recompiles (and rolls back) — see server/api.ts.
 */
export function applyEditsToSource(
  entryPath: string,
  sourceText: string,
  edits: SilkEdit[],
): ApplyEditsResult {
  const project = new Project({
    useInMemoryFileSystem: true,
    manipulationSettings: { indentationText: IndentationText.TwoSpaces, useTrailingCommas: false },
  });
  const source = project.createSourceFile(entryPath, sourceText, {
    // NOTE: explicit key (and not the `{ ScriptKind.TSX }` shorthand-value
    // form) — bun's parser rejects qualified enum names as object values.
    scriptKind: ScriptKind.TSX,
  });
  const nodes = collectElements(source);
  // Entry context (RV09 call sites) is parsed from the LIVE in-memory source
  // — never the stale bytes on disk — so sequential edits in one batch share
  // consistent state.
  const entryCtx = parseEntryContext(entryPath, source.getFullText());

  const outcomes: EditOutcome[] = edits.map((edit) =>
    applyEditToNodes(nodes, edit, entryCtx),
  );

  const newSource = source.getFullText();

  // cheap syntax gate: re-parse and inspect the parser's own diagnostics.
  const reparsed = ts.createSourceFile(
    entryPath,
    newSource,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const parseDiagnostics: readonly ts.Diagnostic[] = (reparsed as any).parseDiagnostics ?? [];
  if (parseDiagnostics.length > 0) {
    const first = parseDiagnostics[0];
    const pos =
      first.file && first.start !== undefined
        ? first.file.getLineAndCharacterOfPosition(first.start)
        : { line: 0, character: 0 };
    return {
      ok: false,
      error: `patched source does not parse (line ${pos.line + 1}:${pos.character + 1}): ${ts.flattenDiagnosticMessageText(first.messageText, " ")}`,
      outcomes,
    };
  }

  return {
    ok: true,
    outcomes,
    newSource,
    diff: lineDiff(sourceText, newSource),
  };
}

/* ------------------------------------------------------------------ */
/* tiny line diff (context-free) for the save report                   */
/* ------------------------------------------------------------------ */

export function lineDiff(before: string, after: string): string[] {
  const a = before.split("\n");
  const b = after.split("\n");
  // LCS table (files are small: ≲ 300 lines)
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: string[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push(`- ${a[i++]}`);
    } else {
      out.push(`+ ${b[j++]}`);
    }
  }
  while (i < n) out.push(`- ${a[i++]}`);
  while (j < m) out.push(`+ ${b[j++]}`);
  return out;
}
