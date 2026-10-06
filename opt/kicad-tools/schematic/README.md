# Flat schematic wire primitives

Small standalone CLI/Python API for agents and humans: **add a wire polyline,
add an explicit junction, or add a local label** to one explicit flat sheet.
No GUI, symbol engine, hierarchy synchronization, PCB edits, or installs.
Uses the existing toolkit's native parser, lossless block spans, and dependency helpers.

```sh
python3 -B opt/kicad-tools/schematic/cli.py inspect --input /path/demo.kicad_sch
python3 -B opt/kicad-tools/schematic/cli.py plan --input /path/demo.kicad_sch \
  --edits edits.json --output-dir /separate/new-draft > plan.json
python3 -B opt/kicad-tools/schematic/cli.py apply --plan plan.json
```

`plan` is write-free; stdout redirection is your explicit plan-file write. Keep
plan/edits files outside the source tree and never redirect onto an input.
Input requires a same-stem `.kicad_pro`, embedded symbols, and unique flat instances.
Output must be **NEW**, outside source/dependency trees, with an existing parent.
`apply` requires native **KiCad CLI 10+**; tested with 10.0.6.

```json
{
  "schema_version": 1,
  "grid_mm": 1.27,
  "edits": [
    {"op": "add_wire", "points": [[15.24, 25.4], [35.56, 25.4]]},
    {"op": "add_local_label", "at": [15.24, 25.4], "text": "SIGNAL"}
  ]
}
```

Review `result.json`: exact native ref/pin/net changes, before/after ERC, and
native save/reload verification. Existing blocks/UUIDs and source files stay
unchanged. Crossing joins require `add_junction`; no-join crossings require an
explicit declaration. ERC findings produce an honest **draft**, not acceptance.
**Wires are not PCB traces. Downstream PCB synchronization plus DRC/schematic
parity checks are required before accepting any design change.**

See [API and safety details](docs/api.md) for Python usage, crossing semantics,
limits, output/exit codes, and synthetic native test commands.
