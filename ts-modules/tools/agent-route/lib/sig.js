// Per-section .sig hashing per design §5.
//
// sig inputs (all section-local except pinned tool versions):
//   - placement elements whose courtyard/centre intersects rect ∪ margin
//     (NOT board-global placement — a nudge in S1 must not invalidate S5)
//   - the endpoints (ref + pin) of the section's connections
//   - the plan section itself (id/name/rect/connections/phaseIndex)
//   - router version + router params (pinned @tscircuit/* versions)
//
// sigForSection(scan, section, opts) -> hex sha256.
//   scan: object from lib/scan.js (components + connEndpoints + board)
//   section: { id, name, rect, connections, phaseIndex, status }
//   opts: { margin, versions, routerParams }
//
// verifySectionSig(scan, section, sig, opts) -> { valid, reason }
import { createHash } from "node:crypto";
import { MARGIN, ROUTER_PARAMS, VERSIONS } from "./constants.js";

export function sigInputsForSection(scan, section, opts = {}) {
  const margin = opts.margin ?? MARGIN;
  const r = section.rect;
  const grown = {
    minX: r.minX - margin,
    maxX: r.maxX + margin,
    minY: r.minY - margin,
    maxY: r.maxY + margin,
  };
  const inRect = (x, y) =>
    x >= grown.minX && x <= grown.maxX && y >= grown.minY && y <= grown.maxY;

  const placement = scan.components
    .filter((c) => inRect(c.center.x, c.center.y))
    .map((c) => ({
      ref: c.ref,
      x: round3(c.center.x),
      y: round3(c.center.y),
      w: c.w,
      h: c.h,
    }))
    .sort((a, b) => a.ref.localeCompare(b.ref));

  const endpoints = [...section.connections].sort();

  // section-local pad coordinates (pads whose ref is a section member and
  // whose x/y falls in rect ∪ margin) — ties placement to the sig so a
  // footprint/pad move inside the rect invalidates, one outside does not.
  const members = new Set(
    scan.components
      .filter((c) => inRect(c.center.x, c.center.y))
      .map((c) => c.ref),
  );
  const padPts = (scan.pads ?? [])
    .filter((p) => p.ref && members.has(p.ref) && inRect(p.x, p.y))
    .map((p) => ({ ref: p.ref, x: round3(p.x), y: round3(p.y) }))
    .sort((a, b) => a.ref.localeCompare(b.ref) || a.x - b.x || a.y - b.y);

  return {
    placement,
    padPts,
    endpoints,
    planSection: {
      id: section.id,
      name: section.name,
      rect: section.rect,
      connections: [...section.connections].sort(),
      phaseIndex: section.phaseIndex,
    },
    versions: opts.versions ?? {
      tscircuit: VERSIONS.tscircuit,
      core: VERSIONS.core,
      capacityAutorouter: VERSIONS.capacityAutorouter,
      checks: VERSIONS.checks,
    },
    routerParams: opts.routerParams ?? ROUTER_PARAMS,
    boardOutline: {
      w: scan.boardDims.width,
      h: scan.boardDims.height,
    },
  };
}

export function sigForSection(scan, section, opts = {}) {
  const inputs = sigInputsForSection(scan, section, opts);
  return createHash("sha256")
    .update(JSON.stringify(inputs))
    .digest("hex");
}

export function verifySectionSig(scan, section, sig, opts = {}) {
  if (!sig) return { valid: false, reason: "no sig file" };
  const cur = sigForSection(scan, section, opts);
  if (cur === String(sig).trim()) return { valid: true, reason: "match" };
  return { valid: false, reason: "inputs changed" };
}

function round3(n) {
  return Math.round(Number(n) * 1000) / 1000;
}
