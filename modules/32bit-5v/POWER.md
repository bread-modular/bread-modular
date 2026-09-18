# 32bit-5v — 5V input, on-board 3.3V rail (v1.1.2, schematic-only)

This note describes the power architecture of the `32bit-5v` variant and the numbers
behind the component choices. The schematic is the authority for the schematic and
`32bit-5v.kicad_pcb` for the board — and as of **v1.1.2** the board still carries the
**v1.1.0** layout, because both the regulator swap (v1.1.1) and the ESP32 bulk-cap
trim (v1.1.2) are **schematic-only** changes (see §1.1 and §6).

---

## 1. Rail map (v1.1.2 — as drawn in `32bit-5v.kicad_sch`)

```
V_SUPPLY1 (1x05, all five pins)   == +5V   (slot rail = 5V_SYS when the base's
       │                                     rail-select jumper is fitted)
       ├── C40 10uF/25V X5R 0805 ..... input bulk
       ├── C42 0.1uF/16V X7R 0402 .... input HF decoupling (the base's own part)
       │
       ▼
   U5  AP2112K-3.3                  600mA LDO, SOT-23-5 — the base module's regulator
       │  VIN  = pin 1  (left lead, top)
       │  EN   = pin 3  (left lead, bottom)  -> tied directly to VIN on +5V
       │  GND  = pin 2  (bottom)
       │  NC   = pin 4  (hidden no-connect pin, exactly as in the base)
       │  VOUT = pin 5  (right lead)
       │
       ├── C41 22uF/25V X5R 0805 ..... output bulk  ** NOT CONNECTED — see §5 **
       │
       ▼
     +3V3  ──┬── C6 0.1uF, C8 10uF ....... output HF + local bulk (pre-existing)
             ├── FB1 ──► +3V3_ESP32 ──► U1 ESP32-S3-WROOM-1U, C1 0.1uF, C2 10uF
             ├── R15 ──► +3V3_8388  ──► U4 ES8388, C5, C7, C21..C39
             ├── R3 pull-up, R10/R12 CV dividers
             └── U3 MCP6002 (V+)
```

* **The same 3.3V loads as v1.1.0, with three documented node moves.** Against v1.1.0
  the `+3V3` net lost `U5`.3 (the old `VO` pin, v1.1.1) and gained `U5`.5 (the new
  `VOUT` pin, v1.1.1); it *also* lost `C41`.1, which is the **pre-existing `1244ad0`
  defect** described in §5 and not a v1.1.2 change. `+3V3_8388` keeps a byte-for-byte
  identical node set, and `+3V3_ESP32` lost exactly the five legacy bulk capacitors
  trimmed in v1.1.2 (all machine-checked, §4).
* **Nothing else on the board sees 5V**: the `+5V` net is exactly the five
  `V_SUPPLY1` pins, `U5` VIN, `U5` EN and the two input capacitors `C40`/`C42`.
* **EN handling** (deliberate deviation from the base): the base ties `EN` to its own
  `LDO_VIN` through `R4` 100k and additionally brings `EN` out to `C16` 220nF +
  `SW1` — a switch that lets the user turn the base's 3.3V rail off. This module has
  no such switch and must always be on, so `EN` is wired **directly to VIN** on
  `+5V`: no extra parts, no new failure mode, and no way to leave the 3.3V rail
  disabled.
* **The regulator is the base's part, field for field.** Both boards order
  `AP2112K-3.3` — Diodes, SOT-23-5, LCSC **`C51118`**, MPN **`AP2112K-3.3TRG1`**,
  Datasheet `https://www.diodes.com/assets/Datasheets/AP2112.pdf`. The Value,
  Footprint, Datasheet, Description, LCSC, MPN and Manufacturer fields in this
  schematic are copied verbatim from the base's `U5` and are compared against the
  base schematic by the netlist check in §4.

### The rail-select jumper must be fitted (unchanged from v1.1.0)

On a base v1.3.0+ board the per-slot mux (`U6..U17`, TPS2111A) connects the module
socket either to `+3.3V` (**jumper open — the fail-safe default**) or to `5V_SYS`
(**jumper fitted**). `32bit-5v` needs **5V**:

* with 5V in, the regulator has ample headroom (AP2112K dropout is 250mV at 600mA);
* with the jumper left open the regulator sees 3.3V, drops out, and the module would
  run at roughly 3.0V — at the ESP32-S3 minimum.

This is a user-facing wiring rule, not a defect: the slot rail is documented on the
base's silkscreen/jumper legend.

### 1.1 Board status after v1.1.2 (pending the owner's routing pass)

`32bit-5v.kicad_pcb` is **untouched** by this revision: no placement, no routing, no
zone refill, no footprint deletion. It still contains the v1.1.0 parts — the `U5`
SOT-223 footprint (`Package_TO_SOT_SMD:SOT-223-3_TabPin2`, bottom side at 60.9, 57.6),
the `C40`/`C41` 0805 footprints on the bottom side and the five `C9`..`C13` 1206
bulk-cap footprints on the ESP32 rail — while the schematic now declares `U5` as a
SOT-23-5, has **added `C42`** (v1.1.1, never placed on the board) and **has no
`C9`..`C13`**. `kicad-cli pcb drc --schematic-parity` has **not been re-run** since the
v1.1.0 board run; the expected outcome is a mismatch list covering at least
`U5` (wrong footprint), `C42` (present in the schematic, absent from the board),
`C9`..`C13` (still on the board, gone from the schematic) and `C41` (whose *net* differs:
the board routes it to `+3V3`, the schematic currently leaves it floating — see §5).
That is **expected and owned by the owner**; it is not something to "fix" from the
schematic side. See §6 for the hand-off.

### 1.2 Regulator decoupling vs the base module

| Position | Base (`modules/base`, `U5`) | `32bit-5v` v1.1.2 | Comment |
|---|---|---|---|
| LDO input bulk | `C2` 1uF 0805, LCSC `C28323` (`CL21B105KBFNNNE`) | `C40` 10uF 0805, LCSC `C15850` (`CL21A106KAYNNNE`) | **deviation**: 10x larger, same Samsung CL21 0805 family. The module's 5V arrives on a slot socket with no upstream bulk, whereas the base has 22uF (`C17`) + 0.1uF (`C21`) ahead of its input ferrite. |
| LDO input HF | `C21` 0.1uF 0402, LCSC `C1525` (`CL05B104KO5NNNC`) | **`C42` 0.1uF 0402, LCSC `C1525`** (added in v1.1.1) | identical part, same value/footprint/LCSC |
| LDO output at the pin | `C4` 4.7uF 0805, LCSC `C1779` | `C41` 22uF 0805, LCSC `C45783` (`CL21A226MAQNNNE`) | **deviation**: larger bulk for the ESP32 + ES8388 load; same Samsung CL21 0805 family. **`C41` is currently NOT connected to `+3V3` — see §5.** |
| Output bulk / HF behind the ferrite | `C6` 22uF 1206 (`C90146`) + `C1` 0.1uF 0402 (`C1525`) | `C8` 10uF + `C6` 0.1uF 0402 on `+3V3`, then `FB1` → `+3V3_ESP32` → `C1` 0.1uF + `C2` 10uF | pre-existing module decoupling; the five 100uF bulk caps behind `FB1` were trimmed in v1.1.2 (§1.3) |
| `EN` | `R4` 100k VIN→EN, `C16` 220nF, `SW1` to GND | `EN` wired directly to VIN (`+5V`) | **deviation**: no switch — the module must always be on |

Net effect: the base's scheme (**bulk + 0.1uF at the input, bulk + 0.1uF at the
output**) is reproduced with the same part family, with the two bulk values kept at
the module's larger, pre-existing values, and with the base's exact 0.1uF part for
the new input HF cap. On the regulator rails no decoupling was removed; the only
capacitors removed in this family of revisions are the five legacy 100uF ESP32 bulk
caps on the far side of the ferrite (§1.3).

### 1.3 ESP32 rail decoupling, v1.1.2 — the legacy 100uF bank is gone

`+3V3_ESP32` (the ESP32 side of `FB1`, feeding `U1` pin 2) used to carry **five
generic 100uF 1206 capacitors in parallel, `C9`..`C13`, on top of `C1` 0.1uF and
`C2` 10uF** — about **510uF** of bulk. They date from the pre-regulator era (module
0.3.0, *"use better power supply for esp32 side with ferrite beads and caps"*), when the
3.3V rail was an unregulated feed and brute-force bulk was the only mitigation
available. The module has had its own LDO since 1.1.0, so the bank was sized against a
design premise that no longer holds, and it is **removed in v1.1.2**.

What Espressif's *ESP32-S3 Hardware Design Guidelines* (schematic checklist) actually
specify, and how it maps onto this module — the two levels must not be conflated:

| Guidance | Applies to | This module |
|---|---|---|
| **10uF + 0.1uF** at the module supply pins (the bulk value is given as 10uF, "highly recommended" for VDD3P3, sized for the digital current steps) | the **module's external 3V3 input**, i.e. exactly the `+3V3_ESP32` rail here | already present as `C2` 10uF + `C1` 0.1uF — kept |
| an **LC circuit on the VDD3P3 rail**, inductor/ferrite rated **≥500mA** | the module's 3V3 feed | `FB1` (GZ2012D121TF), already fitted — kept |
| **≥10uF at the main power entrance** | the board's DC input | `C40` 10uF + `C42` 0.1uF on `+5V`, before the regulator — kept |
| "do not add **excessively large** capacitors" | the **chip-level `VDD_SPI` rail**, which on this design is internal to the module (the flash/PSRAM supply is handled inside `U1`) | **not directly applicable** to `+3V3_ESP32`; quoted here only because it is the one place the guidelines warn about bulk, not as the reason for this trim |

Reference: <https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html>
(power supply chapter); `ESP32-S3-WROOM-1` datasheet, "Power Supply" recommendation for
the module's 3V3 pin.

So the *specified* set for this rail is **one 10uF bulk + one 0.1uF HF**, which the
design already had as `C2` and `C1`; the five 100uF parts were an addition on top of
the specification, not a requirement of it. v1.1.2 deletes `C9`..`C13` and keeps
`C1`/`C2` unchanged (value, footprint and fields). The rail is now:

```
     +3V3 ── FB1 ──► +3V3_ESP32 ──┬── C2 10uF 0603  (the specified bulk)
                                  ├── C1 0.1uF 0402 (the specified HF)
                                  └── U1 ESP32-S3-WROOM-1U pin 2 (3V3)
```

**What is retired with the bank, stated plainly.** A 500uF bank is not the same thing
as a 10uF cap, even when both "meet the datasheet": the bank also supplied charge for
slow load transients and gave a large safety factor against brownout. Espressif sizes
the rail for the module's own current steps with the LDO present, and the regulator's
output network (`C41` 22uF once §5 is fixed, `C8` 10uF, `C6` 0.1uF on `+3V3`) plus
`C40` 10uF + `C42` 0.1uF at the input are what absorb those steps — but **this revision
does not claim to have validated that**. The trim reduces steady-state margin by
design; the load-transient behaviour of the module on this rail is a **bench-validation
item** (§5), not a proven result. If measurement shows brownout or PSRAM-related resets,
the remedy is **one** 0805/1206 bulk cap back behind `FB1`, not the whole bank.

Two caveats that belong to the *board*, not the schematic, and that the routing pass
must honour (they are carried in §6):

* **`C2` and `C1` must be placed close to `U1` pin 2**, with the shortest possible
  return loop to a solid `GND`. With the bank gone there is no longer a distant
  reservoir to fall back on, so the placement of these two parts carries much more of
  the decoupling than it did before;
* **DC-bias derating is unquantified here.** `C2` is a 0603 multi-layer ceramic, so its
  effective capacitance at 3.3V is below the nominal 10uF. The Espressif figure is
  written for a nominal 10uF, but nobody has measured what `C2` actually delivers at
  the rail voltage, so treat the "10uF" as nominal until it is checked (§5). Do not
  quietly downgrade it (e.g. to 1uF) on the grounds that it is "only decoupling".

---

## 2. Current budget — why the 600mA `AP2112K-3.3` is enough

**Owner decision (2026-09-18): WiFi/BT is never used on this module.** The design
budget is therefore the non-RF one:

| Load | Typical | Peak (RF disabled) |
|---|---|---|
| ESP32-S3-WROOM-1U-N16R8 (RF disabled) | 50-90 mA | ~120 mA |
| ES8388 codec + its analogue rails | 15-25 mA | 30 mA |
| MCP6002 (2 sections) | 0.3 mA | 0.5 mA |
| Status LED + pull-ups/dividers | ~2.5 mA | ~3 mA |
| **Module total** | **~0.08-0.12 A** | **~0.15-0.2 A** |

Two independent ceilings bound the worst case:

* the base's per-slot current limit, `I_LIM ≈ 667 mA` (TPS2111A, `R_ILIM` = 750Ω),
  which also caps the module's 5V input;
* the regulator itself: **`AP2112K-3.3` guarantees 600mA** continuous (Diodes
  AP2112 datasheet; LCSC `C51118`).

600mA covers the realistic peak (~0.2A) with **≈3x margin**, and the module's typical
~0.12A with ≈5x. For the record, if the radio were ever enabled the ESP32-S3 TX peak
is ~340mA (module total ~0.4A) — still within the part's 600mA rating (≈1.5x) but
outside this design's stated budget; that firmware path is not used.

---

## 3. Thermal considerations — SOT-23-5 (v1.1.1)

```
PD = (VIN - VOUT) x IOUT          (1.7 V across the pass element on a 5 V input)
PD(max@TA) = (125 C - TA) / theta_JA
```

| Case | IOUT | PD | ΔT at θJA ≈ 250 °C/W (SOT-23-5, no exposed pad) |
|---|---|---|---|
| typical | 0.12 A | 0.20 W | ~51 °C |
| non-RF peak | 0.20 A | 0.34 W | ~85 °C |
| (hypothetical RF peak — not used) | 0.40 A | 0.68 W | ~170 °C |

Unlike the v1.1.0 SOT-223, the SOT-23-5 has **no exposed thermal tab** (ground is the
middle pin), so the package cannot be soldered to a plane directly and θJA stays in
the ~200-250 °C/W class in still air. That puts the thermally-limited continuous
output current at roughly `(125-25)/250/1.7 ≈ 235 mA` at 25 °C ambient — around
190 mA at 45 °C. **The module's realistic load (≤0.2A peak) sits just inside that
envelope and the typical ~0.10-0.12A is comfortable** (ΔT ≈ 43-51 °C, TJ ≈ 70-80 °C);
the owner's no-WiFi decision is what keeps this safe.

*Residual risk, stated explicitly*: sustained RF operation (0.3A+) would take the
SOT-23-5 past its thermal capability — this is a consequence of choosing the small
package, accepted by the owner on the no-WiFi basis. The only thermal levers
available to the routing pass are (a) a solid `GND` copper connection to `U5` pin 2
and the ground ends of `C40`/`C42`/`C41`, and (b) keeping the regulator away from hot
parts. No dedicated copper zone is required for the non-RF budget.

---

## 4. Verification (v1.1.2, schematic-only)

Run with KiCad **10.0.6** (`kicad-cli` 9.x cannot parse this board's KiCad 10
format). Artefacts in `verification/`.

| Check | v1.1.0 | v1.1.1-as-released (`4af97a8`) | v1.1.1 source (`1244ad0` = pre-trim) | v1.1.2 | Delta 1.1.1-source → 1.1.2 |
|---|---|---|---|---|---|
| `kicad-cli sch erc --severity-all` | 54 (34 error / 20 warning) | **54 (34 / 20)** | **56 (35 / 21)** | **56 (35 / 21)** | **0 new findings, 0 changed findings** (normalised per finding: severity + type + affected items + positions) |
| netlist acceptance, regulator swap (`netlist-proof-ldo-swap.json`) | — | **19/19 pass** | *not reproducible* (`C41` — see §5) | *not re-run* | the 1.1.0 → 1.1.1-as-released pair still reproduces 19/19 byte-for-byte |
| netlist acceptance, bulk-cap trim (`proof-bulk-cap-trim.json`) | — | — | — | **20/20 pass** | exactly `C9`..`C13` gone; every surviving part's value/footprint/fields identical; **every** net identical after subtracting only those pins; ERC findings identical; 3-link chain 1.1.0 → 1.1.1-as-released → 1.1.1@1244ad0 → 1.1.2 verified at every hop |
| `verification/check_bulk_cap_trim.py` | — | — | — | reproduces the trim proof | see the docstring for the exact command line |
| `kicad-cli pcb drc --schematic-parity` | 4 parity warnings (measured, the v1.1.0 run in `drc-32bit-5v.json`) | **not re-run** — expected: `U5` footprint mismatch + `C42` missing on the board | **not re-run** — expected: additionally the `C41` net-mismatch | **not re-run** — expected: `U5` + `C42` + `C41` + `C9`..`C13` unmatched | the board is deliberately untouched; all figures except the 1.1.0 one are **expected, not measured** — re-run after the routing pass |

**Why a 54 → 56 jump sits in the v1.1.1 column.** `verification/erc-32bit-5v-1.1.1-pre-1244ad0.json`
is the report that shipped with the v1.1.1 commit; `erc-32bit-5v-1.1.1.json` is a fresh
run against the same *source revision* that v1.1.2 starts from (commit `1244ad0`,
"Update the 32bit schematics a bit", which changed the schematic without refreshing the
artefacts). Normalised against the shipped report, the whole difference is exactly two
findings, both caused by `C41` losing its `+3V3` connection in that commit:

```
+1 error    pin_not_connected          Symbol C41 Pin 1
+1 warning  unconnected_wire_endpoint  Vertical Wire, length 0.0254 mm
```

That is a **pre-existing defect, not a v1.1.2 change** — this revision deliberately does
not touch it (see §5). Against it, **v1.1.2 introduces nothing**: the normalised finding
sets of `erc-32bit-5v-1.1.1.json` and `erc-32bit-5v.json` are identical, element for
element.

The DRC/parity artefacts kept in `verification/` (`drc-32bit-5v.json`,
`drc-32bit-baseline.json`) are the **v1.1.0** board-vs-board runs; they remain accurate
for the board, which did not change in either revision. `erc-32bit-5v.json`,
`netlist-32bit-5v.kicadsexpr`, `proof-bulk-cap-trim.json` and
`netlist-32bit-5v-1.1.1.kicadsexpr` were regenerated for v1.1.2; the older netlists are
kept as `netlist-32bit-5v-1.1.0.kicadsexpr` and
`netlist-32bit-5v-1.1.1-as-released.kicadsexpr`.

---

## 5. Open risks (v1.1.2)

* **`C41` (22uF, LDO output bulk) is not connected to `+3V3`.** Commit `1244ad0`
  re-placed `C41` from (525.78, 29.21) to (464.82, 33.02) but its top stub, wire
  `(464.82, 29.21) → (464.82, 26.67)`, was left ending in mid-air: the `+3V3` trunk
  next to it stops at `x = 444.5`, and the nearest `+3V3` wire is the horizontal run at
  `y = 24.13` from `U5` `VOUT` (459.74, 24.13) to the `+3V3` power symbol
  (467.36, 24.13) — 2.54mm above and not touching. The netlist therefore carries
  `unconnected-(C41-Pad1)` and ERC reports `pin_not_connected` on `C41` pin 1.
  **Impact — not measured, do not assume it is harmless.** `C8` 10uF + `C6` 0.1uF still
  sit on `+3V3`, so the rail is not bare and the module is *expected* to run; but the
  regulator is missing 22uF of its own output bulk, which is a real deviation from the
  documented design and was never validated on the bench. **This must be resolved before
  board synchronisation or manufacture**, not carried along.
  **Remedy (scoped separately; not applied in v1.1.2):** add one wire
  `(464.82, 26.67) → (464.82, 24.13)` plus a junction at (464.82, 24.13). On the current
  source that removes the two `C41` findings (ERC 56 → 54, i.e. back to the v1.1.1
  shipped count) and puts `C41`.1 back on `+3V3`. It does **not** make
  `check_ldo_swap_netlist.py` pass again against 1.1.2: that proof is bound to the
  frozen 1.1.0 → 1.1.1-as-released pair, and a 1.1.2 netlist also has `+3V3_ESP32`
  without `C9`..`C13`, so the historical proof keeps its 19/19 only on its own pair
  (which is how `verification/README.md` documents it).
* **Board work is pending (owner's routing pass)**: delete the SOT-223 `U5` footprint
  and its thermal vias, place the SOT-23-5 regulator plus `C42` (0402), remove the five
  `C9`..`C13` 1206 bulk-cap footprints from the ESP32 rail (with their copper), place
  `C1`/`C2` close to `U1` pin 2, and move `C40`/`C41` to the top side so the module is
  single-side SMD assembled for the first time. Until then the schematic and the board
  disagree by design (§1.1).
* **Jumper dependence** (§1): the module needs the slot rail-select jumper fitted
  (5V). Left open, the module browns out. Unchanged from v1.1.0.
* **Input over-voltage**: the AP2112K's recommended maximum input is 6.0V. The base's
  protection is a PPTC plus an SMAJ5.0A TVS whose peak clamp is 9.2V — an exposure
  the base's own v1.3.0 note already accepts for the very same part. `32bit-5v`
  inherits it unchanged (the 5V comes from the base).
* **Thermal**: see §3 — fine for the no-WiFi budget, not for sustained RF.
* **ESP32 rail: the bulk bank is gone and the replacement is not yet validated**
  (§1.3). The trim follows the specified 10uF + 0.1uF set, but it also retires ~500uF of
  load-transient reservoir, and this revision contains **no measurement** of the module
  on this rail — neither load-transient/brownout behaviour nor the DC-bias-reduced
  effective value of `C2`. Those two measurements are **pending** and should be done on
  the bench before the change is considered closed. If they show brownout or
  PSRAM-related resets, the first thing to try is **one** 0805/1206 bulk cap behind
  `FB1` — and check `C41` is connected (§5) before blaming the trim.
* **Stock/sourcing**: `AP2112K-3.3TRG1` (LCSC `C51118`) is the base module's part and
  a mainstream JLCPCB/LCSC line item (≈66k in stock when last checked); using it here
  means one fewer part number to qualify. Removing five generic 1206 capacitors also
  removes five line items and their placement cost.
* **Package/pinout**: `U5` is a SOT-23-5 (`VIN` 1, `GND` 2, `EN` 3, `NC` 4,
  `VOUT` 5). Any substitute must match this pinout; note that the old SOT-223
  warnings in the v1.1.0 note (AMS1117/LM1117 mirrored pinout) no longer apply,
  because that footprint is being replaced.

---

## 6. Hand-off for the owner's routing pass

| # | Board change | Part / footprint | Notes |
|---|---|---|---|
| 1 | **Delete** the `U5` footprint (`Package_TO_SOT_SMD:SOT-223-3_TabPin2`, bottom side at 60.9, 57.6) and its dedicated vias (3 tab thermal vias, 1 GND-lead via, 1 `C41`-GND via, 1 `+3V3` output via) | `AP7361C-33E-13` is gone from the schematic, so this footprint has no schematic counterpart | nets `+5V`, `GND`, `+3V3` keep their names |
| 2 | **Delete `C9`..`C13`** (five 1206 bulk caps) and their copper from the ESP32 rail | no schematic counterpart in v1.1.2 | frees real estate right where `C1`/`C2` need to sit; the nets `+3V3_ESP32`/`GND` keep their names |
| 3 | **Add** the new regulator | `U5` = `Package_TO_SOT_SMD:SOT-23-5` (`AP2112K-3.3`, SOT-23-5) | pins: 1 `VIN`→`+5V`, 2 `GND`, 3 `EN`→`+5V`, 5 `VOUT`→`+3V3`; pin 4 `NC` unused |
| 4 | **Add** the new input HF cap | `C42` = `Capacitor_SMD:C_0402_1005Metric`, 0.1uF (`C1525`) | on `+5V` next to `C40` |
| 5 | **Move to the top side** (or replace) | `C40` (0805, 10uF) and `C41` (0805, 22uF) | they are on the bottom side today; moving them makes the module single-side SMD |
| 6 | **Place `C1`/`C2` tight to `U1` pin 2** (0402 0.1uF + 0603 10uF) | `Capacitor_SMD:C_0402_1005Metric`, `Capacitor_SMD:C_0603_1608Metric` | values/parts unchanged by v1.1.2, but with the 100uF bank gone there is no distant reservoir left, so these two parts carry the decoupling — short loop to a solid `GND`, per §1.3 |
| 7 | **Keep as is** | `C40` 10uF/25V 0805 (`C15850`), `C41` 22uF/25V 0805 (`C45783`), `C1` 0.1uF, `C2` 10uF, `C6` 0.1uF, `C8` 10uF, `FB1`, all `+3V3` loads | values/parts unchanged by v1.1.1 and v1.1.2 |
| 8 | **Owner decision, do before board sync/manufacture: reconnect `C41` in the schematic** | one wire + one junction (see §5) | not applied in v1.1.2 — it is a pre-existing `1244ad0` defect, deliberately outside this revision's scope; until it is fixed the schematic and any board built from it disagree on `C41`'s net |

Suggested region: the input area around the old regulator / `V_SUPPLY1` and the old
`C40`/`C41` position, on the **top (F.Cu)** side, so that `VIN`+`EN`, `GND` and
`VOUT` stay short and `U5`'s ground pin can be stitched into the GND pour. Nothing
has been placed or routed in this revision.
