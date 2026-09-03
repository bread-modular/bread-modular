// `agent-route retry-section <board> <sectionId>` — re-route ONE section with
// locked others untouched (sig-validated, §4.6).
//
//  1. Load plan + fresh eval + scan + full SRJ.
//  2. Load all done sections' locked records EXCEPT the target (target's old
//     output is dropped — full rip-up of that section only). A sig mismatch on
//     OTHERS → refuse (placement moved under a lock; re-run `run`) rather than
//     rebuild on stale geometry.
//  3. Route the target (same path as `run`: resolution → section SRJ → solver
//     with deadline; no bisect — a single-section retry that needs bisect
//     should go through `run` so sub-sections are recorded).
//  4. On success: overwrite the section file + sig, mark done. On failure:
//     keep last-good (old section file untouched), non-zero exit + report.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  MARGIN,
  ROUTER_PARAMS,
  SUBCIRCUIT_ID,
  distCircuit,
  planPath,
  readJson,
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
  stitchSrj,
  stripConnectivityErrors,
  stripFarMissingConnections,
  summarizeDrc,
  toLockRecords,
} from "./route-lib.js";

const DEFAULT_TIMEOUT_MS = 120000;
const DEFAULT_EFFORT = 10;

export async function retrySection(board, sectionId, opts = {}) {
  const { json = false } = opts;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const effort = opts.effort ?? DEFAULT_EFFORT;
  const routerParams = { ...ROUTER_PARAMS, effort, timeoutMs };
  const out = json ? () => {} : (...a) => console.log(...a);

  const cap = await import("@tscircuit/capacity-autorouter");
  const core = await import("@tscircuit/core");
  const checks = await import("@tscircuit/checks");

  const planFile = planPath(board);
  if (!existsSync(planFile)) {
    console.error(`INPUT_INVALID: no plan file at ${planFile} — run "agent-route plan ${board}" first`);
    return 2;
  }
  const plan = readJson(planFile);
  const section = (plan.sections ?? []).find((s) => s.id === sectionId);
  if (!section) {
    console.error(`INPUT_INVALID: no section ${sectionId} in plan for ${board}`);
    return 2;
  }
  const dist = distCircuit(board);
  if (!existsSync(dist)) {
    console.error(`INPUT_INVALID: no routing-disabled eval at ${dist}`);
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
    console.error(
      `INPUT_INVALID: getSimpleRouteJsonFromCircuitJson threw: ${String(e?.message ?? e).slice(0, 300)}`,
    );
    return 2;
  }

  // Locked others untouched (sig-validated against CURRENT routerParams — the
  // retry's params; a params change intentionally invalidates old locks).
  const lockedSrjTraces = [];
  const lockedCircuitRecords = [];
  const handledSrj = new Set();
  for (const s of plan.sections ?? []) {
    if (s.id === sectionId) continue;
    if ((s.status ?? "pending") !== "done") continue;
    const f = join(sectionDir(board), `${s.id}.${s.name}.agent-route.json`);
    if (!existsSync(f)) continue;
    let stored = null;
    try {
      stored = readFileSync(f.replace(/\.json$/, ".sig"), "utf8").trim() || null;
    } catch {
      stored = null;
    }
    const v = verifySectionSig(scan, s, stored, { routerParams });
    if (!v.valid) {
      console.error(
        `STITCH_MISMATCH: locked section ${s.id} sig invalid (${v.reason}) — re-run "agent-route run ${board}" to re-queue it; refusing to retry ${sectionId} on stale locks`,
      );
      return 1;
    }
    const saved = readJson(f);
    for (const r of saved.lockedRecords ?? []) {
      lockedCircuitRecords.push(r);
      if (r.connection_name) handledSrj.add(r.connection_name);
    }
    for (const t of saved.srjTraces ?? []) lockedSrjTraces.push(t);
  }

  const { srjNames, uncovered } = resolveSectionConns(section.connections, scan, fresh);
  if (uncovered.length > 0) {
    console.error(
      `INPUT_INVALID: ${uncovered.length} plan connection(s) match no SRJ nets: ${uncovered.slice(0, 5).join("; ")}`,
    );
    return 2;
  }
  const names = srjNames.filter((n) => !handledSrj.has(n));
  if (names.length === 0) {
    out(`== ${sectionId}: nothing unhandled (all conns locked by other sections)`);
    return 0;
  }
  const sectionSrj = buildSectionSrj(fullSrj, section.rect, names, {
    lockedTraces: lockedSrjTraces,
  });

  out(`==> [${board}] retry-section ${sectionId} (${names.length} SRJ conns) ...`);
  const t0 = Date.now();
  const sol = solveWithDeadline(cap.AutoroutingPipelineSolver9_PreloadedTraceGraph, sectionSrj, {
    effort,
    timeoutMs,
  });
  const ms = Date.now() - t0;
  if (!sol.ok) {
    // Keep last-good: do NOT touch the old section file.
    const errorClass = classifyError({ solverError: sol.error, timedOut: sol.timedOut });
    if (json) {
      console.log(
        JSON.stringify(
          { board, section: sectionId, ok: false, errorClass, error: sol.error, blockedConnections: names, ms },
          null,
          2,
        ),
      );
    } else {
      out(`❌ [${board}] ${sectionId} still blocked (${errorClass}): ${String(sol.error).slice(0, 300)}`);
      out(`   last-good kept; fix placement/rect, then retry again`);
    }
    updateStatusBlocked(board, sectionId, { ms, errorClass, names });
    return 1;
  }

  const newSrj = newTracesFromOutput(sol.outputSrj, lockedSrjTraces);
  const { records, unmapped } = toLockRecords({ newTraces: newSrj, circuitJson: fresh, sectionId });
  if (unmapped > 0) {
    console.error(`STITCH_MISMATCH: ${unmapped} new traces reference unknown nets — last-good kept`);
    return 1;
  }
  try {
    stitchSrj(cap, fullSrj, lockedSrjTraces, newSrj);
  } catch (e) {
    console.error(`STITCH_MISMATCH: stitch threw (${String(e?.message ?? e).slice(0, 200)}) — last-good kept`);
    return 1;
  }
  const merged = mergeLockedRecords(fresh, [...lockedCircuitRecords, ...records]);
  const scoped = filterCircuitToRect(merged, section.rect, MARGIN);
  const real = stripFarMissingConnections(
    stripConnectivityErrors(await checks.runAllRoutingChecks(scoped)),
    merged,
    section.rect,
    MARGIN,
  );
  if (real.length > 0) {
    console.error(`DRC_CLEARANCE: ${real.length} DRC error(s) in retried ${sectionId} — last-good kept`);
    for (const e of summarizeDrc(real, 10)) console.error(`   - ${e.type}: ${e.message}`);
    return 1;
  }

  // Success → overwrite section file + sig; mark done.
  const { mkdirSync, renameSync } = await import("node:fs");
  mkdirSync(sectionDir(board), { recursive: true });
  const f = join(sectionDir(board), `${section.id}.${section.name ?? section.id}.agent-route.json`);
  const tmp = `${f}.tmp-${process.pid}`;
  writeFileSync(
    tmp,
    JSON.stringify({
      version: 1,
      board,
      section: section.id,
      rect: section.rect,
      connections: section.connections,
      srjConns: names,
      lockedRecords: records,
      srjTraces: structuredClone(newSrj),
      attempts: 1,
      bisectDepth: 0,
      retriedAt: new Date().toISOString(),
    }),
  );
  renameSync(tmp, f);
  writeFileSync(f.replace(/\.json$/, ".sig"), sigForSection(scan, section, { routerParams }) + "\n");
  section.status = "done";
  writeFileSync(planFile, JSON.stringify(plan, null, 2) + "\n");
  markDone(board, sectionId, ms);
  out(`✅ [${board}] ${sectionId} re-routed: ${records.length} traces, ${ms}ms (others untouched)`);
  return 0;
}

function updateStatusBlocked(board, sectionId, { ms, errorClass, names }) {
  const p = statusPath(board);
  const st = existsSync(p) ? readJson(p) : { version: 1, board, completed: [], blocked: null, blockedSections: [], sections: {} };
  if (!st.sections) st.sections = {};
  st.sections[sectionId] = { status: "blocked", ms, attempts: 1, bisectDepth: 0 };
  st.blocked = sectionId;
  if (!st.blockedSections?.includes(sectionId)) {
    st.blockedSections = [...(st.blockedSections ?? []), sectionId];
  }
  st.blockedConnections = names;
  st.errorClass = errorClass;
  writeFileSync(p, JSON.stringify(st, null, 2) + "\n");
}

function markDone(board, sectionId, ms) {
  const p = statusPath(board);
  const st = existsSync(p) ? readJson(p) : { version: 1, board, completed: [], blocked: null, blockedSections: [], sections: {} };
  if (!st.sections) st.sections = {};
  if (!st.completed) st.completed = [];
  st.sections[sectionId] = { status: "done", ms, attempts: 1, bisectDepth: 0 };
  if (!st.completed.includes(sectionId)) st.completed.push(sectionId);
  st.blockedSections = (st.blockedSections ?? []).filter((id) => id !== sectionId);
  if (st.blocked === sectionId) st.blocked = st.blockedSections[0] ?? null;
  writeFileSync(p, JSON.stringify(st, null, 2) + "\n");
}
