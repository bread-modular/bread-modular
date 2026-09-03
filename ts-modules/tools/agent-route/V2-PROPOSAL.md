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
4. **`phases.json` replaces rect plan:** `{ phaseIndex, nets[], region?,
   autorouter, budgetMs }`. `cutNets` metric deleted — uncuttable by schema.
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
