# Nudge Tool — Design Plan

A reusable, agent-friendly CLI that auto-resolves tscircuit autorouter DRC errors
for Bread Modular `ts-modules` by "nudging" component PCB placements, with a
per-module whitelist so only intended parts ever move.

Replaces the throwaway `tools/nudge-sweep.sh` / `tools/nudge-sweep2.sh`.

---

## 1. Goals & non-goals

**Goals**
- One command: `tools/nudge run --module 8bit` (and `plan`, `apply`, `restore`, `status`).
- Whitelist which components may move, which axes, and by how much — nothing else ever moves.
- Target nudges at components actually implicated in DRC errors (not a blind sweep).
- Converge to a 0-DRC-error layout, report the best found, optionally apply it.
- Never leave the repo dirty; always restorable; the final applied layout is verifiable.

**Non-goals**
- Not a general router/tuning tool — it only moves component `pcbX`/`pcbY` props.
- Does not touch nets, traces, footprints, or board geometry.
- Does not try to fix "broken build" errors (`pcb_missing_footprint_error`, missing courtyards) — those are source bugs, not placement bugs.

---

## 2. Ground truth established from the repo (verified, not assumed)

These facts were confirmed by reading `build.sh`, the two nudge scripts, `lib/*`,
an example module, `dist/**/circuit.json`, and the tscircuit package source in
`node_modules`, plus one empirical `--routing-disabled` build of `8bit`.

### 2.1 Build model
- `tsci build <entry>` writes the full circuit to `dist/src/<m>/<m>/circuit.json`.
- `tsci build --routing-disabled <entry>` writes an eval **with no routing** and
  **no autorouting/DRC errors** (verified: 994 elements, zero `*_error` entries).
- Full autoroute takes ~35–60s per build (trick + prompt agree).
- `build.sh` adds a routed-board reuse layer (`.routed.json` + `.sig`) — it will
  **skip re-routing** when the placement signature is unchanged, so it is the
  *wrong* entrypoint for a nudge sweep.

### 2.2 The circuit.json element model (how to map errors → components)
`circuit.json` is a flat JSON **array** of elements. The mapping chain is:

```
pcb_component ──source_component_id──> source_component.name   ("R1", "U2", ...)
pcb_port      ──pcb_component_id──> pcb_component ──> name
              └─source_port_id──> source_port.name              ("pin1", "PA6", "cathode")
pcb_trace     ──source_trace_id──> source_trace.name            ("U2-pa6-rv1", "D1-cathode")
              └─route[] ──> start_pcb_port_id / end_pcb_port_id
source_trace  ──connected_source_port_ids[]──> source_port ──> source_component.name
```

Key observation: **`pcb_component` has NO `name` field.** It only carries
`pcb_component_id` + `source_component_id` (+ center/rotation/etc.). The
designator lives on `source_component.name`, so every component-reference must be
resolved through `source_component_id`. `pcb_smtpad` resolves via
`pcb_component_id` (→ `source_component_id` → name).

### 2.3 Real error shapes (from tscircuit package + corpus)

| `type` | class | nudgeable | example message |
|---|---|---|---|
| `pcb_trace_error` | clearance/overlap | ✅ | `PCB trace trace[...] overlaps with pcb_smtpad "pcb_port[.D3 > .cathode]" (accidental contact)` |
| `pcb_pad_trace_clearance_error` | clearance | ✅ | `Pad ... and trace ... are too close (clearance: …, minimum: …)` |
| `pcb_pad_pad_clearance_error` | clearance | ✅ | pad-to-pad too close |
| `pcb_via_clearance_error` | clearance | ✅ | `pcb_via "…" and … "…" are too close (gap: …mm)` |
| `pcb_via_trace_clearance_error` | clearance | ✅ | `Via … and trace … are too close` |
| `courtyard_overlap_error` / `pcb_courtyard_overlap_error` | placement | ✅ | courtyard of one component overlaps another |
| `pcb_footprint_overlap_error` | placement | ✅ | footprint overlaps another element |
| `placement_error` | placement | ✅ | placement blocks routing |
| `not_connected_error` | incomplete-routing symptom | ⚠️ see 2.4 | a net failed to route (usually because placement blocked the router) |
| `pcb_autorouting_error` | router-failed sentinel | ❌ | `Unexpected numItems value: 0. (capacity-autorouter@0.0.100)` |
| `pcb_autorouting_skipped_*` (`trace_length_violations_*`, `placement_errors_*`) | router-skipped sentinel | ❌ | router bailed after placement violations |
| `pcb_missing_footprint_error` | build-broken | ❌ | `No footprint specified for component: <resistor#64 name=".R1" />` |

Error objects that reference geometry carry useful fields: `pcb_component_ids[]`,
`pcb_port_ids[]`, `pcb_smtpad_id(s)`, `pcb_trace_id`, `center {x,y}`, and a
`message` that embeds human-readable endpoints (`pcb_port[.D3 > .cathode]`,
`.R6 > .cathode`). The exact field set varies by type, so the parser must be
defensive (read any of those fields that are present).

### 2.4 What the throwaway scripts got wrong (design must fix this)
1. **Error counting was conflated.** `count_errors()` counted *anything* whose
   type contains `"error"` except `pcb_autorouting_error`, and separately flagged
   `pcb_autorouting_error` as `+SKIPPED`. That means `not_connected_error` and
   `placement_error` were counted as "clearance errors" — and a run could report
   `0` while still carrying un-routed nets. The tool needs a **classifier** with a
   **lexicographic objective** (section 6), not a naive count.
2. **`not_connected_error` is a symptom, not a target.** A placement that blocks
   the router yields dozens of `not_connected_error` + a `pcb_autorouting_error` /
   `pcb_autorouting_skipped_*` sentinel. The trick already notes this ("78 not
   connected errors = routing was skipped, not a net regression").
3. **Fragile `old => new` string substitution.** Each candidate hardcoded the full
   current `pcbX`/`pcbY` literal and replaced the whole substring. Any drift in
   value (e.g. the file already nudged) makes the pattern miss. Must be replaced
   with name-anchored, value-independent editing (section 5).
4. **The `--routing-disabled` fast path is NOT a shortcut here.** It emits no DRC
   errors at all (verified), so it cannot evaluate a candidate. It is only useful
   as a cheap "does the source still compile/eval" pre-check.

---

## 3. CLI interface

Single executable `tools/nudge` (Python 3 stdlib only — the repo already depends
on `python3` in `build.sh`, so no new runtime dep; it shells out to `tsci`/`node`
exactly like the existing scripts).

```
tools/nudge <command> [options]

Commands:
  plan     --module <m>      Parse errors, list implicated components + proposed
                             moves. No edits. Machine-readable with --json.
  run      --module <m>      Run the search; leave the best layout applied
                             (unless --no-apply).
  apply    --module <m>      Re-apply the best layout recorded in the state file.
  restore  --module <m>      Restore the original .circuit.tsx from the backup.
  status   --module <m>      Current error count + classification (no edits).

Global options:
  --module <name>        Module dir under ts-modules/src/  (default: "8bit")
  --config <path>        Override config (default ts-modules/src/<m>/<m>.nudge.json)
  --strategy <s>         greedy (default) | grid | random
  --max-iters <n>        Max full autoroute builds (default 60)
  --time-budget <sec>    Wall-clock budget (default 900)
  --step <mm>            Override per-axis step (default from config)
  --no-apply             Search but do not leave the file modified (run only)
  --json                 Machine-readable output (for agents)
  --verbose              Print per-candidate score lines
```

Agent invocation pattern (matches the requested UX):

```bash
tools/nudge plan --module 8bit            # diagnose first
tools/nudge run  --module 8bit            # converge + apply
tools/nudge status --module 8bit          # confirm 0 DRC errors
```

---

## 4. Config file format

Location: **`ts-modules/src/<m>/<m>.nudge.json`** — co-located with the module so
the whitelist travels with the circuit, and the tool auto-discovers it from
`--module`.

Schema:

```jsonc
{
  "module": "8bit",
  "entry": "8bit.circuit.tsx",            // relative to src/<m>/
  "stepDefaults": { "x": 0.4, "y": 0.4 }, // fallback step per axis (mm)
  "components": {                          // WHITELIST — only these may move
    "U3":  { "axes": ["x"], "step": 0.4, "range": 1.2 },   // U3 ±x up to 1.2mm
    "U1":  { "axes": ["x"], "step": 0.4, "range": 1.2 },
    "RV1": { "axes": ["x", "y"], "step": 0.5, "range": 1.5 },
    "RV2": { "axes": ["x", "y"], "step": 0.5, "range": 1.5 },
    "RV3": { "axes": ["x", "y"], "step": 0.5, "range": 1.5 },
    "C1":  { "axes": ["x"], "step": 0.5, "range": 1.5 },
    "C2":  { "axes": ["x"], "step": 0.5, "range": 1.5 },
    "C3":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "C4":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R1":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R2":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R3":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R4":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R5":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R6":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R7":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "R8":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 },
    "D1":  { "axes": ["x", "y"], "step": 0.4, "range": 1.2 }
  },
  "neverMove": [                            // explicit, documented lock-list
    "U2", "SW1", "INPUT1", "OUTPUT1", "V_SUPPLY1", "GND1"
  ],
  "build": {
    "cacheDir": ".tscircuit/cache",        // relative to ts-modules/
    "timeoutSec": 180                      // per-build timeout (autoroute ~35-60s)
  },
  "search": {
    "strategy": "greedy",
    "maxIterations": 60,
    "timeBudgetSec": 900
  }
}
```

Rules enforced by the tool:
- **Whitelist is authoritative.** Any component name NOT in `components` is
  immutable. `neverMove` is a human-readable lock-list that must be a *subset* of
  "not in `components`" — if a name appears in both, the tool errors out.
- **`range` bounds the total displacement from the original position** (not per
  step), so a component can never drift more than `range` mm from where it started.
- **`axes`** limits which coordinates may change; `step` may be a scalar or
  per-axis (`{"x":0.4,"y":0.5}`).
- The `8bit` whitelist above intentionally **excludes U2** (the ATtiny1616 MCU —
  its QFN exposed-pad via-in-pad + bottom pour make it the anchor of the whole
  routing; the prior sweeps only ever nudged U1/U3, never U2) and **SW1** (the
  tactile switch with a hand-built footprint + aligned "MODE" caption) and all
  frame parts (connectors/rails/mounting holes).

---

## 5. Locating & editing `pcbX`/`pcbY` robustly

**Requirement:** edit `pcbX`/`pcbY` of a named component without hardcoding its
current coordinate, and without corrupting the hand-formatted JSX (comments,
multi-line props, JSX expressions like `footprint={<TactSwitchFootprint />}`).

**Approach — parse with the TypeScript compiler, edit by source span.**

`typescript` and `@babel/parser` are already present in `node_modules` (transitive
deps of tscircuit — verified). A small helper script
`tools/nudge/lib/locate.mjs`:

1. `typescript.createSourceFile(entry, ts.ScriptKind.TSX)` to parse the file.
2. Walk the AST for `JsxOpeningElement` / `JsxSelfClosingElement` nodes.
3. For each element, read its `name` attribute (a string-literal initializer) to
   get the designator, and the `pcbX` / `pcbY` attributes to get their **numeric
   value** and their **source span** (`attribute.initializer.pos/end` for the
   numeric literal token).
4. Emit a JSON map: `{ "U3": { "pcbX": {"value": -4.11, "start": 1234, "end": 1239},
   "pcbY": {...} }, ... }`.

The Python tool then nudges by **splicing the source string**: replace only the
bytes `source[start:end]` with the new number, leaving every other byte untouched.
This is immune to the value-drift that broke the `old => new` scripts, and never
reformats the rest of the file.

**Number formatting:** round to 4 decimal places, strip trailing zeros, keep a
minimum of 1 decimal, and drop a leading zero (`0.4`, not `0.40`; `-7.83` stays
`-7.83`; `-10.9475` stays `-10.9475`). This matches the existing style
(`5.145`, `-12.2`, `-10.9475`).

**Handling of the custom wrappers:** `MCP6002`, `ATTINY1616`, `RV09Pot`, `SMADiode`
all accept `name` + `pcbX`/`pcbY` on the **same** JSX element, so a single
"find the element whose `name` literal equals the target" lookup covers every
component kind (`resistor`, `capacitor`, `chip`, `led`, `potentiometer`).

**Fallback (no AST):** if `typescript` is unavailable for any reason, fall back to
a *name-anchored* regex that (a) matches the opening tag containing
`name="<TARGET>"`, (b) captures the balanced opening-tag slice (up to the first
unescaped `>` outside braces), then (c) does a targeted replace of
`pcbX={<num>}` / `pcbY={<num>}` inside only that slice. Still value-independent,
but the AST path is preferred and is the documented default.

---

## 6. Parsing errors and extracting implicated components

Read `ts-modules/dist/src/<m>/<m>/circuit.json` (a JSON array). Build indexes:

```
source_component: id -> name
pcb_component:    id -> source_component_id
source_port:      id -> {name, source_component_id}
pcb_port:         id -> {pcb_component_id, source_port_id}
source_trace:     id -> {name, connected_source_port_ids[]}
pcb_trace:        id -> source_trace_id
```

**Classifier** (map `type` → class):

```python
CLEARANCE   = {"pcb_trace_error", "pcb_pad_trace_clearance_error",
               "pcb_pad_pad_clearance_error", "pcb_via_clearance_error",
               "pcb_via_trace_clearance_error"}
PLACEMENT   = {"courtyard_overlap_error", "pcb_courtyard_overlap_error",
               "pcb_footprint_overlap_error", "placement_error"}
ROUTER_FAIL = {"pcb_autorouting_error", "pcb_autorouting_skipped_trace_length_violations",
               "pcb_autorouting_skipped_placement_errors"}  # prefix-match "pcb_autorouting_skipped_"
INCOMPLETE  = {"not_connected_error"}
BROKEN      = {"pcb_missing_footprint_error"}
# anything else with 'error' in type -> unknown (warn, don't count)
```

**Extract implicated component names** from each clearance/placement error, in
priority order (first non-empty wins):

1. `pcb_component_ids[]` / `pcb_smtpad_ids` → `pcb_component` → `source_component.name`.
2. `pcb_port_ids[]` → `pcb_port` → `pcb_component` → name (and record the pin via
   `source_port.name`, e.g. `U2.pin6`).
3. `pcb_trace_id` → `pcb_trace` → `source_trace.connected_source_port_ids[]` →
   `source_port` → `source_component.name`.
4. Fallback: tokenize `source_trace.name` (e.g. `"U2-pa6-rv1"`, `"D1-cathode"`)
   on `-`/`_`/`.` and match case-insensitively against the set of known component
   names (built from `source_component.name`). This is how `U2-pa6-rv1` → `{U2, RV1}`.
5. Last resort: regex the `message` for designators (`.R6`, `pcb_port[.D3 > …]`).

The `center {x,y}` field (where present) is retained as a spatial hint and can be
used (optional, v2) to order candidate moves by distance to the violation — but
the primary driver is the name set above.

`plan` prints a table like:

```
U3  x  implicated by 2 clearance errors (U2.pin6->D1, U2.pin7->RV1)
D1  x  implicated by 1 clearance error
RV1 y  implicated by 1 clearance error
```

---

## 7. Search algorithm & bounding

**Cost model:** each full `tsci build` autoroute ≈ 35–60s. So the search is
*build-bound* — the whole design optimizes "fewest builds to zero".

**Objective (lexicographic, minimize):**

```
score = (router_failed,  # 0/1 — a pcb_autorouting_error / *_skipped_* sentinel present
         n_clearance,    # clearance + placement errors (the real target)
         n_incomplete)   # not_connected_error count (tie-break only)
```

"0 DRC errors" is **only** true when `router_failed == 0 and n_clearance == 0 and
n_incomplete == 0`. `BROKEN` (`pcb_missing_footprint_error`) short-circuits the run
with a hard error — nudging cannot fix it.

**Candidate set** for one iteration (greedy default):
- Start from the components implicated by the current errors; if none are
  implicated (or none are whitelisted), fall back to all whitelisted components.
- For each such whitelisted component, generate one neighbor per allowed axis per
  direction within `range` (`±step`). Example: `U3 axes=["x"]` → `{x+0.4, x-0.4}`.
- Order candidates by "implicated component first", then by axis/component order
  in the config (deterministic).

**Greedy descent:**
1. Baseline build → `best_score`.
2. Evaluate each candidate: apply nudge → `rm -rf <cacheDir>` → `tsci build` →
   score → revert.
3. Accept the candidate with the best (lowest) score. If it strictly improves
   `best_score`, commit it and loop; if it ties, keep the best-so-far but stop
   (plateau) unless a `--sideways` taboo budget is enabled; if nothing improves,
   stop.
4. Stop early on `score == (0,0,0)`.

**`grid` strategy** (cheapest, mirrors the prior success): evaluate the whole
single-step neighborhood once, commit the single best candidate, and stop. The
prior sweep found `U3 x+0.4` took 3 errors → 0 in one step, so this is a strong
default fallback.

**`random` strategy** (for large whitelists): sample K random single-axis moves per
iteration and keep the best — avoids the O(|components| × axes) build cost of an
exhaustive neighborhood.

**Bounding:**
- `--max-iters` (default 60) — hard cap on full autoroute builds.
- `--time-budget` (default 900s) — wall-clock cap; checked before starting each
  new build. With ~60s builds, 900s ≈ 12–15 builds; document this explicitly so
  agents set a realistic budget.
- Each candidate is also guarded by `build.timeoutSec` (default 180s) so a hung
  router can't stall the whole run.

---

## 8. Cache-busting (confirmed)

- The autorouter caches routes under **`ts-modules/.tscircuit/cache`** (confirmed
  present; gitignored). The nudge scripts already `rm -rf` it between candidates —
  **keep doing exactly that**, otherwise identical DRC output is the tell of a
  stale cache (trick confirms: cache key = core version + hash of simpleRouteJson;
  effort level is *not* part of the key).
- **Do NOT run `build.sh` for candidates.** `build.sh` reuses `.routed.json` +
  `.sig` and would skip the autoroute. The tool must invoke
  `tsci build <entry>` directly from `ts-modules/src/<m>/` (exactly like the
  throwaway scripts), which forces a fresh autoroute every time.
- **The `--routing-disabled` fast path cannot evaluate candidates** (verified: it
  emits zero `*_error` entries). Its only role is an optional pre-check that the
  source still evals before spending 60s on a full build.
- Before a run, also `rm -f src/<m>/<m>.routed.json src/<m>/<m>.sig` so a stale
  routing artifact never shadows the result if someone later invokes `build.sh`.

---

## 9. Safety, rollback & verification

- **Backup:** on first mutation, copy `src/<m>/<m>.circuit.tsx` to a sibling
  backup inside the repo-adjacent state dir `tools/nudge-state/<m>/original.tsx`
  (gitignored), plus record its SHA-256. `restore` copies it back and verifies
  the hash.
- **State file:** `tools/nudge-state/<m>/state.json` records the original hash,
  the best layout found (component → {pcbX,pcbY} delta), the best score, and the
  run log. `apply` replays the best deltas; `restore` reverts to original.
- **Never leave the repo dirty:** the only tracked file that changes is
  `src/<m>/<m>.circuit.tsx`. `--no-apply` reverts it at the end; otherwise the
  tool leaves the *best* layout applied and reports the exact diff. `dist/`,
  `.tscircuit/`, and the state dir are all gitignored, so no build artifacts leak
  into `git status`.
- **Verification:** after `run`, `status --module <m>` re-builds once and reports
  the classified error table. "Verified DRC-clean" is asserted only when
  `score == (0,0,0)` from a fresh full build. `run` exits non-zero if it cannot
  reach zero within budget (so agents can detect failure instead of trusting a
  "best so far").
- **Determinism:** a config change that reorders or re-scales candidates can
  change results; the run log in the state file records every candidate + score
  for reproducibility.

---

## 10. File layout (proposed)

```
tools/
  nudge                      # executable (python3, stdlib only)
  nudge-lib/
    classify.py              # error type -> class table + index builders
    locate.mjs               # TSX AST locator (uses node_modules/typescript)
    search.py                # greedy / grid / random drivers
    edit.py                  # span-splicing pcbX/pcbY editor + number formatter
  nudge-state/               # gitignored: backups + run state
ts-modules/src/8bit/
  8bit.nudge.json            # per-module whitelist config
```

The existing `nudge-sweep.sh` / `nudge-sweep2.sh` are left in place for reference
and can be deleted once `tools/nudge` proves out.

---

## 11. Implementation order

1. `tools/nudge-lib/locate.mjs` — AST locate + span output (unit-test against
   `8bit.circuit.tsx`: every component name resolves, spans map to the right bytes).
2. `tools/nudge-lib/classify.py` — index builders + classifier + component-name
   extractor (test against `dist/src/drive/drive/circuit.json` and a synthetic
   error array).
3. `tools/nudge-lib/edit.py` — span splicing + formatter (round-trip test:
   nudge + revert restores byte-identical file).
4. `tools/nudge-lib/search.py` — objective + greedy driver.
5. `tools/nudge` — CLI glue, backup/state/restore, `plan`/`run`/`apply`/`status`.
6. Config: write `ts-modules/src/8bit/8bit.nudge.json`.
7. Smoke test: `tools/nudge plan --module 8bit`, then `run --module 8bit
   --strategy grid` and confirm `status` reports zero.
