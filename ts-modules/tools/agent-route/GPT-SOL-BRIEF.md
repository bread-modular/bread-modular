# GPT Sol Judgement Brief — agent-router v2 reset

Context: Bread Modular repo, `ts-modules/`, branch `ts-circuit`. Model: Meta Muse, NO advisor. v1 = rect-sliced agent-router (`tools/agent-route/`). v2 draft merged at `tools/agent-route/V2-PROPOSAL.md` (full text verbatim in Appendix). Ask: judge root cause + primitive choice + risks before any v2 code.
Rule: brute-force nudging is BANNED by user. Router must route clean placements cleanly.

## 1. v1 failure evidence (exact, from repo)

8bit — `src/8bit/8bit.agent-route/status.json`:
- S1: `done`, 4606ms (~4.6s), attempts 1, deferred `source_net_0`
- S2: `blocked`, 600004ms (~600s), `errorClass: TIMEOUT`, 54 blockedConnections
- Final gate: 7x `pcb_trace_error`, all seam-band S1-locked x S2-locked pairs:
1. `trace[.INPUT1>port.1,.U2>pin11] too close trace[.U3>pin4,.U1>pin4] (gap 0.126mm)` @ (-4.507,8.391)
2. `trace[.INPUT1>port.1,.U2>pin11] overlaps pcb_smtpad "pcb_port[.U2>.PB2]"` @ (-2.6,-6.28)
3. `trace[.INPUT1>port.1,.U2>pin11] overlaps trace[.INPUT1>port.4,.U2>pin12]` @ (-2.666,-6.278)
4. `trace[.U3>pin6,.RV3>port.3] overlaps trace[.U3>pin4,.U1>pin4]` @ (5.220,8.964)
5. `trace[.U3>pin6,.RV3>port.3] overlaps trace[.C3>neg,.RV3>port.1]` @ (5.860,8.365)
6. `trace[.U3>pin6,.RV3>port.3] too close trace[.U2>pin8,.U1>pin5] (gap 0.136mm)` @ (6.625,5.997)
7. `trace[.U3>pin5,.INPUT1>port.3] too close trace[.INPUT1>port.4,.U2>pin12] (gap 0.040mm)` @ (-3.586,17.747)

8bit plan — `src/8bit/8bit.agent-plan.json`:
- S1 section-2: 9 plan conns -> 45 SRJ names, rect y 7.94–26.13
- S2 section-1: 14 plan conns -> 54 SRJ names, rect y -23.59–8.113
- Overlap band y 7.94–8.113 = ~0.17mm. Disjoint net sets, one shared corridor.

Drive — `src/drive/drive.agent-route/status.json`: S1 done 497ms, S2 done 20019ms (~20s scare), S3 done 356ms, finalDrc ok. Same rect-cut cause, got lucky.
Blank — `src/blank/blank.agent-plan.json`: 1 section whole-board, 3 conns, green. No seam = no failure.

## 2. v1 mechanics (from code)

- `lib/route-board.js finishSection` (§6 comment): section gate merges `fresh + NEW records only`, filters to rect+MARGIN, runs checks. Locked priors EXCLUDED. Cumulative merge checked only at final gate (zero-error).
- `lib/retry-section.js`: same scoped gate (fresh + retried records only). Rip-up is by rect.
- `lib/plan.js`: rect = cluster bbox + MARGIN (2.0mm), adjacent rects forced overlap >= OVERLAP (1.0mm). Conns assigned by most-endpoints vote, densest-first phaseIndex.
- `lib/route-lib.js resolveScanConn`: net-expansion — 1 plan conn fans to many SRJ `source_trace_*/source_net_*` names (e.g. 9->45, 14->54). Plan hides true scale.

## 3. Native primitives (verified post-mortem chat)

- `Group_getRoutingPhasePlans`: net-identity split, per-phase `autorouter.algorithmFn(srj)`, next input = full board + locked priors.
- `net`/`trace` `routingPhaseIndex` props.
- `<autoroutingphase name/autorouter/phaseIndex/region/connection>` scoping.
- Per-subcircuit `autorouter` + `groupMode: subcircuit` + `pcbRouteCache` for movable blocks.

## 4. Costs / constraints

- v1 total ~$0.95 / 800+ worker rounds. Post-mortem ~$0.05. Proposal ~$0.02. All Meta Muse, no advisor.
- Brute-force nudging banned. No board `.circuit.tsx` edits in v2 migration.

## 5. v2 recommendation (from proposal)

Phase 0 infra-fixed (pots/IO/rails thin trunks + keepouts, frozen first) + functional net-group middle phases (co-phased corridor nets, whole-board detour) + cumulative locked×new gates + rip-up by net (re-phase) + `phases.json {phaseIndex,nets[],region?,autorouter,budgetMs}`, `cutNets` deleted, 60s per-phase cap (overrun = mis-grouped). Migration: side-by-side `plan-v2`/`route-v2`, prove blank (1 phase) then drive (infra+2-3 phases) before 8bit pilot, keep v1 runnable until 8bit merges clean.

## ASK FOR GPT SOL

(a) Root cause: is `rect ownership ≠ net ownership + blind gates + frozen obstacles` correct and complete? What is missing?
(b) Primitive: net-phase via `Group_getRoutingPhasePlans` vs per-subcircuit vs hybrid — which would you pick and why?
(c) Top 3 risks in the v2 plan + concrete mitigations for each?
(d) Course correction: what would you change in phase decomposition, gate design, and budget policy (60s per-phase cap)?
(e) Migration: keep v1 runnable during migration or cut immediately? Why?

Five rapid answers (yes/no or either/or):
1. Seam collisions are planner-caused, not solver-caused — agree?
2. Cumulative locked×new gates on every phase — required or overkill?
3. Per-phase budget: 60s hard cap or adaptive by net-count?
4. Phase 0 infra trunks: pre-routed fixed geometry or just first phase?
5. v1: keep runnable or delete now?

---
## APPENDIX — V2-PROPOSAL.md FULL TEXT VERBATIM (excluded from line count)

# Agent-Router v2 — Drawing-Board Reset

Status: draft — proposal only, no code / board changes
Date: 2026-09-03 | Branch: ts-circuit | Scope: `ts-modules/tools/agent-route/`
Rule: brute-force nudging is banned. Router must route clean placements cleanly.

## 1. v1 root cause: rect-slicing cuts shared escape corridors

v1 plans by rect (`plan.js`: y-row bucketing + 1mm overlap), not by net.
8bit plan proves it: S1 (upper, y 7.94–26.13) owns 45 nets, S2 (lower,
y −23.59–8.113) owns 54 nets — disjoint net sets sharing one physical
corridor. The overlap band is only ~0.17mm (y 7.94–8.11): no room for two
independent escape plans.

Failure signature (`src/8bit/8bit.agent-route/status.json`): S1 done
(4.6s), S2 TIMEOUT (600s), final merged gate 7× `pcb_trace_error`, all in
the seam band. Critically, all 7 pair one S1-locked net × one S2-locked net
— the partition itself manufactures the collisions.

Why no gate catches it earlier (`route-board.js` / `retry-section.js`):

- Section gates check fresh+new traces only; locked priors are excluded
  from section DRC. So no gate ever sees locked-vs-new until the final merge.
- S1 is marked `done` before S2 routes, freezing S1 geometry as obstacles.
- Re-seeds / bisect / effort bumps re-solve the same bad partition against
  the same frozen obstacles — nondeterminism without a new partition cannot
  converge, only burn time (8bit S2: 600s; drive S2: 20s scare, same cause).
- Net-expansion accounting hides scale: plan counts ~14 conns, solver sees
  ~50 SRJ names per section.

In short: rect ownership ≠ net ownership; seam has no owner; gates are blind
to locked-vs-new; solver pays for the planner's cut.

## 2. Options

### (a) Net-phase routing via native `Group_getRoutingPhasePlans` [preferred primitive]

tscircuit core already splits routing by net identity, not rects: each phase
gets a disjoint net set, runs `autorouter.algorithmFn(srj)`, and the next
phase input = full board + locked priors. Props exist:
`net`/`trace` `routingPhaseIndex`, `<autoroutingphase name autorouter
phaseIndex region connection>` scoping each phase.

- Pros: no seam cuts by construction; whole-board detour room per phase;
  locked priors are inputs, not invisible obstacles; matches upstream.
- Cons: requires adopting phase-planner API; per-phase solver budgets still
  needed; phase-ordering matters.
- Tradeoff: most alignment for least custom code.

### (b) Per-subcircuit local routing

Put `autorouter` on `<subcircuit>` with `groupMode: subcircuit`, reuse
`pcbRouteCache` for movable routed blocks. Each functional block routes
locally, then integrates.

- Pros: true movable blocks; natural functional grouping (op-amp channel,
  CV chain); cache reuse across boards.
- Cons: subcircuit boundaries become mini-seams; inter-block nets still need
  a top-level phase; cache invalidation complexity.
- Tradeoff: best block reuse, weakest global-net story. Complements (a).

### (c) Hierarchical infrastructure-then-signal, thin-trunk first

Route rails/IO/pots escape trunks first as thin fixed geometry, then signal
groups around them. v1 design §Phase-0 intended this but never built it
(densest-first ran instead).

- Pros: fixes the highest-contention copper first; small, reviewable Phase 0;
  works with either (a) or (b).
- Cons: alone it keeps rect sections — trunk helps but seam collisions
  persist; trunk width/placement needs care (keepout + pre-routed bus
  precedent in `module-frame.tsx` applies).
- Tradeoff: necessary but insufficient solo.

## 3. Recommendation

Infrastructure-first + net-phase middle + locked-geometry gates:

1. **Phase 0 — infrastructure fixed:** pots/IO/rails first (thin trunks,
   pre-routed straight-line bus + keepouts per existing frame precedent).
   Frozen before any signal phase.
2. **Middle phases — functional net groups, co-phased:** e.g. 8bit:
   P0 infra, P1 U1/audio-gate, P2 U3/CV1-CV2, P3 U2 digital/MIDI/MODE/LED,
   P4 power/VMID/decoupling remainder. Nets sharing a corridor ride the same
   phase with whole-board detour room — never split across a rect seam.
3. **Routed phases = locked explicit geometry** with cumulative gates: every
   gate checks locked-priors × new (fixes v1 gate blindness). Fail = rip-up
   by net (re-phase that net set), never by rect.
4. **`phases.json` replaces rect plan:** `{ phaseIndex, nets[],
   region?, autorouter, budgetMs }`. `cutNets` metric deleted — uncuttable by schema.
   Per-phase budget 60s (not 600s): overrun = mis-grouped, re-phase instead.

## 4. Migration (blank/drive stay green)

1. Add `plan-v2` (emits `phases.json`, net-identity grouping) alongside v1
   `plan`; v1 files untouched.
2. Add `route-v2` (phase loop on native phase primitive) alongside v1
   `route-board`; reuse scan/sig/DRC helpers read-only.
3. Prove on blank (1 phase) then drive (infra + 2–3 net phases) DRC-clean
   before touching 8bit.
4. 8bit pilot: Phase 0 infra, then §3 groups; success = 0 deferred seam nets,
   all gates cumulative-clean, no TIMEOUT.
5. Promote v2 to default only after 8bit merges clean; keep v1 runnable until
   then. No board `.circuit.tsx` edits, no nudges.
