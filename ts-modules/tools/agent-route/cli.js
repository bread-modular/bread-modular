#!/usr/bin/env node
// agent-route — agent-native section autorouter CLI (design §4.7).
//
//   agent-route plan <board> [--json]              scan + print plan + scoring, write *.agent-plan.json
//   agent-route plan validate <board> [--json]     re-check a hand-edited plan
//   agent-route status <board> [--json]            section states + sig validity + timings
//   agent-route drc <board> [--json]               full-board runAllChecks gate
//   agent-route run <board> ...                    OWNED BY ANOTHER CHAT (stub, exit 2)
//   agent-route retry-section <board> S..          OWNED BY ANOTHER CHAT (stub, exit 2)
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadScanFromCircuitJson, runRoutingDisabledEval } from "./lib/scan.js";
import { buildPlan, validatePlan, scorePlan } from "./lib/plan.js";
import { sigForSection, verifySectionSig } from "./lib/sig.js";
import {
  OVERLAP,
  SRC_DIR,
  distCircuit,
  planPath,
  routedJsonPath,
  sectionDir,
  statusPath,
  readJson,
} from "./lib/constants.js";

const args = process.argv.slice(2);
const jsonOut = args.includes("--json");
const pos = args.filter((a) => !a.startsWith("--"));

function emit(obj, text) {
  if (jsonOut) console.log(JSON.stringify(obj, null, 2));
  else console.log(text);
  process.exit(obj.exitCode ?? 0);
}

function fail(msg, code = 1, extra = {}) {
  if (jsonOut) console.log(JSON.stringify({ ok: false, error: msg, ...extra }, null, 2));
  else console.error(`error: ${msg}`);
  process.exit(code);
}

function needBoard() {
  const b = pos[1] === "validate" ? pos[2] : pos[1];
  if (!b) fail(`usage: agent-route ${pos[0]}${pos[0] === "plan" ? " [validate]" : ""} <board> [--json]`);
  if (!existsSync(join(SRC_DIR, b, `${b}.circuit.tsx`))) {
    fail(`unknown board '${b}' (expected src/${b}/${b}.circuit.tsx)`);
  }
  return b;
}

function doScan(board) {
  const dist = runRoutingDisabledEval(board);
  return loadScanFromCircuitJson(board, dist);
}

// --- plan ---------------------------------------------------------------
function cmdPlan(board) {
  let scan;
  try {
    scan = doScan(board);
  } catch (e) {
    fail(`scan failed: ${e.message}`);
  }
  const { plan, scoring } = buildPlan(scan);
  writeFileSync(planPath(board), JSON.stringify(plan, null, 2) + "\n");

  const rows = plan.sections.map((s) => {
    const d = scoring.densities.find((x) => x.id === s.id);
    return {
      id: s.id, name: s.name, conns: s.connections.length,
      rect: `[${s.rect.minX},${s.rect.maxX}]x[${s.rect.minY},${s.rect.maxY}]`,
      order: s.phaseIndex,
      density: d.connsPerMm2,
    };
  });
  const text = [
    `plan ${board}: ${plan.sections.length} section(s) -> src/${board}/${board}.agent-plan.json`,
    ...rows.map((r) =>
      `  ${r.id} ${r.name}  conns=${r.conns}  rect=${r.rect}  order=${r.order}  density=${r.density}/mm2`,
    ),
    `scoring: cutNets=${scoring.cutNets.length}` +
    (scoring.cutNets.length ? ` (${scoring.cutNets.join("; ")})` : " (none — clean split)"),
    ...scoring.densities.map((d) => `  density ${d.id}: ${d.conns} conns / ${d.areaMm2}mm2 = ${d.connsPerMm2}/mm2`),
    ...scoring.sanity.flatMap((s) =>
      s.notes.length ? [`  sanity ${s.id}: aspect=${s.aspect} coverage=${s.coverage} — ${s.notes.join(", ")}`] : [],
    ),
  ].join("\n");
  emit({ ok: true, exitCode: 0, plan, scoring }, text);
}

// --- plan validate --------------------------------------------------------
function cmdPlanValidate(board) {
  if (!existsSync(planPath(board))) {
    fail(`no plan file (run 'agent-route plan ${board}' first)`);
  }
  let scan;
  try {
    scan = doScan(board);
  } catch (e) {
    fail(`scan failed: ${e.message}`);
  }
  const plan = readJson(planPath(board));
  const res = validatePlan(plan, scan);
  const text = [
    `validate ${board}: ${res.ok ? "OK" : "FAILED"} (${res.errors.length} errors, ${res.warnings.length} warnings)`,
    ...res.errors.map((e) => `  ERROR: ${e}`),
    ...res.warnings.map((w) => `  WARN: ${w}`),
  ].join("\n");
  emit(
    { ok: res.ok, exitCode: res.ok ? 0 : 1, errors: res.errors, warnings: res.warnings },
    text,
  );
  process.exit(res.ok ? 0 : 1);
}

// --- status ---------------------------------------------------------------
function cmdStatus(board) {
  let scan = null;
  try {
    const dist = distCircuit(board);
    if (existsSync(dist)) scan = loadScanFromCircuitJson(board, dist);
  } catch { /* scan optional for status */ }
  if (!scan) {
    try {
      scan = doScan(board);
    } catch { /* last resort: plan-only status */ }
  }
  const hasPlan = existsSync(planPath(board));
  const plan = hasPlan ? readJson(planPath(board)) : null;
  let statusJson = null;
  if (existsSync(statusPath(board))) {
    try { statusJson = readJson(statusPath(board)); } catch { /* ignore */ }
  }
  const sigs = {};
  if (plan && scan) {
    for (const s of plan.sections) {
      const sigFile = join(sectionDir(board), `${s.id}.${s.name}.agent-route.sig`);
      const stored = existsSync(sigFile) ? readFileSync(sigFile, "utf8").trim() : null;
      const v = verifySectionSig(scan, s, stored);
      const routeFile = join(sectionDir(board), `${s.id}.${s.name}.agent-route.json`);
      sigs[s.id] = {
        status: s.status,
        sig: stored ? (v.valid ? "valid" : "STALE") : "none",
        sigReason: v.reason,
        routed: existsSync(routeFile),
        timing: statusJson?.sections?.[s.id] ?? null,
      };
    }
  }
  const rows = plan
    ? plan.sections.map((s) => ({ id: s.id, ...sigs[s.id], conns: s.connections.length }))
    : [];
  const text = [
    `status ${board}: plan=${hasPlan ? `${plan.sections.length} section(s)` : "none"}  routed-sections=${rows.filter((r) => r.routed).length}  status.json=${statusJson ? "present" : "absent"}`,
    ...rows.map((r) =>
      `  ${r.id} status=${r.status} sig=${r.sig} routed=${r.routed ? "yes" : "no"}` +
      (r.timing ? ` ms=${r.timing.ms} attempts=${r.timing.attempts}` : ""),
    ),
    ...(plan ? [] : ["  (no plan yet — run 'agent-route plan <board>')"]),
  ].join("\n");
  emit({ ok: true, exitCode: 0, board, plan: !!plan, sections: rows, statusJson }, text);
}

// --- drc ------------------------------------------------------------------
async function cmdDrc(board) {
  const { runAllChecks, dedupePcbDrcErrors } = await import("@tscircuit/checks");
  // Gate runs on the routed board if present, else the fresh eval.
  let path = routedJsonPath(board);
  let which = "routed";
  if (!existsSync(path)) {
    try {
      path = runRoutingDisabledEval(board);
      which = "eval (unrouted)";
    } catch (e) {
      fail(`drc failed: ${e.message}`);
    }
  }
  const t0 = Date.now();
  const cj = readJson(path);
  const issues = dedupePcbDrcErrors(await runAllChecks(cj));
  const errors = issues.filter((e) => String(e.type).endsWith("_error"));
  const warnings = issues.filter((e) => !String(e.type).endsWith("_error"));
  const ms = Date.now() - t0;
  const withCtx = (list) =>
    list.map((e) => ({ ...e, _refs: implicatedRefs(e), _at: implicatedAt(e) }));
  const text = [
    `drc ${board} (${which}, ${ms}ms): ${errors.length} errors, ${warnings.length} warnings`,
    ...withCtx(errors).map((e) =>
      `  ERROR ${e.type}: ${e.message ?? ""} refs=[${e._refs.join(",")}]` +
      (e._at ? ` at=(${e._at.x},${e._at.y})` : ""),
    ),
    ...withCtx(warnings).slice(0, 10).map((e) => `  warn ${e.type}: ${e.message ?? ""}`),
    ...(warnings.length > 10 ? [`  ... +${warnings.length - 10} more warnings`] : []),
  ].join("\n");
  emit(
    {
      ok: errors.length === 0, exitCode: errors.length === 0 ? 0 : 1,
      board, source: which, ms, errors: withCtx(errors), warnings: withCtx(warnings),
    },
    text,
  );
  process.exit(errors.length === 0 ? 0 : 1);
}

function implicatedRefs(e) {
  const refs = [];
  for (const k of ["source_component_id", "pcb_component_id", "source_port_id", "pcb_port_id", "pcb_trace_id"]) {
    if (e[k]) refs.push(String(e[k]));
  }
  if (Array.isArray(e.implicated_refs)) refs.push(...e.implicated_refs);
  return [...new Set(refs)];
}

function implicatedAt(e) {
  if (typeof e.x === "number" && typeof e.y === "number") return { x: e.x, y: e.y };
  if (e.center && typeof e.center.x === "number") return { x: e.center.x, y: e.center.y };
  if (e.position && typeof e.position.x === "number") return { x: e.position.x, y: e.position.y };
  return null;
}

// --- dispatch ---------------------------------------------------------------
const [cmd, sub] = pos;
if (!cmd || cmd === "help" || cmd === "--help" || cmd === "-h") {
  console.log(`agent-route — agent-native section autorouter CLI
usage:
  agent-route plan <board> [--json]             scan + write *.agent-plan.json
  agent-route plan validate <board> [--json]    re-check a hand-edited plan
  agent-route status <board> [--json]           section states + sig validity
  agent-route drc <board> [--json]              full-board DRC gate
  agent-route run <board>                       (another chat owns it — stub)
  agent-route retry-section <board> S..         (another chat owns it — stub)`);
  process.exit(0);
}
if (cmd === "plan" && sub === "validate") cmdPlanValidate(needBoard());
else if (cmd === "plan") cmdPlan(needBoard());
else if (cmd === "status") cmdStatus(needBoard());
else if (cmd === "drc") await cmdDrc(needBoard());
else if (cmd === "run" || cmd === "retry-section") {
  const msg = `'${cmd}' is owned by another chat — not implemented yet`;
  if (jsonOut) console.log(JSON.stringify({ ok: false, error: msg }));
  else console.error(`error: ${msg}`);
  process.exit(2);
} else fail(`unknown command '${cmd}' (try: plan, status, drc)`);
