# API, safety contract, and verification

## Python (standard library only)

Use `python3 -B` (or `PYTHONDONTWRITEBYTECODE=1`) to suppress import caches too.
Add `opt/kicad-tools` to your Python import path, then:

```python
from schematic import inspect_sheet, plan_edits, apply_plan, strict_json

info = inspect_sheet("/input/demo.kicad_sch")
edits = strict_json(open("/outside/edits.json").read())
plan = plan_edits("/input/demo.kicad_sch", "/drafts/new-demo", edits)
# Review plan; persist as JSON yourself if desired. No file is written by plan_edits.
result = apply_plan(plan, kicad_cli="kicad-cli")
```

The narrow public API is those four functions; `Error` is also exported.
Validation/filesystem errors raise `Error`, `ValueError`, or `OSError` before
output reservation. After reservation, operational errors are returned in
`result.json` with `status: operational_error`; retain the directory for diagnosis,
never treat its candidate as accepted. Choose another NEW output when retrying.
CLI validation/operational errors are JSON, not tracebacks. `--help` is normal text.

## Strict edits schema version 1

Required root keys: `schema_version` (integer `1`), `grid_mm` (number), `edits`
(array of 1–256 operations). Optional root key: `crossings` (array).
Unknown keys at any level, duplicate JSON keys, booleans as numbers, and nonfinite
numbers are rejected. There is no expression evaluation or arbitrary setter.

Grid choices in mm: `0.254`, `0.635`, `1.27`, `2.54` (10, 25, 50, 100 mil).
Every new coordinate must be an exact multiple of the explicitly selected grid,
within ±1000 mm. There is **no snapping, coordinate inference, or rounding**.
The parser retains original source geometry; unrelated source coordinates need
not be on the new edit grid. All existing wire segments must be orthogonal.

Operations, with no undocumented optional keys:

| `op` | Required keys besides `op` | Optional keys |
| --- | --- | --- |
| `add_wire` | `points`: 2–128 `[x_mm,y_mm]` numeric points | none |
| `add_junction` | `at`: `[x_mm,y_mm]` | none |
| `add_local_label` | `at`, `text` | `angle`: integer 0, 90, 180, 270; default 0 |

A polyline becomes separate native wire blocks with unique UUID4s. Segments must
be nonzero and orthogonal; collinear overlaps/duplicates are rejected. The final
sheet may contain at most 1024 segments (bounds quadratic intersection checks).
A local label name matches `[A-Za-z0-9_+\-][A-Za-z0-9_.+\-]{0,79}`; no bus ranges,
variables, formatting syntax, or control characters. Common names such as
`+5V`, `-12V`, and `3V3` are supported. Identical local labels at
separate anchors join nets according to native KiCad. Duplicate label anchors
are rejected. Labels may attach to native pin coordinates as well as wires;
unattached labels are reported by native ERC rather than invented pin geometry.

### Crossings and joins

- Shared wire endpoints naturally connect, including consecutive polyline segments.
- An interior crossing or endpoint-on-interior T-join needs an existing junction,
  an explicit `add_junction`, or (only for interior/interior) `no_join`.
- A junction needs at least three distinct wire arms at that exact coordinate.
- `no_join` does **not** remove connectivity elsewhere (labels, pins, other paths).
  It requests a geometric wire crossing without a junction, not globally separate nets.
- No junction/label/no-connect ambiguity is silently resolved; unused, duplicate,
  conflicting `no_join` declarations and endpoint-on-interior `no_join` are rejected.
- This validation also covers pre-existing wire crossings in the selected sheet.
  Declare their intentional no-join semantics when planning additional edits.
- Pin locations/transforms and electrical nets are **not** computed by this tool.
  Native XML/ERC and user review remain the authority for interactions with symbols.

Example: explicit no-join crossing:

```json
{
  "schema_version": 1, "grid_mm": 1.27,
  "edits": [
    {"op": "add_wire", "points": [[15.24,25.4],[35.56,25.4]]},
    {"op": "add_wire", "points": [[25.4,15.24],[25.4,35.56]]}
  ],
  "crossings": [{"at": [25.4,25.4], "mode": "no_join"}]
}
```

To join instead, remove `crossings` and append
`{"op":"add_junction","at":[25.4,25.4]}` to `edits`. Order within the edit list
does not affect final geometry validation. Wires are not automatically split or
existing wire blocks rewritten at junctions; native save/reload connectivity is
verified on a disposable copy.

## Scope and context

Accepts one modern, BOM-free UTF-8 `.kicad_sch` with a required same-stem
`.kicad_pro`. CRLF and Unicode are retained byte-for-byte. KiCad 10.0.6 does not
load a BOM-prefixed schematic; such input is rejected before staging.
Requires embedded `lib_symbols`, valid unique UUIDs, unique annotated refs, and
one same-stem project instance per symbol at the root UUID path. Rejects hierarchy,
repeated/multi-project/multi-unit instances, sheet children, buses, bus entries,
and sheets containing global/hierarchical labels. No symbol edits are available.

Reuses bounded `project.Plan` dependency discovery for project/rules, local
library tables, and allowlisted native libraries. Missing referenced local
libraries, nonlocal URIs, unsupported library kinds, unresolved variables,
custom schematic drawing-sheet paths, symlink/hardlink inputs, and output aliases
are rejected. A missing library table is allowed with embedded definitions;
resulting native library-related ERC findings remain visible, never assumed clean.
No system library installation or per-user library configuration is changed.

Copies the same-stem schematic/project to the NEW output root. Local dependency
layout is retained; external allowlisted dependencies are copied under `context/`.
Only copied library-table URI string tokens may be rebound to portable
`${KIPRJMOD}/...` paths; these rebindings are reported. Project settings, rules,
exclusions, unrelated schematic blocks, and UUIDs are never rewritten. PCB files
are neither discovered nor copied nor loaded. Native verification runs with
private HOME/config/cache directories inside output.

## Plan and apply preconditions

`inspect` reports source/context SHA-256s, symbols' stored placements (not inferred
pins), wires/labels/junctions, and top-level character spans/block hashes. It does
not run native checks. `plan` validates edits and returns schema/version/kind,
absolute input/output paths, **all** dependency hashes, UUID allocations,
candidate hash, and a canonical `plan_sha256`. It does not create directories,
run native commands, or write plan files. The checksum detects accidental edits;
it is not a cryptographic authorization/signature. Treat plan files as trusted
instructions you review, not as untrusted signed objects.

`apply` strictly validates the plan, rediscovers context, checks all hashes,
reconstructs exactly the planned candidate, and exclusively reserves NEW output.
An existing directory (even empty), stale source/project/library hash, aliases,
changed closure, or tampered plan cannot be overwritten/auto-refreshed. Sources
are checked again during staging and at completion. Do not concurrently edit
source/context or manipulate output ancestors while applying; detected changes
are operational errors. All tooling writes target private/output copies only.

Insertion uses `native.source_blocks`; every original top-level block string
and all original surrounding text/whitespace remain untouched. New blocks are
inserted after the last direct child, before the original root closing suffix.
There is no new general-purpose S-expression parser.

## Native reports and honest status

Each apply performs **native XML netlist export and full ERC before/after** on
staged copies, with exclusions requested too. Full native command records and
raw reports are retained. Delivered project/context hashes are also verified
unchanged after native commands, apart from the declared table URI rebindings. The saved candidate is reread and parsed, and the final
candidate bytes are checked after native commands. A disposable `reload/` copy
is force-saved by `kicad-cli sch upgrade --force`, then loaded by a fresh native
XML export; pins, net names, components, and hierarchy must equal the pre-save
candidate. The delivered schematic is **not** KiCad-reserialized, preserving spans.

`connectivity_delta` includes complete `before_pins`/`after_pins` arrays of exact
`ref`, `pin`, `net` strings; `changed_pins` with `before_net`/`after_net`; and
`changed_nets` with exact member sets. Null means no XML membership, not an
invented unconnected pin. Singleton/unconnected-named nets are retained.
Native local net names include their sheet-path prefix (e.g. `/SIGNAL`).
Unexpected component/hierarchy changes or native save/reload changes are errors.
ERC feedback includes counts, severities, and the original violation objects.

Outputs: same-stem `.kicad_sch`/`.kicad_pro`, copied context, `result.json`,
`reports/{before,after,reloaded}.xml`, `reports/{before,after}-erc.json`, private
`before/` and `reload/` copies, and native private config/cache as needed.

| Status / CLI exit | Meaning |
| --- | --- |
| `draft_schematic_checks_clear` / 0 | No after-ERC findings in requested native scope; still requires user review and PCB work |
| `draft_erc_findings` / 1 | Saved/reloaded candidate exists; after-ERC findings remain; honest draft |
| `error` or `operational_error` / 2 | Invalid input/precondition or failed verification; never accept output |

**`accepted` is always false. No PCB synchronization, PCB net updates, DRC,
full-project parity, or GUI-equivalence claim is made.** Review the delta/ERC,
synchronize the downstream PCB in its own workflow, then run PCB DRC and
schematic parity checks before accepting the design.

## Synthetic tests only

```sh
# Safety tests (native cases explicitly skipped):
python3 -B -m unittest discover -s opt/kicad-tools/schematic/tests -v
# Actual installed KiCad XML/ERC/force-save reload, generated fixtures only:
KICAD_SCHEMATIC_INTEGRATION=1 python3 -B -m unittest discover \
  -s opt/kicad-tools/schematic/tests -v
# Generate a disposable fixture; never edits an existing project:
python3 -B opt/kicad-tools/schematic/tests/synthetic.py --output-dir /tmp/new-fixture-parent
```

Fixtures have known embedded two/three-pin symbols. Tests cover wire/pin joins,
T-junctions, explicit crossing/no-join, label joining, exact native netlist deltas,
span/source/context invariance, native ERC and save/reload, strict JSON/grid and
rejected unsupported edits, missing context/hierarchy, stale hashes, and
alias/overwrite errors. No released Bread project is touched; no global installs.
