// plan-v2 — net-phase planner (v2, side-by-side with v1 lib/plan.js).
//
// v1 plans by RECT (y-row bucketing + 1mm overlap); v2 plans by NET IDENTITY.
// A phase = { phaseIndex, name, nets[] (scan-conn strings), region?, autorouter,
// budgetMs }. There is NO "remainder" phase: validatePhases() requires every
// scan connection to be claimed by exactly one named phase (schema-level
// unclaimedNets: [] check), so the deferral pathology (v1 §8.5: cross-rect nets
// pushed to the worst owner, e.g. 8bit S1 deferredConns source_net_0) cannot
// regrow.
//
// Metric: maxCrossPhaseCorridorOverlap replaces v1 cutNets. Two phases whose
// nets' endpoint bounding boxes overlap heavily in the escape-corridor axis
// must be co-phased (merged) — corridor-affinity grouping, NOT densest-first.
//
// v1 files untouched. Reuses v1 scan.js (loadScanFromCircuitJson) read-only.
import { PLAN_VERSION } from "./constants.js";

export const PHASES_VERSION = 1;

// Adaptive per-phase budget: 2s x SRJ-netted conns, floor 60s, ceiling 180s.
// Overrun = mis-grouped -> re-phase instead of raising the cap. Total board
// budget cap ~15min is enforced by route-v2 (sums phase budgetMs).
export const PHASE_BUDGET_FLOOR_MS = 60000;
export const PHASE_BUDGET_CEIL_MS = 180000;
export const PHASE_BUDGET_PER_NET_MS = 2000;
export const BOARD_BUDGET_CAP_MS = 15 * 60 * 1000;
export const MAX_REPHASE_ROUNDS = 2;

export function budgetForPhase(netCount) {
  return Math.min(
    PHASE_BUDGET_CEIL_MS,
    Math.max(PHASE_BUDGET_FLOOR_MS, netCount * PHASE_BUDGET_PER_NET_MS),
  );
}

// --- corridor geometry ------------------------------------------------------
// Corridor of a net = bbox of its scan endpoints (pad-exact where placed,
// component centre fallback). Two nets "share a corridor" when their bboxes
// overlap (with a small halo so adjacent escape lanes count as shared).
const CORRIDOR_HALO_MM = 1.0;

export function netCorridor(scan, conn, haloMm = CORRIDOR_HALO_MM) {
  const eps = (scan.connEndpoints?.[conn] ?? []).filter(
    (e) => typeof e.x === "number" && typeof e.y === "number",
  );
  // Pad-exact endpoints only: null-coord endpoints (unplaced comps) fall back
  // to the component centre (0,0 for unplaced), which would fake corridor
  // overlaps at the origin — EXCLUDE them instead. A net left with no placed
  // endpoints gets the board-centre corridor (overlaps everything: it must be
  // co-phased cautiously, never silently isolated).
  const pts = eps;
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  if (xs.length === 0) {
    const cx = scan.boardDims?.cx ?? 0;
    const cy = scan.boardDims?.cy ?? 0;
    return { minX: cx - 1, maxX: cx + 1, minY: cy - 1, maxY: cy + 1, unplaced: true };
  }
  return {
    minX: Math.min(...xs) - haloMm,
    maxX: Math.max(...xs) + haloMm,
    minY: Math.min(...ys) - haloMm,
    maxY: Math.max(...ys) + haloMm,
  };
}

function corridorsOverlap(a, b) {
  return a.minX <= b.maxX && b.minX <= a.maxX && a.minY <= b.maxY && b.minY <= a.maxY;
}

// maxCrossPhaseCorridorOverlap: fraction of cross-phase net pairs whose
// corridors overlap. 0 = phases are corridor-disjoint (good); 1 = every
// cross-phase pair fights over the same escape lanes (v1 8bit regime).
// Also returns the overlapping pairs for the re-phase loop.
export function scoreCorridorOverlap(scan, phases, haloMm = CORRIDOR_HALO_MM) {
  const corridors = new Map();
  for (const p of phases) {
    for (const n of p.nets ?? []) {
      if (!corridors.has(n)) corridors.set(n, netCorridor(scan, n, haloMm));
    }
  }
  let total = 0;
  let overlap = 0;
  const overlappingPairs = [];
  for (let i = 0; i < phases.length; i++) {
    for (let j = i + 1; j < phases.length; j++) {
      for (const a of phases[i].nets ?? []) {
        for (const b of phases[j].nets ?? []) {
          total++;
          if (corridorsOverlap(corridors.get(a), corridors.get(b))) {
            overlap++;
            overlappingPairs.push({ a, phaseA: phases[i].phaseIndex, b, phaseB: phases[j].phaseIndex });
          }
        }
      }
    }
  }
  return {
    total,
    overlap,
    maxCrossPhaseCorridorOverlap: total === 0 ? 0 : Math.round((overlap / total) * 1000) / 1000,
    overlappingPairs,
  };
}

// --- grouping ---------------------------------------------------------------
// Corridor-affinity grouping: union-find over nets whose corridors overlap OR
// that share a component (same-ref nets fight over the same pads/pins — e.g.
// drive C1.1/C1.2 on C1: splitting them solo-phases one pad's escape while
// the sibling pad's copper is locked, and the joint-greedy solver then fails
// NO_PATH against its own sibling's geometry),
// then split each corridor-cluster only if it exceeds maxNetsPerPhase (keeps
// phases solver-sized while never splitting shared escape lanes across
// phases). Infra nets (matching INFRA_PATTERNS or the phase-0 explicit list)
// are pulled into phase 0 first so the P0 routability smoke test gates them.
//
// DRIVE LESSON-2 (2026-09-03, 3/3 deterministic both ways): bounds STEER the
// solver, they don't just constrain it. Same 11-net set + same locks: full-
// board bounds = 1 collision (solver wanders into locked edge tails),
// corridor-union bounds = DRC-clean. So each phase carries a `region`
// (corridor-bbox union of its nets + REGION_MARGIN); route-v2 solves with
// bounds = region, NOT full board. This is NET-derived steering (endpoints +
// escape room by construction — core expands to include connection points),
// never a planner sliver: regions covering >90% of the board collapse to
// null (= full board). The 8bit 0.17mm-band pathology cannot recur because a
// region always contains its nets' own escape corridors.
export const REGION_MARGIN_MM = 2.0;

export function regionForNets(scan, nets) {
  if (!nets || nets.length === 0) return null;
  let u = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  for (const n of nets) {
    const c = netCorridor(scan, n);
    u.minX = Math.min(u.minX, c.minX); u.maxX = Math.max(u.maxX, c.maxX);
    u.minY = Math.min(u.minY, c.minY); u.maxY = Math.max(u.maxY, c.maxY);
  }
  const bw = Math.max(scan.boardDims.width, 0.01);
  const bh = Math.max(scan.boardDims.height, 0.01);
  const area = (u.maxX - u.minX) * (u.maxY - u.minY);
  if (area / (bw * bh) > 0.9) return null; // ~whole board: full bounds
  // Clamp to the board outline: halo+margin can push the box off-board, and
  // out-of-board bounds break the solver grid (drive P0-region SOLVE-FAIL).
  const bx = { minX: scan.boardDims.cx - bw / 2, maxX: scan.boardDims.cx + bw / 2 };
  const by = { minY: scan.boardDims.cy - bh / 2, maxY: scan.boardDims.cy + bh / 2 };
  return {
    minX: r3(Math.max(u.minX - REGION_MARGIN_MM, bx.minX)),
    maxX: r3(Math.min(u.maxX + REGION_MARGIN_MM, bx.maxX)),
    minY: r3(Math.max(u.minY - REGION_MARGIN_MM, by.minY)),
    maxY: r3(Math.min(u.maxY + REGION_MARGIN_MM, by.maxY)),
  };
}

function r3(n) {
  return Math.round(Number(n) * 1000) / 1000;
}

// DRIVE LESSON-1 (2026-09-03): the solver is JOINT-greedy — a 9-conn infra-only
// phase failed its cumulative gate (pad-trace clearance) while the SAME nets
// co-phased with their 12 corridor neighbours solved DRC-clean twice. Small
// solo phases let the solver greed a corridor that a later phase must share.
// So: default = ONE phase per corridor-cluster (infra co-phased with its
// cluster), split a cluster ONLY when its estimated budget would breach the
// per-phase ceiling. maxNetsPerPhase is the budget-overflow escape hatch,
// not the default cut.
const INFRA_PATTERNS = [/V_SUPPLY/i, /GND/i, /VCC/i, /VEE/i, /3V3/i, /5V/i];

export function isInfraConn(conn) {
  return INFRA_PATTERNS.some((re) => re.test(conn));
}

export function buildPhases(scan, opts = {}) {
  const maxNetsPerPhase = opts.maxNetsPerPhase ?? 8;
  const haloMm = opts.haloMm ?? CORRIDOR_HALO_MM;
  const explicitInfra = new Set(opts.infra ?? []);
  const conns = [...(scan.connections ?? [])].sort();

  const corridors = new Map(conns.map((c) => [c, netCorridor(scan, c, haloMm)]));
  // Component refs per net (endpoint refs) — shared-ref nets co-phase.
  const refsOf = (c) => new Set((scan.connEndpoints?.[c] ?? []).map((e) => e.ref));
  const refSets = new Map(conns.map((c) => [c, refsOf(c)]));
  const parent = new Map(conns.map((c) => [c, c]));
  const find = (a) => {
    while (parent.get(a) !== a) {
      parent.set(a, parent.get(parent.get(a)));
      a = parent.get(a);
    }
    return a;
  };
  const union = (a, b) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent.set(rb, ra);
  };
  for (let i = 0; i < conns.length; i++) {
    for (let j = i + 1; j < conns.length; j++) {
      if (corridorsOverlap(corridors.get(conns[i]), corridors.get(conns[j]))) {
        union(conns[i], conns[j]);
        continue;
      }
      // Shared component: same-ref endpoints (e.g. C1's pads) share escape
      // geometry even when their far-end corridors are disjoint.
      const a = refSets.get(conns[i]);
      const b = refSets.get(conns[j]);
      for (const r of a) {
        if (b.has(r)) { union(conns[i], conns[j]); break; }
      }
    }
  }
  const clusters = new Map();
  for (const c of conns) {
    const r = find(c);
    if (!clusters.has(r)) clusters.set(r, []);
    clusters.get(r).push(c);
  }

  const phases = [];
  const infraNets = conns.filter((c) => explicitInfra.has(c) || isInfraConn(c));

  // Cluster the NON-infra nets by corridor overlap. The infra nets join the
  // largest corridor-cluster they overlap (joint-greedy solver needs the
  // corridor co-phased; see DRIVE LESSON above). Infra with no corridor
  // overlap at all keeps its own thin P0.
  const sigClusters = [...clusters.values()]
    .map((members) => members.filter((m) => !infraNets.includes(m)))
    .filter((m) => m.length > 0)
    .sort((a, b) => b.length - a.length);

  // Ceiling-driven split: a cluster stays whole unless its budget would
  // breach the per-phase ceiling (then chunk to maxNetsPerPhase).
  const ceilNets = Math.floor(PHASE_BUDGET_CEIL_MS / PHASE_BUDGET_PER_NET_MS);
  const effMax = Math.min(maxNetsPerPhase, ceilNets);

  const infraClusterIdx = (() => {
    let best = -1;
    let bestW = 0;
    sigClusters.forEach((cl, i) => {
      let w = 0;
      for (const n of infraNets) {
        for (const m of cl) {
          if (corridorsOverlap(corridors.get(n), corridors.get(m))) w++;
        }
      }
      if (w > bestW) { bestW = w; best = i; }
    });
    return bestW > 0 ? best : -1;
  })();

  if (infraClusterIdx < 0) {
    // Isolated infra: own thin P0 (smoke test still gates signal phases).
    phases.push({
      phaseIndex: 0,
      name: "infra",
      nets: infraNets,
      region: regionForNets(scan, infraNets),
      autorouter: "capacity-autorouter",
      budgetMs: budgetForPhase(Math.max(infraNets.length, 1)),
    });
  }

  sigClusters.forEach((cluster, ci) => {
    let members = [...cluster];
    if (ci === infraClusterIdx) {
      // Infra nets FIRST, and pinned adjacent to their shared-ref sibling:
      // the joint-greedy solver needs same-component pads (e.g. drive C1.1 /
      // C1.2) in the SAME chunk — appending infra last strands it in a solo
      // tail chunk that fails NO_PATH against its sibling's locked copper.
      const sibIdx = new Map();
      members.forEach((m, i) => sibIdx.set(m, i));
      const withSib = [];
      const withoutSib = [];
      for (const n of infraNets) {
        const nRefs = refSets.get(n) ?? new Set();
        let at = -1;
        for (const m of members) {
          const mRefs = refSets.get(m) ?? new Set();
          for (const r of nRefs) {
            if (mRefs.has(r)) { at = sibIdx.get(m); break; }
          }
          if (at >= 0) break;
        }
        if (at >= 0) withSib.push({ n, at });
        else withoutSib.push(n);
      }
      // Insert sibling-pinned infra right after their sibling; the rest front.
      withSib.sort((a, b) => b.at - a.at);
      for (const { n, at } of withSib) members.splice(at + 1, 0, n);
      members = [...withoutSib, ...members];
    }
    // Infra-joined cluster emits first (contains P0's nets); first chunk out
    // is named infra. (Chunks after the first are signal-N even inside the
    // infra-joined cluster — P0 = first chunk only, smoke-gated.)
    // Chunk with sibling awareness: never strand a shared-ref net in a later
    // chunk while its sibling rides an earlier one (same failure as infra
    // tails — e.g. R7.1/R7.2). Overflow the chunk rather than split siblings,
    // but cap the overflow (2x effMax) so hub-chaining (many nets sharing one
    // ref like U1) still terminates into multiple phases.
    const chunks = [];
    let cur = [];
    const curRefs = new Set();
    const flush = () => { if (cur.length) chunks.push(cur); cur = []; curRefs.clear(); };
    for (const m of members) {
      const mRefs = refSets.get(m) ?? new Set();
      const shares = [...mRefs].some((r) => curRefs.has(r));
      if (cur.length >= effMax && (!shares || cur.length >= 2 * effMax)) flush();
      cur.push(m);
      for (const r of mRefs) curRefs.add(r);
    }
    flush();
    for (const chunk of chunks) {
      const first = phases.length === 0;
      phases.push({
        phaseIndex: phases.length,
        name: first ? "infra" : `signal-${phases.length}`,
        nets: chunk,
        region: regionForNets(scan, chunk),
        autorouter: "capacity-autorouter",
        budgetMs: budgetForPhase(chunk.length),
      });
    }
  });
  // Edge: board with ONLY infra nets (no signal clusters) and infra already
  // emitted above — nothing more to do. If infra joined nothing (no signal
  // conns at all), the P0 above covers it.
  void PLAN_VERSION;

  const phasesDoc = {
    version: PHASES_VERSION,
    board: scan.boardName,
    createdAt: new Date().toISOString(),
    phases,
    unclaimedNets: unclaimedNets(scan, phases),
  };
  return { phases: phasesDoc, scoring: scorePhases(scan, phasesDoc) };
}

export function unclaimedNets(scan, phases) {
  const claimed = new Set();
  const dupes = new Set();
  for (const p of phases) {
    for (const n of p.nets ?? []) {
      if (claimed.has(n)) dupes.add(n);
      claimed.add(n);
    }
  }
  const missing = (scan.connections ?? []).filter((c) => !claimed.has(c));
  return { missing, dupes: [...dupes].sort() };
}

export function scorePhases(scan, phasesDoc) {
  const phases = phasesDoc.phases ?? [];
  const overlap = scoreCorridorOverlap(scan, phases);
  const unclaimed = unclaimedNets(scan, phases);
  const totalBudgetMs = phases.reduce((s, p) => s + (p.budgetMs ?? 0), 0);
  return {
    maxCrossPhaseCorridorOverlap: overlap.maxCrossPhaseCorridorOverlap,
    overlapPairs: overlap.overlap,
    overlapTotal: overlap.total,
    overlappingPairs: overlap.overlappingPairs.slice(0, 20),
    unclaimedNets: unclaimed.missing,
    duplicateNets: unclaimed.dupes,
    phaseSizes: phases.map((p) => ({ phaseIndex: p.phaseIndex, name: p.name, nets: (p.nets ?? []).length, budgetMs: p.budgetMs })),
    totalBudgetMs,
    boardBudgetCapMs: BOARD_BUDGET_CAP_MS,
    overBoardCap: totalBudgetMs > BOARD_BUDGET_CAP_MS,
  };
}

// validatePhases(phasesDoc, scan) -> { ok, errors[], warnings[] }
// Schema-level: every scan net claimed exactly once (no "remainder" phase),
// contiguous phaseIndex, per-phase budget within [floor, ceiling], total
// within the board cap.
export function validatePhases(phasesDoc, scan) {
  const errors = [];
  const warnings = [];
  if (!phasesDoc || typeof phasesDoc !== "object") {
    return { ok: false, errors: ["phases doc is not an object"], warnings };
  }
  if (phasesDoc.board !== scan.boardName) {
    errors.push(`phases.board '${phasesDoc.board}' != scan board '${scan.boardName}'`);
  }
  const phases = Array.isArray(phasesDoc.phases) ? phasesDoc.phases : [];
  if (phases.length === 0) errors.push("phases doc has no phases");
  const idx = phases.map((p) => p.phaseIndex).sort((a, b) => a - b);
  idx.forEach((v, k) => {
    if (v !== k) errors.push(`phaseIndex not contiguous: expected ${k}, saw ${v}`);
  });
  for (const p of phases) {
    if (!p.name) errors.push(`phase ${p.phaseIndex}: missing name (no anonymous remainder phases)`);
    if (!Array.isArray(p.nets)) errors.push(`phase ${p.phaseIndex}: nets not an array`);
    if (typeof p.budgetMs !== "number" || p.budgetMs < PHASE_BUDGET_FLOOR_MS || p.budgetMs > PHASE_BUDGET_CEIL_MS) {
      errors.push(
        `phase ${p.phaseIndex}: budgetMs ${p.budgetMs} outside [${PHASE_BUDGET_FLOOR_MS}, ${PHASE_BUDGET_CEIL_MS}]`,
      );
    }
    if (!p.autorouter) errors.push(`phase ${p.phaseIndex}: missing autorouter`);
  }
  const { missing, dupes } = unclaimedNets(scan, phases);
  for (const m of missing) errors.push(`unclaimed net '${m}' (every net must be claimed by a named phase)`);
  for (const d of dupes) errors.push(`net '${d}' claimed by more than one phase`);
  for (const c of new Set(phases.flatMap((p) => p.nets ?? []))) {
    if (!scan.connections.includes(c)) {
      warnings.push(`net '${c}' in phases but not in scan (stale?)`);
    }
  }
  const total = phases.reduce((s, p) => s + (p.budgetMs ?? 0), 0);
  if (total > BOARD_BUDGET_CAP_MS) {
    errors.push(`total phase budgets ${total}ms exceed board cap ${BOARD_BUDGET_CAP_MS}ms`);
  }
  const overlap = scoreCorridorOverlap(scan, phases);
  if (overlap.maxCrossPhaseCorridorOverlap > 0.5) {
    warnings.push(
      `maxCrossPhaseCorridorOverlap=${overlap.maxCrossPhaseCorridorOverlap} (>0.5: corridor-sharing nets split across phases — consider co-phasing)`,
    );
  }
  return { ok: errors.length === 0, errors, warnings };
}
