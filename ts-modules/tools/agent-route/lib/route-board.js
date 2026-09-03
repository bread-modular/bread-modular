// `agent-route run` — route pending plan sections in phaseIndex order (§4.3).
//
// Per section: scan-conn resolution → full SRJ → hand-built section SRJ
// (section's SRJ conns + locked traces, bounds = rect) → capacity-autorouter
// pipeline via step() loop with iteration cap + wall-clock deadline →
// stitch+lock → section file + sig → plan status → done.
//
// Failure/timeout → fail-stop default (non-zero exit, NO partial write of the
// blocked section, keep last-good) or --keep-going (skip, route rest, report
// ALL blocked). Auto-bisect ON by default (depth ≤ 2, halve longest axis,
// re-assign conns by endpoint, record sub-sections in status.json);
// --no-bisect disables.
//
// Phase order: the plan's phaseIndex already encodes it (planner sorts
// densest-first; global power/GND nets were excluded from affinity so
// power-heavy sections sort first). No auto-derived pseudo-phase: plan files
// are the CLI chat's format — keep them stable, route what's there.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  MARGIN,
  ROUTER_PARAMS,
  SUBCIRCUIT_ID,
  distCircuit,
  planPath,
  readJson,
  routedJsonPath,
  sectionDir,
  statusPath,
} from "./constants.js";
import { loadScanFromCircuitJson } from "./scan.js";
import { sigForSection, verifySectionSig } from "./sig.js";
import {
  buildSectionSrj,
  classifyError,
  filterCircuitToRect,
  mergeLockedRecords,
  newTracesFromOutput,
  resolveSectionConns,
  solveWithDeadline,
  srjConnInRect,
  srjConnPoints,
  stitchSrj,
  stripConnectivityErrors,
  summarizeDrc,
  toLockRecords,
} from "./route-lib.js";

const DEFAULT_TIMEOUT_MS = 120000;
const DEFAULT_EFFORT = 10;
const DEFAULT_MAX_BISECT_DEPTH = 2;

function writeJsonAtomic(p, obj, pretty = false) {
  mkdirSync(join(p, ".."), { recursive: true });
  const tmp = `${p}.tmp-${process.pid}`;
  // pretty=true matches repo style (*.agent-plan.json, committed *.routed.json
  // are 2-space pretty-printed); section files stay compact (solver payloads).
  writeFileSync(tmp, pretty ? JSON.stringify(obj, null, 2) + "\n" : JSON.stringify(obj));
  renameSync(tmp, p);
}

function sectionFile(board, sectionId, name) {
  return join(sectionDir(board), `${sectionId}.${name}.agent-route.json`);
}

function readSigFile(sectionJsonPath) {
  try {
    return readFileSync(sectionJsonPath.replace(/\.json$/, ".sig"), "utf8").trim() || null;
  } catch {
    return null;
  }
}

function newStatus(board) {
  return { version: 1, board, completed: [], blocked: null, blockedSections: [], sections: {} };
}

function readStatusFile(board) {
  const p = statusPath(board);
  if (!existsSync(p)) return newStatus(board);
  try {
    return readJson(p);
  } catch {
    return newStatus(board);
  }
}

export async function routeBoard(board, opts = {}) {
  const { keepGoing = false, bisect = true, json = false } = opts;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const effort = opts.effort ?? DEFAULT_EFFORT;
  const maxBisectDepth = opts.maxBisectDepth ?? DEFAULT_MAX_BISECT_DEPTH;
  const routerParams = { ...ROUTER_PARAMS, effort, timeoutMs };

  const out = json ? () => {} : (...a) => console.log(...a);
  const cap = await import("@tscircuit/capacity-autorouter");
  const core = await import("@tscircuit/core");
  const checks = await import("@tscircuit/checks");

  const planFile = planPath(board);
  if (!existsSync(planFile)) {
    const msg = `INPUT_INVALID: no plan file at ${planFile} — run "agent-route plan ${board}" first`;
    if (json) console.log(JSON.stringify({ ok: false, error: msg }));
    else console.error(msg);
    return 2;
  }
  const plan = readJson(planFile);
  const sections = [...(plan.sections ?? [])].sort(
    (a, b) => (a.phaseIndex ?? 0) - (b.phaseIndex ?? 0),
  );
  if (sections.length === 0) {
    console.error(`INPUT_INVALID: plan for ${board} has no sections`);
    return 2;
  }
  const dist = distCircuit(board);
  if (!existsSync(dist)) {
    console.error(
      `INPUT_INVALID: no routing-disabled eval at ${dist} — run "agent-route plan ${board}" first`,
    );
    return 2;
  }
  const fresh = readJson(dist);
  const scan = loadScanFromCircuitJson(board, dist);

  // ---- resume: load done sections with valid sigs, assemble locked state ---
  const status = readStatusFile(board);
  let fullSrj;
  try {
    fullSrj = core.getSimpleRouteJsonFromCircuitJson({
      circuitJson: fresh,
      subcircuit_id: SUBCIRCUIT_ID,
    }).simpleRouteJson;
  } catch (e) {
    console.error(
      `INPUT_INVALID: getSimpleRouteJsonFromCircuitJson threw: ${String(e?.message ?? e).slice(0, 300)}`,
    );
    return 2;
  }

  let lockedSrjTraces = [];
  let lockedCircuitRecords = [];
  const handledSrj = new Set(); // SRJ conn names already locked

  for (const s of sections) {
    if ((s.status ?? "pending") !== "done") continue;
    const f = sectionFile(board, s.id, s.name);
    if (!existsSync(f)) {
      out(`! ${s.id}: marked done but section file missing — re-queueing as pending`);
      s.status = "pending";
      status.sections[s.id] = { ...(status.sections[s.id] ?? {}), status: "pending" };
      status.completed = status.completed.filter((id) => id !== s.id);
      continue;
    }
    const v = verifySectionSig(scan, s, readSigFile(f), { routerParams });
    if (!v.valid) {
      out(`! ${s.id}: sig ${v.reason} — re-queueing as pending`);
      s.status = "pending";
      status.sections[s.id] = { ...(status.sections[s.id] ?? {}), status: "pending" };
      status.completed = status.completed.filter((id) => id !== s.id);
      continue;
    }
    const saved = readJson(f);
    for (const r of saved.lockedRecords ?? []) {
      lockedCircuitRecords.push(r);
      if (r.connection_name) handledSrj.add(r.connection_name);
    }
    for (const t of saved.srjTraces ?? []) lockedSrjTraces.push(t);
  }

  const runOrder = sections.filter((s) => (s.status ?? "pending") !== "done");
  const blockedNow = [];

  for (const s of runOrder) {
    out(`==> [${board}] routing ${s.id} (${s.name ?? ""}) phase=${s.phaseIndex ?? 0} ...`);
    const t0 = Date.now();
    const res = await routeOneSection({
      scan,
      sections,
      section: s,
      fullSrj,
      fresh,
      lockedSrjTraces,
      lockedCircuitRecords,
      handledSrj,
      cap,
      checks,
      timeoutMs,
      effort,
      bisect,
      maxBisectDepth,
      out,
    });
    const ms = Date.now() - t0;
    if (res.ok) {
      lockedCircuitRecords.push(...res.lockRecords);
      lockedSrjTraces.push(...res.srjTraces);
      for (const c of res.handledSrj) handledSrj.add(c);
      s.status = "done";
      writeFileSync(planFile, JSON.stringify(plan, null, 2) + "\n");
      writeSectionFile(board, scan, s, res, routerParams);
      if (!status.completed.includes(s.id)) status.completed.push(s.id);
      status.sections[s.id] = {
        status: "done",
        ms,
        attempts: res.attempts,
        bisectDepth: res.bisectDepth,
        effort,
        timeoutMs,
        ...(res.subSections ? { subSections: res.subSections } : {}),
        ...(res.deferredConns ? { deferredConns: res.deferredConns } : {}),
      };
      writeJsonAtomic(statusPath(board), status, true);
      out(
        `    ✅ ${s.id} done: ${res.lockRecords.length} traces, ${ms}ms, attempts=${res.attempts}${res.bisectDepth ? ` bisectDepth=${res.bisectDepth}` : ""}`,
      );
    } else {
      blockedNow.push(s.id);
      status.sections[s.id] = {
        status: "blocked",
        ms,
        attempts: res.attempts,
        bisectDepth: res.bisectDepth,
        effort,
        timeoutMs,
        blockedConnections: res.blockedConnections,
        blockedRect: res.blockedRect,
        implicatedRefs: res.implicatedRefs,
        errorClass: res.errorClass,
        drcErrors: res.drcErrors,
        suggestion: suggestFix(s, res),
      };
      if (!keepGoing) {
        status.blocked = s.id;
        status.blockedSections = blockedNow;
        Object.assign(status, failStopFields(s, res));
        writeJsonAtomic(statusPath(board), status, true);
        printFailStop({ board, status, out, json });
        return 1;
      }
      out(`    ❌ ${s.id} blocked (${res.errorClass}) — continuing (--keep-going)`);
    }
  }

  if (blockedNow.length > 0) {
    status.blocked = blockedNow[0];
    status.blockedSections = blockedNow;
    Object.assign(status, failStopFields(sections.find((s) => s.id === blockedNow[0]), status.sections[blockedNow[0]]));
    writeJsonAtomic(statusPath(board), status, true);
    printFailStop({ board, status, out, json });
    return 1;
  }

  // All sections done → final gate: full runAllChecks must be zero-error
  // before *.routed.json promotion.
  status.blocked = null;
  writeJsonAtomic(statusPath(board), status, true);
  const finalCode = await finalizeBoard({ board, fresh, lockedCircuitRecords, checks, out, status });
  if (json) console.log(JSON.stringify({ board, ok: finalCode === 0, status }, null, 2));
  return finalCode;
}

async function routeOneSection({
  scan,
  sections,
  section,
  fullSrj,
  fresh,
  lockedSrjTraces,
  lockedCircuitRecords,
  handledSrj,
  cap,
  checks,
  timeoutMs,
  effort,
  bisect,
  maxBisectDepth,
  out,
}) {
  // Resolve the section's scan conns → SRJ names; minus already-handled.
  const { srjNames, uncovered } = resolveSectionConns(section.connections, scan, fresh);
  if (uncovered.length > 0) {
    return {
      ok: false,
      errorClass: "INPUT_INVALID",
      error: `${uncovered.length} plan connection(s) match no SRJ nets: ${uncovered.slice(0, 5).join("; ")}`,
      blockedConnections: uncovered,
      blockedRect: { ...section.rect },
      implicatedRefs: implicatedRefsFor(uncovered),
      drcErrors: [],
      attempts: 0,
      bisectDepth: 0,
    };
  }
  const names = srjNames.filter((n) => !handledSrj.has(n));
  if (names.length === 0) {
    return {
      ok: true,
      lockRecords: [],
      srjTraces: [],
      handledSrj: [],
      attempts: 0,
      bisectDepth: 0,
      note: "no-unhandled-connections",
    };
  }
  // The SRJ collapses already-connected fragments (pre-routed pcbStraightLine
  // rail bus, taps into powered nets) — only SRJ-present names are routable.
  // The rest is pre-connected copper, counted as handled (locked implicitly).
  const srjSet = new Set(fullSrj.connections.map((c) => c.name));
  const routable = names.filter((n) => srjSet.has(n));
  const preconnected = names.filter((n) => !srjSet.has(n));
  if (routable.length === 0) {
    return {
      ok: true,
      lockRecords: [],
      srjTraces: [],
      handledSrj: names,
      attempts: 0,
      bisectDepth: 0,
      note: `all-preconnected (${preconnected.length} already-connected fragments)`,
    };
  }
  const sectionSrj = buildSectionSrj(fullSrj, section.rect, routable, {
    lockedTraces: lockedSrjTraces,
  });
  // §8.5 boundary-port handoff: a net with endpoints outside this rect is
  // routed in the LATER section that owns its far endpoint (fixed target at
  // the earlier endpoint). Defer conns with <2 endpoints in-rect UNLESS every
  // owner section is already done (last section routes all leftovers).
  const inRect = (p) =>
    p.x >= section.rect.minX &&
    p.x <= section.rect.maxX &&
    p.y >= section.rect.minY &&
    p.y <= section.rect.maxY;
  const laterOwnerPending = (connName) => {
    for (const s of sections) {
      if (s.id === section.id) continue;
      if ((s.status ?? "pending") === "done") continue;
      if ((s.phaseIndex ?? 0) <= (section.phaseIndex ?? 0)) continue;
      const { srjNames } = resolveSectionConns(s.connections, scan, fresh);
      if (srjNames.includes(connName)) return true;
    }
    return false;
  };
  const deferred = [];
  sectionSrj.connections = sectionSrj.connections.filter((c) => {
    const nPts = srjConnPoints(c).length;
    const inside = srjConnPoints(c).filter(inRect).length;
    if (inside >= 2 || inside === nPts) return true;
    if (laterOwnerPending(c.name)) {
      deferred.push(c.name);
      return false;
    }
    return true;
  });
  if (deferred.length > 0) {
    out(`    … ${section.id}: deferring ${deferred.length} cross-section net(s) to later owner (§8.5): ${deferred.join(", ")}`);
  }
  // handledSrj for THIS section = routed now + preconnected + deferred-to-later
  // is NOT handled (a later owner will route it). Track routed set explicitly.
  const routedNow = new Set(sectionSrj.connections.map((c) => c.name));
  if (sectionSrj.connections.length === 0) {
    return {
      ok: false,
      errorClass: "INPUT_INVALID",
      error: `section SRJ has no connections after restriction (${routable.length} wanted, none in full SRJ)`,
      blockedConnections: [...routable],
      blockedRect: { ...section.rect },
      implicatedRefs: implicatedRefsFor(routable),
      drcErrors: [],
      attempts: 0,
      bisectDepth: 0,
    };
  }

  let attempts = 0;
  const attempt = (srj, ms) => {
    attempts++;
    return solveWithDeadline(cap.AutoroutingPipelineSolver9_PreloadedTraceGraph, srj, {
      effort,
      timeoutMs: ms ?? timeoutMs,
    });
  };

  const sol = attempt(sectionSrj);
  // handledNames = what THIS section takes ownership of: routed-now conns +
  // preconnected fragments. Deferred-to-later conns stay unhandled so the
  // later owner routes them (§8.5); the final gate catches anything orphaned.
  const ownedNow = [...routedNow, ...preconnected];
  // Greedy fallback (§4.3): the joint solve can fail the DRC gate even when a
  // subset routes clean (solver greed on shared corridors). Retry without each
  // gated conn, keep the first clean result; the dropped conn stays unhandled
  // for a later owner / retry.
  if (sol.ok && bisect && maxBisectDepth > 0) {
    const gate = await finishSection({
      section,
      fullSrj,
      fresh,
      checks,
      cap,
      lockedSrjTraces,
      lockedCircuitRecords,
      newSrjTraces: newTracesFromOutput(sol.outputSrj, lockedSrjTraces),
      handledNames: ownedNow,
      attempts,
      bisectDepth: 0,
    });
    if (gate.ok) return gate;
    if ((gate.drcErrors ?? []).length > 0) {
      out(`    ! ${section.id} gate failed (${gate.drcErrors.length} DRC) — greedy subset fallback`);
      const sub = await greedySubset({
        section,
        fullSrj,
        fresh,
        checks,
        cap,
        lockedSrjTraces,
        lockedCircuitRecords,
        routableNow: [...sectionSrj.connections.map((c) => c.name)],
        preconnected,
        attempt,
        out,
      });
      if (sub) return sub;
      // Fall through to fail-stop with the gate's report (more useful than
      // the solver report — the solver "succeeded" but geometry is bad).
      return { ...gate, attempts, bisectDepth: 0 };
    }
  }
  if (!sol.ok && bisect && maxBisectDepth > 0) {
    out(`    ! ${section.id} failed (${shortErr(sol.error)}) — auto-bisect (depth ≤ ${maxBisectDepth})`);
    const bis = await bisectSection({ section, sectionSrj, attempt, maxDepth: maxBisectDepth, out });
    attempts = bis.attempts;
    if (bis.ok) {
      return finishSection({
        section,
        fullSrj,
        fresh,
        checks,
        cap,
        lockedSrjTraces,
        lockedCircuitRecords,
        newSrjTraces: bis.newSrjTraces,
        handledNames: ownedNow,
        attempts,
        bisectDepth: bis.depth,
        subSections: bis.subSections,
      });
    }
    return {
      ok: false,
      ...classifyFailure(section, [...sectionSrj.connections.map((c) => c.name)], sol, maxBisectDepth),
      attempts,
      bisectDepth: maxBisectDepth,
    };
  }
  if (!sol.ok) {
    return {
      ok: false,
      ...classifyFailure(section, [...sectionSrj.connections.map((c) => c.name)], sol, 0),
      attempts,
      bisectDepth: 0,
    };
  }
  const newSrj = newTracesFromOutput(sol.outputSrj, lockedSrjTraces);
  return finishSection({
    section,
    fullSrj,
    fresh,
    checks,
    cap,
    lockedSrjTraces,
    lockedCircuitRecords,
    newSrjTraces: newSrj,
    handledNames: ownedNow,
    attempts,
    bisectDepth: 0,
  });
}

async function bisectSection({ section, sectionSrj, attempt, maxDepth, out }) {
  // Depth ≤ 2, halve longest axis, re-assign conns by endpoint.
  const queue = [{ rect: { ...section.rect }, depth: 0, label: section.id }];
  const subSections = [];
  let allNew = [];
  let attempts = 0;
  let maxReached = 0;
  while (queue.length > 0) {
    const cur = queue.shift();
    const conns = sectionSrj.connections.filter((c) => srjConnInRect(c, cur.rect));
    if (conns.length === 0) {
      subSections.push({ rect: cur.rect, status: "empty", conns: [] });
      continue;
    }
    const srj = {
      ...structuredClone(sectionSrj),
      bounds: { ...cur.rect },
      connections: structuredClone(conns),
    };
    const sol = attempt(srj);
    attempts++;
    if (sol.ok) {
      const fresh2 = newTracesFromOutput(sol.outputSrj, [...sectionSrj.traces, ...allNew]);
      allNew.push(...fresh2);
      sectionSrj.traces.push(...structuredClone(fresh2));
      maxReached = Math.max(maxReached, cur.depth);
      subSections.push({
        rect: cur.rect,
        status: "done",
        conns: conns.map((c) => c.name),
        traces: fresh2.length,
      });
      out(`    + bisect ${cur.label}: done (${conns.length} conns, ${fresh2.length} traces)`);
    } else if (cur.depth < maxDepth) {
      const [a, b] = splitRect(cur.rect);
      queue.push(
        { rect: a, depth: cur.depth + 1, label: `${cur.label}a` },
        { rect: b, depth: cur.depth + 1, label: `${cur.label}b` },
      );
      out(`    + bisect ${cur.label}: split (depth ${cur.depth + 1})`);
    } else {
      subSections.push({
        rect: cur.rect,
        status: "blocked",
        conns: conns.map((c) => c.name),
        error: shortErr(sol.error),
      });
      return { ok: false, attempts, depth: maxDepth, subSections };
    }
  }
  return { ok: true, attempts, depth: maxReached, subSections, newSrjTraces: allNew };
}

function splitRect(rect) {
  const w = rect.maxX - rect.minX;
  const h = rect.maxY - rect.minY;
  if (w >= h) {
    const mid = (rect.minX + rect.maxX) / 2;
    return [
      { ...rect, maxX: mid },
      { ...rect, minX: mid },
    ];
  }
  const mid = (rect.minY + rect.maxY) / 2;
  return [
    { ...rect, maxY: mid },
    { ...rect, minY: mid },
  ];
}

/**
 * Greedy subset fallback: retry the section solve once per omitted conn
 * (largest-geometry first — offender heuristic), keep the first result whose
 * DRC gate passes. The omitted conn stays unhandled for a later owner or a
 * targeted retry-section. Returns the finishSection result or null.
 */
async function greedySubset({
  section,
  fullSrj,
  fresh,
  checks,
  cap,
  lockedSrjTraces,
  lockedCircuitRecords,
  routableNow,
  preconnected,
  attempt,
  out,
}) {
  // Offender heuristic: conns with the most route points in the joint solve
  // output touch the most geometry — try dropping them first.
  const order = [...routableNow].sort((a, b) => {
    const pa = srjConnPoints(fullSrj.connections.find((c) => c.name === a) ?? { points: [] }).length;
    const pb = srjConnPoints(fullSrj.connections.find((c) => c.name === b) ?? { points: [] }).length;
    return pb - pa;
  });
  for (const drop of order) {
    const keep = routableNow.filter((n) => n !== drop);
    if (keep.length === 0) continue;
    const srj = buildSectionSrj(fullSrj, section.rect, keep, {
      lockedTraces: lockedSrjTraces,
    });
    const sol = attempt(srj);
    if (!sol.ok) {
      out(`    … greedy: without ${drop} solver failed — skipping`);
      continue;
    }
    const res = await finishSection({
      section,
      fullSrj,
      fresh,
      checks,
      cap,
      lockedSrjTraces,
      lockedCircuitRecords,
      newSrjTraces: newTracesFromOutput(sol.outputSrj, lockedSrjTraces),
      handledNames: [...keep, ...preconnected],
      attempts: 1,
      bisectDepth: 0,
    });
    if (res.ok) {
      res.deferredConns = [drop];
      out(`    + greedy: without ${drop} gate passes (${res.lockRecords.length} traces) — ${drop} left for later owner/retry`);
      return res;
    }
    out(`    … greedy: without ${drop} still ${res.drcErrors?.length ?? 0} DRC`);
  }
  return null;
}

async function finishSection({
  section,
  fullSrj,
  fresh,
  checks,
  cap,
  lockedSrjTraces,
  lockedCircuitRecords,
  newSrjTraces,
  handledNames,
  attempts,
  bisectDepth,
  subSections,
}) {
  const { records, unmapped } = toLockRecords({
    newTraces: newSrjTraces,
    circuitJson: fresh,
    sectionId: section.id,
  });
  if (unmapped > 0) {
    return {
      ok: false,
      errorClass: "STITCH_MISMATCH",
      error: `${unmapped} new traces reference unknown nets (stitch mismatch)`,
      blockedConnections: handledNames,
      blockedRect: { ...section.rect },
      implicatedRefs: implicatedRefsFor(handledNames),
      drcErrors: [],
      attempts,
      bisectDepth,
    };
  }
  // SRJ-level stitch sanity (reconnect maps reroute→root; identity here).
  try {
    stitchSrj(cap, fullSrj, lockedSrjTraces, newSrjTraces);
  } catch (e) {
    return {
      ok: false,
      errorClass: "STITCH_MISMATCH",
      error: `stitch threw: ${String(e?.message ?? e).slice(0, 300)}`,
      blockedConnections: handledNames,
      blockedRect: { ...section.rect },
      implicatedRefs: implicatedRefsFor(handledNames),
      drcErrors: [],
      attempts,
      bisectDepth,
    };
  }
  // Per-section DRC gate on rect ∪ margin (strip section-eval connectivity).
  // Scope rule (§6): the gate judges THIS section's new geometry. Prior
  // sections' locked records were gated when created; if an old locked trace
  // already violates inside this rect (e.g. a keepout the whole-board router
  // also has to cross), that is a board-level placement conflict, not a
  // verdict on the new traces. So: gate fresh + NEW records only. The
  // cumulative merge is still checked at the final gate (zero-error).
  const merged = mergeLockedRecords(fresh, records);
  const scoped = filterCircuitToRect(merged, section.rect, MARGIN);
  const errors = await checks.runAllRoutingChecks(scoped);
  const real = stripConnectivityErrors(errors);
  if (real.length > 0) {
    return {
      ok: false,
      errorClass: "DRC_CLEARANCE",
      error: `${real.length} DRC error(s) in ${section.id} rect ∪ margin`,
      blockedConnections: handledNames,
      blockedRect: { ...section.rect },
      implicatedRefs: implicatedRefsFor(handledNames),
      drcErrors: summarizeDrc(real),
      attempts,
      bisectDepth,
    };
  }
  return {
    ok: true,
    lockRecords: records,
    srjTraces: structuredClone(newSrjTraces),
    handledSrj: handledNames,
    attempts,
    bisectDepth,
    ...(subSections ? { subSections } : {}),
  };
}

export { resolveSectionConns };

function classifyFailure(section, names, sol, bisectDepth) {
  return {
    errorClass: classifyError({ solverError: sol.error, timedOut: sol.timedOut }),
    error: shortErr(sol.error),
    blockedConnections: names,
    blockedRect: { ...section.rect },
    implicatedRefs: implicatedRefsFor(names),
    drcErrors: [],
    bisectDepth,
  };
}

function implicatedRefsFor(names) {
  // SRJ conn names are source_trace_*/source_net_* ids — report them; the
  // status consumer maps nets → refs via the plan/scan.
  return [...new Set(names)].slice(0, 20);
}

function shortErr(e) {
  return String(e ?? "failed").slice(0, 160);
}

function failStopFields(section, res) {
  return {
    blockedRect: res.blockedRect ?? { ...(section?.rect ?? {}) },
    blockedConnections: res.blockedConnections ?? [],
    implicatedRefs: res.implicatedRefs ?? [],
    errorClass: res.errorClass ?? "NO_PATH",
    drcErrors: res.drcErrors ?? [],
    suggestion: suggestFix(section, res),
  };
}

function suggestFix(section, res) {
  const cls = res.errorClass ?? "NO_PATH";
  if (cls === "TIMEOUT")
    return `raise --timeout-ms / --effort for ${section?.id}, or bisect ${section?.id} into smaller rects`;
  if (cls === "DRC_CLEARANCE")
    return `move components in ${section?.id} rect apart or widen the rect; see drcErrors`;
  if (cls === "VIA_EXHAUSTED")
    return `reduce layer transitions in ${section?.id} (spread components, widen rect)`;
  if (cls === "INPUT_INVALID")
    return `re-run "agent-route plan validate" — plan/scan drift suspected; check blockedConnections`;
  return `check ${section?.id} rect covers its endpoints; try --keep-going to see the full board picture, or hand-edit the plan rect`;
}

function printFailStop({ board, status, out, json }) {
  if (json) {
    console.log(JSON.stringify(status, null, 2));
    return;
  }
  out(`\n❌ [${board}] BLOCKED at ${status.blocked} (${status.errorClass})`);
  out(`   completed: ${(status.completed ?? []).join(", ") || "(none)"}`);
  out(`   blocked rect: ${JSON.stringify(status.blockedRect)}`);
  out(`   blocked conns: ${(status.blockedConnections ?? []).join(", ")}`);
  out(`   suggestion: ${status.suggestion}`);
  out(`   full report: ${statusPath(board)}`);
}

function writeSectionFile(board, scan, section, res, routerParams) {
  const f = sectionFile(board, section.id, section.name ?? section.id);
  writeJsonAtomic(f, {
    version: 1,
    board,
    section: section.id,
    rect: section.rect,
    connections: section.connections,
    srjConns: res.handledSrj,
    lockedRecords: res.lockRecords,
    srjTraces: res.srjTraces,
    attempts: res.attempts,
    bisectDepth: res.bisectDepth,
    ...(res.deferredConns ? { deferredConns: res.deferredConns } : {}),
  });
  // Bare-hex .sig via the CLI chat's helper (single owner of sig inputs).
  writeFileSync(f.replace(/\.json$/, ".sig"), sigForSection(scan, section, { routerParams }) + "\n");
}

async function finalizeBoard({ board, fresh, lockedCircuitRecords, checks, out, status }) {
  const merged = mergeLockedRecords(fresh, lockedCircuitRecords);
  const routingErrors = await checks.runAllRoutingChecks(merged);
  const real = stripConnectivityErrors(routingErrors);
  if (real.length > 0) {
    out(`❌ [${board}] per-section routing clean but ${real.length} DRC error(s) on merged board`);
    for (const e of summarizeDrc(real, 10)) out(`   - ${e.type}: ${e.message}`);
    status.finalDrc = { ok: false, errors: summarizeDrc(real) };
    writeJsonAtomic(statusPath(board), status, true);
    return 1;
  }
  const all = await checks.runAllChecks(merged);
  // *_warning diagnostics are advisory, not routing failures (the committed
  // build.sh artifacts carry courtyard warnings DRC-clean).
  const blocking = all.filter((e) => !String(e.type).endsWith("_warning"));
  if (blocking.length > 0) {
    out(`❌ [${board}] final DRC gate: ${blocking.length} error(s) — NOT promoting *.routed.json`);
    for (const e of summarizeDrc(blocking, 15)) out(`   - ${e.type}: ${e.message}`);
    status.finalDrc = { ok: false, errors: summarizeDrc(blocking) };
    writeJsonAtomic(statusPath(board), status, true);
    return 1;
  }
  // Promote: merged board → src/<board>/<board>.routed.json (+ .routed.sig).
  // *.routed.json is a FULL circuit artifact (build.sh copies dist circuit.json
  // verbatim: fresh eval + routing). The merge above is exactly that shape —
  // fresh non-route elements + fresh route elements + locked records — so
  // downstream build.sh merge_routes + exports keep working. Pretty-printed
  // to match the committed file style.
  const rp = routedJsonPath(board);
  writeJsonAtomic(rp, merged, true);
  const sig = createHash("sha256").update(JSON.stringify(merged)).digest("hex");
  writeFileSync(rp + ".sig", sig + "\n");
  out(`✅ [${board}] DRC-clean — promoted ${board}.routed.json (${lockedCircuitRecords.length} locked traces)`);
  status.finalDrc = { ok: true, errors: [] };
  status.routedJson = rp;
  writeJsonAtomic(statusPath(board), status, true);
  return 0;
}
