# Current release-status handoff - 32bit-5v

## Scope and ownership

- Current isolated workspace: `/home/azero/.okbrain/workspaces/bread-modular-kicad/282`.
- Current app branch: `okbrain/bread-modular-kicad/282-bcaa15d1`; HEAD/base `65e1d7202f22f0ef8b387e9f1e0c1b6740731ead`.
- Native review/merge target: original `32bit-5v`, unchanged. Complete delta is staged, uncommitted; no commit, merge, push or order authorized/performed.
- Exact input: 75 staged regular module files from read-only workspace `/home/azero/.okbrain/workspaces/bread-modular-kicad/279`, branch `okbrain/bread-modular-kicad/279-57e03384`, same base. Only those file bytes were ported; source/index untouched; no core/cache/pyc/runtime files.
- This closeout changes only `production/manifest.json`, release-status strings/hash inventory in `tools/regenerate_production.py`, and this new handoff. Hardware, libraries, project rules, SCH, PCB, nets, placement, pads, routes, filled zones, stack, ZIPs, CSVs and inherited evidence are unchanged from workspace279.
- No regenerator, migration/finalizer, routing, sourcing, CAM development, artwork rendering or advisor call was run. Supplied final native DRC/ERC reports are reused by exact input identity; no new native DRC/ERC run is claimed.

## Current release status

- User instruction: **"Keep those THT stuff as is."** Retention of all six THT footprints, including the four underside connector bodies, is approved. All 55 SMD parts stay on the front. Actual existing **four copper layers** remain F.Cu, In1.Cu, In2.Cu, B.Cu.
- **Electrical/export data complete; no order authorized.** DRC: 0 errors, 0 opens, 0 parity findings, 98 warnings. ERC: 0 errors, 16 warnings. These are the final source-report gates, not assembly certification.
- Inventory: 61 physical references; 55 top-SMD assembly references; 6 THT/manual references. Bodies: 57 top / 4 bottom. Full BOM/CPL retains all 61; separate assembly BOM/CPL has all 55 top SMD. THT: GND1, INPUT1, OUTPUT1, RV1, RV2, V_SUPPLY1; underside: GND1, INPUT1, OUTPUT1, V_SUPPLY1; RV1/RV2 stay front-facing.
- Delivered fabrication ZIP contains 13 members, including all four copper layers and PTH/NPTH drill files. ZIP/CSV bytes and current final reports are preserved; no outputs were rebuilt.
- Current manifest ownership points here; documentary hashes use the existing `source_sha256`/`outputs_sha256`/`historical_sha256` schema. Historical port, Astra, pre-EP focused checks, EP-delta and export-report ownership/time-state remain intact. Older "side decision pending" wording in byte-preserved manual CSV/export history is superseded by the explicit user approval above, not silently rewritten.

## Remaining preorder assembler review - not waived by THT approval

- **GND1/header-pot fit:** inspect actual lead protrusion/trim and RV1/RV2 pot-case clearance. GND1 pins1/2 overlap RV1 courtyard and pins4/5 overlap RV2 courtyard; opposite body sides alone neither prove a collision nor certify clearance.
- **U4 process:** qualify the retained nine drilled thermal pads/via-in-pad geometry, paste-wicking/voiding risk, stencil thickness/apertures and reflow/thermal process. Via fill/cap or a suitable qualified assembly process remains assembler responsibility; no process approval is claimed.
- **Source/assembly matching:** match missing supplier identifiers and actual parts, confirm MPN/package/pin identity, placement/rotation and assembler preview before ordering. Data completeness is not sourcing readiness or permission to order.
- **EP qualification:** front ES8388 EP is project-selected nominal 2.60 mm copper / 2.65 mm nominal mask; retained 28 outer leads, nine thermal drills and four paste windows. The cached device outline is not manufacturer recommended PCB-land/stencil approval. Preserve the explicit qualification and process cautions.
- Historical Astra review passed pre-EP routing/artwork/identity and requested EP correction. Sol279's final EP correction and actual-ZIP evidence are inherited unchanged; **no post-EP Astra approval exists or is claimed**. This closeout obtains no advisor review.

## Exact preserved SHA-256

```text
PCB 9474a84e034ae9df0aa8cb9f31aa39a5036cc3d9f4fcb5d5bc9974d640fe4fbe
SCH bd774146e97fb1a453b6c3d8cc5af1db08e39f408329eda1f7f8d0b5c0a5741b
ZIP 65ec59b461c919cb4baa325d7d34966051679b4f189611abe3fc4e0b49bbc68f
```

## Staged path inventory

Exactly 76 module-only regular paths: the exact 75-path source inventory plus this handoff. The complete intended delta is staged uncommitted for native review/merge back to `32bit-5v`.

```text
modules/32bit-5v/32bit-5v.kicad_dru
modules/32bit-5v/32bit-5v.kicad_pcb
modules/32bit-5v/32bit-5v.kicad_pro
modules/32bit-5v/32bit-5v.kicad_sch
modules/32bit-5v/Module32.kicad_sym
modules/32bit-5v/Module32.pretty/ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias.kicad_mod
modules/32bit-5v/Module32.pretty/HRO-TYPE-C-31-M-12.kicad_mod
modules/32bit-5v/fp-lib-table
modules/32bit-5v/production/32bit-5v.zip
modules/32bit-5v/production/assembly/32bit-5v-gerbers.zip
modules/32bit-5v/production/assembly/bom.csv
modules/32bit-5v/production/assembly/export-report.json
modules/32bit-5v/production/assembly/positions.csv
modules/32bit-5v/production/bom.csv
modules/32bit-5v/production/designators.csv
modules/32bit-5v/production/full/32bit-5v-gerbers.zip
modules/32bit-5v/production/full/bom.csv
modules/32bit-5v/production/full/export-report.json
modules/32bit-5v/production/full/positions.csv
modules/32bit-5v/production/gerbers/32bit-5v-B_Cu.gbr
modules/32bit-5v/production/gerbers/32bit-5v-B_Mask.gbr
modules/32bit-5v/production/gerbers/32bit-5v-B_Paste.gbr
modules/32bit-5v/production/gerbers/32bit-5v-B_Silkscreen.gbr
modules/32bit-5v/production/gerbers/32bit-5v-Edge_Cuts.gbr
modules/32bit-5v/production/gerbers/32bit-5v-F_Cu.gbr
modules/32bit-5v/production/gerbers/32bit-5v-F_Mask.gbr
modules/32bit-5v/production/gerbers/32bit-5v-F_Paste.gbr
modules/32bit-5v/production/gerbers/32bit-5v-F_Silkscreen.gbr
modules/32bit-5v/production/gerbers/32bit-5v-In1_Cu.gbr
modules/32bit-5v/production/gerbers/32bit-5v-In2_Cu.gbr
modules/32bit-5v/production/gerbers/32bit-5v-NPTH.drl
modules/32bit-5v/production/gerbers/32bit-5v-PTH.drl
modules/32bit-5v/production/manifest.json
modules/32bit-5v/production/manual-assembly.csv
modules/32bit-5v/production/netlist.ipc
modules/32bit-5v/production/positions.csv
modules/32bit-5v/production/previews/32bit-5v-B_Cu.png
modules/32bit-5v/production/previews/32bit-5v-B_Cu.svg
modules/32bit-5v/production/previews/32bit-5v-F_Cu.png
modules/32bit-5v/production/previews/32bit-5v-F_Cu.svg
modules/32bit-5v/production/previews/32bit-5v-In1_Cu.png
modules/32bit-5v/production/previews/32bit-5v-In1_Cu.svg
modules/32bit-5v/production/previews/32bit-5v-In2_Cu.png
modules/32bit-5v/production/previews/32bit-5v-In2_Cu.svg
modules/32bit-5v/production/previews/actual-gerber-top.png
modules/32bit-5v/production/previews/actual-gerber-top.svg
modules/32bit-5v/production/previews/es8388-ep-actual-zip.png
modules/32bit-5v/production/previews/pcb-3d-top.png
modules/32bit-5v/production/previews/pcb-top.png
modules/32bit-5v/production/previews/pcb-top.svg
modules/32bit-5v/production/previews/routed-four-layers.png
modules/32bit-5v/sym-lib-table
modules/32bit-5v/tools/correct_models.py
modules/32bit-5v/tools/finalize_pcb.py
modules/32bit-5v/tools/finish_models.py
modules/32bit-5v/tools/regenerate_production.py
modules/32bit-5v/verification/astra-response.md
modules/32bit-5v/verification/es8388-ep-delta.json
modules/32bit-5v/verification/evidence/ES8388-intended-datasheet.pdf
modules/32bit-5v/verification/evidence/HRO-TYPE-C-31-M-12-drawing.pdf
modules/32bit-5v/verification/excluded-ignored-summary.json
modules/32bit-5v/verification/final-drc.json
modules/32bit-5v/verification/final-erc.json
modules/32bit-5v/verification/final-netlist.xml
modules/32bit-5v/verification/focused-independent-checks.json
modules/32bit-5v/verification/focused-preservation.json
modules/32bit-5v/verification/identity-land-evidence.json
modules/32bit-5v/verification/ignored-check-audit.json
modules/32bit-5v/verification/layout-migration.json
modules/32bit-5v/verification/obsolete-cap-stubs.json
modules/32bit-5v/verification/original-drc.json
modules/32bit-5v/verification/original-erc.json
modules/32bit-5v/verification/original-netlist.xml
modules/32bit-5v/verification/port-report.json
modules/32bit-5v/verification/release-handoff.md
modules/32bit-5v/verification/working-drc.json
```
