# Migration inventory: add a thin toolkit, not a board rewrite

This inventory distinguishes reusable operations from frozen board evidence.
No existing command is replaced, no frozen source guards are changed, and no
migration/finalizer is replayed by this toolkit.

| Area | Portable operation | What deliberately stays where it is |
| --- | --- | --- |
| `opt/kicad-jlcpcb/export.py` | Facade `export`, exact pass-through; copy unmodified | Export selection, filtering, field/exclusion semantics and its original isolation/provenance limits |
| `assembly.py`, `catalog.py`, `bom_audit.py`, `passive_planner.py` | Facade `assembly`, common-tool-first API/CLI | Live/offline evidence, request bounds, Basic/Economy gates, no-order-approval policy |
| `add_production_files.py` | Packaged unchanged; existing standalone command supported | Module selection/production mirrors remain repository-oriented, not a generic project installer |
| Repeated balanced-block operations in `modules/base/tools/build_slot_template.py` and migration scripts | `native.source_blocks`, matching-path rebinding in memory, exclusive separate-output helper | Original generators/migrations, reference/UUID/layout assumptions, native engineering decisions |
| Repeated native XML netlist/ref/pin validation in engineering verifiers | `native.read_netlist`, exact identity comparison and conservative PCB ref/pin/net parity; reuse shared XML component parser | Board-specific pin-role/polarity/rail/datum/sourcing/engineering assertions and tolerances |
| ERC/DRC orchestration | `check`, private dependency closure, explicit raw reports/logs/hashes | No edits to rules, exclusions, ignores, connectivity or component placement |
| `modules/{base,16bit-5v,32bit-5v}/tools` | **Nothing executed or modified** by toolkit implementation/tests | Hash-frozen finalizers, regenerators, engineering verifiers and sourcing guards are board evidence, not templates |
| `modules/16bit-5v/tools/jlcpcb_export.py` | **No extraction/replacement** | Intentional frozen duplicate required by guarded evidence |
| `opt/kicad-routing` / `docs/kicad-routing-research.md` | Optional transparent `route` facade and source-only bundle hook | Separately owned routing/runtime/synthetic DSN/SES implementation; no edits, rebases, downloads or router implementation here |
| Libraries / projects / production / firmware / `.history` | Not bundled; source native dependencies copied privately only during checks | User approval/source policies and unrelated main/workspace dirt unchanged |

## Moving to another KiCad project

1. Copy an allowlisted bundle into a **new** directory; retain its relative layout.
2. Make an explicit profile with paths relative to that profile, or select a
   directory/board/root schematic via CLI. Declare custom dependencies; don't
   inherit implicit global custom libraries or module symlink requirements.
3. Run doctor/dry-run, then actual private checks to fresh external reports. Save
   source hashes and all pre-existing findings. Native hierarchical annotation
   and ref/pin/net identity outrank regex-only flattened comparisons.
4. Apply only user-approved design edits to distinct review outputs. Use native
   GUI/Python per the project's policies; never weaken frozen guards or run a
   copied module finalizer on a different board.
5. Manually constrain and route critical nets before optional bounded autorouting.
   Verify source hashes, ERC/DRC/parity and visual output afterward. Export through
   shared tooling with a separate output directory; keep release/order decisions
   under the user's existing manual approval gates.

This is an inventory and workflow, not a source migration or automatic hardware
installation. Do not confuse copied tooling provenance with circuit provenance.
