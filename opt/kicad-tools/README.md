# Portable KiCad toolkit

Common tools for **private ERC/DRC, native netlist inspection, JLCPCB export and
read-only assembly sourcing**. Canonical home: `opt/kicad-tools/`. No board
migration, global install or automatic production/order approval.

## Quick start

From the repository or portable distribution root:

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor
python3 -B opt/kicad-tools/kicad_tools.py export --help
python3 -B opt/kicad-tools/kicad_tools.py assembly --help
```

Python **3.8+**, stdlib only. Private checks need **KiCad CLI 10+**; the standalone
exporter retains **KiCad 9+** support. `pcbnew` is optional for core commands;
[routing](GUIDE.md#optional-routing-integration) has separate requirements.
No new third-party packages are installed by this toolkit.

## Choose a task

| Task | Command / guide |
| --- | --- |
| Select a project, diagnose dependencies, run private checks | [`doctor` / `check`](GUIDE.md#select-inputs-not-an-entire-repository), [profile template](examples/project.json) |
| Inspect or compare exact ref/pin/net identities | [`netlist`](GUIDE.md#native-schematicnetlist-helpers) |
| Produce Gerber ZIP, BOM and CPL | [`export`](jlcpcb/README.md) |
| Catalog lookup, BOM audit, passive planning / existing Python APIs | [`assembly`](jlcpcb/ASSEMBLY.md) |
| Install by copy, relocate or re-bundle | [`bundle`](BUNDLING.md) |
| Optional separately owned routing | [`route`](GUIDE.md#optional-routing-integration) |

## Locations and safety

- **JLCPCB tools:** `jlcpcb/`; historical `opt/kicad-jlcpcb` is a relative symlink.
- **Agent skills:** [KiCad workflow](skills/kicad-workflow/SKILL.md) and
  [JLCPCB assembly](skills/jlcpcb-assembly/SKILL.md) live in `skills/`;
  `.agents/skills/{name}` are relative discovery symlinks, not duplicate skills.
- Checks use private copies and fresh external reports, keep source hashes and
  native findings, and never weaken rules/exclusions. Export/assembly delegates
  preserve their own output, overwrite and explicit network options.
- Frozen module scripts, designs and production releases stay untouched.
  No generic source-edit API is introduced here; manual electrical/release/order
  approval remains separate.

## Read more

[Detailed command/safety guide](GUIDE.md) · [Layout and bundle contract](BUNDLING.md) ·
[Migration boundaries](MIGRATION.md) · [Tests and verification](VERIFICATION.md)

Agents: read the relevant skill and actual subcommand `--help` before acting.
