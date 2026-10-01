# BASE 1.3.13 — current power/audio implementation and limitations

**Current authority: `base.kicad_sch` + hierarchical `slot.kicad_sch`.** The PCB
is now synchronized and routed to that circuit, including the 1.3.11 input
protection change. `production/manifest.json` identifies the software-checked
candidate. It does **not** authorize an order or claim bench/mating approval.
Older CHANGELOG/migration evidence is history, not instructions to restore parts.
Astra's prior 1.3.12 copper/connectivity/fabrication review passed; assembly was
held for J5. This bounded pass invoked no advisor/model review; focused 1.3.13
confirmation is pending, separately from the unperformed vendor preview.

The exact original 979-line engineering/source rationale, including numbered
historical sections 1–11, is preserved in
[POWER-HISTORICAL-pre-1.3.12.md](POWER-HISTORICAL-pre-1.3.12.md).
That clearly **superseded historical record** is not current circuit, PCB,
manufacturing or ordering guidance; use the present schematics and release
manifest for current behavior and artifacts.

## Circuit retained

```
USB-C J5 VBUS -> F1 -> VBUS_PROT
                       |-> D2 TVS -> GND
                       |-> input bulk/decoupling + status LED
                       |-> FB1 -> LDO_VIN -> U5 AP2112K-3.3 -> FB2 -> +3.3V
                       |-> F2 -> 5V_SYS -> D3 TVS + C46/C47
                       |-> each mux MODE + J7..J18 pin 1 (logic reference)
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
| 4 | PR1 | SEL_n, J(n+6).2, 100k pulldown |
| 5 | MODE | VBUS_PROT |
| 6 | VIN2 | +3.3V |
| 8 | ST | Explicit no-connect; no trace/via/zone on that pad net |

`J7..J18` are unchanged mechanically, 3.80 mm above the corresponding supply
row and inside the module shadow. Each pad is still a single 0.25 mm logic
leaf; neither header is a series slot-current conductor. MODE and header pin 1
are on `VBUS_PROT`, not `+3.3V`.

| State | Shunt absent (PR1 pulldown) | Shunt fitted |
|---|---|---|
| Normal USB supply | VIN2 / +3.3V | VIN1 / 5V_SYS |
| Reset pressed; +3.3V off | Selected VIN2 collapses; no intended 5 V fallback | 5V_SYS remains selected |
| Power-up / power-off | Sequencing and low-MODE transition need bench observation | Same bench requirement |

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
- Shorting a header pin-1 reference to GND faults `VBUS_PROT` upstream of F2.
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
- `U18/J23/R55/C48` implement the approved mono selector. `R55=100k` pulls
  `MONO_SEL` low. J23 is **DNP**, so the shipped assembly defaults to stereo.
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

J23's silk says `J23 LINE MONO` / `OPEN=STEREO`: a fitted shunt changes the U18
LINE selector. It does not promise to mono every headphone channel.

## Layout / software proof

- Two copper layers, outline `(30.48,17.78)..(254.00,177.80)` =
  **223.52 × 160.02 mm**, and all **28 existing mounting holes** are preserved.
- Fixed mating sockets, jacks, pots, rail selectors, USB/reset hardware and
  unaffected components are compared independently to the branch input in
  `verification/mechanical-invariants.json` (114 preserved footprint/pad sets).
- The 1.3.12 package/local changes remain; this pass preserves all 157 existing
  pad/anchor sets and 1109 existing copper items, adding only three supply caps
  and their local connections. J5 has assembly-only metadata and F.Fab body art,
  not moved copper. Only intentional package swaps, new circuit parts and local mux output
  decoupler placements change. Main power trunks retain broad routing; local
  input drops are 0.8 mm and slot socket feeds 1.0 mm, with 0.25 mm fine-pitch
  escapes. There is a saved/refilled board-wide B.Cu GND reference plane.
- Local selector/audio routing preserves the approved circuit and existing
  audio anchors. Return stitching and short C48/output-cap connections are
  software/visual layout evidence, not a measured noise/stability result.
- Manufacturing drill/place origin is the **lower-left corner (30.48,177.80)**.
  CPL uses millimetres, Cartesian positive Y upward, no independent bottom-X
  reflection. J5 uses the independently evidenced HRO 8.94 × 7.35 mm shell
  centre: XY correction (+3.675,0) in that exported frame, CPL (4.035,130.810),
  unchanged rotation 270°. See verification/J5-assembly-datum.md. JLCPCB's part-specific placement preview remains mandatory.
- KiCad CLI 10.0.6 on the exact saved release PCB: **0 error-level DRC,
  0 unconnected, 0 schematic parity**, with **70 visible library-copy warnings**.
  See `verification/warnings.md` and the actual JSON report.
- ERC still has **7 errors + 4 warnings**, identical to the input circuit's
  findings. They are explained in `verification/warnings.md`, not suppressed.

## Stack height / real-world holds

The existing component-drawing calculation remains **5.0 mm nominal / 3.8 mm
worst-case clearance** above the rail selector envelope. This is not a physical
mating trial. Female sockets must meet the documented 6.6 mm nominal minimum;
8.5 mm recommended housings are assumed to accept the module mating pins.
The module-side header PN/contact depth remain assumptions.

The source's slot-1 offset (-0.12 mm X / -0.10 mm Y) is preserved. Current module
inspection covers 28 readable boards: 26 have bottom-mounted headers; **4mix and
imix have top-mounted headers and cannot mate downwards as drawn**. `line_in`
contains only one matching rail/ground male connector. These are documented
module/assembly limitations, not silently repaired BASE geometry.

Before any order/release signoff: focused independent 1.3.13 confirmation, actual socket/module/shunt
mating trial, all selector/reset/startup/load states, stereo/mono and headphone
bench checks, and JLCPCB package/polarity/placement preview remain unperformed.
There is no live cost/stock qualification in this release. Old pricing is stale.
