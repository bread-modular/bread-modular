# BASE v1.3.0 — power architecture, protection and per-slot rail selection

Scope of v1.3.0: **schematic, footprints and part numbers only.** The PCB
(`base.kicad_pcb`) is intentionally *not* updated, placed or routed — that is the
follow-up (Phase 2) chat. Nothing in this note overrides the schematic.

---

## 1. Rail map

```
USB-C J5 (power only, VBUS)
   │
  F1  polyfuse 1.1 A hold / 16 V        (input protection, in series with VBUS)
   │
   ▼
net VBUS_PROT ──┬── D2 TVS (SMAJ5.0A) ── GND
                ├── C17 22 µF, C21 0.1 µF, D1 status LED
                ├── FB1 ──► LDO_VIN ──► U5 AP2112K-3.3 ──► +3.3V   (unchanged since v1.2.0)
                └── F2  polyfuse 1.1 A hold / 16 V ──► net 5V_SYS ─┬── D3 TVS (SMAJ5.0A) ── GND
                                                                   ├── C46 100 µF/16 V (1210 X5R), C47 0.1 µF
                                                                   ├── PWR_FLAG (ERC: externally sourced)
                                                                   └── 12 × U6..U17  IN1
```

Per module slot *n* (1…12):

```
   +3.3V ─────┐
              ├── U(n+5) TPS2111APWR (2:1 power mux, manual mode)
   5V_SYS ────┘        │            │                │
                  D1 = SEL_n     ILIM           OUT ─┴──► net VSLOT_n ──► all five pins of the
                       │            │                                  existing VSUPPLY_n socket
         J(n+6) ── 1 = +3.3V        R(27+2n-1) 1.6 k ── GND
                  2 = SEL_n
                       │
              R(27+2n) 100 k ── GND            C(20+2n) 1 µF, C(21+2n) 0.1 µF  VSLOT_n ── GND
```

The socket pinout is unchanged: every `VSUPPLY_n` socket still has all five pins
tied to one slot rail (now `VSLOT_n` instead of unconditionally `+3.3V`), and
`GND_n` remains the mating ground socket.

## 2. Per-slot selection — truth table and fail-safe

`SEL_n` is the mux select input and is pulled down by a 100 kΩ resistor.

| Jumper `J(n+6)` | SEL_n | Mux D1 | Output on VSLOT_n |
|---|---|---|---|
| shunt **fitted** | high (3.3 V) | 1 | **5V_SYS** |
| shunt **absent / lost** | low (0 V, 100 k pulldown) | 0 | **+3.3 V** |

* Fail-safe default is **+3.3 V** for every existing (3.3 V) module. A lost shunt
  can never put 5 V on a 3.3 V-only module.
* The mux is wired in **manual mode**: `D0` is tied to GND (`D0 = 0` selects manual
  switching) and `VSNS` is tied to GND (unused in manual mode, kept deterministic).
* In manual mode the TPS2111A never switches on its own: with `D1 = 0` the output is
  IN2 (+3.3 V) and stays there even if one rail disappears — there is **no automatic
  fallback to 5 V**.
* The mux is reverse-blocking and cross-conduction blocking, so a module that drives
  or back-feeds its slot cannot push current into `+3.3V` or `5V_SYS`.
* The header carries **logic current only** (µA): module current flows through the mux.
* **IN1 = 5V_SYS and IN2 = +3.3 V** — see deviation D1 below.

## 3. Deviations from the frozen brief (need sign-off)

**D1 — mux input assignment swapped.** The brief fixes `VIN1 = +3.3V`,
`VIN2 = 5V_SYS` *and* "shunt fitted ⇒ SEL high ⇒ 5 V". The TPS2111A (and every other
JLCPCB-stocked, current-limit-programmable, manual-select power mux) selects
**IN1 when the select pin is high**, so the two statements cannot both hold.
SEL polarity is the safety-critical requirement, therefore `IN1 = 5V_SYS` and
`IN2 = +3.3V`. The external behaviour is exactly as specified (shunt fitted ⇒ 5 V,
absent ⇒ 3.3 V).

**D2 — per-slot current limit is NOT inside the datasheet's guaranteed range.**
The brief asks for ~250–300 mA per slot. The only JLCPCB-assemblable manual-select
power mux with current-limit programming is TPS2111APWR, whose *guaranteed*
adjustment range is 0.63–1.25 A (`ILIM = 500 / R_ILIM`); below 0.63 A TI does not
specify accuracy. `R_ILIM = 1.6 kΩ` gives ≈ 312 mA *by extrapolation* — that number is
**not a datasheet-guaranteed limit** and must not be quoted as meeting the
250–300 mA requirement. It is implemented as the closest match to the requested
value, and is **provisional pending an explicit decision**:

* accept the extrapolated ≈ 312 mA setting — **this is not the requested protection
  level**, it is an unguaranteed value: the real limit could be materially lower (and
  nuisance-trip a heavy module) **or materially higher** (and fail to protect the
  slot), or
* change the twelve 1.6 kΩ resistors to `750 Ω` for ≈ 667 mA, inside the guaranteed
  range (weaker but specified protection), or
* drop the deliverable-level requirement and re-scope (e.g. a load-switch pair with a
  different current-limit scheme).

The part that fits 0.31–0.75 A exactly (TPS2114A) was rejected because **JLCPCB stock
= 0** (TPS2114APWR, TPS2110APWR). The TPS2116 matches the 1.6–5.5 V range and is
cheap/stocked, but it has **no current-limit programming at all**, so it fails the
brief.

**D3 — new reference designators.** The brief names the TVS `D1`/`D2` and the fuses
`F1`/`F2`; `D1` is already the status LED and designators must be kept, so the new
parts are **D2 = VBUS TVS, D3 = 5V_SYS TVS, F1 = VBUS polyfuse, F2 = 5V_SYS polyfuse**.

## 4. Open items / things to watch

1. **F1 sizing vs total load.** F1 is 1.1 A hold / 16 V as requested. Twelve slots in
   5 V mode can exceed 1 A in aggregate and the PPTC hold current also derates with
   ambient temperature. If more than ~6 digital modules may run at once, re-size F1
   (e.g. 1.5–2 A hold) or document a maximum module count. Not changed here.
2. **TVS coordination is UNRESOLVED protection, not just a note.** SMAJ5.0A clamps at
   9.2 V at peak pulse current (7.0 V max breakdown) while the downstream parts
   (TPS2111A, AP2112K) are rated 6 V absolute maximum. Bulk capacitance does not
   establish safety here — it only slows the rail. A rated solution is required and
   needs approval, e.g. a lower-clamp device (accepting DC leakage/derating on the 5 V
   rail), a series impedance ahead of the semiconductors, or explicitly accepting a
   surge beyond the downstream absolute maximum with the risk documented. Not resolved
   in v1.3.0.
3. **100 µF/10 V vs 16 V.** The brief asks ≥ 100 µF/10 V; C46 is **100 µF/16 V X5R
   1210** (better DC-bias derating, ≈ 50–60 µF effective at 5 V).
4. **Current-limit accuracy** (D2 above) — needs a decision.
5. **LCSC numbers**: 13 BOM lines are marked `TO-VERIFY` (see §6). `TO-VERIFY` is a
   deliberate marker; `opt/kicad-jlcpcb/export.py` rejects non-`C#####` values, so the
   JLCPCB export will refuse to run until each one is replaced with a real C-number.

### 4.1 Concrete proposals for the two electrical decisions (need approval)

**P1 — over-voltage protection (TVS clamp vs 6 V downstream rating).** Pick one:

| | Proposal | Effect | Cost |
|---|---|---|---|
| P1a | **Recommended direction (part not chosen):** add a rated OVP switch in series with **`VBUS_PROT`**, i.e. upstream of *both* FB1 → U5 and F2 → 5V_SYS (an integrated OVP/eFuse in the TPS1663 class is the candidate, but **the part, price, current-limit capability, clamp/cutoff tolerance and transient overshoot are NOT verified** — this needs a datasheet study before it can be specified) | **design target:** disconnect before the node exceeds the 6 V absolute maximum of *both* downstream branches (U5 through FB1 and every mux input). Whether a given part actually meets that target, and by how much it overshoots during a surge, is exactly what has to be verified | unknown until verified |
| P1b | Accept the TVS as surge protection only and document the residual risk (the `VBUS_PROT` node may briefly exceed 6 V during a surge, exposing both U5 through FB1 and every mux input) | no change, no cost | $0 |
| P1c | Drop `5V_SYS` for v1.3.0 (3.3 V-only base, keep the input protection) | removes the mux inputs from the exposed set, but **U5 is still fed from `VBUS_PROT` through FB1**, so the exposure is reduced, not eliminated | $0, removes a feature |

Note: a series OVP switch does **not** by itself establish F1/F2 fuse coordination (F1
still feeds both branches), and it does not replace the per-slot current limit.

**P2 — current-limit setting.** Pick one:

| | Proposal | Effect |
|---|---|---|
| P2a | keep `R_ILIM = 1.6 kΩ` (≈ 312 mA *extrapolated*, outside the guaranteed 0.63–1.25 A range) | as implemented; unguaranteed in either direction |
| P2b | fit `750 Ω` (≈ 667 mA) | inside the guaranteed range, weaker but specified protection |
| P2c | use TPS2114A with consigned/sourced stock (guaranteed range 0.31–0.75 A) | gets into a guaranteed range, but **it still does not meet 250–300 mA**: 0.31 A is the datasheet minimum, so only ≈310 mA of the requested band would be in range; JLCPCB stock is also 0 today |

**P3 — fuse coordination.** F1 and F2 are identical 1.1 A-hold PPTCs, so a 5 V-side fault
may open F1 (taking down `+3.3V` too) before F2. Proposal: make **F2 = 1.1 A hold** (as
now) and **F1 = 2 A hold** (protecting the USB source and the input wiring rather than
the branch), so the 5 V branch is the more likely to give first. This changes the frozen
"~1 A hold" for F1 and therefore needs approval. Note that P1a does *not* remove the
coordination question — F1 still feeds both branches.

## 5. Phase 2 (PCB) constraints — please honour these when routing

* **F1 and D2 must be placed next to J5 / the VBUS entry**, before FB1, with the TVS
  return to the connector ground (short loop).
* **The 2-pin jumpers J7…J18 must sit hidden underneath a mated module** (set the
  shunt *before* plugging a module in, then remove the module to change it). Place
  them **over/on the slot power rail, close to it**, and **not in the gap between the
  ground socket (`GND_n`) and the power socket (`VSUPPLY_n`)**. They must stay
  accessible with the module removed and the shunt must not foul the module body.
* Use a low-profile header: v1.3.0 uses a **1×02 2.00 mm vertical header**
  (`Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical`, ~2.8 mm body,
  4 mm pins) so a mated module can sit above it. The mating shunt is user-fitted.
* Keep the mux close to its slot socket; the channel is a power path
  (reuse the existing wide trace style for `VSLOT_n`, IN1/IN2 and GND).
* 12 extra mux + 24 R + 24 C + 12 headers were added: check placement room per slot
  on the current board before routing.
* Do **not** re-route or move the existing 3.3 V LDO, FB1/FB2 or the VSUPPLY/GND sockets.

## 6. Parts, part numbers and verification

Part numbers were verified against the **JLCPCB assembly parts library** (which is
what determines whether a part can actually be placed) — the `LCSC` field on every
symbol carries `C#####`, or the literal marker `TO-VERIFY`.

New parts (all verified, in stock at the time of writing):

| Ref | Part | Package / footprint | LCSC | Price @100 | Verified |
|---|---|---|---|---|---|
| U6–U17 | TPS2111APWR (2:1 power mux, manual select, ILIM, reverse blocking) | TSSOP-8 (`Package_SO:TSSOP-8_4.4x3mm_P0.65mm`) | C471060 | $1.38 | yes (stock 2482) |
| F1, F2 | MF-MSMF110/16-2 (PPTC 1.1 A hold / 16 V) | 1812 (`Fuse:Fuse_1812_4532Metric`) | C210834 | $0.066 | yes (stock 24 734) |
| D2, D3 | SMAJ5.0A/TR13 (TVS unidirectional 400 W) | SMA (`Diode_SMD:D_SMA`) | C78401 | $0.044 | yes (stock 98 557) |
| C46 | EMK325ABJ107MM-T (Taiyo Yuden) 100 µF 16 V X5R (brief: ≥100 µF/10 V) | 1210 (`Capacitor_SMD:C_1210_3225Metric`) | C394395 | $0.52 | yes (stock 39 609) |
| C47, C23, C25…C45 (0.1 µF) | CL05B104KO5NNNC 100 nF 16 V X7R | 0402 | C1525 | $0.0045 | yes (basic) |
| C22, C24…C44 (1 µF) | CL05A105KA5NQNC 1 µF 25 V X5R | 0402 | C52923 | $0.0099 | yes (basic) |
| R28…R51 (pulldown) | 0402WGF1003TCE 100 kΩ 1 % | 0402 | C25741 | $0.0025 | yes (basic) |
| R28…R51 (ILIM) | 0402WGF1601TCE 1.6 kΩ 1 % | 0402 | C4908 | $0.0028 | yes |
| J7–J18 | PZ200-1-02-Z, 1×02 2.00 mm vertical header | `Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical` | C2905948 | $0.024 | yes |

Spot-check of a part whose value/package could easily be confused: **R26 (100 Ω,
0402)** is `C25076 = 0402WGF1000TCE`; the JLCPCB record states 100 Ω, ±1 %, 50 V, 0402,
so MPN, value and the assigned `Resistor_SMD:R_0402_1005Metric` all agree. (R10/R12 are
a different part — 10 Ω 1206 — and remain `TO-VERIFY`.)

Existing parts that now carry a verified number: C1525 (0.1 µF), C15008 (100 µF/6.3 V
1206), C90146 (22 µF/16 V 1206), C1779 (4.7 µF/25 V 0805), C1705 (4.7 µF/10 V 0603),
C472806 (10 nF 0805), C11702 (1 kΩ), C25741 (100 kΩ), C25744 (10 kΩ), C26083 (1 MΩ),
C23137 (330 kΩ), C23186 (5.1 kΩ), C25890 (3.3 kΩ), C25076 (100 Ω), C7377
(MCP6002T-I/SN), C51118 (AP2112K-3.3TRG1), C2286 (KT-0603R LED, red 0603 — the colour
was not specified in v1.2.0).

`TO-VERIFY` BOM lines (no reliable lookup was possible — **do not invent numbers**):
`5V14` (2×05 socket), `C2` (1 µF 0805), `C16` (220 nF 0402), `FB1,FB2`
(GZ2012E800TF 0805), the 24 `GND_n`/`VSUPPLY_n` sockets, `INPUT1` (1×05 socket),
`J1/J2/J4/J6` (QingPu WQP-PJ366ST jack), `J5` (HRO-TYPE-C-31-M-12), `R10,R12` (10 Ω
1206), `RV1,RV2` (RV09 50 k pot), `SW1` (K2-1808SN-A4SW-01). Also still to source:
the **2.00 mm shunt / jumper cap** for J7…J18.

## 7. Reproducing the generated parts of this revision

```sh
# netlist + ERC (both must be clean apart from the pre-existing v1.2.0 findings)
kicad-cli sch export netlist --format kicadsexpr -o base.net base.kicad_sch
kicad-cli sch erc --severity-all --format json -o erc.json base.kicad_sch

# production BOM (same column layout as before, LCSC column now populated)
kicad-cli sch export bom base.kicad_sch -o production/bom.csv \
  --fields 'Reference,Footprint,${QUANTITY},Value,LCSC' \
  --labels 'Designator,Footprint,Quantity,Value,LCSC Part #' \
  --group-by 'Value,Footprint,LCSC' --sort-field Reference --exclude-dnp
```

The 12 channel blocks are deliberately *repeated* (not hierarchical) so that every
slot can be reviewed, probed and modified independently; the layout is a 4 × 3 grid
in the free area of the sheet, each block identical (x 241…466 mm, y 190…270 mm; the
protection block sits at x 254…292 mm, y 122…146 mm).

Placement was chosen from the free area of the A2 sheet and verified two ways:
mechanically (the rendered v1.2.0 sheet has **no drawing element inside the interior of
any of the twelve blocks or the protection block** — SVG element coordinates were
compared) and visually: the v1.3.0 sheet was plotted to PDF/PNG and every new block was
inspected, which is how the field-text collisions were found and fixed (mux and header
annotations moved clear of the nets, capacitor/resistor fields rotated, the protection
block re-spaced, the note moved into the empty strip below the block grid).

Two KiCad connectivity gotchas found while generating this (they cost real debugging
time, keep them in mind when hand-editing `base.kicad_sch`):

1. **Split wires at every junction.** A wire stub that ends on the *interior* of a long
   wire (with a junction dot) is not reliably connected by `kicad-cli`; the long wire
   must be split into separate segments at the junction points. All buses in v1.3.0 are
   generated that way.
2. **Field text angle is relative to the symbol.** A field stored with angle 0 on a
   symbol rotated 90° is drawn rotated; set the field angle to 90 to get horizontal
   text (and note the justification is mirrored when KiCad normalises 180°).

`production/netlist.ipc`, `positions.csv`, `designators.csv` and `base.zip` are
PCB/fabrication-toolkit outputs and were **left untouched** — they can only be
regenerated after the Phase 2 PCB update. `production/bom.csv` *was* regenerated.
