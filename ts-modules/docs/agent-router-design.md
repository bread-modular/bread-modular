# Agent-Native Section Autorouter — Design Doc

Status: `draft` — ready for review by a second agent
Date: 2026-09-03
Scope: `ts-modules/` (ts-circuit rewrite of Bread Modular)
Author: research agent (Meta Muse)

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

- `@tscircuit/checks` → `DrcEvaluator` (or equivalent `runChecks` entry).
  Use as the final gate AND per-section gate.
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
- Planner prints a summary table (id, name, #conns, rect, order) for the agent.
- Agent may edit rects / order / connections before routing, or accept as-is.

### 4.3 ROUTE (one section at a time)

For section `Si` in `phaseIndex` order:

1. Load full `SimpleRouteJson` via `getSimpleRouteJsonFromCircuitJson`.
2. Slice with `getRerouteSimpleRouteJson(srj, rect_i)` — only `connections_i`
   are routed; prior sections' traces are preloaded as locked
   (`PreloadedTraceGraph`-style: they are obstacles + connectivity).
3. Run the section router: default = capacity-autorouter pipeline
   (`beta_pipeline9` / `latest`) invoked through `algorithmFn` with a per-section
   timeout + attempt budget. Custom per-phase `autorouter` overrides allowed.
4. On success: convert new traces to locked geometry, append to
   `sections/Si.agent-route.json`, update `plan.json` status → `done`.
5. On failure/timeout: fail-stop (see §4.5), do NOT proceed to `Si+1`.

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

On failure the router STOPS and prints / writes `status.json`:

```json
{
  "completed": ["S1", "S2"],
  "blocked": "S3",
  "blockedRect": { "minX": 0, "maxX": 15, "minY": 0, "maxY": 10 },
  "blockedConnections": ["U2.5 > J3.1"],
  "implicatedRefs": ["U2", "J3", "C9"],
  "errorClass": "DRC_CLEARANCE | NO_PATH | TIMEOUT | STITCH_MISMATCH",
  "drcErrors": [ { "type": "...", "refs": [], "at": {} } ],
  "suggestion": "move U2 +2mm in +x or widen S3 rect by 3mm"
}
```

- `errorClass` taxonomy must be small and stable so agents can branch on it.
  Starting set: `NO_PATH`, `DRC_CLEARANCE`, `VIA_EXHAUSTED`, `TIMEOUT`,
  `STITCH_MISMATCH`, `INPUT_INVALID`.
- Human summary mirrors the same data (✅ completed / ❌ blocked + why).
- Exit code non-zero; no partial write of the blocked section (keep last-good).

### 4.6 AGENT FIX LOOP

1. Agent reads `status.json` + DRC errors.
2. Agent edits placement (`pcbX/pcbY/pcbRotation` in `.circuit.tsx`) or section
   rect / order in `*.agent-plan.json`, or adds explicit pre-routes / keepouts.
3. Agent re-invokes only the blocked section: `agent-route retry-section S3`.
4. Locked prior sections are untouched (sig-validated). No full re-route.

### 4.7 CLI shape (proposed, mirrors `build.sh`/`tsci.sh` UX)

```
tools/agent-route plan <board>              # scan + print plan, write *.agent-plan.json
tools/agent-route run <board>               # route all pending sections in order
tools/agent-route status <board>            # table of section states + sig validity
tools/agent-route retry-section <board> S3  # re-route one section
tools/agent-route drc <board>               # DRC gate only (checks lib)
```

All commands MUST be non-interactive and emit both human text and `--json`.

---

## 5. File formats & invalidation

- `*.agent-plan.json`: `{ version, board, sections[] }` as in §4.2.
- `*.agent-route.json`: section-local solved traces in circuit-json
  (`pcb_trace`/`pcb_via`) or `SimpleRouteJson` fragment + the `rect` +
  input hashes. Must be re-appliable via `manualEdits`-style merge.
- `*.sig`: hash of (placement-relevant source files + plan section + router
  version + router params). Any mismatch → section status back to `pending`.
- Final `*.routed.json`: stitched full-board solution, reusing the existing
  `build.sh` routed-board reuse flow.
- NEVER store agent state inside `.tscircuit/cache`.

---

## 6. DRC design

- Per-section gate: run `DrcEvaluator` (from `@tscircuit/checks`) restricted to
  the section rect + its connections after each section. Fail → fail-stop.
- Final gate: full-board `DrcEvaluator` run. Must be zero-error before
  `*.routed.json` is promoted to final.
- DRC errors are attached to the fail-stop report with implicated refs and
  coordinates so the agent can localise the fix.
- `excludeRefs`-style DRC waivers are NOT a substitute for routing fixes;
  waivers (if ever needed) must be explicit, per-error, and recorded in the
  plan file — never silent.

---

## 7. Validation plan (spike tests first)

1. **Injection spike** (`blank` module): pass a trivial `algorithmFn`
   (e.g. delegate to capacity-autorouter) via `<board autorouter>` and confirm
   `build.sh`-equivalent output is unchanged.
2. **Slice+stitch spike** (`blank`, then `8bit`): `getRerouteSimpleRouteJson`
   on a half-board rect → route → `reconnect…Region` → DRC-clean. This is the
   highest-risk primitive (§8.1) — prove it before building the CLI.
3. **Lock spike**: emit one section as explicit-geometry traces, re-run full
   eval, confirm the router preserves them and routes the remainder.
4. **Fail-stop spike**: craft an unroutable section (blocked rect) and confirm
   the report schema in §4.5 is produced with correct implicated refs.
5. **Resume spike**: route S1, delete cache, re-run — confirm S1 is reused from
   `*.agent-route.json` (sig-valid) and only S2 routes.

---

## 8. Risks & open questions (for reviewer)

1. **Stitch quality at section boundaries.** `reconnect…Region` may introduce
   kinks / clearance violations where section traces cross rect edges.
   Mitigation: overlap rects slightly; run DRC on rect ∪ margin; allow a
   dedicated low-effort "seam polish" pass. Needs the §7.2 spike.
2. **Section ordering sensitivity.** Power / long rails first vs. dense clusters
   first? Proposal: rails + fanout first (they constrain the most), dense
   signal clusters after. Reviewer: is there prior art in the
   `MultiSection*` solvers to copy the ordering heuristic from?
3. **Keepout interaction per section.** Keepouts span section boundaries;
   pre-route trick must be applied per crossing, not globally. Confirm
   `initiallyConnectedMap` semantics hold when traces are added incrementally.
4. **Rect granularity.** Too-small rects starve the maze router (no escape
   room); too-large rects lose the section benefit. Starting rule: rect =
   cluster bbox + clearance margin (≥ 2× max trace pitch). Reviewer: sane default?
5. **Subnet splitting.** A single electrical net spanning two sections needs a
   defined handoff (via / boundary port / breakout point?). Proposal: route
   cross-section nets in the later section with the earlier section's endpoint
   as a fixed obstacle+target. Confirm with spike.
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

1. Does the `algorithmFn` + `<autoroutingphase>` + slice/stitch composition
   actually hold together, or is there a lifecycle ordering problem
   (phase plans vs. custom algorithm invocation) in `@tscircuit/core`?
2. Is the `*.agent-route.json` + `.sig` persistence model sound, or should it
   be expressed as `manualEdits` files instead?
3. Is the `errorClass` taxonomy sufficient for an agent to act without human help?
4. Is the CLI surface minimal-complete? Anything missing for the jigsaw loop?
5. Any correctness risk in freezing sections as explicit geometry (DRC /
   connectivity counting of pours & PTH pads, cf. QFN-EP / via-in-pad precedents)?

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
