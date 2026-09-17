# 32bit-5v — 5V input, on-board 3.3V rail

This note describes the power architecture of the `32bit-5v` variant and the
numbers behind the component choices. Nothing here overrides the schematic or the
PCB; both are the authority.

---

## 1. Rail map

```
V_SUPPLY1 (1x05, all five pins)   == +5V   (slot rail, 5V_SYS when the base's
       │                                     rail-select jumper is fitted)
       │
       ├── C40 10uF/25V X5R 0805 ........ input capacitor, 1.3mm from the pin
       │
       ▼
   U5  AP7361C-33E-13           1A low-dropout LDO, SOT-223
       │  VIN  = pin 1  (right-hand lead, top)
       │  GND  = pin 2  (middle lead *and* the exposed tab, bottom side)
       │  VOUT = pin 3  (right-hand lead, bottom)
       │
       ├── C41 22uF/25V X5R 0805 .... output capacitor, 1.6mm from the pin
       │
       ▼
     +3V3  ──┬── FB1 ──► +3V3_ESP32 ──► U1 ESP32-S3-WROOM-1U, C1, C2, C9..C13
             ├── R15 ──► +3V3_8388  ──► U4 ES8388, C5, C7, C21..C39
             ├── C6 0.1uF, C8 10uF        (original decoupling, unchanged)
             ├── R3 pull-up, R10/R12 CV dividers
             └── U3 MCP6002 (V+)
```

The `+3V3` net list is unchanged apart from the two new members: the regulator
output (`U5` pin 3) and its output capacitor (`C41` pin 1) replace the five
`V_SUPPLY1` pins that used to feed the rail. `+3V3_ESP32`, `+3V3_8388` and `GND`
keep exactly the loads they had (machine-checked, see §4).

### The rail-select jumper must be fitted

On a base v1.3.0+ board the per-slot mux (`U6..U17`, TPS2111A) connects the
module socket either to `+3.3V` (**jumper open — the fail-safe default**) or to
`5V_SYS` (**jumper fitted**). `32bit-5v` needs **5V**:

* with 5V in, the AP7361C regulates 3.3V with 1.36V of margin over its 340mV
  dropout;
* with the jumper left open the regulator sees 3.3V, drops out, and the module
  would run at roughly 2.9-3.0V — at or below the ESP32-S3 minimum.

This is a user-facing wiring rule, not a defect: the slot rail is documented on
the base's silkscreen/jumper legend.

---

## 2. Why a 1A part

The module's real 3.3V load (no RF is used by this firmware):

| Load | Typical | Peak |
|---|---|---|
| ESP32-S3-WROOM-1U-N16R8 (no WiFi/BT in use) | 50-90 mA | ~340 mA (radio TX, unused here) |
| ES8388 codec + its analogue rails | 15-25 mA | 30 mA |
| MCP6002 (2 sections) | 0.3 mA | 0.5 mA |
| Status LED + pull-ups/dividers | ~2.5 mA | ~3 mA |
| **Module total** | **~0.08-0.12 A** | **~0.25-0.4 A** |

Two independent ceilings bound the worst case:

* the base's per-slot current limit, `I_LIM ≈ 667 mA` (TPS2111A, R_ILIM = 750Ω),
  which also caps the module's 5V input;
* the AP7361C itself, 1.0A guaranteed.

A 1A SOT-223 part therefore covers the module with >2x margin over the realistic
peak, and the LDO's own 1.1-1.5A current limit plus thermal shutdown back up the
base's mux limit.

---

## 3. Thermal analysis

```
PD = (VIN - VOUT) x IOUT
PD(max@TA) = (150 C - TA) / theta_JA
```

| Case | IOUT | PD | ΔT with θJA = 110 °C/W (datasheet, minimum pad) |
|---|---|---|---|
| typical | 0.12 A | 0.20 W | 22 °C |
| realistic peak | 0.40 A | 0.68 W | 75 °C |
| base-board ceiling (worst case the hardware can deliver) | 0.667 A | **1.13 W** | 125 °C |

At a 45 °C ambient that is TJ ≈ 67 / 120 / 170 °C. The 1.13W column would reach
the AP7361C's 150 °C thermal-shutdown threshold, so the plain "minimum
recommended pad" figure is **not** good enough for the pathological case, and the
layout therefore makes the tab a real heat-sink:

* the SOT-223 tab is the GND pin in this package, so it is soldered to a
  2.0 x 3.8mm pad that carries **four 0.6/0.3mm thermal vias straight into the
  `In1.Cu` ground plane** (a full-board pour), plus one more via in the GND lead
  pad and two at the capacitor grounds;
* the plane is the heat-spreader: on a 4-layer board with a solid inner GND
  plane, θJA for a SOT-223 tab tied into it is ≈ 45-60 °C/W rather than the
  datasheet's 110 °C/W minimum-pad number.

At θJA ≈ 50 °C/W the worst case is ΔT ≈ 57 °C → TJ ≈ 102 °C at TA = 45 °C, and the
realistic peak is ΔT ≈ 34 °C → TJ ≈ 79 °C. **Conclusion: the copper and vias are
sufficient**, with headroom to the 150 °C absolute maximum; the module is not
relying on the base board for any of this heat path.

(No dedicated `+3V3` copper zone was added: the tab is ground, so the ground
plane—not the output rail—is the heat spreader.)

---

## 4. Verification

Run with KiCad **10.0.6** (`kicad-cli` 9.x cannot parse this board's KiCad 10
format). Artefacts in `verification/`.

| Check | Original `32bit` | `32bit-5v` | Delta |
|---|---|---|---|
| `kicad-cli sch erc --severity-all` | 55 findings | 54 findings | **0 new**, 1 removed (the `+3V3` net gained a power output) |
| `kicad-cli pcb drc --severity-all --schematic-parity` | 102 violations | 105 violations | +3 `lib_footprint_mismatch` warnings (same class as the 53 pre-existing ones) |
| … unconnected items | 0 | **0** | — |
| … schematic parity issues | 62 | **4** | 58 `Datasheet` field mismatches fixed; the remaining 4 are the pre-existing J5 USB-C `net_conflict`s |
| netlist acceptance (`verification/netlist-proof.json`) | — | **15/15 pass** | `+5V` = {V_SUPPLY1.1-5, U5.IN, C40.1} only; every original `+3V3` load still driven |

Known, deliberate DRC deltas:

1. **+3 `lib_footprint_mismatch`** for `U5`, `C40`, `C41`: their bottom-side
   silkscreen graphics were removed and all fields hidden, because leaving the
   library silkscreen in place on the back side produces ~40
   `silk_over_copper` / `silk_overlap` / `nonmirrored_text_on_back_layer`
   findings. This is a warning, the same class as the 53 `lib_footprint_mismatch`
   warnings the board already had.
2. **4 `silk_over_copper`** findings on `V_SUPPLY1`'s pads are the *same*
   pre-existing findings as the original, re-labelled from `+3V3` to `+5V`
   because the socket now carries 5V. No geometry changed.
3. The literal "0 errors, 0 parity" target is not reachable on this board: the
   original already reports 2 `clearance` errors that are listed in the project's
   DRC exclusions (the J5 USB-C pad pair), and the 4 J5 `net_conflict` parity
   warnings come from pads that this symbol/footprint pair has never had pins
   for.

---

## 5. Open risks

* **Jumper dependence** (§1): the module needs the slot rail-select jumper fitted
  (5V). Left open, the module browns out.
* **Input over-voltage**: the AP7361C's absolute maximum input is 6.5V
  (recommended 6.0V). The base's protection is a PPTC plus an SMAJ5.0A TVS whose
  peak clamp is 9.2V, which the base's own v1.3.0 note already accepts as an
  exposure for its AP2112K; `32bit-5v` inherits the same exposure. A pin-compatible
  alternative with an 18V input (e.g. LDL1117S33R, LCSC `C435835`) can be
  substituted if that ever needs closing.
* **Stock**: LCSC showed ~295 pieces of `C500795` at the time of writing — in
  stock but thin. `AMS1117-3.3` (LCSC `C6186`, JLCPCB basic, 1M+ stock) is
  pin-compatible in SOT-223 (1=GND, 2=OUT/tab, 3=IN) and can be dropped in, at
  the cost of its 1.3V dropout and 5mA quiescent current.
* **Bottom-side assembly**: `U5`, `C40`, `C41` are the module's first bottom-side
  SMD parts, so the JLCPCB CPL now contains `bottom` lines for this module.
