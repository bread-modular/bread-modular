# agent-route — agent-native section autorouter CLI

Implements design `docs/agent-router-design.md` §4.1 (SCAN), §4.2 + §5 (PLAN),
§4.3–§4.6 (ROUTE/stitch/lock/fail-stop via `run.js` + `lib/route-*.js`),
§4.7 (CLI), §6 (DRC gate).

## Usage

```sh
./tools/agent-route/agent-route plan <board> [--json]            # scan + write src/<board>/<board>.agent-plan.json
./tools/agent-route/agent-route plan validate <board> [--json]   # re-check a hand-edited plan
./tools/agent-route/agent-route status <board> [--json]          # section states + sig validity + timings
./tools/agent-route/agent-route drc <board> [--json]             # full-board runAllChecks gate
./tools/agent-route/agent-route run <board> [--keep-going] [--no-bisect] [--json]
                                          [--timeout-ms N] [--effort N] [--max-bisect-depth N]
./tools/agent-route/agent-route retry-section <board> S3 [--json] [--timeout-ms N] [--effort N]
```

All commands are non-interactive; `--json` switches human text to JSON.
`drc` exits non-zero when any `*_error` is reported (warnings are OK).

## File layout (§4.4)

```
tools/agent-route/
  agent-route          # bash wrapper (mirrors tsci.sh UX)
  cli.js               # command dispatch + human/--json output
  lib/
    constants.js       # paths, plan version, margins, pinned versions
    scan.js            # SCAN: routing-disabled eval + extraction + clustering
    plan.js            # PLAN: rects + assignment + scoring + validate
    sig.js             # per-section .sig hash (shared helper for routing chat)
  test/
    sig.test.js        # sig unit test: node test/sig.test.js [board]
src/<board>/
  <board>.agent-plan.json        # { version, board, createdAt, sections[] }
  <board>.agent-route/           # per-section files (routing chat writes these)
    S1.<name>.agent-route.json
    S1.<name>.agent-route.sig
    status.json
```

Plan schema (§4.2): `sections[{id, name, rect{minX,maxX,minY,maxY},
connections["REF.pin > REF.pin"], phaseIndex, status}]`.

## How planning works

1. **SCAN**: `tsci build --routing-disabled src/<board>/<board>.circuit.tsx`,
   then extract component centres, pads/holes, board outline, and connectivity
   nets (`subcircuit_connectivity_map_key` groups). Nets touching >40% of
   components are marked **global** (excluded from affinity).
2. **Cluster**: union-find over non-global nets → y-row bucketing (8mm gap
   splits) → small rows (<3) merged into best-affinity neighbour → unplaced
   parts attached by affinity. <6 routable nets → whole-board single section
   (e.g. `blank`).
3. **Rects**: cluster bbox over member centres **and pads** + 2mm margin;
   adjacent rects expanded until every pair overlaps by ≥1mm (≥2× trace pitch).
4. **Scoring** (printed, also in `--json`): `cutNets` (connections spanning a
   boundary), per-rect density (conns/mm²), aspect/coverage sanity notes.
5. **Validate** (`plan validate`): exactly-one-section per connection, every
   attributable pad inside some rect, no orphans, pairwise overlap, warn on
   nets spanning 3+ sections.

## Pinned versions (resolved, 2026-09-03)

Design Appendix A was written against these and they still match
(`tscircuit` meta-package now in package.json):

- `tscircuit` 0.0.2462, `@tscircuit/core` 0.0.1816,
  `@tscircuit/capacity-autorouter` 0.0.851, `@tscircuit/checks` 0.0.178,
  `@tscircuit/cli` 0.1.2021, `@tscircuit/eval` 0.0.1321.
- Pinned into every section sig (a version bump invalidates all sections).

## Current plans

- `blank`: 1 section (whole-board fallback), 3 conns, cutNets=0.
- `8bit`: 2 sections (11 + 12 conns), cutNets=9.
- `drive`: 3 sections (5 + 10 + 2 conns), cutNets=8.
