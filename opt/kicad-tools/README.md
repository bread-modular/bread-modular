# Portable KiCad toolkit

Native checks, **offline PCB/schematic candidate edits**, bounded routing, JLCPCB
export and assembly sourcing. Canonical home: `opt/kicad-tools/`; no global install
or hardware approval. Agents and humans: start with task `--help`, then its API.

## Quickstart

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor
python3 -B opt/kicad-tools/kicad_tools.py pcb --help
python3 -B opt/kicad-tools/kicad_tools.py schematic --help
python3 -B opt/kicad-tools/kicad_tools.py route --help
```

## Capabilities

| Task | Command | Details |
| --- | --- | --- |
| Dependencies / private ERC, DRC, parity | `doctor`, `check` | [Guide](GUIDE.md), [profile template](examples/project.json) |
| Exact native ref/pin/net comparison | `netlist inspect\|compare` | [Native helpers](GUIDE.md#native-schematicnetlist-helpers) |
| Move/rotate/flip/add footprints; copper, vias, zones, outlines, text, selected deletion | `pcb inspect\|plan\|apply` | [PCB API](automation/docs/api.md) |
| Flat-sheet wires, junctions, local labels | `schematic inspect\|plan\|apply` | [Schematic API](schematic/docs/api.md) |
| Supported ordinary-project DSN/SES routing | `route inspect-project\|plan-project\|route-project` | [Handoff workflow](API.md), [subset](../kicad-routing/SUPPORTED_SUBSET.md) (optional sibling) |
| Gerber ZIP / BOM / CPL | `export` | [Standalone exporter](jlcpcb/README.md) |
| Catalog / BOM audit / passive planning | `assembly` | [Assembly API](jlcpcb/ASSEMBLY.md) |
| Copy / relocate / re-bundle | `bundle [--include-routing]` | [Bundle contract](BUNDLING.md) |

Core Python 3.8+, stdlib only; checks/schematic apply need KiCad CLI 10+.
PCB editing needs matching CLI + pcbnew 10.0.x; routing has separate Linux/native
requirements. Operations edit actual geometry in **NEW private candidates**, not
live GUI push/shove. No automatic placement; a move does **not** drag traces.
Schematic edits need explicit downstream PCB synchronization. See [workflow and
status gates](API.md); a draft is not acceptance or manufacturing approval.

## Useful links

[Detailed guide](GUIDE.md) · [Workflow/API](API.md) · [Verification](VERIFICATION.md) ·
[Migration boundaries](MIGRATION.md) · [Workflow skill](skills/kicad-workflow/SKILL.md) ·
[Assembly skill](skills/jlcpcb-assembly/SKILL.md)

Historical `opt/kicad-jlcpcb` and both `.agents/skills` discovery paths are the
three validated relative aliases. Designs, frozen module scripts and releases
are never migrated by these tools; standalone CLIs and Python APIs remain available.

Experimental discovery: [TraceMaker copied-board runner](tracemaker/README.md) — explicit research-only signal trials; **not** the default router, facade, admission gate or production bundle.
