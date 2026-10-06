# Portable KiCad toolkit

This is an allowlisted install-by-copy distribution, not a Bread project or a
KiCad/runtime installer. The MIT [LICENSE](LICENSE) and exact copied-source
SHA-256 are in `toolkit-manifest.json`; those hashes are not signed approvals.

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor
python3 -B opt/kicad-tools/kicad_tools.py doctor --project-dir '/path/to/My project'
```

- [Toolkit commands, private checks, profile template and limitations](opt/kicad-tools/README.md)
- [Generic common-tool-first KiCad workflow skill](.agents/skills/kicad-workflow/SKILL.md)
- [Standalone unmodified JLCPCB exporter](opt/kicad-jlcpcb/README.md)
- [Assembly/catalog/audit/planning docs](opt/kicad-jlcpcb/ASSEMBLY.md)
- [Assembly approval/evidence skill](.agents/skills/jlcpcb-assembly/SKILL.md)
- [Migration inventory](opt/kicad-tools/MIGRATION.md) and [verification](opt/kicad-tools/VERIFICATION.md)

Python stdlib + installed KiCad CLI only; no Git or original checkout is needed.
Local checks need no network; catalog/live sourcing and optional routing runtime
commands retain their own explicit policies. Optional routing source/research is
included only when requested and available; never its runtime/JAR/temp files.
No project/library/production/credentials/history/vendor files are installed.
Always use fresh outputs, retain source hashes and native findings, and obtain
manual design/production/order approval under the target project's own policies.
