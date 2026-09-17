# BASE v1.3.0 — Phase 2 layout verification

**Electrical layout complete; mechanical assembly release is ON HOLD.** The actual
female slot socket and fitted-shunt height are not established. Do not order or
claim a verified mated stack from the Phase 1 part-number description.

## What changed

- Added and routed all **78** new board components: F1/F2, D2/D3, U6–U17,
  J7–J18, R28–R51 and C22–C47. Total: **163 footprints**.
- Input: both USB VBUS contacts → F1 → VBUS_PROT → FB1/LDO branch and F2;
  F2 → 5V_SYS → twelve mux IN1 pins. D2/D3 cathodes go to their protected
  rails; anodes have short, wide ground connections and paired vias.
- Retained the regulator, FB1/FB2, utility/audio 3.3 V distribution and existing
  hardware. Replaced the old shared slot conductors with isolated VSLOT buses.
  A short audio-feed detour reconnects the original slot-6 take-off to 3.3 V,
  not VSLOT_6. Two audio signal traces detour around channel 12, on the same layer.
- Every VSLOT_n has exactly its five socket pads, mux OUT and two capacitor
  rail pads. Every header pin is a **single 0.25 mm trace endpoint**, not a
  through-route: pin 1 = +3.3V, pin 2 = SEL_n. No VSLOT or 5V_SYS header pad.
- J5's physical A1/A4 lands were renamed B12/B9 to match the existing power-only
  schematic symbol's second GND/VBUS contacts. Their coordinates, sizes and holes
  did not change. Previously those two physical contacts had no PCB nets.
- Cleaned reference-label sizing, moved pad-overlapping jack/switch artwork to
  F.Fab, removed the old filled INPUT silk banner, removed dangling copper, and
  changed the board's printed version to 1.3.0.
- Schematic **byte-for-byte unchanged**. All **85** original footprint positions,
  rotations, pad geometry and UUIDs, all **28 mounting holes**, Edge.Cuts and the
  **two copper layers** are preserved. Actual outline coordinates remain
  (30.48,17.78) to (254.00,177.80): **223.52 × 160.02 mm**.

## Jumper placement interpretation and evidence

The supply sockets are horizontal rows above their corresponding ground sockets.
“On/over the power rail, not in the gap” is implemented as **on the outer/upper
side of the supply row, with the jumper pins parallel to that row**, never on the
module-interior strip between supply and GND. Each header anchor is **3.80 mm above
the supply row**. Its full footprint envelope clears the supply socket envelope
by **0.45 mm**; it remains inside the module shadow.

The 16bit, 8bit, mcc and wave boards all have the same **30.48 × 68.58 mm** outline
(46.99,40.64) to (77.47,109.22), with power at y=50.80 and ground at y=96.52.
Aligning the physical leftmost ground pins (not their reversed front/back pin
numbers) registers the module without changing any connector.

For slot 2:

| Feature | Coordinates / extent, mm |
|---|---|
| Module shadow | x=82.55…113.03; y=27.94…96.52 |
| J8 pin 1 / pin 2 | (91.44,34.30) / (93.44,34.30) |
| J8 full footprint envelope | x=89.915…94.965; y=32.775…35.825 |
| Supply socket full envelope | x=89.625…103.425; y=36.275…39.925 |
| Supply / GND pin rows | y=38.10 / 83.82 |

`connectivity.json` records this check for **all 12 slots**. No additional
bottom-side module component occupies the jumper body area on the four inspected
module boards. This is an XY check, **not a height sign-off**.

The original slot-1 supply row is offset **−0.12 mm in X / −0.10 mm in Y** from the
common module registration. That existing discrepancy was preserved, per the
no-move requirement; check it during the physical mating trial.

![Whole board, module shadows and jumper envelopes](whole-board.png)

![Slot 2: full module shadow and magnified rail-side cluster](slot-2.png)

These are native KiCad layer plots with measured overlays. Teal dashed lines are
module outlines; magenta surrounds headers; orange marks the forbidden inter-row
area. The zoom shows B.Cu routing in blue, F.Cu in red. **Filled zones are omitted
only from a temporary plotting copy** so routes remain visible. Production uses
the saved, filled PCB. Visual inspection found a consistent repeated cluster and
no text collisions; DRC likewise reports no silk/text/dangling warnings.

## Stack-height finding — owner decision required

The Phase 1 sourcing text is not reliable enough to establish a mated height:

- **C2905948 / PZ200-1-02-Z** has **2.0 mm insulation + 4.0 mm mating pin =
  6.0 mm nominal above the base PCB**. Its **2.8 mm** dimension is the solder
  tail, not the above-board body height. [source](https://jlcpcb.com/partdetail/HCTL-PZ200_1_02Z/C2905948)
- **C2894928 / PZ254-1-05-Z-8.5** is a **male header**, with **2.5 mm insulation
  and 6.0 mm mating pins**, not an 8.5 mm-tall female socket. It cannot establish
  the base-to-module gap with the module's existing male header. The schematic
  and BOM were not silently substituted. [source](https://www.lcsc.com/product-detail/Pin-Headers_HCTL-PZ254-1-05-Z-8-5_C2894928.html)
- **C5664** is a 2.00 mm open-top shunt, but its body height and seating tolerance
  were **not verified** from an accessible dimensional drawing. Open-top does not
  by itself prove that it fits under the module. [source](https://jlcpcb.com/partdetail/6116-2_0_Short_circuitcap/C5664)

Required physical check: identify the **actual female socket**, measure the fully
mated base-top-to-module-underside gap, and measure the fitted C5664 envelope.
The nominal header/shunt top is `2.0 + max(4.0, H_shunt)` mm if the shunt seats on
the header body; add seating and manufacturing tolerances. Use at least **0.5 mm
assembly margin** above the worst-case fitted envelope as a design target.
Even with a shunt no taller than 4 mm, this means a **nominal minimum 6.5 mm gap**,
not a claim that the present stack supplies it. No measured stack clearance is
available in this repository. The shunts remain user-fit, not pre-assembled.

## Trace widths, clearances and ground

Assumption: **35 µm / 1 oz external copper**, **10 °C rise** screening calculation.
IPC-2221 external-layer fit: `I = 0.048 × rise^0.44 × area_mil²^0.725`.
It gives minimum widths of **0.172 mm at 0.667 A**, **0.343 mm at 1.1 A**, and
**0.781 mm at 2 A**. This is a sizing estimate, not a thermal test under modules.
The fabrication house's IPC-based calculator describes the model and its limits. [source](https://www.advancedpcb.com/en-us/tools/trace-width-calculator/)

| Routing | Implemented width / drill |
|---|---|
| F1/VBUS_PROT main current path | 1.2 mm; 1.0 mm protected LDO/bulk branch |
| USB contact fanout | two separate 0.5 mm legs, widening at their merge |
| 5V_SYS row buses and input trunk | 1.2 mm |
| New 3.3 V row buses / mux input branches | 0.8 mm (original regulator/audio/utility tracks retained) |
| VSLOT socket buses and main output runs | 1.0 mm |
| Capacitor branches | 0.4–0.8 mm |
| Short TSSOP pin escapes and logic | 0.25 mm; power escape segments approximately 1.2–1.34 mm |
| New ordinary vias | 0.8 mm diameter / 0.4 mm drill |
| Main 5 V layer transitions | paired 1.0 mm diameter / 0.5 mm drill vias; C46 local branch 0.8/0.4 |

General clearance remains **0.20 mm**, minimum track width **0.20 mm**, minimum via
0.70 mm and annulus 0.15 mm; the original global DRC severities and ERC settings
are unchanged. The only clearance exception is an explicit **0.15 mm pad-to-pad
rule wholly inside J5**, whose fixed USB land pattern has 0.175 mm nominal gaps.
It does **not** relax tracks, other parts or the power rails. The two inherited
silent J5 exclusions were removed; final exclusions are empty.

Ground strategy: a filled, board-wide **B.Cu GND plane** (0.25 mm local clearance,
0.4 mm thermal spokes), with short new return traces and local vias at mux ground,
manual-mode pins, resistors and capacitors. Original local pour definitions and
socket GND conductors remain; redundant right-edge GND links were replaced by the
continuous back plane. No return depends on a jumper. Zones were refilled using
the real project settings before final DRC and production export.

### FB1/FB2 land-pattern close-out

Retained the existing capacitor-named 0805 footprint **without moving/resizing its
pads**: each pad is **1.00 × 1.45 mm**, center spacing **1.90 mm**, hence inner gap
**0.90 mm**. Sunlord PZ series Table 4-1 specifies the 2012 recommended dimensions
as `A` (gap) **0.80–1.20**, `B` (pad length) **0.80–1.20**, `C` (width)
**0.90–1.60 mm**. All three actual land dimensions are inside those ranges; the
library nickname need not be changed. This does not change the Phase 1 sourcing
substitution decision. [source](https://www.alfatec.de/fileadmin/productfiles/datasheets/sunlord_pz_series.pdf)

## DRC and electrical verification

KiCad CLI **9.0.8**. Both reports include the same flags:

```sh
kicad-cli pcb drc --format json --schematic-parity --severity-all \
  -o modules/base/verification/drc-after.json modules/base/base.kicad_pcb
/usr/bin/python3 modules/base/tools/verify_power.py \
  --report modules/base/verification/connectivity.json
```

| Finding | Before (v1.2.0 PCB) | After |
|---|---:|---:|
| Active DRC errors | 0 | **0** |
| Previously excluded errors, also exposed by `--severity-all` | 2 | **0** |
| Unconnected items | 0 | **0** |
| Schematic-parity findings | 170 | **0** |
| DRC warnings | 110 | **59** |
| Silk/text/dangling warnings | 57 | **0** |

The before board was fully connected to its **old** nets, not the merged schematic;
its zero ratsnest count was not parity evidence. Final verification passes **1713
assertions** over pin nets/values/sourcing fields, protected geometry, original
project rules/ERC, header leaf routing and all module shadows. No ghost nets remain.
A separate temporary-board test physically removed all twelve header footprints;
independent KiCad DRC still found **0 errors / 0 unconnected items**, proving that
no power connection relies on header copper (`header-removal-proof.json`).
The forensic layout generator was also smoke-tested to a separate board with
zero DRC errors/unconnected items and identical component/net/placement data.
The existing fabrication exporter passed **all 28 tests, including its three
KiCad integration tests**.

### Retained warnings

All 59 are `lib_footprint_mismatch`, not copper connectivity or placement errors:

- **53 inherited instances** retain their existing library-revision/customized
  geometry instead of blindly replacing lands and disturbing the routed board.
- **J5** intentionally adapts two physical pad names to the schematic as explained
  above. Do not refresh it from the unadapted shared footprint without preserving
  that mapping.
- **J1/J2/J4/J6/SW1** intentionally move only pad-overlapping internal silk artwork
  to F.Fab; physical pads and hardware positions remain unchanged.

Full per-instance findings are in `drc-after.json`; reference list is in
`warnings.md`. The inherited mismatches are not a fresh qualification of every
legacy component's manufacturer land pattern. Do not suppress the warnings or
interpret a routed-board DRC pass as assembly certification.

## Production outputs and reproduction

Run after saving/refilling the PCB:

```sh
/usr/bin/python3 modules/base/tools/regenerate_production.py
/usr/bin/python3 modules/base/tools/plot_power.py
```

The regeneration script refuses DRC errors (including excluded errors), missing
connections, or schematic-parity findings. It emits:

- `production/netlist.ipc` — KiCad IPC-D-356, containing the new protected/slot nets.
- `production/designators.csv` — legacy `ref:1` mapping, **163 refs**.
- `production/bom.csv`, `production/positions.csv` — full **163-component**
  hand-assembly-inclusive BOM/CPL. Positions now use native KiCad footprint anchors,
  not Fabrication Toolkit's old auto-translated body centroids; the drill/place
  origin is shared with the Gerbers.
- `jlcpcb/base/{bom.csv,positions.csv,export-report.json,base-gerbers.zip}` —
  **119 SMD components / 32 BOM groups**, with all LCSC numbers present.
- `production/base.zip` and `jlcpcb/production_files/GERBER-base.zip` — exact copies
  of that fresh fabrication ZIP, not stale alternate exports.
- `jlcpcb/gerber/` — freshly extracted **9 Gerbers + PTH/NPTH drills**. Legacy
  renamed Gerbers, stale drill-map PDFs and the old non-copper VScore plot were
  removed rather than mixed with current data. Historical `production/backups`
  and the old JLC plugin database are not production inputs and were not changed.
- `production/manifest.json` records source and artifact SHA-256 hashes and the
  explicit **assembly hold**. The JLC report contains source hashes as well.

Gerber/CPL generation succeeded, but the female-socket/shunt stack and assembler
part/rotation preview still require approval before ordering.

For forensic layout reproduction only, `tools/apply_power_layout.py` accepts an
explicit pre-upgrade PCB and fresh schematic XML. It checks the baseline PCB hash,
loads the real project design rules, and uses `SaveBoard(..., aSkipSettings=True)`
to prevent standalone pcbnew from overwriting the project/ERC settings. Do not
re-run it against later hand-edited layouts; the routed PCB is the deliverable.

## v1.3.1 structure refactor — netlist identity evidence

v1.3.1 moves the twelve flat per-slot power blocks into the hierarchical template
`slot.kicad_sch` (instantiated as `Slot1` … `Slot12`). It is a drawing change
only; the PCB is intentionally untouched. The evidence in this directory:

- `netlist-before.kicadsexpr` — flat netlist exported from the v1.3.0
  `base.kicad_sch` (HEAD before the refactor).
- `netlist-after.kicadsexpr` — flat netlist exported from the v1.3.1 schematic.
- `erc-before.json`, `erc-after.json` — ERC reports (`--severity-all`).
- `slot-refactor-netlist-diff.md` — the tool-generated comparison: **78 nets,
  513 nodes, 163 components, identical names/membership/values**, plus the
  per-instance reference table.
- `slot-template.svg` — plot of the template sheet for review.

Reproduce with:

```sh
kicad-cli sch export netlist --format kicadsexpr -o verification/netlist-after.kicadsexpr base.kicad_sch
kicad-cli sch erc --format json --severity-all -o verification/erc-after.json base.kicad_sch
tools/verify_slot_refactor.py --before verification/netlist-before.kicadsexpr \
    --after verification/netlist-after.kicadsexpr \
    --erc-before verification/erc-before.json --erc-after verification/erc-after.json
```

`production/netlist.ipc` is exported from the **PCB** (not the schematic) and is
byte-identical; `kicad-cli pcb drc --schematic-parity` still reports 0 unconnected
items and 0 schematic-parity findings. The only netlist-file differences are the
per-component `Sheetname` / `Sheetfile` properties and 48 instance-neutralised
`Description` texts (see POWER.md section 8).
