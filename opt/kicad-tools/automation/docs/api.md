# Python API and v1 JSON schema

## Import without pcbnew in the agent process

```python
import sys
sys.path.insert(0, "/path/to/toolkit/opt/kicad-tools")
from automation import inspect, plan, apply, Error, validate

view = inspect(project_dir="/input/design")
p = plan({"schema_version": 1, "operations": [
    {"op": "move_footprint", "target": {"ref": "R1"}, "at": [24, 18]},
    {"op": "rotate_footprint", "target": {"ref": "R1"}, "rotation_deg": 90}
]}, project_dir="/input/design", allow_draft_opens=True)
r = apply(p, "/candidates/new-design")
assert r["status"] in ("accepted", "draft")  # A draft is NOT accepted/clean.
```

`inspect(*, project_dir=None, board=None, schematic=None, config=None,
python="python3")` returns sorted item UUIDs, kind, references, pad numbers,
nets, absolute mm positions, rotation, sides, layer names and group IDs, plus
closure hashes/native diagnostics. Pads and footprint fields are also enumerated;
only top-level editable kinds can be deleted. Use the **actual enabled layer
names in inspect**, not hardcoded numeric layer IDs.

`plan(operations, *, ops_base=None, allow_draft_opens=False, python="python3",
kicad_cli="kicad-cli", **selection)` accepts a dict or operations JSON file.
Relative `.kicad_mod` paths resolve against that JSON file, or explicit `ops_base`
for a dict. It validates geometry, native targets/layers/nets/locks in memory;
never saves or creates temp files. It returns deterministic operations,
preconditions, anticipated created/touched/deleted UUIDs and `plan_sha256`.
Baseline ERC/XML export/DRC are deliberately deferred until apply.

`apply(edit_plan, output, *, operations=None, python="python3",
kicad_cli="kicad-cli")` accepts a returned plan dict or saved plan JSON filename.
It revalidates all original file hashes (including the original operations file),
closure, native versions, inspection and tool hashes. Supplying `operations` is
optional; it does not allow replacing or weakening the planned operations.
Preflight errors raise `Error`; after candidate creation failures return a
`status="failed"` result and forensic logs. Existing outputs are never reused.

`validate(document, base=None)` only performs strict structural/numeric schema
validation and normalization, returning an independent dict. It does not check
KiCad/netlist semantics. All unknown fields and operations are errors. No eval,
generic setters, symbol creation or automatic reference/net assignment.

Selection uses the existing `project.select_project`/`Plan` closure contract:
`--project-dir` scans only top-level PCB names; multiple require `--board`.
`--board`/`--schematic` paths are relative to that directory. Config and explicit
selection cannot be mixed. Config paths are relative to the config file:

```json
{
  "schema_version": 1,
  "project_dir": "source",
  "board": "source/design.kicad_pcb",
  "root_schematic": "source/design.kicad_sch",
  "dependencies": [],
  "variables": {}
}
```

## Operations document

Exactly `{ "schema_version": 1, "operations": [ ... ] }`; 1..256 operations,
executed in order. All coordinates absolute `[x_mm,y_mm]`, finite numbers
(not bool), within -1000..1000 mm, representable at integer nanometres. Angles
absolute degrees in -360..360 (not deltas). Width/size/drill/clearance values
0.001..20 mm; drill smaller than diameter, text thickness at most size/4.
Duplicate JSON keys/operation UUIDs, nil/noncanonical UUIDs, duplicate added refs,
placeholder refs, controls in strings and unknown nested fields are rejected.

Existing footprint `target` is exactly `{"ref":"R1"}` or
`{"uuid":"canonical-lowercase-uuid"}`. Reference selectors must be unique.
Creation UUIDs are explicit, non-nil lowercase canonical UUIDs and must not
collide with existing items. For polylines/outlines, the first segment uses the
operation UUID, subsequent segments use UUIDv5(operation UUID, decimal segment
index). New footprint children use UUIDv5(operation UUID, `child:N`). No UUIDs of
existing pads/footprints are regenerated.

| `op` | Exactly required keys (plus `op`) | Optional keys |
| --- | --- | --- |
| `move_footprint` | `target`, `at` | none |
| `rotate_footprint` | `target`, `rotation_deg` | none |
| `flip_footprint` | `target`, `side` (`front` or `back`) | none |
| `add_footprint` mechanical | `uuid`, `file`, `mechanical_only:true`, `at`, `rotation_deg`, `side` | none |
| `add_footprint` electrical | mechanical keys with `mechanical_only:false`, plus `reference`, `value`, `footprint_id`, `symbol_path`, `pad_nets` | none |
| `add_polyline` | `uuid`, `net`, `layer`, `width_mm`, `start`, `end` | `waypoints` (default `[]`) |
| `add_via` | `uuid`, `net`, `at`, `diameter_mm`, `drill_mm` | none |
| `add_zone` | `uuid`, `net`, `layer`, `polygon`, `clearance_mm`, `min_thickness_mm` | none |
| `add_outline` | `uuid`, `polygon`, `width_mm` | none |
| `add_edge_line` | `uuid`, `start`, `end`, `width_mm` | none |
| `add_text` | `uuid`, `text`, `layer`, `at`, `rotation_deg`, `size_mm`, `thickness_mm` | none |
| `delete_item` | `uuid`, `expected_kind` | none |

Native `flip_footprint` uses left/right flip about the footprint's current origin;
it is side-setting/idempotent, not a generic mirror. Native flip transforms pad,
field and graphic geometry and rotation; a subsequent absolute rotate sets the
requested orientation. Never rely on copied top/bottom angles being equivalent.

Electrical additions require `footprint_id="Library:Name"`, an explicit
`symbol_path="/root-uuid/.../symbol-uuid"`, and a complete `pad_nets` map such as
`{"1":"SIGNAL","2":"GND"}`. No unknown nets can be created. On apply, ref,
value/library ID and ref/pin/net membership must match the native schematic XML;
then native DRC additionally checks schematic paths/fields/library geometry.
Pins absent from native XML/no-connect electrical pads are not inferred: such
additions are currently unsupported. Existing no-net pads are preserved.

Mechanical additions deliberately have **no reference/pad_nets/value fields**:
board-only footprints with empty reference; templates must have zero electrical
pads (only unnumbered netless NPTH pads or graphics). Templates with groups,
zones, locked children, models/images/embedded files fail closed.

Polyline `start` and `end` are exactly one of:

```json
{"pad": {"ref": "R1", "number": "1"}}
```
```json
{"uuid": "a1a32fdb-03d4-5af0-ba30-cc61ebb78fdb"}
```
```json
{"track": "63528896-a37f-5d61-be91-0b247e3a6e4e", "at": [25, 20]}
```

The UUID endpoint must be a pad/through-via; a branch endpoint must lie exactly on
an existing straight track centerline. Endpoints must be on the named net and
support the requested copper layer. Duplicated pad numbers require pad UUIDs.
Previously created via/track/footprint identities may be endpoints in later ops.
Waypoints are explicit coordinates; repeated/zero-length vertices are rejected.
A branch joins without changing or splitting the original copper item.

Through-vias explicitly span F.Cu/B.Cu; no blind/buried/microvia inference. A layer
transition is three polylines and two explicit vias, not a live routing action.
Zones are single-layer, simple polygons, solid direct pad connection, no holes/
thermal options/keepouts/hatching. `polygon` lists 3..256 distinct vertices and
closes implicitly; self-intersections, zero area and collinear adjacent edges
fail. Outline polygons create Edge.Cuts lines; `add_edge_line` adds a single line.
Final native DRC must validate closure, board shape and clearances.

Text permits `F.Silkscreen`, `B.Silkscreen`, `User.Drawings`, `User.Comments` only
(if enabled); back silkscreen is mirrored. No copper/edge text. Delete requires
the exact selected top-level UUID and expected kind `track`, `via`, `edge_line`
or `text`. Footprint/pad/arc/zone/group deletion, group membership edits, and
same-batch creation-then-deletion are deferred.

## Example: branch routing

```json
{
  "schema_version": 1,
  "operations": [{
    "op": "add_polyline",
    "uuid": "a8861844-ce35-4014-a099-321ca35c05e9",
    "net": "SIGNAL", "layer": "F.Cu", "width_mm": 0.25,
    "start": {"track": "63528896-a37f-5d61-be91-0b247e3a6e4e", "at": [25, 20]},
    "end": {"pad": {"ref": "R3", "number": "1"}},
    "waypoints": []
  }]
}
```

Use UUIDs from your own `inspect`, not these synthetic examples. The same-net
endpoint check is NOT a short/clearance waiver; crossing foreign copper rejects
apply even under explicit draft policy.
