#!/usr/bin/env node
/**
 * locate.mjs — TSX AST locator for the Nudge Tool.
 *
 * Parses a `.circuit.tsx` file with the TypeScript compiler (resolved from
 * `ts-modules/node_modules`), walks the JSX tree, and for every element that
 * carries a string-literal `name` attribute and at least one numeric-literal
 * `pcbX`/`pcbY` attribute it records the *numeric value* and the *byte span*
 * of the numeric token in the UTF-8 source. Partial coordinates (only one of
 * `pcbX`/`pcbY`) are recorded; duplicate names warn and keep the first.
 *
 * Byte spans (not UTF-16 offsets) are emitted so the Python editor can splice
 * `source_bytes[start:end]` directly — this keeps round-trips byte-identical
 * even though the file contains multi-byte UTF-8 characters (em-dashes, the
 * degree sign, etc.) in comments *before* the coordinate literals.
 *
 * Usage:
 *   node locate.mjs <path-to-tsx>
 *
 * Emits on stdout:
 *   { "<NAME>": { "pcbX": {"value": -4.11, "start": 1234, "end": 1239, "raw": "-4.11"},
 *                 "pcbY": {...} }, ... }
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
// Resolve the `typescript` compiler from ts-modules/node_modules, independent
// of the caller's cwd.
const require = createRequire(path.join(repoRoot, "ts-modules", "package.json"));
const ts = require("typescript");

const filePath = process.argv[2];
if (!filePath) {
  console.error("usage: locate.mjs <path-to-tsx>");
  process.exit(2);
}

const sourceText = readFileSync(filePath, "utf8");
const sf = ts.createSourceFile(filePath, sourceText, ts.ScriptKind.TSX, true);

/** Convert a UTF-16 code-unit offset into a UTF-8 byte offset. */
function byteOffset(utf16Index) {
  return Buffer.byteLength(sourceText.slice(0, utf16Index), "utf8");
}

/** Return {value, raw, start, end} (byte offsets) for a numeric JSX expression. */
function numericSpan(node) {
  if (!node) return null;
  // Unwrap parenthesized expressions, e.g. pcbX={(-4.11)}.
  let n = node;
  while (n && ts.isParenthesizedExpression(n)) {
    n = n.expression;
  }
  if (n && (ts.isNumericLiteral(n) || ts.isPrefixUnaryExpression(n))) {
    const start = n.getStart(sf);
    const end = n.getEnd();
    const raw = sourceText.slice(start, end);
    return {
      // Strip numeric separators (4_000 -> 4000) before parsing so a
      // separator is never silently truncated by parseFloat.
      value: Number.parseFloat(raw.replace(/_/g, "")),
      raw,
      start: byteOffset(start),
      end: byteOffset(end),
    };
  }
  return null;
}

/** Read the JSX attributes of an opening/self-closing element into a map. */
function readAttributes(element) {
  const attrs = {};
  const attrNode = element.attributes;
  if (!attrNode) return attrs;
  for (const prop of attrNode.properties) {
    if (!ts.isJsxAttribute(prop)) continue;
    const name = prop.name.text;
    const init = prop.initializer;
    if (init == null) {
      attrs[name] = { kind: "bare" };
    } else if (ts.isStringLiteral(init)) {
      attrs[name] = { kind: "string", value: init.text };
    } else if (ts.isJsxExpression(init)) {
      attrs[name] = { kind: "expr", node: init.expression };
    }
  }
  return attrs;
}

const result = {};

function visit(node) {
  if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
    const attrs = readAttributes(node);
    if (attrs.name && attrs.name.kind === "string") {
      const entry = {};
      if (attrs.pcbX) {
        const x = numericSpan(attrs.pcbX.node);
        if (x) entry.pcbX = x;
      }
      if (attrs.pcbY) {
        const y = numericSpan(attrs.pcbY.node);
        if (y) entry.pcbY = y;
      }
      const name = attrs.name.value;
      // Record a component if it carries at least one coordinate (partial
      // coordinates are supported; the caller decides which axes to touch).
      if (Object.keys(entry).length > 0) {
        if (Object.prototype.hasOwnProperty.call(result, name)) {
          console.error(`locate: warning: duplicate component name "${name}" — keeping first occurrence`);
        } else {
          result[name] = entry;
        }
      }
    }
  }
  ts.forEachChild(node, visit);
}
visit(sf);

process.stdout.write(JSON.stringify(result, null, 2) + "\n");
