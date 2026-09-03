// `agent-route run-v2` — CLI-owned net-phase routing loop (v2, side-by-side
// with v1 lib/route-board.js which is UNTOUCHED).
//
// SPIKE VERDICT (installed @tscircuit/core v0.0.1816): Group_getRoutingPhasePlans
// is NOT exported and NOT externally controllable — phase membership derives
// from in-band `routingPhaseIndex` props inside the core render lifecycle, and
// per-phase `autorouter.algorithmFn(srj)` runs inside core's opaque
// _runLocalAutorouting. There is no API to pass per-phase net sets or a custom
// algorithmFn from outside. So per the task fallback: the phase loop is
// CLI-owned here in route-v2, reusing v1 scan/sig/DRC helpers read-only,
// with native filter/merge semantics reimplemented outside core:
//
//   per phase: full SRJ, connections restricted to the phase's SRJ name set,
//   ALL locked traces carried, bounds = phase region (net-derived corridor
//   bbox; null = full board).
//
// TRUE ROOT CAUSE this fixes (v1 lib/route-lib.js buildSectionSrj):
//   `bounds = rect` — the solver is FORBIDDEN from leaving the rect, not
//   merely dodging frozen S1 copper. v1's 0.17mm overlap band gives two
//   independent escape plans no shared room by construction. v2 bounds are
//   NET-derived per phase (region = corridor-bbox union of the phase's own
//   nets + margin; null collapses to full board) — a region always contains
//   its nets' escape corridors, so the 8bit sliver-band pathology cannot
//   recur, while the solver still gets steering (drive lesson: corridor
//   bounds route clean where full-board bounds wander into locked tails).
//
// Gates: cumulative locked x new against the FULL-BOARD merged circuit every
// phase (no filterCircuitToRect, no stripFarMissingConnections hacks — those
// die here). A passed phase is NEVER auto-ripped-up: fail = FAIL-STOP with
// blockedNets/implicatedRefs per design §4.5, or a re-phase suggestion.
// Re-phase loop cap 2; total board budget cap ~15min.
//
// P0 SMOKE TEST: phase 0 (infra) must pass a routability smoke test (gated +
// promoted to locked) before any signal phase runs.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  ROUTER_PARAMS,
  SRC_DIR,
  SUBCIRCUIT_ID,
  distCircuit,
  readJson,
  routedJsonPath,
} from "./constants.js";
import { MAX_REPHASE_ROUNDS, BOARD_BUDGET_CAP_MS, PHASE_BUDGET_CEIL_MS } from "./plan-v2.js";
import { loadScanFromCircuitJson } from "./scan.js";
import {
  classifyError,
  mergeLockedRecords,
  newTracesFromOutput,
  resolveSectionConns,
  solveWithDeadline,
  stitchSrj,
  stripConnectivityErrors,
  summarizeDrc,
  toLockRecords,
} from "./route-lib.js";

export function phasesPath(board) {
  // Side-by-side with the v1 plan: src/<board>/<board>.agent-phases.json.
  // (constants.js is a v1 file — do NOT extend it; keep v1 untouched.)
  return join(SRC_DIR, board, `${board}.agent-phases.json`);
}

export function phaseStatusPath(board) {
  return join(SRC_DIR, board, `${board}.agent-route-v2`, "status.json");
}

export function phaseDir(board) {
  return join(SRC_DIR, board, `${board}.agent-route-v2`);
}

function writeJsonAtomic(p, obj, pretty = false) {
  mkdirSync(join(p, ".."), { recursive: true });
  const tmp = `${p}.tmp-${process.pid}`;
  writeFileSync(tmp, pretty ? JSON.stringify(obj, null, 2) + "\n" : JSON.stringify(obj));
  renameSync(tmp, p);
}

function phaseFile(board, phaseIndex, name) {
  return join(phaseDir(board), `P${phaseIndex}.${name}.agent-route-v2.json`);
}

function newPhaseStatus(board) {
  return { version: 2, board, completed: [], blocked: null, blockedPhases: [], phases: {} };
}

function readPhaseStatusFile(board) {
  const p = phaseStatusPath(board);
  if (!existsSync(p)) return newPhaseStatus(board);
  try {
    return readJson(p);
  } catch {
    return newPhaseStatus(board);
  }
}

export async function routeBoardV2(board, opts = {}) {
  const { json = false } = opts;
  const effort = opts.effort ?? 10;
  // Re-phase loop: on a phase DRC failure, merge the blocked phase's nets
  // into the most corridor-overlapping already-planned neighbour and retry
  // from the merge point (passed EARLIER phases are never ripped up — the
  // retry re-solves the merged set jointly against earlier locks). Cap 2.
  const maxRephase = opts.maxRephase ?? MAX_REPHASE_ROUNDS;
  const out = json ? () => {} : (...a) => console.log(...a);

  const cap = await import("@tscircuit/capacity-autorouter");
  const core = await import("@tscircuit/core");
  const checks = await import("@tscircuit/checks");

  const pFile = phasesPath(board);
  if (!existsSync(pFile)) {
    const msg = `INPUT_INVALID: no phases file at ${pFile} — run "agent-route plan-v2 ${board}" first`;
    if (json) console.log(JSON.stringify({ ok: false, error: msg }));
    else console.error(msg);
    return 2;
  }
  const phasesDoc = readJson(pFile);
  // NOTE: `phases` ALIASES phasesDoc.phases (same array + same objects) so
  // the re-phase loop's splice/renumber persists via the writeFileSync below.
  // Do NOT spread-copy here (a copy would silently drop re-phase edits).
  phasesDoc.phases = [...(phasesDoc.phases ?? [])].sort((a, b) => a.phaseIndex - b.phaseIndex);
  const phases = phasesDoc.phases;
  if (phases.length === 0) {
    console.error(`INPUT_INVALID: phases doc for ${board} has no phases`);
    return 2;
  }
  const totalBudget = phases.reduce((s, p) => s + (p.budgetMs ?? PHASE_BUDGET_CEIL_MS), 0);
  if (totalBudget > BOARD_BUDGET_CAP_MS) {
    console.error(
      `INPUT_INVALID: total phase budgets ${totalBudget}ms exceed board cap ${BOARD_BUDGET_CAP_MS}ms — re-phase first`,
    );
    return 2;
  }

  const dist = distCircuit(board);
  if (!existsSync(dist)) {
    console.error(`INPUT_INVALID: no routing-disabled eval at ${dist} — run "agent-route plan-v2 ${board}" first`);
    return 2;
  }
  const fresh = readJson(dist);
  const scan = loadScanFromCircuitJson(board, dist);

  let fullSrj;
  try {
    fullSrj = core.getSimpleRouteJsonFromCircuitJson({
      circuitJson: fresh,
      subcircuit_id: SUBCIRCUIT_ID,
    }).simpleRouteJson;
  } catch (e) {
    console.error(`INPUT_INVALID: getSimpleRouteJsonFromCircuitJson threw: ${String(e?.message ?? e).slice(0, 300)}`);
    return 2;
  }
  // Bounds per phase: net-derived region when the planner computed one,
  // else full board. (v1 `bounds = rect` died here: the planner's rect could
  // forbid escape. A v2 region always contains its nets' own corridors.)
  const boardBounds = { ...fullSrj.bounds };
  const boundsFor = (phase) =>
    phase.region && typeof phase.region.minX === "number" ? { ...phase.region } : { ...boardBounds };
  const status = readPhaseStatusFile(board);
  let lockedSrjTraces = [];
  let lockedCircuitRecords = [];
  const handledSrj = new Set();

  for (const p of phases) {
    if ((p.status ?? "pending") !== "done") continue;
    const f = phaseFile(board, p.phaseIndex, p.name ?? `phase-${p.phaseIndex}`);
    if (!existsSync(f)) {
      out(`! P${p.phaseIndex}: marked done but phase file missing — re-queueing as pending`);
      p.status = "pending";
      continue;
    }
    const saved = readJson(f);
    for (const r of saved.lockedRecords ?? []) {
      lockedCircuitRecords.push(r);
      if (r.connection_name) handledSrj.add(r.connection_name);
    }
    for (const t of saved.srjTraces ?? []) lockedSrjTraces.push(t);
  }

  const boardT0 = Date.now();
  const state = { lockedSrjTraces, lockedCircuitRecords, handledSrj, blockedNow: [] };

  const rebuildLocksBelow = (keepBelow) => {
    // Keep locks strictly below keepBelow (earlier dones survive — never rip
    // up a pass); everything at/after is re-queued as pending.
    state.lockedSrjTraces = [];
    state.lockedCircuitRecords = [];
    state.handledSrj.clear();
    for (const q of phases) {
      if ((q.status ?? "pending") !== "done" || q.phaseIndex >= keepBelow) {
        if (q.phaseIndex >= keepBelow) q.status = "pending";
        continue;
      }
      const f = phaseFile(board, q.phaseIndex, q.name ?? `phase-${q.phaseIndex}`);
      if (!existsSync(f)) { q.status = "pending"; continue; }
      const saved = readJson(f);
      for (const r of saved.lockedRecords ?? []) {
        state.lockedCircuitRecords.push(r);
        if (r.connection_name) state.handledSrj.add(r.connection_name);
      }
      for (const t of saved.srjTraces ?? []) state.lockedSrjTraces.push(t);
    }
    writeFileSync(pFile, JSON.stringify(phasesDoc, null, 2) + "\n");
  };

  const runPendingPhases = async () => {
    const runOrder = phases
      .filter((p) => (p.status ?? "pending") !== "done")
      .sort((a, b) => a.phaseIndex - b.phaseIndex);
    for (const p of runOrder) {
      if (Date.now() - boardT0 > BOARD_BUDGET_CAP_MS) {
        out(`❌ [${board}] board budget cap hit before P${p.phaseIndex} — FAIL-STOP (mis-grouped, re-phase)`);
        return failStop(board, status, p, {
          errorClass: "TIMEOUT",
          error: `board budget cap ${BOARD_BUDGET_CAP_MS}ms hit`,
          blockedConnections: [...(p.nets ?? [])],
        }, state.blockedNow, out, json);
      }
      out(`==> [${board}] routing P${p.phaseIndex} (${p.name ?? ""}) ${(p.nets ?? []).length} nets, budget=${p.budgetMs}ms ...`);
      const t0 = Date.now();
      const res = await routeOnePhase({
        scan,
        phase: p,
        fullSrj,
        phaseBounds: boundsFor(p),
        fresh,
        lockedSrjTraces: state.lockedSrjTraces,
        lockedCircuitRecords: state.lockedCircuitRecords,
        handledSrj: state.handledSrj,
        cap,
        checks,
        effort,
        out,
      });
      const ms = Date.now() - t0;
      if (res.ok) {
        state.lockedCircuitRecords.push(...res.lockRecords);
        state.lockedSrjTraces.push(...res.srjTraces);
        for (const c of res.handledSrj) state.handledSrj.add(c);
        p.status = "done";
        writeFileSync(pFile, JSON.stringify(phasesDoc, null, 2) + "\n");
        writePhaseFile(board, p, res, { effort });
        if (!status.completed.includes(p.phaseIndex)) status.completed.push(p.phaseIndex);
        status.phases[p.phaseIndex] = {
          status: "done",
          name: p.name,
          ms,
          attempts: res.attempts,
          effort,
          budgetMs: p.budgetMs,
          nets: res.handledSrj.length,
          ...(p.phaseIndex === 0 ? { smoke: res.smoke } : {}),
        };
        writeJsonAtomic(phaseStatusPath(board), status, true);
        out(`    ✅ P${p.phaseIndex} done: ${res.lockRecords.length} traces, ${ms}ms (budget ${p.budgetMs}ms)`);
        if (p.phaseIndex === 0) {
          out(`    ✅ P0 infra smoke: ${res.smoke.nets} nets, ${res.smoke.traces} traces, ${res.smoke.drcErrors} DRC — signal phases unlocked`);
        }
        continue;
      }
      // Re-phase loop (cap maxRephase): merge the blocked phase's nets into
      // the most corridor-overlapping PENDING neighbour and retry from the
      // merge point. Passed (done) phases are never ripped up — the merged
      // retry solves jointly against earlier locks. This is the answer to
      // joint-greedy pairs (drive INPUT1 x V_SUPPLY): some nets can ONLY be
      // solved jointly, so the loop co-phases them instead of failing stop.
      const merged = tryMergeBlockedPhase({ phases, blockedPhase: p, scan });
      if (merged && (status.rephaseRounds ?? 0) < maxRephase) {
        const round = (status.rephaseRounds ?? 0) + 1;
        status.rephaseRounds = round;
        out(`    ↻ P${p.phaseIndex} blocked (${res.errorClass}) — re-phase round ${round}/${maxRephase}: merged into P${merged.into} (${merged.nets} nets jointly)`);
        writeJsonAtomic(phaseStatusPath(board), status, true);
        rebuildLocksBelow(Math.min(p.phaseIndex, merged.into));
        return runPendingPhases();
      }
      state.blockedNow.push(p.phaseIndex);
      status.phases[p.phaseIndex] = {
        status: "blocked",
        name: p.name,
        ms,
        attempts: res.attempts ?? 1,
        effort,
        budgetMs: p.budgetMs,
        blockedConnections: res.blockedConnections,
        blockedNets: res.blockedConnections,
        implicatedRefs: res.implicatedRefs,
        errorClass: res.errorClass,
        drcErrors: res.drcErrors,
        suggestion: res.suggestion ?? rephaseSuggestion(p, res, maxRephase - (status.rephaseRounds ?? 0)),
      };
      // Never auto-rip-up a passed phase: FAIL-STOP, keep last-good.
      status.blocked = p.phaseIndex;
      status.blockedPhases = state.blockedNow;
      Object.assign(status, {
        blockedNets: res.blockedConnections ?? [],
        implicatedRefs: res.implicatedRefs ?? [],
        errorClass: res.errorClass ?? "NO_PATH",
        drcErrors: res.drcErrors ?? [],
        suggestion: status.phases[p.phaseIndex].suggestion,
      });
      writeJsonAtomic(phaseStatusPath(board), status, true);
      printPhaseFailStop({ board, status, out, json });
      return 1;
    }
    return null; // all pending phases done
  };

  const pendingCode = await runPendingPhases();
  if (pendingCode !== null) return pendingCode;

  status.blocked = null;
  writeJsonAtomic(phaseStatusPath(board), status, true);
  const finalCode = await finalizeBoardV2({ board, fresh, lockedCircuitRecords: state.lockedCircuitRecords, checks, out, status });
  if (json) console.log(JSON.stringify({ board, ok: finalCode === 0, status }, null, 2));
  return finalCode;
}

// Re-phase helper: merge the blocked phase's nets into the most
// corridor-overlapping PENDING neighbour phase (later phase preferred —
// earlier DONEs are never touched). Renumbers phases contiguously, re-derives
// the merged budget adaptively. Returns { into, nets } or null when no
// pending neighbour exists (FAIL-STOP instead).
import { netCorridor as corridorOf, budgetForPhase, regionForNets } from "./plan-v2.js";

function tryMergeBlockedPhase({ phases, blockedPhase, scan }) {
  const pending = phases
    .filter((q) => q.phaseIndex !== blockedPhase.phaseIndex && (q.status ?? "pending") !== "done")
    .sort((a, b) => a.phaseIndex - b.phaseIndex);
  if (pending.length === 0) return null;
  const bCorr = (blockedPhase.nets ?? []).map((n) => corridorOf(scan, n));
  const overlap = (q) => {
    let w = 0;
    for (const n of q.nets ?? []) {
      const c = corridorOf(scan, n);
      for (const b of bCorr) {
        if (c.minX <= b.maxX && b.minX <= c.maxX && c.minY <= b.maxY && b.minY <= c.maxY) w++;
      }
    }
    return w;
  };
  // Prefer a LATER pending neighbour (keeps phase order stable); tie-break by
  // corridor overlap.
  const later = pending.filter((q) => q.phaseIndex > blockedPhase.phaseIndex);
  const cands = later.length > 0 ? later : pending;
  let best = cands[0];
  let bestW = -1;
  for (const q of cands) {
    const w = overlap(q);
    if (w > bestW) { bestW = w; best = q; }
  }
  const intoIdx = phases.findIndex((q) => q.phaseIndex === best.phaseIndex);
  const blkIdx = phases.findIndex((q) => q.phaseIndex === blockedPhase.phaseIndex);
  const keepIdx = Math.min(intoIdx, blkIdx);
  const dropIdx = Math.max(intoIdx, blkIdx);
  const mergedNets = [...new Set([...(phases[keepIdx].nets ?? []), ...(phases[dropIdx].nets ?? [])])].sort();
  const kept = phases[keepIdx];
  kept.nets = mergedNets;
  kept.name = kept.name ?? `signal-${keepIdx}`;
  kept.budgetMs = budgetForPhase(mergedNets.length);
  kept.status = "pending";
  // Recompute the joint region from the merged net set (wider room for the
  // joint retry; regionForNets collapses to null/full-board past 90%).
  try {
    kept.region = regionForNets(scan, mergedNets);
  } catch {
    kept.region = null;
  }
  phases.splice(dropIdx, 1);
  // Renumber contiguously (phaseIndex = execution order).
  phases
    .sort((a, b) => a.phaseIndex - b.phaseIndex)
    .forEach((q, i) => { q.phaseIndex = i; if ((q.status ?? "pending") !== "done") q.status = "pending"; });
  return { into: kept.phaseIndex, nets: mergedNets.length };
}

function failStop(board, status, phase, res, blockedNow, out, json) {  blockedNow.push(phase.phaseIndex);
  status.phases[phase.phaseIndex] = {
    status: "blocked",
    name: phase.name,
    blockedConnections: res.blockedConnections,
    blockedNets: res.blockedConnections,
    implicatedRefs: res.implicatedRefs ?? [],
    errorClass: res.errorClass,
    drcErrors: res.drcErrors ?? [],
    suggestion: res.suggestion ?? rephaseSuggestion(phase, res, 0),
  };
  status.blocked = phase.phaseIndex;
  status.blockedPhases = blockedNow;
  writeJsonAtomic(phaseStatusPath(board), status, true);
  printPhaseFailStop({ board, status, out, json });
  return 1;
}

async function routeOnePhase({
  scan,
  phase,
  fullSrj,
  phaseBounds,
  fresh,
  lockedSrjTraces,
  lockedCircuitRecords,
  handledSrj,
  cap,
  checks,
  effort,
  out,
}) {
  // Scan-conn (plan-level) -> SRJ names via the v1 resolver (read-only reuse).
  const { srjNames, uncovered } = resolveSectionConns(phase.nets, scan, fresh);
  if (uncovered.length > 0) {
    return {
      ok: false,
      errorClass: "INPUT_INVALID",
      error: `${uncovered.length} phase net(s) match no SRJ nets: ${uncovered.slice(0, 5).join("; ")}`,
      blockedConnections: uncovered,
      implicatedRefs: uncovered.slice(0, 20),
      drcErrors: [],
      attempts: 0,
    };
  }
  const names = srjNames.filter((n) => !handledSrj.has(n));
  if (names.length === 0) {
    return { ok: true, lockRecords: [], srjTraces: [], handledSrj: [], attempts: 0, smoke: emptySmoke() };
  }
  const srjSet = new Set(fullSrj.connections.map((c) => c.name));
  const routable = names.filter((n) => srjSet.has(n));
  const preconnected = names.filter((n) => !srjSet.has(n));
  // Ownership = routable conns actually solved now + preconnected fragments
  // belonging to THIS phase's nets. A phase whose nets all resolved to
  // already-handled SRJ names owns nothing (no double-count of srjConns).
  const ownedNow = [...routable, ...preconnected.filter((n) => !handledSrj.has(n))];
  if (routable.length === 0) {
    return { ok: true, lockRecords: [], srjTraces: [], handledSrj: ownedNow, attempts: 0, smoke: emptySmoke() };
  }

  // Phase SRJ: connections restricted to this phase's net set, ALL locked
  // traces carried, bounds = the phase's net-derived region (or full board
  // when region is null). No planner rect anywhere.
  const phaseSrj = {
    ...structuredClone(fullSrj),
    bounds: { ...phaseBounds },
    connections: structuredClone(fullSrj.connections.filter((c) => routable.includes(c.name))),
    traces: structuredClone(lockedSrjTraces),
  };

  // v2 has NO deferral: every net is claimed by exactly one named phase
  // (validator-enforced), so cross-phase nets cannot exist. Any phase SRJ
  // connection not in the full SRJ is pre-connected copper, handled above.
  const budgetMs = phase.budgetMs ?? PHASE_BUDGET_CEIL_MS;
  const sol = solveWithDeadline(cap.AutoroutingPipelineSolver9_PreloadedTraceGraph, phaseSrj, {
    effort,
    timeoutMs: budgetMs,
  });
  if (!sol.ok) {
    const errorClass = classifyError({ solverError: sol.error, timedOut: sol.timedOut });
    return {
      ok: false,
      errorClass,
      error: String(sol.error ?? "failed").slice(0, 300),
      blockedConnections: [...routable],
      implicatedRefs: implicatedRefsFor(routable),
      drcErrors: [],
      attempts: 1,
      suggestion: rephaseSuggestion(phase, { errorClass }, MAX_REPHASE_ROUNDS),
    };
  }
  const newSrj = newTracesFromOutput(sol.outputSrj, lockedSrjTraces);
  // handledNames = what THIS phase takes ownership of: routed-now conns +
  // preconnected fragments NOT already handled by an earlier phase.
  const ownedPre = preconnected.filter((n) => !handledSrj.has(n));
  return finishPhase({
    phase,
    fullSrj,
    fresh,
    checks,
    cap,
    lockedSrjTraces,
    lockedCircuitRecords,
    newSrjTraces: newSrj,
    handledNames: [...routable, ...ownedPre],
    attempts: 1,
    out,
  });
}

async function finishPhase({
  phase,
  fullSrj,
  fresh,
  checks,
  cap,
  lockedSrjTraces,
  lockedCircuitRecords,
  newSrjTraces,
  handledNames,
  attempts,
  out,
}) {
  const { records, unmapped } = toLockRecords({
    newTraces: newSrjTraces,
    circuitJson: fresh,
    sectionId: `P${phase.phaseIndex}`,
  });
  if (unmapped > 0) {
    return {
      ok: false,
      errorClass: "STITCH_MISMATCH",
      error: `${unmapped} new traces reference unknown nets (stitch mismatch)`,
      blockedConnections: handledNames,
      implicatedRefs: implicatedRefsFor(handledNames),
      drcErrors: [],
      attempts,
    };
  }
  try {
    stitchSrj(cap, fullSrj, lockedSrjTraces, newSrjTraces);
  } catch (e) {
    return {
      ok: false,
      errorClass: "STITCH_MISMATCH",
      error: `stitch threw: ${String(e?.message ?? e).slice(0, 300)}`,
      blockedConnections: handledNames,
      implicatedRefs: implicatedRefsFor(handledNames),
      drcErrors: [],
      attempts,
    };
  }
  // CUMULATIVE gate: locked-priors + new against the FULL-BOARD merged
  // circuit. This is the v1-blindness fix — locked-vs-new is checked at
  // EVERY phase, not just the final merge. No rect scoping, no
  // stripFarMissingConnections: a missing connection here is real (every
  // net is owned by exactly one phase, so no far-branch scope artefact).
  const merged = mergeLockedRecords(fresh, [...lockedCircuitRecords, ...records]);
  const errors = await checks.runAllRoutingChecks(merged);
  const real = stripConnectivityErrors(errors);
  if (real.length > 0) {
    const errorClass = classifyError({ drcErrors: real });
    void out;
    return {
      ok: false,
      errorClass,
      error: `${real.length} DRC error(s) in cumulative P${phase.phaseIndex} gate (locked x new, full board)`,
      blockedConnections: handledNames,
      implicatedRefs: implicatedRefsFor(handledNames),
      drcErrors: summarizeDrc(real),
      attempts,
      suggestion: rephaseSuggestion(phase, { errorClass }, MAX_REPHASE_ROUNDS),
    };
  }
  const smoke =
    phase.phaseIndex === 0
      ? { pass: true, nets: handledNames.length, traces: records.length, drcErrors: 0 }
      : undefined;
  return {
    ok: true,
    lockRecords: records,
    srjTraces: structuredClone(newSrjTraces),
    handledSrj: handledNames,
    attempts,
    ...(smoke ? { smoke } : { smoke: emptySmoke() }),
  };
}

function emptySmoke() {
  return { pass: true, nets: 0, traces: 0, drcErrors: 0, note: "no-unhandled-connections" };
}

function implicatedRefsFor(names) {
  return [...new Set(names)].slice(0, 20);
}

function rephaseSuggestion(phase, res, roundsLeft) {
  const cls = res?.errorClass ?? "NO_PATH";
  if (cls === "TIMEOUT") {
    return (
      `P${phase.phaseIndex} overran its ${phase.budgetMs}ms budget — overrun = mis-grouped, ` +
      `re-phase (co-phase its corridor-sharing nets, cap ${MAX_REPHASE_ROUNDS} rounds, ${roundsLeft} left), do NOT just raise the budget`
    );
  }
  return (
    `re-phase the P${phase.phaseIndex} net set (corridor-affinity: merge with the overlapping phase), ` +
    `never rip up a passed phase; see blockedNets/implicatedRefs`
  );
}

function printPhaseFailStop({ board, status, out, json }) {
  if (json) {
    console.log(JSON.stringify(status, null, 2));
    return;
  }
  out(`\n❌ [${board}] v2 BLOCKED at P${status.blocked} (${status.errorClass}) — passed phases kept (no auto-rip-up)`);
  out(`   completed: ${(status.completed ?? []).join(", ") || "(none)"}`);
  out(`   blocked nets: ${(status.blockedNets ?? []).join(", ")}`);
  out(`   suggestion: ${status.suggestion}`);
  out(`   full report: ${phaseStatusPath(board)}`);
}

function writePhaseFile(board, phase, res, routerParams) {
  const f = phaseFile(board, phase.phaseIndex, phase.name ?? `phase-${phase.phaseIndex}`);
  writeJsonAtomic(f, {
    version: 2,
    board,
    phase: phase.phaseIndex,
    name: phase.name,
    nets: phase.nets,
    bounds: phase.region ?? "full-board",
    srjConns: res.handledSrj,
    lockedRecords: res.lockRecords,
    srjTraces: res.srjTraces,
    attempts: res.attempts,
  });
  const sig = createHash("sha256")
    .update(JSON.stringify({ board, phase: phase.phaseIndex, nets: [...phase.nets].sort(), routerParams, versions: "v2" }))
    .digest("hex");
  writeFileSync(f.replace(/\.json$/, ".sig"), sig + "\n");
}

async function finalizeBoardV2({ board, fresh, lockedCircuitRecords, checks, out, status }) {
  const merged = mergeLockedRecords(fresh, lockedCircuitRecords);
  const routingErrors = await checks.runAllRoutingChecks(merged);
  const real = stripConnectivityErrors(routingErrors);
  if (real.length > 0) {
    out(`❌ [${board}] v2 phases clean but ${real.length} DRC error(s) on merged board`);
    for (const e of summarizeDrc(real, 10)) out(`   - ${e.type}: ${e.message}`);
    status.finalDrc = { ok: false, errors: summarizeDrc(real) };
    writeJsonAtomic(phaseStatusPath(board), status, true);
    return 1;
  }
  const all = await checks.runAllChecks(merged);
  const blocking = all.filter((e) => !String(e.type).endsWith("_warning"));
  if (blocking.length > 0) {
    out(`❌ [${board}] v2 final DRC gate: ${blocking.length} error(s) — NOT promoting *.routed.json`);
    for (const e of summarizeDrc(blocking, 15)) out(`   - ${e.type}: ${e.message}`);
    status.finalDrc = { ok: false, errors: summarizeDrc(blocking) };
    writeJsonAtomic(phaseStatusPath(board), status, true);
    return 1;
  }
  // Promote to a v2-suffixed artifact — never overwrite the v1 *.routed.json
  // (v1 stays runnable; promotion to default only after the 8bit pilot).
  const rp = routedJsonPath(board).replace(/\.routed\.json$/, ".routed-v2.json");
  writeJsonAtomic(rp, merged, true);
  const sig = createHash("sha256").update(JSON.stringify(merged)).digest("hex");
  writeFileSync(rp + ".sig", sig + "\n");
  out(`✅ [${board}] v2 DRC-clean — promoted ${board}.routed-v2.json (${lockedCircuitRecords.length} locked traces)`);
  status.finalDrc = { ok: true, errors: [] };
  status.routedJson = join("src", board, `${board}.routed-v2.json`);
  writeJsonAtomic(phaseStatusPath(board), status, true);
  return 0;
}
export { resolveSectionConns };
