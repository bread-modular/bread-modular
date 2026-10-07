# Recommended hybrid routing — explicit, bounded, experimental

**Recommend TraceMaker for compatible ordinary signal work:** inspect intent and fixed
mechanics, place core ICs/power/decouplers/interfaces explicitly, protect critical copper,
freeze the approved layout, let the pinned offline router do selected work, then inspect
and polish with PCB CLI operations. This is not automatic placement or production signoff.
Freerouting remains an explicit alternative for its separately tested subset, never fallback.

## Qualified net-format handoff (supported subset, not blanket admission)

The adapter strictly resolves both legacy top-level numbered definitions and native
KiCad 10 inline quoted names such as `(net "SIGNAL")`. At pin
`c5e1e8497ffef194206a012ee98f0ba156827f71`, a real CPU synthetic loop now passes:
facade placement → complete freeze → selected segment removal → **one deliberate open
closed by two engine-added segments** → independent native/engine checks → recorded CLI
replacement with two ordinary vias → fresh final checks. Matching CLI/pcbnew: 10.0.6.
No upstream patch, format conversion, invented net IDs, downgraded save or relaxed gate.

Quoted numeric name `"1"` is NOT numeric reference `1`. Global definitions must be
unique, consistent and include empty net0; numeric references must resolve exactly.
Inline/global mixtures must agree with existing definitions. Unknown codes, conflicting
names, malformed or ambiguous references reject before strip/run writes. Netless/empty,
mounting, power, unconnected, locked and grouped protections remain. Native via manifests
record canonical names and include numeric codes **only when explicitly defined**.
See [opt-in synthetic proof](tracemaker/test_native.py). Repository-only compact evidence
is `tracemaker/synthetic-verification.json`; it is not a runtime or bundled dependency.
This proves a tiny compatible signal fixture, not full-board/production/GPU placement,
all advanced rules/resources or live GUI interoperability. Other blockers stay explicit.

Freeze now uses the existing bounded `Plan` dependency discovery for same-stem projects:
missing hierarchy/local libraries block; transitive native files are copied, with only
private table/sheet paths rebound. External dependencies require explicit `--library-root`.
3D/image/embedded resource closure is blocked. No HOME/config is discovered or bundled.
Board-only historical freeze is not schematic/parity qualification.

## 1. Inspect and approve placement/critical routes

From a distribution root (`T` may instead be an absolute quoted path):

```sh
T=opt/kicad-tools/kicad_tools.py
python3 -B "$T" pcb inspect --project-dir '/private/selected project' > inspected.json
python3 -B "$T" pcb plan --project-dir '/private/selected project' \
  --ops placement.json --allow-draft-opens > placement-plan.json
python3 -B "$T" pcb apply --plan placement-plan.json --output '/private/NEW placement'
```

Operations/plans must be outside source/output directories. Review actual unique refs,
UUIDs, pad nets, enabled layers and native diagnostics first. This **real v1 schema**
uses the bundled synthetic fixture's R1/R2/SIGNAL; other designs must use their inspection:

```json
{"schema_version":1,"operations":[
  {"op":"move_footprint","target":{"ref":"R2"},"at":[30,21]},
  {"op":"delete_item","uuid":"<inspected existing track UUID>","expected_kind":"track"},
  {"op":"add_polyline","uuid":"<new canonical lowercase UUID>","net":"SIGNAL",
   "layer":"F.Cu","width_mm":0.25,"start":{"pad":{"ref":"R1","number":"1"}},
   "end":{"pad":{"ref":"R2","number":"1"}},"waypoints":[[25,20],[26,21]]}
]}
```

The UUID placeholders are **not executable**. Resolve from inspection/create distinct
UUIDs; [native synthetic test](tracemaker/test_native.py) (optional payload) runs actual
values, placement, selected deletion/replacement and explicit 0.7/0.3 mm vias.
Python API equivalent (no pcbnew imported into the caller):

```python
from automation import inspect, plan, apply
view = inspect(project_dir=source, python="/usr/bin/python3")
p = plan(operations_document, project_dir=source, allow_draft_opens=True,
         python="/usr/bin/python3", kicad_cli="/usr/bin/kicad-cli")
r = apply(p, new_output, python="/usr/bin/python3", kicad_cli="/usr/bin/kicad-cli")
```

Respect outline, pots, sockets, edge clearances, sides/orientations and mechanical anchors.
Place core ICs and power/decouplers/interfaces yourself; route power/returns, sensitive
analog, feedback, clocks/differential and other critical nets manually first. No lock/unlock
API exists. Existing locked items/ancestors are rejected. Moves do **not** drag copper;
no trace dragging, push-shove, live GUI, full-board or automatic-acceptance claim.
A completed `completion.json` is needed for PCB candidates; only explicit opens-only
`--allow-draft-opens` can yield draft (CLI exit 1), never waive ERC/parity/clearances.
Known baseline warnings/exclusions/ignored rules that conflict with PCB apply are blockers,
not permission to relax policy. Use the completion's `board` path under its `inputs/`.

## 2. Freeze, select and route qualified legacy or native inline-named boards

Optional controllers: copy with `bundle NEW --include-tracemaker`; read
[controller help](tracemaker/README.md) and [manual provisioning](tracemaker/BUILD.md)
when that payload is present. No automatic runtime installation.
All following paths are **inspected placeholders**, not a production-board recipe;
`board.kicad_pcb` is an existing root basename and `SIG` an approved ordinary signal.
`ENGINE`, `DEPS`, `DIGEST` must identify the reviewed pinned CPU build.
This stage accepts qualified legacy numeric and native KiCad 10 inline-named boards,
including PCB API saved placement candidates. Freeze the completed candidate (or
explicit opens-only draft) with its complete project context; the strict resolver and
supported-subset gates above still apply, without conversion or waived checks.

```sh
python3 -B "$T" tracemaker --help
python3 -B "$T" tracemaker doctor
python3 -B "$T" tracemaker freeze '/approved/board.kicad_pcb' '/private/NEW frozen'
python3 -B "$T" check --project-dir '/private/NEW frozen' --reports '/private/NEW baseline checks'
python3 -B "$T" tracemaker validate '/private/NEW frozen' board.kicad_pcb '/private/NEW native baseline'
python3 -B "$T" tracemaker run inspect '/private/NEW frozen' board.kicad_pcb '/private/NEW inventory' \
  --engine "$ENGINE" --sha256 "$DIGEST" --deps "$DEPS"
python3 -B "$T" tracemaker run drc '/private/NEW frozen' board.kicad_pcb '/private/NEW engine baseline' \
  --engine "$ENGINE" --sha256 "$DIGEST" --deps "$DEPS"
python3 -B "$T" tracemaker strip '/private/NEW frozen' board.kicad_pcb '/private/NEW stripped' \
  --net SIG --segment-uuid "$AUTHORIZED_SEGMENT_UUID"
python3 -B "$T" tracemaker validate '/private/NEW stripped' board.kicad_pcb '/private/NEW stripped native'
# Deliberate opens: expect validation nonzero here; retain report, NOT acceptance.
python3 -B "$T" tracemaker run route '/private/NEW stripped' board.kicad_pcb '/private/NEW engine output' \
  --experimental --only-net SIG --engine "$ENGINE" --sha256 "$DIGEST" --deps "$DEPS"
```

Freeze preserves **all** transforms, footprint/pad definitions, mechanics/settings and
non-authorized copper exactly, not merely flags. Repeated `--net` authorizes ordinary
signals. `strip` without `--segment-uuid` authorizes **all segments on those nets**;
prefer exact inspected segment UUIDs. Vias remain unless both
`--regenerate-signal-vias` and exact repeated `--via-uuid` are approved; only plain
0.7/0.3 mm F/B signal through-vias qualify. Never strip mounting/net0/power/locked/grouped
objects. Omit strip for already-unrouted qualified signals. `--only-net` bounds one net;
without it the engine can attempt all opens, so every open must belong to the approved set
and unauthorized output must be rejected, not cleaned automatically.

## 3. Independent checks, complete context, then bounded manual polish

Engine exit zero is **not** route completion. First raw-compare the stripped input to
engine output, authorizing only selected additions. Create a NEW **complete candidate**
copy (not the engine-output directory alone), then seal it for independent engine DRC:

```python
import shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path("opt/kicad-tools/tracemaker").resolve()))
import trial
assert trial.compare(stripped / pcb_name, engine_output / pcb_name, ["SIG"])["passed"]
shutil.copytree(stripped, complete_candidate)  # destination NEW
shutil.copy2(engine_output / pcb_name, complete_candidate / pcb_name)
trial.seal(complete_candidate)
```

```sh
python3 -B "$T" tracemaker run drc "$COMPLETE_CANDIDATE" board.kicad_pcb '/private/NEW engine candidate drc' \
  --engine "$ENGINE" --sha256 "$DIGEST" --deps "$DEPS"
python3 -B "$T" tracemaker compare '/private/NEW stripped/board.kicad_pcb' \
  '/private/NEW engine output/board.kicad_pcb' --net SIG
python3 -B "$T" tracemaker validate '/private/NEW stripped' board.kicad_pcb '/private/NEW judged' \
  --candidate '/private/NEW engine output/board.kicad_pcb' --net SIG \
  --baseline-report '/private/NEW native baseline/drc.json'
python3 -B "$T" tracemaker compare '/private/NEW stripped native/canonical.kicad_pcb' \
  '/private/NEW judged/canonical.kicad_pcb' --semantic --net SIG
python3 -B "$T" check --project-dir '/private/NEW judged/project' --reports '/private/NEW final checks'
python3 -B "$T" pcb inspect --project-dir '/private/NEW judged/project'
```

Native validation is raw protection **before reload**, all-track DRC/parity/refill/save,
unchanged assets, exact baseline finding identities, and a pcbnew `snapshot.json` plus
canonical save. Require successful native command completion; warnings/exclusions remain
visible. Independently compare `snapshot.json` footprints/pad/net partition, outline,
layers/zones and vias to the frozen/stripped native baseline. Run full ERC + native XML
ref/pin/net parity as above; inspect geometry/returns visually. Neither DRC nor this
controller proves electrical/mechanical design approval.

Polish via a new reviewed `pcb plan/apply`: explicit selected `delete_item` followed by
replacement `add_polyline`, `add_via`, or approved move/rotate/flip. Reinspect endpoints;
do not reuse stale UUIDs. Every edited baseline needs its operations/plan/completion and
new freeze/native checks. **Do not blindly compare intentional geometry edits to the
old immutable router baseline**: preserve it and retain the authorized delta separately.
CLI-polished native inline-named output can now pass the strict format gate. Re-run final
ERC/DRC/parity/inventory and independent engine DRC on the complete sealed edited
candidate. Missing/unsupported rules or engine warnings remain blockers, not waivers;
otherwise record blocked/draft, not acceptance. Keep hashes, removals, commands,
raw/canonical comparisons and findings as the audit chain; never auto-promote a candidate.
