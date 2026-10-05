# Base routing and sourcing preservation checkpoint

This bounded **Sol Max-only** verification checks the completed, previously uncommitted
main-checkout changes against parent `ca5f903c426c55c39533b570dea412630d880741`. Advisor/delegation is disabled.
This is a preservation checkpoint, **not Economy readiness, order approval or a new
full-board release review**. Original circuit files were not edited by this verification.

## Actual results

- Fresh CLI checks on exact live sources copied to private `/tmp` inputs: **0 DRC errors,
  0 unconnected, 0 schematic-parity issues**, both saved-copper and temporary-refill checks.
  **73 lib_footprint_mismatch warnings** remain (parent 70; added C46/R60/R61).
  `--severity-all --exit-code-violations` returns **5**, honestly reflecting warnings.
- ERC remains **7 errors** (J2/J4 R/T disconnected; U5 VIN and #PWR025/#PWR026 power
  not driven) + **4 library-symbol warnings**. Complete violation objects match parent.
  CLI exit **5**. Project/rules and all severities/exclusions are byte-unchanged.
- **162 physical references /519 connected reference-pin netsets** match between native
  schematic XML and PCB. R11/R13/R22/R23/V1/V2/V3 are explicit, pre-existing native
  simulation-only board exclusions, unchanged from parent; not new waivers.
- Both inputs preserve 2M via 1M **C26083** pairs R5+R60 /R24+R61. Only existing
  R5.1/R24.2 pin nets change to the two series midpoints; midpoint nets contain exactly
  the appropriate two resistor pads. All other old pad nets and placement anchors match.
- C46 stays 100uF, now **C15008 /CL31A107MQHNNNE /C_1206_3216Metric**.
  Pad-local centres stay +/-1.475 mm; pad size changes 1.15x2.7 -> **1.15x1.8 mm**.
  This is the only old footprint/pad geometry change. Voltage metadata changes
  16V -> **6.3V**; derating/vendor approval was not newly verified.
- Exact production report source SHA-256 values match PCB and schematic. **33 BOM rows,
  117 unique refs /quantity /CPL refs**, zero source-metadata mismatches/missing codes.
- BOM/CPL byte-match a private re-export. Both committed ZIP locations byte-match,
  CRC passes, all **11 loose Gerber/drill members** byte-match their archive. Fresh
  re-export member content matches after normalizing **only creation timestamp comments**.
- Correctly populated private fixtures: **52 exporter/wrapper tests passed, no skips**,
  including real base/J5/capacitor integration and MCP6002/line_in/4mix real exports.
  **6 assembly-datum tests passed** (non-fatal KiCad binding diagnostics were emitted).
  The partial-copy missing-fixture failures were corrected by copying actual inputs;
  only obsolete base totals **115 ->117 /35 ->33** were changed in existing test source.

## Source identities

```text
modules/base/base.kicad_pcb  806a7603e50f22f0fc7c1b6e73fbe40f8e090f56e90e9c32dd5670e36fc01af9
modules/base/base.kicad_sch  360b5e3e47a98325d677192a294077f12536ab459660d62b0c0c941250f8d8d7
```

## Verified topology

```text
IN_R_PROT -- R5.2 [R5 1M] R5.1 -- Net-(R5-Pad1) -- R60.2 [R60 1M] R60.1 -- +2.5V
IN_L_PROT -- R24.1 [R24 1M] R24.2 -- Net-(R24-Pad2) -- R61.1 [R61 1M] R61.2 -- +2.5V
C46.1 = 5V_SYS; C46.2 = GND; C46 anchor/rotation unchanged.
```

## Pertinent actual source diff excerpts (tabs expanded for display)

```diff
        )
    )
-   (footprint "Capacitor_SMD:C_1210_3225Metric"
-       (layer "F.Cu")
-       (uuid "e5858e04-7693-48ce-8842-dd59061336b4")
-       (at 51.2 35.8 180)
-       (descr "Capacitor SMD 1210 (3225 Metric), square (rectangular) end terminal, IPC-7351 nominal, (Body size source: IPC-SM-782 page 76, https://www.pcb-3d.com/wordpress/wp-content/uploads/ipc-sm-782a_amendment_1_and_2.pdf), generated with kicad-footprint-generator")
...
+           )
+       )
+       (property "LCSC" "C15008"
+           (at 0 0 180)
+           (layer "F.SilkS")
+           (hide yes)
+           (uuid "a4a8ecee-b2c1-41de-adf5-0a9e8fed0640")
...
+       (descr "Resistor SMD 0402 (1005 Metric), square (rectangular) end terminal, IPC_7351 nominal, (Body size source: IPC-SM-782 page 72, https://www.pcb-3d.com/wordpress/wp-content/uploads/ipc-sm-782a_amendment_1_and_2.pdf), generated with kicad-footprint-generator")
+       (tags "resistor")
+       (property "Reference" "R60"
+           (at 2.1 1.1 180)
+           (layer "F.SilkS")
+           (uuid "d00a06a1-015c-468f-a88c-01662ff130cd")
+           (effects
...
+       (descr "Resistor SMD 0402 (1005 Metric), square (rectangular) end terminal, IPC_7351 nominal, (Body size source: IPC-SM-782 page 72, https://www.pcb-3d.com/wordpress/wp-content/uploads/ipc-sm-782a_amendment_1_and_2.pdf), generated with kicad-footprint-generator")
+       (tags "resistor")
+       (property "Reference" "R61"
+           (at -0.002 1.143 0)
+           (layer "F.SilkS")
+           (uuid "b3c379ac-ff8d-41f2-9ea4-3e3a33eda571")
+           (effects
...
+           (layers "F.Cu" "F.Mask" "F.Paste")
+           (roundrect_rratio 0.25)
+           (net "Net-(R5-Pad1)")
+           (pintype "passive")
+           (uuid "a6b7a1c4-5b6d-4b93-9236-cc851cf6dd77")
+       )
+       (embedded_fonts no)
...
+           (layers "F.Cu" "F.Mask" "F.Paste")
+           (roundrect_rratio 0.25)
+           (net "Net-(R24-Pad2)")
+           (pintype "passive")
+           (uuid "dd0f2d07-9d35-4b1b-affd-77067b338220")
+       )
+       (pad "2" smd roundrect
```

Other exact sourcing deltas: C5 C472806 ->C1710, C6/C17 C90146 ->C12891,
C18/C19 C1705 ->C19666; native MPN/manufacturer values synchronized. Full
per-reference metadata deltas, pin/pad details and payload hashes are in the sibling JSON.

## Shared-tool preservation

`export.py` and base assembly-datum tools/docs have **no pending diff**: their existing
private CLI staging/native XML and offset support is already in HEAD and retained.
This checkpoint adds the existing 311-line production wrapper, its 15 tests and README
usage section. `tests/test_export.py` changes **only the two base total expectations**;
J5 `(4.035000,130.810000,270.000000,top)`, C50-C52 C1525 metadata, source-immutability
and CSV-parity checks stay intact. No sourcing-worker changes are included.

## Important limitations

- R18/R19 **680k C25822 are Preferred Extended, not Basic**. No claim of full-board
  Basic/Economy conversion. Supplier tiers/stock and order-review status are not revalidated.
- Prior `verification/` release/assembly records are preserved historical evidence;
  their old 115/35/70 counts and frozen confirmation do not approve current source hashes.
  This new checkpoint records the current bounded results without rewriting old baselines.
- Unknown nested repositories `modules/base/.history/` and `modules/32bit-5v/.history/`
  remain untracked and untouched. No stash/reset/checkout/clean/deletion or branch merge.

## Exact narrowly scoped checkpoint paths

```text
modules/base/base.kicad_pcb
modules/base/base.kicad_sch
modules/base/jlcpcb/base/base-gerbers.zip
modules/base/jlcpcb/base/bom.csv
modules/base/jlcpcb/base/export-report.json
modules/base/jlcpcb/base/positions.csv
modules/base/jlcpcb/gerber/base-B_Cu.gbr
modules/base/jlcpcb/gerber/base-B_Mask.gbr
modules/base/jlcpcb/gerber/base-B_Paste.gbr
modules/base/jlcpcb/gerber/base-B_Silkscreen.gbr
modules/base/jlcpcb/gerber/base-Edge_Cuts.gbr
modules/base/jlcpcb/gerber/base-F_Cu.gbr
modules/base/jlcpcb/gerber/base-F_Mask.gbr
modules/base/jlcpcb/gerber/base-F_Paste.gbr
modules/base/jlcpcb/gerber/base-F_Silkscreen.gbr
modules/base/jlcpcb/gerber/base-NPTH.drl
modules/base/jlcpcb/gerber/base-PTH.drl
modules/base/jlcpcb/production_files/GERBER-base.zip
opt/kicad-jlcpcb/README.md
opt/kicad-jlcpcb/add_production_files.py
opt/kicad-jlcpcb/tests/test_add_production_files.py
opt/kicad-jlcpcb/tests/test_export.py
modules/base/verification/routing-sourcing-checkpoint.json
modules/base/verification/routing-sourcing-checkpoint.md
```
