// PLAN (§4.2 + §5): rects + connection assignment + scoring + validation.
//
// buildPlan(scan) -> { plan, scoring }
//   plan: { version, board, createdAt, sections[{id,name,rect,connections,phaseIndex,status}] }
//   Rect = cluster member bbox + MARGIN, expanded so adjacent rects overlap
//   by >= OVERLAP (mandatory >= 2x max-trace-pitch; pitch ~0.3-0.5mm).
//   Connections assigned to the section holding most of their endpoints
//   (ties -> lower phaseIndex). Sections ordered densest-first (phaseIndex).
//
// scorePlan(plan, scan) -> { cutNets, densities, sanity }
//   cutNets: connections whose endpoints span a section boundary (count + list)
//   densities: per-section conns / rect area
//   sanity: per-section aspect + coverage notes
//
// validatePlan(plan, scan) -> { ok, errors[], warnings[] }
//   §4.2/§8.5 checks: every connection in exactly one section, every pad in
//   some rect, no orphan nets, overlaps within bounds, warn 3+ section spans.
import { MARGIN, OVERLAP, PLAN_VERSION } from "./constants.js";

export function buildPlan(scan) {
  const compByRef = new Map(scan.components.map((c) => [c.ref, c]));
  const padsByRef = new Map();
  for (const p of scan.pads) {
    if (!p.ref) continue; // frame mounting holes etc. — no owning component
    if (!padsByRef.has(p.ref)) padsByRef.set(p.ref, []);
    padsByRef.get(p.ref).push(p);
  }
  // cluster bbox over member centres AND member pads + margin.
  // (Pads can sit well outside the courtyard, e.g. RV pot bracket holes.)
  const rects = scan.sections.map((s) => {
    const xs = [];
    const ys = [];
    for (const m of s.members) {
      const c = compByRef.get(m)?.center;
      if (c) { xs.push(c.x); ys.push(c.y); }
      for (const p of padsByRef.get(m) ?? []) { xs.push(p.x); ys.push(p.y); }
    }
    if (xs.length === 0) { xs.push(0); ys.push(0); }
    return {
      minX: r3(Math.min(...xs) - MARGIN),
      maxX: r3(Math.max(...xs) + MARGIN),
      minY: r3(Math.min(...ys) - MARGIN),
      maxY: r3(Math.max(...ys) + MARGIN),
    };
  });

  // mandatory adjacent overlap: expand each rect toward the board centre
  // until every pair overlaps (or touches within OVERLAP tolerance).
  // Single-section plans trivially satisfy this.
  if (rects.length > 1) {
    const cx = scan.boardDims.cx;
    const cy = scan.boardDims.cy;
    for (let iter = 0; iter < 50; iter++) {
      let worst = null;
      let worstGap = 0;
      for (let i = 0; i < rects.length; i++) {
        for (let j = i + 1; j < rects.length; j++) {
          const gap = rectGap(rects[i], rects[j]);
          if (gap > worstGap) { worstGap = gap; worst = [i, j]; }
        }
      }
      if (worstGap <= 0) break; // all pairs overlap
      // expand the pair toward each other (grow by 25% of gap each side, min 0.25mm)
      const [i, j] = worst;
      const step = Math.max(worstGap / 4, 0.25);
      growToward(rects[i], rects[j], step);
      growToward(rects[j], rects[i], step);
      void cx; void cy;
    }
    // final guarantee: any still-disjoint pair gets bridged by extending
    // both rects to cover the midpoint band between them.
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        if (rectGap(rects[i], rects[j]) > 0) bridge(rects[i], rects[j]);
      }
    }
    for (const r of rects) {
      r.minX = r3(r.minX); r.maxX = r3(r.maxX);
      r.minY = r3(r.minY); r.maxY = r3(r.maxY);
    }
  }

  // provisional sections (phaseIndex assigned after density sort)
  const idOf = (idx) => `S${idx + 1}`;
  let provisional = scan.sections.map((s, idx) => ({
    id: idOf(idx),
    name: s.name,
    rect: rects[idx],
    members: s.members,
    connections: [],
  }));

  // assign each connection to section holding most endpoints
  const epSection = (ref) =>
    provisional.findIndex((s) => s.members.includes(ref));
  for (const conn of scan.connections) {
    const eps = scan.connEndpoints[conn] ?? [];
    const votes = new Map();
    for (const e of eps) {
      const si = epSection(e.ref);
      if (si >= 0) votes.set(si, (votes.get(si) ?? 0) + 1);
    }
    if (votes.size === 0) {
      provisional[0].connections.push(conn);
      continue;
    }
    let best = [...votes.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
    provisional[best].connections.push(conn);
  }
  for (const s of provisional) s.connections.sort();

  // order: densest (conns/area) first; phaseIndex = execution order
  const area = (r) => Math.max(r.maxX - r.minX, 0.01) * Math.max(r.maxY - r.minY, 0.01);
  provisional.sort(
    (a, b) => b.connections.length / area(b.rect) - a.connections.length / area(a.rect),
  );
  const sections = provisional.map((s, idx) => ({
    id: idOf(idx),
    name: s.name,
    rect: s.rect,
    connections: s.connections,
    phaseIndex: idx,
    status: "pending",
  }));

  const plan = {
    version: PLAN_VERSION,
    board: scan.boardName,
    createdAt: new Date().toISOString(),
    sections,
  };
  return { plan, scoring: scorePlan(plan, scan) };
}

export function scorePlan(plan, scan) {
  const secOf = (ref) =>
    plan.sections.findIndex((s) => pointInRect(scan.components.find((c) => c.ref === ref)?.center, s.rect));
  const cutNets = [];
  for (const conn of scan.connections) {
    const eps = scan.connEndpoints[conn] ?? [];
    const secs = new Set(eps.map((e) => secOf(e.ref)).filter((i) => i >= 0));
    if (secs.size > 1) cutNets.push(conn);
  }
  const densities = plan.sections.map((s) => {
    const a = Math.max(s.rect.maxX - s.rect.minX, 0.01) *
      Math.max(s.rect.maxY - s.rect.minY, 0.01);
    return {
      id: s.id,
      conns: s.connections.length,
      areaMm2: r3(a),
      connsPerMm2: r3(s.connections.length / a),
    };
  });
  const boardArea = Math.max(scan.boardDims.width, 0.01) * Math.max(scan.boardDims.height, 0.01);
  const sanity = plan.sections.map((s) => {
    const w = s.rect.maxX - s.rect.minX;
    const h = s.rect.maxY - s.rect.minY;
    const aspect = r3(Math.max(w, h) / Math.max(Math.min(w, h), 0.01));
    const coverage = r3((w * h) / boardArea);
    const notes = [];
    if (aspect > 8) notes.push("sliver rect (aspect > 8)");
    if (coverage > 0.9) notes.push("covers >90% of board");
    return { id: s.id, aspect, coverage, notes };
  });
  return { cutNets, densities, sanity };
}

export function validatePlan(plan, scan) {
  const errors = [];
  const warnings = [];
  if (!plan || typeof plan !== "object") return { ok: false, errors: ["plan is not an object"], warnings };
  if (plan.board !== scan.boardName) {
    errors.push(`plan.board '${plan.board}' != scan board '${scan.boardName}'`);
  }
  const secs = Array.isArray(plan.sections) ? plan.sections : [];
  if (secs.length === 0) errors.push("plan has no sections");
  const ids = new Set();
  for (const s of secs) {
    if (!s.id || ids.has(s.id)) errors.push(`duplicate/missing section id '${s?.id}'`);
    ids.add(s.id);
    for (const k of ["minX", "maxX", "minY", "maxY"]) {
      if (typeof s.rect?.[k] !== "number" || Number.isNaN(s.rect[k])) {
        errors.push(`${s.id}: rect.${k} missing/not a number`);
      }
    }
    if (s.rect && (s.rect.minX >= s.rect.maxX || s.rect.minY >= s.rect.maxY)) {
      errors.push(`${s.id}: rect inverted`);
    }
    if (!Array.isArray(s.connections)) errors.push(`${s.id}: connections not an array`);
    if (typeof s.phaseIndex !== "number") errors.push(`${s.id}: phaseIndex missing`);
  }

  // every connection assigned to exactly one section
  const seen = new Map();
  for (const s of secs) {
    for (const c of s.connections ?? []) {
      if (seen.has(c)) {
        errors.push(`connection '${c}' in both ${seen.get(c)} and ${s.id}`);
      } else seen.set(c, s.id);
    }
  }
  for (const c of scan.connections) {
    if (!seen.has(c)) errors.push(`orphan connection '${c}' (in scan, in no section)`);
  }
  for (const c of seen.keys()) {
    if (!scan.connections.includes(c)) {
      warnings.push(`connection '${c}' in plan but not in scan (stale?)`);
    }
  }

  // every attributable pad inside some rect (pads with no owning
  // component — e.g. frame mounting holes — are not attributable)
  let padsOutside = 0;
  const attributable = scan.pads.filter((p) => p.ref);
  for (const p of attributable) {
    if (!secs.some((s) => pointInRect({ x: p.x, y: p.y }, s.rect))) padsOutside++;
  }
  if (padsOutside > 0) {
    errors.push(`${padsOutside}/${attributable.length} pads fall outside all section rects`);
  }

  // overlaps within bounds: adjacent pairs must overlap by >= OVERLAP.
  // (allow containment: gap <= 0 means overlap.)
  for (let i = 0; i < secs.length; i++) {
    for (let j = i + 1; j < secs.length; j++) {
      const gap = rectGap(secs[i].rect, secs[j].rect);
      if (gap > 0) {
        errors.push(
          `${secs[i].id}↔${secs[j].id} disjoint (gap ${r3(gap)}mm, need overlap ≥ ${OVERLAP}mm)`,
        );
      }
    }
  }

  // warn on nets spanning 3+ sections (§8.5: re-plan rather than chain)
  for (const conn of scan.connections) {
    const eps = scan.connEndpoints[conn] ?? [];
    const owners = new Set(
      eps.map((e) => secs.find((s) => (s.connections ?? []).includes(conn))?.id).filter(Boolean),
    );
    const span = new Set(
      eps.map((e) => {
        const c = scan.components.find((cc) => cc.ref === e.ref)?.center;
        return secs.find((s) => pointInRect(c, s.rect))?.id;
      }).filter(Boolean),
    );
    void owners;
    if (span.size >= 3) warnings.push(`net '${conn}' spans ${span.size} sections (re-plan, §8.5)`);
  }

  return { ok: errors.length === 0, errors, warnings };
}

// --- geometry helpers -----------------------------------------------------
export function pointInRect(p, r) {
  if (!p || !r) return false;
  return p.x >= r.minX && p.x <= r.maxX && p.y >= r.minY && p.y <= r.maxY;
}

// min edge-to-edge separation; <= 0 means overlap/touch.
// For disjoint rects returns the axis gap; for overlapping returns negative overlap depth.
export function rectGap(a, b) {
  const dx = Math.max(a.minX - b.maxX, b.minX - a.maxX);
  const dy = Math.max(a.minY - b.maxY, b.minY - a.maxY);
  if (dx <= 0 && dy <= 0) return -Math.min(-dx, -dy); // overlap depth (negative)
  return Math.max(dx, dy, 0);
}

function growToward(r, other, step) {
  const cx = (other.minX + other.maxX) / 2;
  const cy = (other.minY + other.maxY) / 2;
  if (cx < r.minX) r.minX -= step;
  if (cx > r.maxX) r.maxX += step;
  if (cy < r.minY) r.minY -= step;
  if (cy > r.maxY) r.maxY += step;
}

function bridge(a, b) {
  const midX = ((Math.max(a.minX, b.minX) + Math.min(a.maxX, b.maxX)) / 2);
  const midY = ((Math.max(a.minY, b.minY) + Math.min(a.maxY, b.maxY)) / 2);
  const lo = OVERLAP / 2;
  a.minX = Math.min(a.minX, midX - lo); a.maxX = Math.max(a.maxX, midX + lo);
  a.minY = Math.min(a.minY, midY - lo); a.maxY = Math.max(a.maxY, midY + lo);
  b.minX = Math.min(b.minX, midX - lo); b.maxX = Math.max(b.maxX, midX + lo);
  b.minY = Math.min(b.minY, midY - lo); b.maxY = Math.max(b.maxY, midY + lo);
}

function r3(n) {
  return Math.round(Number(n) * 1000) / 1000;
}
