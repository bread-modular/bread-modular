# BASE 1.3.14 — current power/audio implementation and limitations

**Current authority: `base.kicad_sch` + hierarchical `slot.kicad_sch` and the
saved/refilled PCB.** The current uncommitted candidate adds SMD rail/MONO
selectors and mode LEDs, cleans selector routing, and corrects headphone
control-to-channel mapping. Current source-bound evidence is in
`verification/footprint-library/summary.json`. The earlier `selectors/` and
`routing-polish/` summaries are historical snapshots of the preceding work.
These are software checks, not order, bench, mating, or vendor-placement approval.
Older CHANGELOG/migration evidence and frozen release scripts remain history.

**Completion audit:** the twelve slot schematics now contain the actual selector,
MOSFET, LED and resistor circuits, and all 48 PCB associations use their real
schematic UUIDs. All 636 physical ref/pin/net pairs match the native XML netlist.
The earlier completion pass removed the saved dangling +3.3V branch (two vias and
four segments) and refilled zones without changing placements or other copper.

**Footprint-library follow-up:** all 61 library-copy warnings are resolved using
14 explicitly project-local footprint variants and matching schematic assignments.
All physical geometry, pad nets, placement, copper, silk, fills and rules are
unchanged. Current results: **0 DRC errors, 0 warnings, 0 opens, 0 parity findings**.
The same 7 pre-existing root-sheet ERC errors and 4 symbol-library warnings remain;
there are no new selector-sheet findings or suppressions.

The earlier routing-polish and LED-placement before/after reports were missing.
Their restored READMEs explicitly distinguish current preservation evidence from
unverified historical counts. The stack/mating claims below were not remeasured
by this completion audit; `selectors/summary.json` does not certify those claims.

Current JLCPCB upload files are `jlcpcb/base/base-gerbers.zip`, `bom.csv` and
`positions.csv` (169 top-side placements, 35 BOM rows). The earlier live Basic
part audit is retained in `verification/selectors/jlcpcb-basic-parts.json`;
no part substitutions were needed. Vendor placement/polarity preview and order
approval remain outstanding.

The exact original 979-line engineering/source rationale, including numbered
historical sections 1–11, is preserved in
[POWER-HISTORICAL-pre-1.3.12.md](POWER-HISTORICAL-pre-1.3.12.md).
That clearly **superseded historical record** is not current circuit, PCB,
manufacturing or ordering guidance; use the present schematics and current
verification summaries for behavior and artifacts.

## Circuit retained

```
USB-C J5 VBUS -> F1 -> VBUS_PROT
                       |-> D2 TVS -> GND
                       |-> input bulk/decoupling + status LED
                       |-> FB1 -> LDO_VIN -> U5 AP2112K-3.3 -> FB2 -> +3.3V
                       |-> F2 -> 5V_SYS -> D3 TVS + C46/C47
                       |-> each mux MODE + SW2..SW13 pin 3 (logic reference)
```

- F1 is the existing 2 A hold input PPTC; F2 is the existing 1.1 A hold
  **shared** 5 V branch PPTC. PPTC trip ordering is intent, not guaranteed
  discrimination under all ambient temperatures/fault currents.
- `SW1` controls the regulator enable/reset path. It does not cut `VBUS_PROT`
  or `5V_SYS`. `VBUS_PROT`, not the resettable 3.3 V rail, biases the selectors.
- Bread Modular's signal contract is **0–3.3 V**, also for modules powered from
  a 5 V slot using their own regulator. It is not a 5 V audio-input contract.

## All twelve TPS2116DRLR muxes

`U6..U17` use the real `Package_TO_SOT_SMD:SOT-583-8` land pattern. The pin
map is checked against the current schematic and TI's DRL package/pin table.
The footprint uses eight 0.67 × 0.30 mm lands at 0.50 mm pitch with 1.48 mm
row spacing. [source](https://www.ti.com/lit/ds/symlink/tps2116.pdf)

| TPS2116 pin | Signal | Board net, slot n |
|---|---|---|
| 1 | GND | GND |
| 2, 7 | VOUT | VSLOT_n, all five VSUPPLY_n pins, output decouplers |
| 3 | VIN1 | 5V_SYS |
| 4 | PR1 | SEL_n, SW(n+1).2, Qn gate, 100k pulldown |
| 5 | MODE | VBUS_PROT |
| 6 | VIN2 | +3.3V |
| 8 | ST | Explicit no-connect; no trace/via/zone on that pad net |

`J7..J18` have been replaced by **SW2..SW13**, MSK12C02 / C431540 SMD
slide switches placed between the corresponding supply and GND connectors.
Pin 2 = SEL_n, pin 3 = VBUS_PROT, pin 1 = NC; four shell pads are GND.
The 100k pulldowns remain. These are logic contacts, not slot-current conductors.
Q1..Q12 independently buffer the select signal for D4..D15 through 1k R62..R73.
D4..D15 are directly right of their respective switches with a bold `5V` caption
matching the existing MONO font. The former SWn 5V LED / OFF=3V3 captions are
removed. Q1..Q12 were slightly nudged for clearance; the circuit is unchanged.
See `verification/led-placement/README.md` for the current placement snapshot
and preservation check; the earlier move-by-move evidence was unavailable.
LED current comes from 5V_SYS, not the mux logic. LED ON means 5V is selected
and its indicator supply is present; it is not an output-voltage measurement.

| State | Switch 2–1 / open (PR1 pulldown) | Switch 2–3 |
|---|---|---|
| Normal USB supply | VIN2 / +3.3V; LED off | VIN1 / 5V_SYS; LED on |
| Reset pressed; +3.3V off | Selected VIN2 collapses; no intended 5 V fallback | 5V_SYS remains selected |
| Power-up / power-off | Sequencing and low-MODE transition need bench observation | Same bench requirement |

Set **3V3** by continuity check before shipping/use; switch assembly position is
not an automatic safe default. An open contact is pulled down to 3V3. Change
selection with power removed and the module unplugged. Installed modules may
obscure both switch access and the LED.

The full prior design rationale is in the historical 1.3.9 CHANGELOG entry and
mux-select migration evidence. This table states circuit intent, **not measured
reset/startup proof**. The obsolete TPS2111A TSSOP packages, twelve ILIM resistors
`R28/R30/.../R50` and their ILIM copper/nets are removed from this PCB.

### Accepted protection limits — unchanged, not hidden

- **No per-slot programmable ILIM.** A fault is constrained by the common F2,
  regulator/source limits and device protection, not by the former per-slot
  resistor limit. One bad slot can disturb other slots before an upstream trip.
- Thermal shutdown is not an adjustable per-slot current limit.
- Existing TVS circuitry is not guaranteed protection of every mux/control pin
  against arbitrary surges. The TPS2116 absolute maximum on VIN/control pins is
  6 V; this design has not been surge/ESD qualified. [source](https://www.ti.com/lit/ds/symlink/tps2116.pdf)
- Shorting a selector pin-3 reference to GND faults `VBUS_PROT` upstream of F2.
- Shared input rails/bulk are retained. No new per-mux input capacitor was added
  beyond the authoritative circuit. Startup/load-step behavior on long shared
  rails remains a bench check; output decouplers are locally routed to each mux.

## Audio / mono / input protection

- `U2/U4` remain MCP6002; `U3` is **TS922IDT / C93687**. All three use plain
  SOIC-8 with only pads 1–8: no fictitious exposed pad or paste islands. Their
  approved anchors and eight external pad positions are preserved.
- The single approved line-out feedback state is retained: R18/R19 = 680k and
  R16/R17 = 1M. `R16.1`/`R17.1` connect directly to `RFB_A`/`LFB_A`.
  No loud-gain option exists. `U19/J24/R53/R54/R56/C49`, obsolete solder jumpers
  J20/J21/J22 and ghost gain/feedback nets are absent.
- `U18/SW14/R55/C48` implement the LINE mono selector. `R55=100k` pulls
  `MONO_SEL` low; SW14 2–3 selects MONO, 2–1/open selects STEREO. J23 is removed.
  Q13/R74/D16 provide a separately buffered MONO indicator from +3.3V; the
  assembler must set and continuity-check STEREO before shipping.
  `U18.9=IN_R_PROT`, `U18.2=BUFF_IN_L`, `U18.10=RIN_SEL`; both controls 1/5
  are on `MONO_SEL`. The unused channel's pads 4/6/7 and ground pin 3 are GND.
- `R57=100 ohm / C25076` connects INPUT1 return pins 3/4/5 to GND through the
  approved resistor, not a hard short. INPUT1's anchor and drills are unchanged.
- `R58/R59=10k / C25744` are fitted before **all** protected input branches.
  Raw socket nets are `IN_L`/`IN_R`; downstream nets are `IN_L_PROT`/`IN_R_PROT`.
  The protected right input feeds U2 and U18; this is not protection of U18 alone.
- At 3.3 V and the resistor's -1% tolerance, the simple upper bound is
  `3.3 / 9900 = 0.333... mA` per driven channel. This is current limiting,
  **not powered-off isolation** or proof of reset/discharge timing. Residual
  backfeed remains possible. See `verification/input-protection.json`.

### Local supply bypassing added in 1.3.13

C50/U2, C51/U3, C52/U4 are populated 100 nF +3.3V-to-GND capacitors copied from
the exact sourced C15 C1525 / CL05B104KO5NNNC / 0402 type. Short dedicated pin-8
connections (2.582 / 1.888 / 1.625 mm) and adjacent GND via returns (0.40 / 0.72 /
0.80 mm) are saved/refilled and DRC-clean. C14/C15/C20 remain on +2.5V bias.
This is local supply bypassing, not evidence of a proven oscillation or bench fix.
All 523 prior schematic pin memberships and old metadata are preserved except
J5 assembly-only XY fields; only six new supply/GND pins were added.

SW14's silk says `SW14 LINE MONO` / `LED ON=MONO` / `OFF=STEREO`.
This changes the U18 LINE selector, not every headphone channel. LED OFF also
includes loss of the +3.3V indicator supply.

### Headphone LEFT/RIGHT correction

The physical **LEFT** control (RV1) now receives BUFF_IN_L; its wiper feeds R7,
U3A, C3/C8/C10/C12 and R12, ending at **J6 tip / HEAD_OUT_L**. The physical
**RIGHT** control (RV2) receives BUFF_IN_R; its wiper feeds R6, U3B,
C7/C9/C11/C13 and R10, ending at **J6 ring / HEAD_OUT_R**. Previously the two
pots disagreed with the physical legends. Only four pot signal memberships and
their local signal routing were changed. The tip/ring assignments themselves,
input channel identities, LINE path, feedback/bias circuits and pot/legend
placements remain unchanged. End-to-end native netlist checks pass; playback
and minimum-volume behavior still require bench confirmation.

## Layout / software proof

- Two copper layers, outline `(30.48,17.78)..(254.00,177.80)` =
  **223.52 × 160.02 mm**, and all **28 existing mounting holes** are preserved.
- All 201 current footprint placements, all 3D-model nodes, pad geometries,
  original mechanics and current silkscreen were preserved during routing cleanup.
  The selector migration intentionally replaces thirteen jumper footprints with
  52 switch/driver/LED/resistor footprints; all 149 retained component placements
  are unchanged. Only the two headphone pots have the four authorized net edits.
- Manual selector cleanup replaces 1,602 small grid segments with 276 cleaner
  segments while retaining attachment points and vias. Main power trunks, audio
  feedback and unaffected original copper are retained. Twelve headphone signal
  segments are replaced and two transition vias added for the channel correction.
- The documented TraceMaker CPU engine was privately built and inspected. Its
  baseline checker did not reproduce the scoped J5 clearance rule, so no
  autorouted copper was accepted. The authorized manual fallback passed native
  checks without lowering rules. Details: `verification/routing-polish/README.md`.
- There is a saved/refilled board-wide B.Cu GND reference plane. Existing local
  power drops and audio decoupling remain intact. Return/noise/stability behavior
  remains a bench review, not a claim derived from a DRC pass.
- Manufacturing drill/place origin is the **lower-left corner (30.48,177.80)**.
  CPL uses millimetres, Cartesian positive Y upward, no independent bottom-X
  reflection. J5 uses the independently evidenced HRO 8.94 × 7.35 mm shell
  centre: XY correction (+3.675,0) in that exported frame, CPL (4.035,130.810),
  unchanged rotation 270°. See verification/J5-assembly-datum.md. JLCPCB's part-specific placement preview remains mandatory.
- KiCad CLI 10.0.6 on the exact saved release PCB: **0 error-level DRC,
  0 unconnected, 0 schematic parity**, with **61 visible library-copy warnings**.
  See `verification/warnings.md` and the actual JSON report.
- ERC still has **7 errors + 4 warnings**, identical to the input circuit's
  findings. They are explained in `verification/warnings.md`, not suppressed.

## Stack height / real-world holds

The updated switch drawing calculation gives **9.6 mm nominal / 8.8 mm assumed
worst-case clearance** to the module plane. The 1.4 mm switch body has a
conservative 1.6 mm envelope including tolerance/solder stand-off. This retains
8.5 mm socket + 2.5 mm module-header assumptions, not proven contact depth or a
physical mating trial. The previously referenced per-module coverage report was
not present when this completion audit resumed. The current selector summary
certifies connectivity/preservation/export checks only, not underside clearance.

The source's slot-1 offset (-0.12 mm X / -0.10 mm Y) is preserved. Current module
inspection covers 28 readable boards: 26 have bottom-mounted headers; **4mix and
imix have top-mounted headers and cannot mate downwards as drawn**. `line_in`
contains only one matching rail/ground male connector. These are documented
module/assembly limitations, not silently repaired BASE geometry.

Before any order/release signoff: focused independent current-candidate confirmation, actual socket/module/switch
mating trial, all selector/reset/startup/load states, stereo/mono and headphone
bench checks, and JLCPCB package/polarity/placement preview remain unperformed.
The earlier live JLCPCB classification/stock check for the new selector-related
parts is retained in `verification/selectors/jlcpcb-basic-parts.json`. It is a
point-in-time sourcing check, not reserved stock or a current assembly quote.
Old pricing is stale.
