# Portable KiCad toolkit

Private native checks, offline PCB/schematic edits, bounded ordinary-project
routing and unchanged JLCPCB/assembly delegates. Install-by-copy is **not** a
project, runtime installer or hardware approval.

## Quickstart

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py pcb --help
python3 -B opt/kicad-tools/kicad_tools.py schematic --help
```

| Capability | Discover |
| --- | --- |
| Checks / netlist / edits / export / sourcing / optional routing | [Task table and requirements](opt/kicad-tools/README.md) |
| Candidate handoff / statuses / Python APIs | [Workflow/API](opt/kicad-tools/API.md) |
| Copy / relocate / exact hashes + three relative aliases | [Bundle contract](opt/kicad-tools/BUNDLING.md) |

## Useful links

[Guide](opt/kicad-tools/GUIDE.md) · [Workflow skill](opt/kicad-tools/skills/kicad-workflow/SKILL.md) ·
[Assembly skill](opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md) ·
[Verification](opt/kicad-tools/VERIFICATION.md) · [LICENSE](LICENSE)

Keep the whole relative `opt/` / `.agents/` layout. No original checkout or Git
is needed. Runtime/JAR/work/logs, designs and releases are never bundled.
Geometry edits are not live GUI push/shove; no automatic placement or trace drag.
Schematic edits require explicit PCB synchronization. All approval remains manual.
