# Reproducible tests and compact evidence

Run from repository root; tests only use generated projects, never released modules.
Use a new native prefix/smoke ID on every run. Nothing commits, merges or pushes.

```sh
# Offline unit/CLI tests: unchanged historical 32 + ordinary-project regressions.
/usr/bin/python3 -B -m unittest discover -s opt/kicad-routing/tests -v

# Native/Java integration requires installed KiCad and explicitly prepared runtime.
# Does NOT download or run Java outside Bubblewrap.
/usr/bin/python3 -B opt/kicad-routing/tests/native_project_checks.py --run-prefix local-final

# Historical synthetic-only flow is still separately available.
/usr/bin/python3 -B opt/kicad-routing/run.py smoke --run-id ordinary-final-smoke --route-timeout 120
```

`tests/project_fixture.py` independently generates **Orchard Controller**, a normal
same-stem project in nested paths with spaces, embedded single-sheet schematic,
local symbol library/table and on-grid pins (ERC-clean for PCB editor handoff),
local rect/oval SMD and round PTH footprints, rectangular outline, scalar Default
rules (0.32 mm track, 0.24 mm gap, 0.70/0.35 mm via, 0.65 mm edge). Opposite-layer
SMD terminals force a **real through-via/layer-change**. An existing DATA stub is
explicitly authorized for reroute; SENSITIVE has both locked and unlocked copper,
and footprints are unlocked to exercise placement protection. This is not renamed
historical smoke and never reads released module inputs.

Native suite covers actual NEW CLI plan/apply plus via/save/reload/DRC/parity,
protected locked/unlocked copper, authorized completed-net reroute, standalone
placement-candidate handoff and stale placement approval, write-free planning,
unsupported conditional rule, protected/unplanned opens, stale rules/context,
real 1 s timeout/process-group kill, SES/DSN hashes and session base-design, changed
plan, candidate/run overwrite, native malicious SES placement/protected additions,
path/symlink rejection, and an existing protected through-via roundtrip.
Copied Orchard snapshots also check native inspect/plan parity for both adjacent
and `../Libraries/...` relative fp/sym table URIs, unchanged placements/open UUIDs
and no source writes, plus actual plan/apply routing of the sibling-library copy. Board/footprint groups (locked and unlocked) are explicitly
rejected before native inspection. Unit tests
also cover add/delete invariant comparisons, missing libraries/context, aliases,
unknown schemas, arcs/custom pads/overrides/zones/stackups, effective-setting drift,
explicit approval/no selected-net/auto-placement options and differential intent.

Raw native suite CLI logs and `summary.json` stay in
`work.tmp/native-tests-<prefix>/`; routing runs in `work.tmp/runs/<id>/`. Runtime,
logs, generated inputs/outputs and legal files use existing `*.tmp` ignore rules.
Only source/tests/docs and [compact evidence](docs/project-evidence.json) are
reviewable repository additions. The [pre-merge review evidence](docs/premerge-review-evidence.json)
records the relative-library/group/CWD fixes: **75 unit tests, 15 native tests and
historical smoke passed**. Historical `smoke-summary.json` and original
`tests/test_routing.py` remain unchanged; [SMOKE.md](SMOKE.md) preserves the old
README as historical documentation, not today's general-project authorization.

Native PROPERTY_ENUM assertions and denied read-only instance-lock diagnostics
remain visible/retained. Early probes exposed SWIG `Remove()` proxy ownership and
stdout leak warnings; the general adapter uses `RemoveNative()`, retains borrowed
items only during its bounded worker, and snapshots primitives before DSN export.
No assertion is silently filtered into a claim of board safety.
