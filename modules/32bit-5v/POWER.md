# 32bit-5v — 5V input, on-board 3.3V rail (v1.1.1, schematic-only)

This note describes the power architecture of the `32bit-5v` variant and the numbers
behind the component choices. The schematic is the authority for the schematic and
`32bit-5v.kicad_pcb` for the board — and as of **v1.1.1** the board still carries the
**v1.1.0** regulator layout, because the regulator swap is a **schematic-only**
change (see §1.1 and §6).

---

## 1. Rail map (v1.1.1 — as drawn in `32bit-5v.kicad_sch`)

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
       ├── C41 22uF/25V X5R 0805 ..... output bulk
       │
       ▼
     +3V3  ──┬── C6 0.1uF, C8 10uF ....... output HF + local bulk (pre-existing)
             ├── FB1 ──► +3V3_ESP32 ──► U1 ESP32-S3-WROOM-1U, C1, C2, C9..C13
             ├── R15 ──► +3V3_8388  ──► U4 ES8388, C5, C7, C21..C39
             ├── R3 pull-up, R10/R12 CV dividers
             └── U3 MCP6002 (V+)
```

* **Exactly the same 3.3V loads as v1.1.0.** The `+3V3` node set is unchanged apart
  from the regulator's own pin (old `VO` pin 3 → new `VOUT` pin 5); `+3V3_ESP32` and
  `+3V3_8388` keep byte-for-byte identical node sets (machine-checked, §4).
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

### 1.1 Board status after v1.1.1 (pending the owner's routing pass)

`32bit-5v.kicad_pcb` is **untouched** by this revision: no placement, no routing, no
zone refill, no footprint deletion. It still contains the v1.1.0 parts — the `U5`
SOT-223 footprint (`Package_TO_SOT_SMD:SOT-223-3_TabPin2`, bottom side at 60.9, 57.6)
and the `C40`/`C41` 0805 footprints on the bottom side — while the schematic now
declares `U5` as a SOT-23-5 and adds `C42`. Therefore
`kicad-cli pcb drc --schematic-parity` will legitimately report the `U5` mismatch
until the routing pass is done. That is **expected and owned by the owner**; it is
not something to "fix" from the schematic side. See §6 for the hand-off.

### 1.2 Regulator decoupling vs the base module

| Position | Base (`modules/base`, `U5`) | `32bit-5v` v1.1.1 | Comment |
|---|---|---|---|
| LDO input bulk | `C2` 1uF 0805, LCSC `C28323` (`CL21B105KBFNNNE`) | `C40` 10uF 0805, LCSC `C15850` (`CL21A106KAYNNNE`) | **deviation**: 10x larger, same Samsung CL21 0805 family. The module's 5V arrives on a slot socket with no upstream bulk, whereas the base has 22uF (`C17`) + 0.1uF (`C21`) ahead of its input ferrite. |
| LDO input HF | `C21` 0.1uF 0402, LCSC `C1525` (`CL05B104KO5NNNC`) | **`C42` 0.1uF 0402, LCSC `C1525`** (added) | identical part, same value/footprint/LCSC |
| LDO output at the pin | `C4` 4.7uF 0805, LCSC `C1779` | `C41` 22uF 0805, LCSC `C45783` (`CL21A226MAQNNNE`) | **deviation**: larger bulk for the ESP32 + ES8388 load; same Samsung CL21 0805 family |
| Output bulk / HF behind the ferrite | `C6` 22uF 1206 (`C90146`) + `C1` 0.1uF 0402 (`C1525`) | `C8` 10uF + `C6` 0.1uF 0402 on `+3V3`, then `FB1` → `+3V3_ESP32` | pre-existing module decoupling, unchanged |
| `EN` | `R4` 100k VIN→EN, `C16` 220nF, `SW1` to GND | `EN` wired directly to VIN (`+5V`) | **deviation**: no switch — the module must always be on |

Net effect: the base's scheme (**bulk + 0.1uF at the input, bulk + 0.1uF at the
output**) is reproduced with the same part family, with the two bulk values kept at
the module's larger, pre-existing values, and with the base's exact 0.1uF part for
the new input HF cap. No decoupling was removed.

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

## 4. Verification (v1.1.1, schematic-only)

Run with KiCad **10.0.6** (`kicad-cli` 9.x cannot parse this board's KiCad 10
format). Artefacts in `verification/`.

| Check | v1.1.0 | v1.1.1 | Delta |
|---|---|---|---|
| `kicad-cli sch erc --severity-all modules/32bit-5v/32bit-5v.kicad_sch` | 54 (34 error / 20 warning) | **54 (34 error / 20 warning)** | **0 new findings, no new finding kind** |
| netlist acceptance (`verification/netlist-proof-ldo-swap.json`) | — | **19/19 pass** | `+5V` confined to the regulator path; every 3.3V load still driven; `AP7361C` gone; `U5` fields identical to the base's `U5` |
| `verification/check_ldo_swap_netlist.py` | — | reproduces the proof | compares the 1.1.0 netlist artefact against the current export |
| `kicad-cli pcb drc --schematic-parity` | 4 parity warnings | **+1 expected `U5` mismatch** | the board is deliberately untouched; re-run after the routing pass |

The DRC/parity artefacts kept in `verification/` (`drc-32bit-5v.json`,
`drc-32bit-baseline.json`) are the **v1.1.0** board-vs-board runs; they remain
accurate for the board, which did not change in this revision. `erc-32bit-5v.json`
and `netlist-32bit-5v.kicadsexpr` were regenerated for v1.1.1, and the 1.1.0 netlist
is kept as `netlist-32bit-5v-1.1.0.kicadsexpr`.

---

## 5. Open risks (v1.1.1)

* **Board work is pending (owner's routing pass)**: delete the SOT-223 `U5`
  footprint and its thermal vias, place the SOT-23-5 regulator plus `C42` (0402),
  and move `C40`/`C41` to the top side so the module is single-side SMD assembled
  for the first time. Until then the schematic and the board disagree on `U5` by
  design.
* **Jumper dependence** (§1): the module needs the slot rail-select jumper fitted
  (5V). Left open, the module browns out. Unchanged from v1.1.0.
* **Input over-voltage**: the AP2112K's recommended maximum input is 6.0V. The base's
  protection is a PPTC plus an SMAJ5.0A TVS whose peak clamp is 9.2V — an exposure
  the base's own v1.3.0 note already accepts for the very same part. `32bit-5v`
  inherits it unchanged (the 5V comes from the base).
* **Thermal**: see §3 — fine for the no-WiFi budget, not for sustained RF.
* **Stock/sourcing**: `AP2112K-3.3TRG1` (LCSC `C51118`) is the base module's part and
  a mainstream JLCPCB/LCSC line item (≈66k in stock when last checked); using it here
  means one fewer part number to qualify.
* **Package/pinout**: `U5` is a SOT-23-5 (`VIN` 1, `GND` 2, `EN` 3, `NC` 4,
  `VOUT` 5). Any substitute must match this pinout; note that the old SOT-223
  warnings in the v1.1.0 note (AMS1117/LM1117 mirrored pinout) no longer apply,
  because that footprint is being replaced.

---

## 6. Hand-off for the owner's routing pass

| # | Board change | Part / footprint | Notes |
|---|---|---|---|
| 1 | **Delete** the `U5` footprint (`Package_TO_SOT_SMD:SOT-223-3_TabPin2`, bottom side at 60.9, 57.6) and its dedicated vias (3 tab thermal vias, 1 GND-lead via, 1 `C41`-GND via, 1 `+3V3` output via) | `AP7361C-33E-13` is gone from the schematic, so this footprint has no schematic counterpart | nets `+5V`, `GND`, `+3V3` keep their names |
| 2 | **Add** the new regulator | `U5` = `Package_TO_SOT_SMD:SOT-23-5` (`AP2112K-3.3`, SOT-23-5) | pins: 1 `VIN`→`+5V`, 2 `GND`, 3 `EN`→`+5V`, 5 `VOUT`→`+3V3`; pin 4 `NC` unused |
| 3 | **Add** the new input HF cap | `C42` = `Capacitor_SMD:C_0402_1005Metric`, 0.1uF (`C1525`) | on `+5V` next to `C40` |
| 4 | **Move to the top side** (or replace) | `C40` (0805, 10uF) and `C41` (0805, 22uF) | they are on the bottom side today; moving them makes the module single-side SMD |
| 5 | **Keep as is** | `C40` 10uF/25V 0805 (`C15850`), `C41` 22uF/25V 0805 (`C45783`), `C6` 0.1uF, `C8` 10uF, `FB1`, all `+3V3` loads | values/parts unchanged by v1.1.1 |

Suggested region: the input area around the old regulator / `V_SUPPLY1` and the old
`C40`/`C41` position, on the **top (F.Cu)** side, so that `VIN`+`EN`, `GND` and
`VOUT` stay short and `U5`'s ground pin can be stitched into the GND pour. Nothing
has been placed or routed in this revision.
