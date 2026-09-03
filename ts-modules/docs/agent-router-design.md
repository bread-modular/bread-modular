# Agent-Native Section Autorouter — Design Doc

Status: `draft` — revised after first review (Kimi K3, 2026-09-03); ready for re-review
Date: 2026-09-03
Scope: `ts-modules/` (ts-circuit rewrite of Bread Modular)
Author: research agent (Meta Muse)

> **Revision note (2026-09-03, review pass 1):**
> First review verified every cited primitive against the installed
> `node_modules` (core 0.0.1816, capacity-autorouter 0.0.851, checks 0.0.178) —
> all exist, and the `algorithmFn` cache-skip claim is confirmed in core source.
> Corrections and design changes folded in below:
> - Fixed §3.6/§6: `DrcEvaluator` does not exist; the real entries are
>   `runAllChecks` / `runAllRoutingChecks` + `dedupePcbDrcErrors`.
> - Resolved the dual-lifecycle ambiguity with an explicit decision (§4.0).
> - Per-section sig invalidation instead of board-global (§5).
> - Phase-0 global-net routing, fail-continue + auto-bisect, plan scoring /
>   `plan validate`, boundary-port net handoff, concrete timeout mechanism.

> **IMPORTANT — Out of scope / do not reference:**
> `tools/nudge`, `tools/nudge-lib/`, `tools/NUDGE_TOOL_PLAN.md`, and any nudge-related
> trick/docs are **explicitly out of scope**. Treat them as if they do not exist.
> Do NOT read them, do NOT reuse their UX, do NOT copy their classification logic.
> This design must stand on its own on top of ts-circuit. The reviewer should also
> ignore all nudge-related files.

---

## 1. Goal

Design an auto-router that **always works with agents** (LLM coding agents doing
PCB layout), replacing the mental model of ts-circuit's built-in autorouter while
reusing its low-level algorithms / check tools where useful.

Desired workflow (jigsaw-puzzle model):

1. **Scan → Plan.** Analyse the board, propose sections. Closely-placed,
   densely-connected components can be routed faster in sections. Sometimes the
   whole board is one section.
2. **Route section-by-section.** Route one section at a time, lock it, move on.
3. **Persist progress.** Save completed sections to file(s) so we never redo work.
4. **Fail-stop with explanation.** If routing fails, stop. Report what completed,
   what is blocked, and why (blocking nets / refs / rect / DRC class).
5. **Agent guides / nudges placement.** Agent moves components, edits section rects,
   and asks to route again (only the blocked section).
6. **Final DRC.** Proper DRC check pass/fail gate.

---

## 2. Problem with the current ts-circuit autorouter (for agents)

Verified against installed versions in `ts-modules/`:

- `@tscircuit/core 0.0.1816`
- `@tscircuit/capacity-autorouter 0.0.851`
- `@tscircuit/checks 0.0.178`

Observed pain points:

- **Monolithic run.** One call routes the whole board (~35–60s per `build.sh` run).
  Any placement nudge reshuffles ALL routes → whack-a-mole DRC.
- **Binary pass/fail.** No per-net / per-region progress, no "blocked by X" report
  an agent can act on.
- **Stale cache.** `.tscircuit/cache` key does not account for all inputs
  (e.g. effort level); stale routes get reused silently.
- **Keepouts are hard obstacles for ALL traces.** There is no per-trace
  keepout exemption (`excludeRefs` is DRC-only). Current workaround in
  `ts-modules/lib/module-frame.tsx` (`PowerRail`) is to pre-route the rail bus
  with `<trace pcbStraightLine>` so the router's spanning tree skips it
  (`initiallyConnectedMap`). Any section design must handle this.
- **No resume.** No first-class "keep these traces, retry the rest" flow exposed
  to the agent (primitives exist, see §3, but no agent UX).

---

## 3. Reusable primitives found in ts-circuit (do NOT reimplement)

All of these exist in the installed `node_modules` — the design builds on them:

### 3.1 Custom router injection — the replacement point

`autorouter={{ algorithmFn }}` is a first-class prop (`autorouterConfig` in
`@tscircuit/props/lib/components/group.ts`):

```tsx
autorouter={{
  local: true,
  groupMode: "subcircuit",
  algorithmFn: async (simpleRouteJson) => MyAgentRouter(simpleRouteJson),
}}
```

Can be set on `<board>` or per `<subcircuit>`. Preset resolution in
`@tscircuit/core` (`getPresetAutoroutingConfig`) honours `algorithmFn`.
`algorithmFn` results are NOT put through the registry cache — a plus for us
(no stale-cache class of bugs).

### 3.2 Native sections — `<autoroutingphase>`

`@tscircuit/props/lib/components/autoroutingphase.ts`:

```ts
interface AutoroutingPhaseProps {
  name?: string
  autorouter?: AutorouterProp   // per-phase router override
  phaseIndex?: number
  region?: { shape?: "rect", minX, maxX, minY, maxY }  // section rect
  connection?: string           // single selector, e.g. "R1.1 > C3.2"
  connections?: string[]        // section net list
  reroute?: boolean
}
```

Plus `trace routingPhaseIndex` / `net routingPhaseIndex` assignment props.
This is the built-in section-by-section mechanism — prefer emitting these
declaratively from the planner rather than inventing a new section language.
(See §4.0 for how this reconciles with the CLI-driven slicing of §4.3.)

Reference impl: `Group_getRoutingPhasePlans` in `@tscircuit/core/dist/index.js`.

### 3.3 Rect re-route + stitch helpers

In `@tscircuit/capacity-autorouter/dist/index.d.ts`:

- `getRerouteSimpleRouteJson(simpleRouteJson, rectRegion)` — slice the
  `SimpleRouteJson` down to one rect (a section).
- `reconnectReroutedSimpleRouteJsonRegion(original, rerouted)` — stitch a
  re-routed section back into the full-board solution.
- `createSectionSimpleRouteJson(...)` + `MultiSectionPortPointOptimizer` +
  `AutoroutingPipelineSolver9_PreloadedTraceGraph` — precedent for local
  rip-up / retry with preloaded (locked) traces.

These are exactly the "route one jigsaw piece, keep the rest" operators.

### 3.4 Lock completed work via pre-routed traces

A `<trace>` with explicit PCB geometry (`pcbStraightLine`, `pcbVia`, etc.)
is treated as already routed and skipped by the router's spanning-tree build
(`initiallyConnectedMap`). Precedent: `PowerRail` in `module-frame.tsx`
pre-routes the rail pin bus for exactly this reason (keepout-immune rails).

Design rule: **a completed section is frozen by emitting its traces as
explicit-geometry `<trace>` elements** (or equivalent circuit-json trace
records). Later sections treat them as obstacles + connectivity.

### 3.5 Save / resume serialisation points

- `getSimpleRouteJsonFromCircuitJson(circuitJson)` — board → router input.
- `unrouteCircuitJson(circuitJson)` — strip routing, keep placement.
- `PcbRouteCache` interface (`autorouter.cache`) + existing repo pattern of
  `*.routed.json + *.sig` files (see `ts-modules/build.sh` routed-board reuse).

Design rule: persist per-section `*.agent-route.json` + sig/hash files
(see §5). Never rely on `.tscircuit/cache` for agent state.

### 3.6 DRC + pinning

- `@tscircuit/checks` → `runAllChecks` / `runAllRoutingChecks` /
  `runAllPlacementChecks` (aggregators) + `dedupePcbDrcErrors` and the
  individual `check*` functions (`checkPcbTraceLengths`,
  `checkEachPcbTraceNonOverlapping`, `checkViaPadClearance`, …).
  NOTE: there is NO `DrcEvaluator` class in 0.0.178 — use the aggregators.
  Use `runAllRoutingChecks` as the final gate AND per-section gate
  (circuit-json filtered to rect ∪ margin, see §6).
- `manualEdits` file (`manual_edits_file` in `@tscircuit/props`) — declarative
  pinning of placements/traces the agent has approved. Prefer emitting
  `manualEdits` over ad-hoc json patching where possible.

---

## 4. Proposed architecture

```
┌──────────┐   ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌─────┐
│  SCAN    │──▶│   PLAN   │──▶│ ROUTE     │──▶│  STITCH  │──▶│ DRC │
│ (no route)│   │(sections)│   │ section N │   │ + lock   │   │ gate│
└──────────┘   └──────────┘   └───────────┘   └──────────┘   └─────┘
      ▲              │               │               │             │
      │              ▼               ▼               ▼             ▼
   placement    plan.json      section files    board files   report
   (circuit-     (rects +       *.agent-route    *.routed      pass/
    json)        conns)          .json            .json         fail-stop
```

### 4.0 Lifecycle decision — ONE execution mechanism (resolved from review)

The first draft had two section lifecycles competing: declarative
`<autoroutingphase>` executed inside core's render (§3.2) vs. the CLI
hand-driving `getRerouteSimpleRouteJson` / stitch outside core (§4.3).
Mixing them risks phase plans fighting the CLI's own slicing and two sources
of truth for "what is routed".

**Decision: the CLI owns the pipeline; core phases are NOT used at runtime.**

- `<autoroutingphase>` stays as the *vocabulary* of the plan (`rect` /
  `connections` / `phaseIndex` map 1:1), but the CLI drives
  slice → route → stitch itself (§4.3) so it controls persistence, fail-stop,
  resume, and per-section reporting — none of which core exposes mid-render.
- We do NOT rely on core's in-render phase execution because: (a) a phase
  failure aborts the whole render with no machine-readable per-section state;
  (b) we cannot persist/resume between phases inside one `tsci eval`.
- Revisit only if core gains a phase-level event/persist hook. Spike both in
  §7.1 to confirm the lifecycle assumption before committing.

### 4.1 SCAN (routing-disabled evaluation)

- Run `tsci eval --routing-disabled` (or `build.sh` equivalent flag) to get
  unrouted circuit-json: `pcb_component` centres / courtyards, `source_trace`
  netlist, `pcb_smtpad` / `pcb_plated_hole` locations, board outline.
- Cluster by (a) geometric proximity (courtyard / centre distance) and
  (b) net affinity (shared `source_trace` / `source_net`).
- Output: candidate sections. Heuristic starting point: connected-components
  of the "components × nets" bipartite graph, merged/split by rect overlap.
- Whole-board single section MUST remain a valid plan (fallback when clustering
  is ambiguous or board is small, e.g. `blank` module).

### 4.2 PLAN (human/agent-readable)

`plan.json` (per board, versioned):

```json
{
  "version": 1,
  "board": "8bit",
  "createdAt": "2026-09-03T07:55:00.000Z",
  "sections": [
    {
      "id": "S1",
      "name": "mcu-cluster",
      "rect": { "minX": -20, "maxX": 5, "minY": -10, "maxY": 12 },
      "connections": ["U1.3 > C4.1", "U1.4 > R2.1"],
      "phaseIndex": 0,
      "status": "pending"
    }
  ]
}
```

- `rect` maps 1:1 to `<autoroutingphase region>`, `connections` to
  `<autoroutingphase connections>`, `phaseIndex` to execution order.
- **Adjacent rects MUST overlap by ≥ 2× max trace pitch / clearance** (promoted
  from §8.1 risk-mitigation to a design default): it gives the stitch helper
  seam room and lets each section's DRC margin catch boundary violations.
- Planner prints a summary table (id, name, #conns, rect, order) for the agent.
- **Plan scoring is mandatory output**: for the proposed plan the planner
  reports (a) `cutNets` — connections whose endpoints span a section boundary,
  (b) per-rect connection density, (c) rect aspect/coverage sanity. High
  cut-net count = bad plan; the agent SHOULD regenerate or hand-edit before
  routing. A bad plan is the cheapest thing to fix and the most expensive
  thing to route.
- Agent may edit rects / order / connections before routing, or accept as-is.
- `agent-route plan validate <board>` (§4.7) re-checks a hand-edited plan:
  every connection assigned to exactly one section, every pad inside some
  rect, no orphan nets, overlaps within bounds. Cheap, catches agent edits.

### 4.3 ROUTE (one section at a time)

**Phase 0 — global nets first.** Power/GND rails (and any net touching nearly
every section) are routed as their own dedicated first phase, generalising
the existing `PowerRail` pre-route trick: emit them as explicit-geometry
traces (or a plain full-board section restricted to global nets) BEFORE any
signal section. Signal sections then never deal with cross-section power,
which is the worst case for the §8.5 handoff problem.

For section `Si` in `phaseIndex` order:

1. Load full `SimpleRouteJson` via `getSimpleRouteJsonFromCircuitJson`.
2. Slice with `getRerouteSimpleRouteJson(srj, rect_i)` — only `connections_i`
   are routed; prior sections' traces are preloaded as locked
   (`PreloadedTraceGraph`-style: they are obstacles + connectivity).
   OPEN SPIKE QUESTION (§7.1): confirm the slice helper preloads out-of-rect
   locked traces as obstacles — upstream it was built for "re-route an
   already-routed rect", not "assemble a never-fully-routed board".
3. Run the section router: default = capacity-autorouter pipeline
   (`beta_pipeline9` / `latest`) invoked through `algorithmFn`. Custom
   per-phase `autorouter` overrides allowed.
   **Timeout mechanism (concrete):** the capacity solvers are `BaseSolver`
   step-loops, so the CLI drives `solver.step()` itself with (a) a max
   iteration count and (b) a wall-clock deadline checked between steps —
   no worker threads needed. Budget defaults: per-section timeout +
   attempt count recorded in `status.json`.
4. On success: convert new traces to locked geometry, append to
   `sections/Si.agent-route.json`, update `plan.json` status → `done`.
5. On failure/timeout: fail-stop by default (see §4.5); `--keep-going`
   continues with independent later sections (see §4.5).

Keepout-crossing sections: apply the pre-route trick per section (emit the
crossing as explicit geometry first), not just for power rails.

### 4.4 STITCH + LOCK

- After each section: `reconnectReroutedSimpleRouteJsonRegion(original, rerouted)`
  (or circuit-json equivalent: merge locked traces back into the board).
- Emit locked traces as explicit `<trace pcbStraightLine …>` / `pcb_trace`
  records so subsequent `tsci` runs preserve them without re-routing.
- Per-section files: `sections/Si.agent-route.json` (+ `.sig` hash of inputs:
  placement hash + plan hash + ts-circuit version). If sig mismatches on resume,
  invalidate ONLY that section.

Suggested layout (per board, e.g. `ts-modules/src/8bit/`):

```
8bit.agent-plan.json
8bit.agent-route/
  S1.mcu-cluster.agent-route.json
  S1.mcu-cluster.agent-route.sig
  S2.power.agent-route.json
  ...
8bit.routed.json          # final stitched board (existing reuse pattern)
8bit.routed.sig
```

### 4.5 FAIL-STOP REPORT (machine-readable + human-readable)

On failure the router STOPS (default) and prints / writes `status.json`:

```json
{
  "completed": ["S1", "S2"],
  "blocked": "S3",
  "blockedRect": { "minX": 0, "maxX": 15, "minY": 0, "maxY": 10 },
  "blockedConnections": ["U2.5 > J3.1"],
  "implicatedRefs": ["U2", "J3", "C9"],
  "errorClass": "DRC_CLEARANCE | NO_PATH | TIMEOUT | STITCH_MISMATCH",
  "drcErrors": [ { "type": "...", "refs": [], "at": {} } ],
  "suggestion": "move U2 +2mm in +x or widen S3 rect by 3mm",
  "sections": {
    "S1": { "status": "done", "ms": 8200, "attempts": 1 },
    "S2": { "status": "done", "ms": 21400, "attempts": 2 },
    "S3": { "status": "blocked", "ms": 60000, "attempts": 3, "bisectDepth": 0 }
  }
}
```

- `errorClass` taxonomy must be small and stable so agents can branch on it.
  Starting set: `NO_PATH`, `DRC_CLEARANCE`, `VIA_EXHAUSTED`, `TIMEOUT`,
  `STITCH_MISMATCH`, `INPUT_INVALID`.
- Per-section `ms` + `attempts` are always recorded (also on success) so the
  agent can learn which sections are expensive and re-plan.
- Human summary mirrors the same data (✅ completed / ❌ blocked + why).
- Exit code non-zero; no partial write of the blocked section (keep last-good).

**Fail-continue (`--keep-going`).** Strict fail-stop withholds information:
sections after the blocked one may be independent and routable. With
`--keep-going` the router skips the blocked section, routes the rest, and the
final report lists ALL blocked sections. Default stays fail-stop (safest for
naive agents); `--keep-going` is for agents that want a full board picture in
one pass.

**Auto-bisect on failure.** Before declaring a section blocked, the router
splits its rect into 2–4 sub-rects (halving the longest axis, connections
re-assigned by endpoint location) and retries with the same budgets, up to
`bisectDepth` 2. A dense cluster that fails whole often routes as quadrants.
Only when the bisection budget is exhausted does the section report `blocked`.
Sub-sections are recorded in `status.json` so the agent sees the granularity
at which routing actually succeeded.

### 4.6 AGENT FIX LOOP

1. Agent reads `status.json` + DRC errors.
2. Agent edits placement (`pcbX/pcbY/pcbRotation` in `.circuit.tsx`) or section
   rect / order in `*.agent-plan.json`, or adds explicit pre-routes / keepouts.
3. Agent re-invokes only the blocked section: `agent-route retry-section S3`.
4. Locked prior sections are untouched (sig-validated). No full re-route.

### 4.7 CLI shape (proposed, mirrors `build.sh`/`tsci.sh` UX)

```
tools/agent-route plan <board>              # scan + print plan + scoring, write *.agent-plan.json
tools/agent-route plan validate <board>     # re-check a hand-edited plan (coverage, orphans, overlaps)
tools/agent-route run <board> [--keep-going] [--no-bisect]   # route pending sections in order
tools/agent-route status <board>            # table of section states + sig validity + timings
tools/agent-route retry-section <board> S3  # re-route one section (locked others untouched)
tools/agent-route drc <board>               # DRC gate only (checks lib)
```

All commands MUST be non-interactive and emit both human text and `--json`.
`run` defaults: fail-stop ON, auto-bisect ON (depth ≤ 2).

---

## 5. File formats & invalidation

- `*.agent-plan.json`: `{ version, board, sections[] }` as in §4.2.
- `*.agent-route.json`: section-local solved traces in circuit-json
  (`pcb_trace`/`pcb_via`) or `SimpleRouteJson` fragment + the `rect` +
  input hashes. Must be re-appliable via `manualEdits`-style merge.
- `*.sig`: **per-section** hash of:
  - placement elements whose courtyard/centre intersects `rect ∪ margin`
    (NOT board-global placement — a nudge in S1 must not invalidate S5),
  - the endpoints (refdes + pin) of the section's `connections`,
  - the plan section itself + router version + router params.
  Any mismatch → that section's status back to `pending`; all other sections
  keep their sigs and stay `done`. This per-section granularity is what makes
  "never redo work" actually true — board-global hashing would collapse the
  design back into monolithic re-routes on every nudge.
- Final `*.routed.json`: stitched full-board solution, reusing the existing
  `build.sh` routed-board reuse flow.
- NEVER store agent state inside `.tscircuit/cache`.

---

## 6. DRC design

- Per-section gate: run `runAllRoutingChecks` (from `@tscircuit/checks`,
  + `dedupePcbDrcErrors`) on the circuit-json filtered to the section
  **rect ∪ margin** (margin ≥ section overlap, see §4.2) after each section.
  The margin is mandatory, not optional: it is what catches boundary/seam
  violations introduced by stitching. Fail → fail-stop (or `--keep-going`).
- Final gate: full-board `runAllChecks`. Must be zero-error before
  `*.routed.json` is promoted to final.
- DRC errors are attached to the fail-stop report with implicated refs and
  coordinates so the agent can localise the fix.
- `excludeRefs`-style DRC waivers are NOT a substitute for routing fixes;
  waivers (if ever needed) must be explicit, per-error, and recorded in the
  plan file — never silent.

---

## 7. Validation plan (spike tests first)

Order matters: 1–2 are the highest-risk unknowns and gate everything else.

1. **Lifecycle + slice/stitch semantics spike** (`blank`, then `8bit`) —
   THE gating experiment, combining two questions:
   a. Does `getRerouteSimpleRouteJson` on a rect of a NEVER-fully-routed board
      keep out-of-rect locked traces as obstacles+connectivity? (Upstream it
      was built to re-route an already-routed rect; semantics may not
      transfer. If not, fall back to building the section SRJ manually from
      `getSimpleRouteJsonFromCircuitJson` + filtering.)
   b. Does `reconnect…Region` stitch a section routed this way back into the
      board DRC-clean? Proves §4.0's CLI-owns-pipeline decision on evidence
      rather than assumption.
2. **Injection spike** (`blank` module): pass a trivial `algorithmFn`
   (e.g. delegate to capacity-autorouter) via `<board autorouter>` and confirm
   `build.sh`-equivalent output is unchanged.
3. **Lock spike**: emit one section as explicit-geometry traces, re-run full
   eval, confirm the router preserves them and routes the remainder.
4. **Global-nets phase-0 spike** (`8bit`): route GND/VCC as phase 0, then a
   signal section; confirm signal routing improves vs. no phase 0.
5. **Fail-stop + auto-bisect spike**: craft an unroutable section (blocked
   rect), confirm the §4.5 report schema with correct implicated refs, then
   confirm bisection routes a borderline-dense section as quadrants.
6. **Resume + per-section sig spike**: route S1, nudge a component inside S2's
   rect only, re-run — confirm S1 stays `done` (sig valid) and only S2
   re-routes. Then a board-global change (board outline) → all sections
   invalidate.

---

## 8. Risks & open questions (for reviewer)

1. **Stitch quality at section boundaries.** `reconnect…Region` may introduce
   kinks / clearance violations where section traces cross rect edges.
   Mitigations are now design defaults: overlapping rects (§4.2), per-section
   DRC on rect ∪ margin (§6). Residual risk: a dedicated low-effort
   "seam polish" pass if spikes show systematic seam errors.
1a. **Slice/stitch semantics mismatch (highest risk, gates the design).**
   `getRerouteSimpleRouteJson` + `reconnect…Region` were designed for
   "unroute a rect inside an already-routed board, re-route it, merge back".
   This design assembles a board that was never fully routed, section by
   section. Whether the slice preloads locked out-of-rect traces as obstacles
   is unverified — §7.1 spike decides; fallback is hand-built section SRJs.
2. **Section ordering sensitivity.** Power / long rails first vs. dense clusters
   first? Resolved partially by phase-0 global nets (§4.3). Remaining question:
   order among signal sections — proposal: most-constrained (highest density
   from plan scoring) first, since early sections have the most free space.
   Reviewer: is there prior art in the `MultiSection*` solvers to copy the
   ordering heuristic from?
3. **Keepout interaction per section.** Keepouts span section boundaries;
   pre-route trick must be applied per crossing, not globally. Confirm
   `initiallyConnectedMap` semantics hold when traces are added incrementally.
4. **Rect granularity.** Too-small rects starve the maze router (no escape
   room); too-large rects lose the section benefit. Starting rule: rect =
   cluster bbox + clearance margin (≥ 2× max trace pitch), PLUS mandatory
   ≥ 2× clearance overlap with neighbours (§4.2). Auto-bisect (§4.5) gives a
   runtime escape hatch when a rect is still too coarse. Reviewer: sane default?
5. **Subnet splitting / cross-section nets.** Now mitigated two ways:
   (a) phase-0 routes global nets (power/GND) before any signal section, so
   the common worst case never crosses sections;
   (b) remaining cross-section signal nets use **boundary ports**: route the
   net in the later section with a fixed target at the earlier section's
   endpoint — reuse the `PortPointSection` boundary-port model from
   `MultiSectionPortPointOptimizer` rather than inventing a handoff format.
   Confirm with spike; a net spanning 3+ sections should be re-planned
   (plan validate warns on it) rather than chained through handoffs.
6. **`algorithmFn` versioning.** Pin `@tscircuit/*` versions in the sig hash;
   a version bump invalidates all sections (safe default).

---

## 9. Alternatives considered

- **Fork capacity-autorouter internals.** Rejected: high maintenance burden;
  injection + slice/stitch achieves sectioning without forking.
- **Cloud autorouter (`auto-cloud`) as the engine.** Rejected as default
  (non-deterministic, network-dependent, cache-opaque); keep as opt-in
  per-phase override.
- **Single-shot whole-board routing with retries.** Status quo; kept only as
  the degenerate single-section plan.
- **Nudge-style post-hoc trace editing.** Explicitly out of scope for this doc
  (see header). Sections + re-route subsume that loop: fix placement, re-route
  the section, rather than hand-editing traces.

---

## 10. What the reviewer should check

1. ~~Does the `algorithmFn` + `<autoroutingphase>` + slice/stitch composition
   hold together?~~ → Resolved as §4.0 (CLI owns the pipeline). Remaining:
   does the §7.1 spike confirm slice/stitch semantics for never-fully-routed
   boards, and is hand-built section SRJ an acceptable fallback?
2. Is the per-section `*.sig` scoping (§5: rect ∪ margin placement + section
   endpoints) sound, or are there non-local inputs that must also invalidate
   (e.g. board outline, net class rules, keepout changes)?
3. Is the `errorClass` taxonomy sufficient for an agent to act without human
   help? Does auto-bisect (§4.5) need its own `BISECT_EXHAUSTED` class or is
   `NO_PATH` + `bisectDepth` enough?
4. Is the CLI surface minimal-complete? Anything missing for the jigsaw loop?
5. Any correctness risk in freezing sections as explicit geometry (DRC /
   connectivity counting of pours & PTH pads, cf. QFN-EP / via-in-pad precedents)?
6. Phase-0 global nets (§4.3): any interaction with `initiallyConnectedMap`
   when the rail pre-routes come from a CLI phase rather than `PowerRail`
   in-render? Same mechanism, but confirm.

---

## Appendix A — version pins & file pointers (at time of research)

- `ts-modules/package.json` → `@tscircuit/core 0.0.1816`-era API,
  `@tscircuit/capacity-autorouter 0.0.851`, `@tscircuit/checks 0.0.178`.
- Props: `ts-modules/node_modules/@tscircuit/props/lib/components/group.ts`
  (`autorouterConfig`, `AutorouterProp`), `.../autoroutingphase.ts`
  (`AutoroutingPhaseProps`).
- Core: `ts-modules/node_modules/@tscircuit/core/dist/index.js`
  (`getPresetAutoroutingConfig`, `Group_getRoutingPhasePlans`).
- Router: `ts-modules/node_modules/@tscircuit/capacity-autorouter/dist/index.d.ts`
  (`getRerouteSimpleRouteJson`, `reconnectReroutedSimpleRouteJsonRegion`,
  `createSectionSimpleRouteJson`, `MultiSectionPortPointOptimizer`,
  `AutoroutingPipelineSolver9_PreloadedTraceGraph`).
- Repo patterns: `ts-modules/build.sh` (routed-board reuse), `ts-modules/tsci.sh`,
  `ts-modules/lib/module-frame.tsx` (`PowerRail` pre-route trick),
  `ts-modules/src/8bit/8bit.circuit.tsx` (largest current board — best test target).
