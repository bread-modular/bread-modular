# Read-only Basic-passive / Economy branch-worker handoff

Prepared from committed Git objects only. No repository files, branches, commits, production outputs or concurrent jobs were changed. No advisor, delegation, authentication, upload or order. Temporary evidence only under /tmp/basic-economy-readonly-vd1r3iml.

**Implementation wait gate:** base checkpoint/job must be complete and shared opt/kicad-jlcpcb catalog.py tooling must be published, documented and tested by its owner. This preparation does NOT certify catalog.py readiness. Do not commit or implement based on the separately relayed commit instruction in this read-only task.

## Authoritative snapshots and source/output paths

### 16bit-5v: `1e50e798d68e3d8d3167fb5fb47bdcb7ee436b83`
- Source: `modules/16bit-5v/16bit-5v.kicad_sch`, `modules/16bit-5v/16bit-5v.kicad_pcb`, `modules/16bit-5v/16bit-5v.kicad_pro`; actual routed/filled board, copper layers ['F.Cu', 'B.Cu'].
- Release: `modules/16bit-5v/production/manifest.json`; SMD-only `modules/16bit-5v/production/assembly/16bit-5v-gerbers.zip`, `assembly/bom.csv`, `assembly/positions.csv`, `assembly/export-report.json`.
- Complete physical inventory: `modules/16bit-5v/production/bom.csv`, `positions.csv`, `manual-assembly.csv`, `netlist.ipc`; legacy `16bit-5v.zip` byte-equals assembly archive. 32bit additionally has production/full and loose production/gerbers.
- Actual assembled R/C refs 43 in 18 BOM groups; unassigned LCSC refs 40.
- All assembled R/C source/PCB values, footprint identifiers and LCSC/MPN/manufacturer fields match; both assembly BOM/CPL ref sets equal actual SMD footprint set. All passive pins agree with committed final netlist (16bit 86 pins; 32bit 90). Library-only KiCad generator/filter fields differ as expected, not sourcing fields. Native voltage/dielectric/tolerance/power-rating fields are absent for ALL R/C groups.
- Manifest SHA checks match committed sources and listed payloads, resolving the 16bit fp-lib-table symlink to committed opt/fp-lib-table. No fresh DRC/ERC/production generation was run.

| Refs | Native value | Exact footprint ID | Recorded LCSC / MPN | Recorded ratings / tolerance | Circuit role / review constraint |
|---|---|---|---|---|---|
| C1, C5 | 0.1uf | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | 3V3 local IC decoupling; preserve local high-frequency current loops. |
| C2, C8, C11, C12, C13, C14, C15, C16, C17, C18, C24 | 100n | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | 3V3 decoupling except C8/C11 on 1V1; retain individual local placement, not a single distant equivalent. |
| C3, C4 | 15p | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | Y1 crystal load capacitors; preserve 15pF, low loss/stable dielectric and oscillator layout; R2 is its damping resistor. |
| C6, C7 | 4.7u | RP2350_60QFN_minimal:C_0402_1005Metric_small_pads | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | C6 RP2350 switching-regulator VIN bulk; C7 1V1 output bulk. Custom reduced lands: package change needs explicit electrical/layout review. |
| C9, C10 | 4.7u | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | C9 VREG_AVDD bypass behind R5 33ohm; C10 far-side 1V1 bulk. Preserve filtering and regulator output/feedback network. |
| C19 | 10u | Capacitor_SMD:C_0805_2012Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | 3V3 bulk; evaluate effective capacitance, ESR and transient support. |
| C20 | 10nf | Capacitor_SMD:C_0805_2012Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | USB shield-to-GND AC coupling; not a supply decoupler. Review dielectric/voltage for the shield application. |
| C21 | 100uf | Capacitor_SMD:C_1206_3216Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | 3V3 100uF bulk; voltage, dielectric, effective capacitance, inrush/ESR not specified natively. |
| C22, C23 | 10nf | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | Audio low-pass shunts on AOUT_1/2; pair with R17/R18 1k, nominal pole about 15.9kHz; preserve stereo matching. |
| C25 | 10u | Capacitor_SMD:C_0805_2012Metric | C15850 / CL21A106KAYNNNE | 16bit CHANGELOG records 25V; 32bit POWER.md records 25V X5R; native rating/tolerance fields absent. | AP2112 input bulk on +5V; retain voltage headroom and effective capacitance. |
| C26 | 100n | Capacitor_SMD:C_0402_1005Metric | C1525 / CL05B104KO5NNNC | 32bit POWER.md records 16V X7R; native rating/tolerance fields absent. | AP2112 +5V input high-frequency bypass. |
| C27 | 1u | Capacitor_SMD:C_0805_2012Metric | C28323 / CL21B105KBFNNNE | 16bit CHANGELOG records 50V; native rating/tolerance fields absent. | AP2112 local +3V3 output capacitor; manufacturer 1uF stability basis must survive tolerance/DC bias; do not rely on nominal value alone. |
| R2, R4, R6, R9, R17, R18 | 1k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | R2 crystal damping; R4 RUN switch series-to-GND; R6 USB_BOOT/QSPI protection; R9 LED current limit; R17/R18 audio series low-pass legs. |
| R3, R11 | 5.1k | Resistor_SMD:R_0603_1608Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | USB-C CC1/CC2 Rd pulldowns; preserve 5.1k and separately review chosen tolerance/compliance. |
| R5 | 33 | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | RP2350 VREG_AVDD 33ohm feed/filter with C9; preserve isolation and noise performance. |
| R7, R8 | 27 | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | RP2350 USB D+/D- series terminations; preserve 27ohm and close-to-MCU placement. |
| R10, R12, R15, R16 | 100k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | R10/R12 CV pullups; R15/R16 AIN pulldowns; preserve input bias/load impedance. |
| R14 | 10k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | PSRAM chip-select pullup; preserve startup/boot behavior. |

Committed verification: [{"kind": "DRC", "committed_path": "verification/drc-final.json", "errors": 0, "warnings": 75, "excluded": 0, "types": {"silk_over_copper": 24, "lib_footprint_mismatch": 47, "lib_footprint_issues": 1, "via_dangling": 3}, "opens": 0, "parity": 0}, {"kind": "ERC", "committed_path": "verification/erc-final.json", "errors": 0, "warnings": 12, "excluded": 0, "types": {"endpoint_off_grid": 5, "lib_symbol_mismatch": 6, "footprint_link_issues": 1}, "opens": 0, "parity": 0}]

### 32bit-5v: `74db23e0aaec4286caaf95eb2c00461ab0999e3e`
- Source: `modules/32bit-5v/32bit-5v.kicad_sch`, `modules/32bit-5v/32bit-5v.kicad_pcb`, `modules/32bit-5v/32bit-5v.kicad_pro`; actual routed/filled board, copper layers ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'].
- Release: `modules/32bit-5v/production/manifest.json`; SMD-only `modules/32bit-5v/production/assembly/32bit-5v-gerbers.zip`, `assembly/bom.csv`, `assembly/positions.csv`, `assembly/export-report.json`.
- Complete physical inventory: `modules/32bit-5v/production/bom.csv`, `positions.csv`, `manual-assembly.csv`, `netlist.ipc`; legacy `32bit-5v.zip` byte-equals assembly archive. 32bit additionally has production/full and loose production/gerbers.
- Actual assembled R/C refs 45 in 17 BOM groups; unassigned LCSC refs 42.
- All assembled R/C source/PCB values, footprint identifiers and LCSC/MPN/manufacturer fields match; both assembly BOM/CPL ref sets equal actual SMD footprint set. All passive pins agree with committed final netlist (16bit 86 pins; 32bit 90). Library-only KiCad generator/filter fields differ as expected, not sourcing fields. Native voltage/dielectric/tolerance/power-rating fields are absent for ALL R/C groups.
- Manifest SHA checks match committed sources and listed payloads, resolving the 16bit fp-lib-table symlink to committed opt/fp-lib-table. No fresh DRC/ERC/production generation was run.

| Refs | Native value | Exact footprint ID | Recorded LCSC / MPN | Recorded ratings / tolerance | Circuit role / review constraint |
|---|---|---|---|---|---|
| C1, C4, C6, C21, C22, C26, C34, C36, C39 | 0.1uf | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | C1 ESP32 rail bypass; C4 CHIP_PU/EN RC; C6 main 3V3 bypass; C21/C22/C26/C39 codec rail bypass; C34 VMID and C36 ADCVREF bypass. Do not pool these by equal value. |
| C2, C8 | 10uf | Capacitor_SMD:C_0603_1608Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | C2 ESP32 supply bulk after FB1; C8 main 3V3 bulk. C2 nominal 10uF must not be downgraded; DC-bias/transient qualification outstanding. |
| C3 | 1uf | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | CHIP_PU/EN reset timing with R3 10k and C4 100nF in parallel. Nominal RC about 11ms; changes need power-up/reset review. |
| C5, C27, C33, C35, C37, C38 | 10uf | Capacitor_SMD:C_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | C5/C37/C38 codec rail bulk; C27 VREF; C33 VMID; C35 ADCVREF. 10uF in 0402: DC-bias/stability/noise review before package/value changes. |
| C7 | 100uf | Capacitor_SMD:C_1206_3216Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | Codec rail +3V3_8388 bulk after R15 10ohm; review effective capacitance, supply drop/filtering, ESR and inrush. |
| C20 | 10nf | Capacitor_SMD:C_0805_2012Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | USB shield-to-GND AC coupling; not a supply decoupler. |
| C40 | 10uf | Capacitor_SMD:C_0805_2012Metric | C15850 / CL21A106KAYNNNE | 16bit CHANGELOG records 25V; 32bit POWER.md records 25V X5R; native rating/tolerance fields absent. | AP2112 +5V input bulk; retain effective capacitance/voltage headroom. |
| C41 | 22uf | Capacitor_SMD:C_0805_2012Metric | C45783 / CL21A226MAQNNNE | 32bit POWER.md records 25V X5R; native rating/tolerance fields absent. | AP2112 +3V3 output bulk; preserve regulator stability and transient response. |
| C42 | 0.1uf | Capacitor_SMD:C_0402_1005Metric | C1525 / CL05B104KO5NNNC | 32bit POWER.md records 16V X7R; native rating/tolerance fields absent. | AP2112 +5V input high-frequency bypass. |
| R1, R2, R9, R13, R17 | 1k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | R1/R2 gate-output series resistance; R9 LED current limit; R13/R17 codec analog-output series resistance. |
| R3 | 10k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | ESP32 CHIP_PU/EN pullup; RC timing with C3/C4. |
| R4, R11 | 5.1k | Resistor_SMD:R_0603_1608Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | USB-C CC1/CC2 Rd pulldowns; preserve 5.1k and review tolerance/compliance. |
| R5, R6 | 1.5k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | CV-buffer-to-pot series resistors; preserve transfer/range with RV1/RV2 50k. |
| R7, R8, R14, R18, R26 | 33 | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | Codec serial-data/clock damping: ASDOUT, LRCK, DSDIN, SCLK, MCLK respectively; these are NOT the USB terminations. |
| R10, R12, R16, R19 | 100k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | R10/R12 CV pullups; R16/R19 analog-input bias to codec VMID, NOT GND; preserve bias/load/noise. |
| R15 | 10 | Resistor_SMD:R_0603_1608Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | Codec +3V3_8388 supply isolation from +3V3; RC filtering and DC drop/power depend on codec load and C5/C7/etc. |
| R24, R25 | 4.7k | Resistor_SMD:R_0402_1005Metric | Unassigned / unassigned | Not recorded; no resistor power/tolerance or capacitor voltage/dielectric/tolerance | Codec control-bus pullups CDATA/CCLK to +3V3_8388; preserve rise-time/loading and voltage domain. |

Committed verification: [{"kind": "DRC", "committed_path": "verification/final-drc.json", "errors": 0, "warnings": 98, "excluded": 0, "types": {"silk_over_copper": 26, "text_height": 16, "lib_footprint_mismatch": 48, "footprint_type_mismatch": 1, "silk_edge_clearance": 3, "via_dangling": 1, "track_dangling": 3}, "opens": 0, "parity": 0}, {"kind": "ERC", "committed_path": "verification/final-erc.json", "errors": 0, "warnings": 16, "excluded": 0, "types": {"lib_symbol_mismatch": 16}, "opens": 0, "parity": 0}]

## Known supplier identities: specification confirmation only, NOT present availability

- `C15850` / `CL21A106KAYNNNE`: 25V X5R +/-10%. Not reliably exposed in retrieved page; do not infer Basic/Extended. 16bit CHANGELOG records 25V; 32bit POWER.md records 25V X5R; native rating/tolerance fields absent. [source](https://jlcpcb.com/partdetail/16287-CL21A106KAYNNNE/C15850)
- `C1525` / `CL05B104KO5NNNC`: 16V X7R +/-10%. Public page shows Basic, SMT, Economic and Standard; no stock claim. 32bit POWER.md records 16V X7R; native rating/tolerance fields absent. [source](https://jlcpcb.com/partdetail/1877-CL05B104KO5NNNC/C1525)
- `C28323` / `CL21B105KBFNNNE`: 50V X7R +/-10%. Public page shows Basic, SMT, Economic and Standard; no stock claim. 16bit CHANGELOG records 50V; native rating/tolerance fields absent. [source](https://jlcpcb.com/partdetail/29074-CL21B105KBFNNNE/C28323)
- `C45783` / `CL21A226MAQNNNE`: 25V X5R +/-20%. Public page shows Basic, SMT, Economic and Standard; no stock claim. 32bit POWER.md records 25V X5R; native rating/tolerance fields absent. [source](https://jlcpcb.com/partdetail/46786-CL21A226MAQNNNE/C45783)

## Non-Basic status versus electrical-review candidates

No existing R/C is proven non-Basic from the native records: 40/43 (16bit) and 42/45 (32bit) have no purchasing code. Do not label these Extended/non-Basic without catalog evidence. C15850 classification was not reliably exposed; the other three known capacitor pages show Basic. Current stock, service-specific order eligibility and attrition quantities remain unverified.
- 16bit priority reviews: C6/C7 custom 0402 small-pad 4.7uF regulator network; C9/C10 4.7uF; C21 100uF/1206; crystal C3/C4; audio C22/C23; retain R5 33ohm and USB R7/R8 27ohm.
- 32bit priority reviews: C5/C27/C33/C35/C37/C38 10uF/0402; C7 100uF/1206; C2 10uF/0603 ESP32 reservoir; R15 10ohm codec rail; reset R3/C3/C4. Unknown ratings must be specified before selecting replacements.
- Basic-passive alternatives may require larger footprints or parallel capacitance; electrical review must preserve effective capacitance at operating bias/temperature/tolerance, ESR/ESL, placement/return loop, regulator stability, codec reference/startup/noise, filter response and inrush. Series/parallel resistance must preserve equivalent resistance, power/voltage limits and parasitic behavior. Do not series/parallel redesign crystal, USB or clock damping merely to reuse a feeder. Adding refs invalidates existing release counts/graph assertions; document intentional deltas, do not bypass tests.
- AP2112 U6 (16bit) / U5 (32bit): manufacturer specifies stability with 1.0uF output and recommends X5R/X7R ceramic. Review effective local output capacitance, not nominal-only C27; higher bulk is not proof of transient/thermal qualification. [source](https://www.diodes.com/assets/Datasheets/AP2112.pdf)
- RP2350 switching network and crystal are layout-sensitive; official guide calls for 4.7uF input/output/AVDD network, 33ohm AVDD filter, specific Abracon inductor orientation and 15pF crystal loads with 1k damping. This pass did not establish a numerical minimum effective switching-output capacitance or bench performance. Full RP2350 datasheet retrieval on host returned HTTP403; do not invent that minimum. [source](https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf)
- ESP32 reference recommends 10uF bulk, supply bypass and RC reset usually 10k/1uF. Preserve C1/C2 at U1 supply, and R3/C3/C4 timing; nominal R3*(C3+C4) = 11ms, not a tested reset time. Existing POWER.md records a non-RF design budget, not permission to enable WiFi/BT. [source](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html)
- ES8388 C27(VREF), C33/C34(VMID), C35/C36(ADCVREF) are reference filters, not interchangeable rail bulk. Existing intended codec datasheet and pin/package evidence: modules/32bit-5v/verification/evidence/ES8388-intended-datasheet.pdf and identity-land-evidence.json. No new codec noise/startup/stability qualification was performed.

## Assembly boundaries and waivers

- 16bit: 62 physical refs, 56 top SMD plus RV1/RV2 1M front manual pots; bottom manual GND1/V_SUPPLY1/J1/J2. 32bit: 61 physical refs, 55 top SMD plus RV1/RV2 50k front manual pots; bottom manual GND1/V_SUPPLY1/INPUT1/OUTPUT1. Exclusion from assembly CSV is footprint type (not DNP); do not upload full physical BOM as an Economy one-side selection.
- 32bit manual CSV still says connector side decision pending, while manifest/release-handoff records user approval to keep placement. Treat approval as placement-only, not physical clearance/process/order approval.
- Both final DRC/ERC have zero errors, zero exclusions, DRC zero opens/parity. 16bit warnings 75 DRC/12 ERC; 32bit 98 DRC/16 ERC. These are stored reports, not fresh execution.
- Both projects explicitly ignore DRC: footprint_filters_mismatch, missing_courtyard, npth_inside_courtyard, pth_inside_courtyard, track_not_centered_on_via, tuning_profile_track_geometries. No added per-item DRC/ERC exclusions, no 32bit rule relaxation (.kicad_dru is comments plus version only).
- 32bit explicitly ignores ERC footprint_filter, four_way_junction, simulation_model_issue, single_global_label. 16bit manifest lists the same four, but its .kicad_pro explicitly serializes only simulation_model_issue; the other three default/tool settings need re-audit on the later CLI. Do not confuse manifest/default ignore accounting with explicit serialized settings.
- Warning types remain disclosed: 16bit silk_over_copper, lib_footprint_mismatch/issues, via_dangling; ERC endpoint_off_grid, lib_symbol_mismatch, footprint_link_issues. 32bit silk_over_copper/edge clearance, text_height, lib_footprint_mismatch, footprint_type_mismatch, via_dangling, track_dangling; ERC lib_symbol_mismatch.
- Both retain underside THT/header-to-pot physical-fit hold, purchased-part matching, rotations/polarity and bench checks. 32bit ES8388 nominal 2.60mm EP, 60.8254% paste and nine open thermal PTH need assembler via-in-pad/stencil/reflow validation. Do not disturb thermal pads, mounts, connector registration or saved copper stack in a passive-only update.
- Historical POWER.md / verification/README.md routing status is stale for 32bit; current authority is actual committed board plus production/manifest.json, verification/final-drc.json, final-erc.json, final-netlist.xml, es8388-ep-delta.json, release-handoff.md.

## Later isolated-worker validation and export commands (NOT executed in this preparation)

Use KiCad 10-compatible CLI and an interpreter with pcbnew for native wrappers; recorded exports used 10.0.6. Preserve libraries/symlinks in the isolated worker copy. Never execute these against the concurrent main checkout. Set M to modules/16bit-5v or modules/32bit-5v and N to its matching basename, OUT to a fresh temporary report directory.

```sh
kicad-cli pcb drc --format json --all-track-errors --schematic-parity --severity-all -o "$OUT/drc.json" "$M/$N.kicad_pcb"
kicad-cli sch erc --format json --severity-all -o "$OUT/erc.json" "$M/$N.kicad_sch"
kicad-cli sch export netlist --format kicadxml -o "$OUT/netlist.xml" "$M/$N.kicad_sch"
python3 -B opt/kicad-jlcpcb/export.py "$M" --output "$OUT/assembly" --require-part-numbers
```

Gate JSON explicitly: no errors (including excluded findings), no opens/parity, empty exclusion lists, disclosed warning/ignore inventory. Check every selected source/PCB value/footprint/LCSC/MPN/rating field, BOM=CPL=actual footprint selection, sides, placement/rotation, filled zones and intended electrical graph; inspect actual ZIP, not native previews alone. Exporter value/footprint differences are warnings and PCB controls BOM; exporter is NOT an electrical/sourcing/DRC approval.

Existing native wrapper command names:
```sh
/usr/bin/python3 -B modules/16bit-5v/tools/verify_power.py --report "$OUT/connectivity.json"
/usr/bin/python3 -B modules/16bit-5v/tools/regenerate_production.py --review-preparation
/usr/bin/python3 -B modules/32bit-5v/tools/regenerate_production.py
```

**Do not run these wrappers unchanged later:** 16bit hard-pins historical workspace/branch/HEAD (39f70c6), final SCH/PCB hashes and authorized copper delta; it refuses a fresh worker or modified source. 32bit enforces 61/55/6 counts, 4Cu, ES8388 footprint identity and original net graph, then hashes /tmp/astra-final-delta-20261002/HANDOFF.md; it is not self-contained and writes outputs before late assertions. Its manifest text also assumes unchanged inherited hardware. Deliberately rebind guards/evidence to the reviewed new worker delta before release; never disable assertions or reuse historical review approval. Do not run historical finalize_pcb.py/apply_review_layout.py/model migration scripts.
- Shared add_production_files.py is generic jlcpcb-tree export, NOT a replacement for either guarded production manifest workflow. Shared exporter permits blanks by default; --require-part-numbers is required for final sourced assembly.
- After shared-tool owner finishes, read updated opt/kicad-jlcpcb/README.md and catalog.py help/tests; no catalog command arguments are guessed here. Existing documented exporter unit command: python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v (not run while that worker edits).

## Official Economy / Economic restrictions and unknowns

Official documentation retrieved 2026-10-05 04:58:34-04:58:36 UTC, with exact timestamps, hashes and cached HTML in supplier-document-retrievals.json. Public catalog specification pages were also read during this pass; they do not establish live stock/reservation.
- Economic PCBA: single-sided placement (SMT/through-hole); Standard supports single/double. 2/4/6Cu, 0.8-1.6mm, 0402 minimum, IC pitch >=0.4mm, standard stack only; delivery single PCB/mouse-bite panel, not V-cut. Limits/options must be checked against the specific board/color/finish/quantity. Both current boards already have one-sided SMD assembly selection; bottom manual parts do not require an SMD side move. [source](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)
- Basic parts incur no feeder loading; Preferred Extended (currently also called Promotional Extended) are manually loaded Extended parts but exempt from Economic feeder fees. Ordinary Extended parts are not categorically excluded from Economic; they incur setup/loading cost. A strict Basic-passive requirement is therefore narrower than Economy or zero-feeder cost. [source](https://jlcpcb.com/help/article/pcb-assembly-faqs) [source](https://jlcpcb.com/parts/basic_parts)
- Economy and Standard service eligibility is a separate part-page field (PCBA Type), not inferred from Basic/Extended or MPN. This pass saw Economic and Standard on C1525/C28323/C45783. An equivalence/shared-stock-pool guarantee for all Economic/Standard parts was NOT established.
- LCSC in-stock does not establish JLC assembly stock: official FAQ explains warehouse-source differences; restock dates unpredictable. Recheck JLC actual service, source/pool, stock timestamp, required quantity plus attrition, MOQ and purchased-part ownership; no present availability claim from repository metadata. [source](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2)
- Economy depanelizing tolerance about 0.2mm; official recommendation trace/component edges >0.3mm from board edge. Open via-in-pad can drain solder; this matters for both existing thermal-hole patterns. Economics does not grant stencil/via/thermal signoff. [source](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2)
- Unknown until later reviewed quote/process check: whole-BOM service eligibility/stock, actual Basic vs Preferred status for unassigned passives, color/finish/volume-specific options, PCB thickness/process fit, QFN inspection/stencil/via handling, component orientation and all physical/bench approvals. No login, upload, quote reservation or order was done.
