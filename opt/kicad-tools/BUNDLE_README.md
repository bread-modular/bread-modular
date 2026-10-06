# Portable KiCad toolkit

Private native checks, netlist inspection, JLCPCB export and read-only assembly
sourcing. This allowlisted install-by-copy distribution is **not** a Bread
project, KiCad/runtime installer or hardware approval.

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor
python3 -B opt/kicad-tools/kicad_tools.py export --help
```

- [Start here: commands, requirements and safety](opt/kicad-tools/README.md)
- [Detailed command guide](opt/kicad-tools/GUIDE.md)
- [Canonical layout, manifest, compatibility symlinks and re-bundling](opt/kicad-tools/BUNDLING.md)
- [KiCad workflow skill](opt/kicad-tools/skills/kicad-workflow/SKILL.md) and
  [assembly skill](opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md)
- [Standalone exporter](opt/kicad-tools/jlcpcb/README.md) and
  [assembly/catalog/audit/planning APIs](opt/kicad-tools/jlcpcb/ASSEMBLY.md)
- [Migration boundaries](opt/kicad-tools/MIGRATION.md) and
  [verification](opt/kicad-tools/VERIFICATION.md)

Canonical files live under `opt/kicad-tools/`. Historical `opt/kicad-jlcpcb` and
both `.agents/skills/{name}` paths are validated relative directory symlinks;
preserve them when relocating. [LICENSE](LICENSE) and `toolkit-manifest.json`
cover tooling file/link-text provenance, not signed design/release approval.

Core Python 3.8+, stdlib + installed KiCad CLI; no Git or original checkout
needed. Local checks/bundling are offline. Catalog/live sourcing retains its
explicit policies. Optional routing is included only when requested and
available, with reviewed code/tests/research/historical evidence, **never** its
runtime/JAR/temp files. Routing separately needs Python 3.9+, Linux x86_64,
KiCad 10.0.6 system bindings and Bubblewrap (see `opt/kicad-routing/README.md`).
No project/library/production/credentials/history/vendor files are installed.
Use fresh outputs, keep source hashes/native findings and obtain manual
electrical/production/order approval under your own project's policies.
