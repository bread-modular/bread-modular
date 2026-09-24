# BASE v1.3.0 — power architecture, protection and per-slot rail selection

Scope of v1.3.0: **schematic, footprints and part numbers only.** The PCB
(`base.kicad_pcb`) is intentionally *not* updated, placed or routed — that is Phase 2.
Nothing in this note overrides the schematic.

**Signal contract:** Bread Modular signals are **0–3.3 V**. A 5 V slot powers a
module's internal regulator; it does not imply 5 V signals. The schematic now
includes modest reset/power-off input-current limiting (v1.3.11, §11), not full
powered-off isolation.

---

## 1. Rail map

```
USB-C J5 (power only, VBUS)
   │
  F1  PPTC 2 A hold / 4 A trip / 16 V     (BSMD1812-200-16V, C883156)
   │
   ▼
net VBUS_PROT ──┬── D2 TVS (SMAJ5.0A) ── GND
                ├── C17 22 µF, C21 0.1 µF, D1 status LED
                ├── FB1 ──► LDO_VIN ──► U5 AP2112K-3.3 ──► +3.3V   (unchanged since v1.2.0)
                └── F2  PPTC 1.1 A hold / 2.2 A trip / 16 V   (MF-MSMF110/16-2, C210834)
                          │
                          ▼
                     net 5V_SYS ──┬── D3 TVS (SMAJ5.0A) ── GND
                                  ├── C46 100 µF/16 V (1210 X5R) + C47 0.1 µF
                                  ├── PWR_FLAG (ERC: externally sourced)
                                  └── 12 × U6..U17  IN1
```

Per module slot *n* (1…12) — **v1.3.9 select arrangement** (see §1a and §2):

```
   VBUS_PROT ──┬── U(n+5).MODE       manual-mode bias, ≥ 1 V external (v1.3.9)
               └── J(n+6) pin 1      shunt ⇒ PR1 high ⇒ VIN1 = 5V_SYS

   +3.3V ─────┐
               ├── U(n+5) TPS2116DRLR (2:1 power mux, manual mode)
   5V_SYS ─────┘        │                  │               │
                  PR1 = SEL_n         VOUT pins 2+7 ──┴──► net VSLOT_n ──► all five pins of the
                       │                                     existing VSUPPLY_n socket
              R(27+2n) 100 k ── GND      C(20+2n) 1 µF, C(21+2n) 0.1 µF   VSLOT_n ── GND
```

*(`U(n+5)` is `TPS2111APWR` on the fabricated board and `TPS2116DRLR` in the current
schematic. The two parts are **not** pin- or behaviour-equivalent, and since v1.3.9 the
control reference is `VBUS_PROT` rather than `+3.3 V` — see §1a.)*

The socket pinout is unchanged: every `VSUPPLY_n` socket still has all five pins on one
slot rail (now `VSLOT_n` instead of unconditionally `+3.3V`), and `GND_n` remains the
mating ground socket.

## 1a. v1.3.8/v1.3.9 — per-slot mux swapped to TPS2116DRLR, select re-referenced to VBUS_PROT (schematic only, PCB pending)

The twelve per-slot muxes (`U6…U17`, one per slot-template instance) are `TPS2116DRLR` in
the schematic. The board is untouched: the working tree's `base.kicad_pcb` is byte-identical
to this branch's committed board (sha256 `b8df0829…`, **not** the `routed_pcb_sha256` pin
`9fc20400…`, which is the older v1.3.2 fab release and is already stale on this branch), and
every payload in `production/` is still the **v1.3.2** release (`manifest.json`
`release_version: "1.3.2"`). Phase 2 swaps the twelve footprints, moves the twelve jumper
pin-1 nets, re-routes them and re-exports.

> **Status: the v1.3.8 reset blocker is resolved in the schematic (v1.3.9).** `MODE` and the
> `J(n+6)` pin-1 select reference now come from `VBUS_PROT`, so the select survives a reset —
> see *Blocker 1 (v1.3.8, as drawn then) → fix (v1.3.9)* below and the state table in §2.
> **What is still not protected, and is now the only electrical gap:** the per-slot 667 mA
> `ILIM` limit is gone and is **accepted by the owner for this revision** (*Consequence 2*),
> and the §3.2 surge limitation is unchanged.


Why: measured on the JLCPCB parts API on 2026-09-18, `TPS2111APWR` (C471060) is
**$1.3804 @100 / $2.0267 @1-9 with 2 482 in stock**, and there is no cheaper TSSOP-8
sibling (`TPS2110APWR` $1.6848/0, `TPS2114APWR` $1.2714/0, `TPS2115APWR` $1.7499/206,
`TPS2113APWR` $1.5579/2 121, `TPS2112PWR` $2.0902/199). `TPS2116DRLR` (C3235557,
SOT-583) is **$0.2052 @500-999 with 48 871 in stock** → **≈$13.1/board cheaper**
(12 × $1.2974 − 12 × $0.2052), and it deletes the twelve ILIM resistors with it.

| pin | TPS2111APWR | net | TPS2116DRLR | net |
|---|---|---|---|---|
| 1 | `D0` | GND (manual-mode strap) | `GND` | GND |
| 2 | `D1` | `SEL_n` | `VOUT` | `VSLOT_n` |
| 3 | `VSNS` | GND | `VIN1` | `5V_SYS` |
| 4 | `ILIM` | 750 Ω → GND | `PR1` | `SEL_n` |
| 5 | `GND` | GND | `MODE` | `VBUS_PROT` (external bias ≥ 1 V; was `+3.3V` in v1.3.8) |
| 6 | `IN2` | `+3.3V` | `VIN2` | `+3.3V` |
| 7 | `OUT` | `VSLOT_n` | `VOUT` | `VSLOT_n` |
| 8 | `IN1` | `5V_SYS` | `ST` | *no connect* |

* Normal-operation polarity is preserved: shunt fitted ⇒ `SEL_n` high ⇒ `PR1` high ⇒
  `VIN1 = 5V_SYS`; shunt absent (100 kΩ pulldown) ⇒ `PR1` low ⇒ `VIN2 = +3.3 V`.
  **v1.3.9 changed only the reference rail of the select**: `MODE` and the jumper pin 1 now
  come from `VBUS_PROT` instead of `+3.3 V`, so the select state no longer collapses with the
  3.3 V rail. `MODE` is not tied to `VIN1`; a ≥ 1 V external bias is what selects manual
  mode. The jumper, the 100 kΩ pulldown and every `SEL_n`/`VSLOT_n` net name are unchanged.
* **Blocker 1 (v1.3.8, as drawn then) → fix (v1.3.9).** In v1.3.8 `MODE` was tied to
  `VIN2 = +3.3 V` and `PR1` was fed from the *same* rail through the `J(n+6)` shunt
  (pin 1 = `+3.3 V`, pin 2 = `SEL_n`). `SW1` gates `U5.EN`, so **every reset press removed
  `+3.3 V` while `5V_SYS` (from `VBUS_PROT` through `F2`, not from the LDO) stayed up** and
  both control pins fell with the rail: `MODE` below `VIL,MODE = 0.35 V` with `PR1` already
  below `VREF ≈ 1 V`. The part then entered *diode mode* — quoting the datasheet, **"When
  the PR1 pin is pulled low, the higher voltage supply between VIN1 and VIN2 is passed to
  the output"** — i.e. **a 3.3 V-jumpered slot was fed `5V_SYS` on every reset press, shunt
  fitted or absent.** The TPS2111A did not behave this way (`D0 = GND` / `D1 = SEL_n`
  selected the channel purely by logic, so a reset only sagged the 3.3 V rail). The
  datasheet wording that makes the low-`MODE` state a diode/OR-ing mode rather than a
  defined off state is also the subject of
  [this TI E2E thread](https://e2e.ti.com/support/power-management-group/power-management/f/power-management-forum/1559536/tps2116-confusing-logic-description-in-the-datasheet).
* **The fix: the select reference is `VBUS_PROT`, not `+3.3 V`.** `MODE` and the jumper
  pin 1 moved to `VBUS_PROT` (the always-on protected 5 V upstream of `F2`); `VIN2` stays on
  `+3.3 V`. Datasheet basis — TI **SLVSFG1A** (*TPS2116*, Jan 2021, rev. May 2021):
  * §5 Table 5-1 — `MODE`: "Device is put into Priority mode when MODE is tied to VIN1 and
    **manual mode when MODE is pulled up to an external voltage**"; §7.6.1.2 — "the GPIO pin
    can be **directly connected to the PR1 pin when MODE is tied high (≥ 1 V)**", i.e. no
    series resistor is required and the existing 100 kΩ pulldown is what defines the
    un-shunted state. No other resistor is needed or added.
  * §6.5 Electrical Characteristics — `VIH,MODE = 1…5.5 V`, `VIL,MODE = 0…0.35 V`,
    `VREF = 0.92/1/1.08 V`. A ~5 V `VBUS_PROT` is unambiguously logic high and
    unambiguously above `VREF` (≥ 4× margin on `VIH,MODE`).
  * §6.3 Recommended Operating Conditions — `VST, VMODE, VPR1 = 0…5.5 V`, **independent of
    VINx**; §6.1 Absolute Maximum Ratings — control pins `−0.3…6 V`. Biasing these two pins
    from `VBUS_PROT` is therefore **inside spec**: no divider and no level shift is needed.
    (A divider from `VBUS_PROT` was considered and rejected — it adds 24 parts and a
    high-impedance failure mode, and the datasheet's own manual-mode wiring is a direct
    connection. A series resistor would not protect against the §3.2 surge either, because
    no current flows in that pin.)
  * §7.6.1 nuance — the device decides manual mode from the **level on `MODE`** (≥ 1 V
    external bias), not from which node feeds it. `VBUS_PROT` and `VIN1 = 5V_SYS` are the
    same source separated only by the `F2` PPTC (~0.6 Ω), so even if the silicon read the
    pin as "tied to VIN1" the selection would be identical: in both modes, a hard-driven
    `PR1` selects `VIN1` above `VREF` and `VIN2` below it (§7.3.1 truth table, §7.6.1).
    `PR1` is always driven hard from the header, never divided off `VIN1`.
* **Why the reset is now safe, in one line.** `VIN1`, `VIN2` *and* the select reference are
  all derived from the single `VBUS_PROT` node, so the residual diode-mode window
  (`MODE ≤ 0.35 V`) can only occur while `VBUS_PROT ≤ 0.35 V` — and therefore while **both**
  inputs are ≤ 0.35 V. The "higher of the two" that diode mode passes can never be 5 V. The
  full state table, including the reset and power-up rows, is in §2.
* **Consequence 2 — no programmable `ILIM`, accepted by the owner for this revision.** The
  667 mA per-slot current limit of §3.3 is gone (the `TPS2116DRLR` has no `ILIM` pin) and
  `R28/R30/…/R50` (750 Ω) are deleted from the schematic (they stay fitted on the board
  until Phase 2). **Stated plainly, what is still not protected:** a slot-level overload (a
  stub, a reversed module, a shorted module input) is bounded only by the **upstream**
  limits — the `5V_SYS` PPTC `F2` (1.1 A hold / 2.2 A trip, **shared by all twelve slots**),
  the `U5` LDO limit on the 3.3 V branch, the mux's soft start and its reverse-current
  blocking, plus **thermal shutdown (170 °C — an over-temperature trip, *not* a current
  limit)**. The mux itself is rated 2.5 A continuous, so one bad slot can pull the whole
  `5V_SYS` branch down (and brown out every other slot) before `F2` trips. If a per-slot
  limit must come back, the cheapest mux with an adjustable one is `TPS2120` (C1850326,
  $0.6626 @100, DSBGA-20).
* Evidence (v1.3.9): `tools/reroute_mux_select_vbus_prot.py` is the deterministic migration
  (refuses to run twice). With `kicad-cli` it proves that the **only** netlist difference is
  the 12 `MODE` pins and the 12 `J(n+6)` pin-1 pins leaving `+3.3 V` and joining `VBUS_PROT`
  (every other net — including all twelve `SEL_n` and all twelve `VSLOT_n` — and every
  component byte-identical), that **all twelve** instances (`U6…U17` / `J7…J18`) carry the
  change, and that the ERC findings are identical by identity (severity + type + sheet +
  affected items): **11 before / 11 after, none added, none removed**. It writes
  `verification/mux-select-vbus-prot.json` plus the post-change netlist. The v1.3.8 evidence
  for the part swap itself is still `verification/mux-swap-tps2116.json` (its stored
  "after" netlist describes the pre-v1.3.9 schematic, by design).
* Guard: `tools/verify_power.py` now expects `MODE` on `VBUS_PROT` and lists the twelve
  `J7…J18` pin-1 pads in `moved_jumper_ref_pads` (board-side *PCB pending*). **It does not
  run to completion on this branch**: it aborts at
  `check(project['erc'] == baseline['project_erc'], 'ERC setup changed')` because three pins
  in `verification/fixed-geometry.json` (`project_erc`, `schematic_sha256`,
  `routed_pcb_sha256`) predate the KiCad 10 project format and the 1.3.7/1.3.8 schematics.
  That abort is **pre-existing** — it reproduces on untouched `e18b038` — and is unrelated to
  this change (it is the same `check` call, shifted from line 165 to 173 by the lines added
  here). The assertions touched by this change were evaluated directly against the exported
  netlist and the board instead.
* Phase 2 checklist: swap `U6…U17` to `Package_TO_SOT_SMD:SOT-583-8`, delete
  `R28/R30/…/R50`, **move the twelve `J7…J18` pin-1 nets from `+3.3V` to `VBUS_PROT`**,
  re-route the local pads, re-run `kicad-cli pcb drc --schematic-parity`, then
  `verify_stack_height.py`, `verify_power.py` (drop `PCB_PENDING`, after re-pinning the stale
  `fixed-geometry.json` hashes) and `regenerate_production.py`. Bench-check all four states —
  shunt fitted, shunt absent, reset pressed, and power-up sequencing — before releasing.
* Residual risks, recorded and **not** fixed here: (a) the per-slot `ILIM` gap above;
  (b) the §3.2 surge limitation, which since v1.3.9 also covers the `MODE`/`PR1` pins (they
  share the same 6 V absolute maximum); (c) a stray short from a select header pin 1 to
  ground now pulls `VBUS_PROT` through `F1` (2 A hold) rather than into the LDO's own limit —
  the header is a logic-only 2 mm pin pair under a shunt, unchanged in use.

## 2. Per-slot 2:1 selection — truth table (v1.3.9, as implemented)

Select reference rail = `VBUS_PROT` (~5 V whenever USB power is present; upstream of `F2`, so
it survives both a reset press and an `F2` trip). `VIN1 = 5V_SYS`, `VIN2 = +3.3 V`;
`MODE` = `VBUS_PROT` (≥ 1 V ⇒ **manual mode**); `PR1` = `SEL_n` (shunt fitted ⇒ pin 1 =
`VBUS_PROT` ⇒ `PR1` ≈ 5 V; shunt absent ⇒ 100 kΩ pulldown ⇒ `PR1` = 0 V).

| # | state | `VBUS_PROT` | `+3.3 V` | `5V_SYS` | `MODE` | mode | `PR1` open / shunt | `VOUT` — 3.3 V-jumper | `VOUT` — 5 V-jumper |
|---|---|---|---|---|---|---|---|---|---|
| 1 | normal, shunt absent | ≈5 V | 3.3 V | ≈5 V | ≈5 V | manual | 0 V / — | **`VIN2` = 3.3 V** | — |
| 2 | normal, shunt fitted | ≈5 V | 3.3 V | ≈5 V | ≈5 V | manual | — / ≈5 V | — | **`VIN1` = 5 V** |
| 3 | **RESET pressed** (`SW1` ⇒ `+3.3 V` = 0 V) | ≈5 V | 0 V | ≈5 V | ≈5 V | **manual** | 0 V / ≈5 V | **0 V** (deselected — *never* `5V_SYS`) | **`VIN1` = 5 V** |
| 4 | 3.3 V-rail-only fault (`+3.3 V` = 0 V) | ≈5 V | 0 V | ≈5 V | ≈5 V | manual | 0 V / ≈5 V | **0 V** | **5 V** |
| 5 | power-up, `VBUS_PROT` ≤ 0.35 V | ≤0.35 V | 0 V | ≤0.35 V | ≤0.35 V | diode (self-bounded) | 0 V / ≤0.35 V | ≤0.35 V | ≤0.35 V |
| 6 | power-up, `VBUS_PROT` ≈1…2.5 V (LDO not started) | 1…2.5 V | 0 V | 1…2.5 V | ≥1 V | manual | 0 V / ≥1 V | **0 V** | follows `VBUS_PROT` |
| 7 | no USB attached | 0 V | 0 V | 0 V | 0 V | diode (both inputs 0 V) | 0 V / 0 V | 0 V | 0 V |

* **Target met.** A **3.3 V-jumpered slot never sees `5V_SYS` in any state** — rows 1, 3, 4,
  5, 6 and 7 all leave it on `VIN2` (3.3 V, 0 V, or ≤ 0.35 V) — and a **5 V-jumpered slot
  still gets 5 V** (rows 2, 3, 4).
* Rows 5 and 7 are the diode-mode states. Row 5 (the only one with any rail energy, during
  power-up) is **self-limiting**: `VIN1` (`5V_SYS`) and `VIN2` (`+3.3 V`) are both derived
  from `VBUS_PROT`, while diode mode needs `MODE ≤ 0.35 V`, i.e. `VBUS_PROT ≤ 0.35 V` — so
  **both** inputs are ≤ 0.35 V and the "higher input" the device passes cannot be 5 V. The
  undefined band `0.35 V < MODE < 1 V` (i.e. `VBUS_PROT` between 0.35 V and 1 V) also sits
  below the device's own 1.6 V minimum `VIN`, with `VIN1` ≤ 1 V there. Row 7 has both inputs
  at 0 V.
* **v1.3.8 for contrast:** with `MODE` on `+3.3 V`, rows 3 and 4 had `MODE` = 0 V / diode mode
  and the slot rail was the *higher* input = `5V_SYS` even on a 3.3 V-jumpered slot — the
  blocker described in §1a.
* **Fail-safe default is still +3.3 V**: a missing, forgotten or vibrated-out shunt always
  leaves the slot on the 3.3 V rail. The polarity is never inverted anywhere in the design.
* Datasheet basis (TPS2116, SLVSFG1A §7.3.1 truth table / §7.6.1): `MODE ≥ 1 V` ⇒ manual
  mode; in manual mode `OUT` connects to `VIN1` if `PR1 > VREF` and to `VIN2` if
  `PR1 < VREF`; `MODE ≤ 0.35 V` with `PR1` high puts both channels off (`Hi-Z`), and with
  `PR1` low passes the higher input.
* **Input assignment**: `VIN1 = 5V_SYS`, `VIN2 = +3.3 V`. The original brief wrote
  `VIN1 = +3.3V, VIN2 = 5V_SYS` together with "shunt ⇒ 5 V"; with every assemblable
  manual-select mux *select high selects IN1*, so those two statements cannot both hold.
  The mandated, safety-critical part is the jumper polarity, so the input labels were swapped
  instead. Externally the behaviour is exactly as specified.
* **Current path**: slot power flows `IN1/IN2 → OUT` **through the mux only**. The header
  carries the µA select level (`pin 1` = `VBUS_PROT` reference since v1.3.9, `pin 2` =
  `SEL_n`) and nothing else — verified in §5/§8.
* Manual mode means there is **no automatic fallback**: if the selected rail disappears the
  slot rail is simply that rail (3.3 V or 5 V); it never silently switches to the other one.

## 3. Protection hierarchy and the four closed decisions

### 3.1 Fuse hierarchy (decision P3 = accepted and implemented)

| Element | Rating | Protects |
|---|---|---|
| **F1** (input, in series with VBUS) | PPTC **2 A hold / 4 A trip / 16 V** | the USB source + the input wiring + the whole `VBUS_PROT` node |
| **F2** (5 V branch) | PPTC **1.1 A hold / 2.2 A trip / 16 V** | the `5V_SYS` branch |
| U5 AP2112K | internal current limit + thermal shutdown | the 3.3 V branch |
| U6…U17 ILIM | 667 mA nominal per slot (see 3.3) — **v1.3.8: removed; accepted by the owner, see §1a** | each slot's wiring and module |

Because F1 > F2, a 5 V-branch fault is *the more likely* to open F2 first and leave the 3.3 V
rail alive. Note that this is a PPTC hierarchy, not a coordinated fuse/breaker scheme: PPTC
trip times depend strongly on ambient temperature and overload current, so the ordering is a
design intent rather than a guaranteed discrimination.

### 3.2 Over-voltage protection (decision P1b = accepted with a documented limitation)

`D2`/`D3` (SMAJ5.0A) clamp `VBUS_PROT` and `5V_SYS` against surges, but their peak-pulse
clamping voltage is **9.2 V — above the 6 V absolute maximum of the TPS2116 inputs
(VIN1/VIN2) and of the `MODE`/`PR1` control pins, and of U5 (through FB1)**. This is
accepted knowingly since v1.3.0:

> **Accepted limitation:** during a surge, `VBUS_PROT` (and therefore both downstream
> branches) can transiently exceed the 6 V absolute maximum of the TPS2116 inputs and of
> U5. **Since v1.3.9 the `MODE` and `PR1` control pins are tied to `VBUS_PROT` as well**, so
> they join this exposure — they share the same `−0.3…6 V` rating (§6.1 of SLVSFG1A). A
> series resistor or a divider does **not** remove it (no current flows in a control pin
> during a DC surge, so there is no drop to trade); only a clamp or a rated switch would.
> **No rated OVP switch is fitted in v1.3.9.** Bulk capacitance and the PPTCs do not
> remove this exposure; they only reduce its duration/energy. This is a field-surge/ESD
> robustness limitation, not a continuous-operation limit (the rails are 3.3 V / 5 V).

*Future option (documented, not implemented):* if the application ever needs the rail to stay
inside 6 V under surge, the planned mitigation is a **rated OVP switch in series with
`VBUS_PROT`, upstream of both `FB1 → U5` and `F2 → 5V_SYS`** (integrated OVP/eFuse in the
TPS1663 class, or a controller + P-FET), ≈ $0.6–1.5 + ~4 passives. The part, price, cutoff
tolerance and transient overshoot must be verified against the datasheet before adoption, and
a series switch does **not** by itself establish F1/F2 coordination.

### 3.3 Per-slot current limit (decision P2b = implemented in v1.3.0–v1.3.7; **removed in v1.3.8, accepted**)

> **Not in the current schematic.** `R28/R30/…/R50` (750 Ω) and the 667 mA per-slot limit
> were removed with the `TPS2116DRLR` swap (v1.3.8) and the **owner accepts the gap for this
> revision** (§1a, *Consequence 2*). The text below is the v1.3.0–v1.3.7 rationale and still
> describes the released, frozen board.

`R_ILIM = 750 Ω` → **I_LIM ≈ 667 mA nominal** (`I = 500 / R` for TPS2111A), which sits inside
the datasheet's **guaranteed current-limit adjustment range of 0.63–1.25 A**. A specified,
weaker limit was chosen over an unguaranteed tighter one: the previous candidate value
(1.6 kΩ → ~312 mA) lies *below* the recommended minimum, where the datasheet does not
guarantee accuracy and the real limit could be materially lower (nuisance-tripping a heavy
module) or higher (failing to protect). 667 mA still bounds a slot fault well below the 5 V
branch fuse and the mux's own 1.25 A capability.

If a tighter per-slot limit is ever required, the part to use is **TPS2114A**
(guaranteed range 0.31–0.75 A) — note that even that only makes ≈310 mA of the originally
requested 250–300 mA band an in-range setting, and it currently has **0** JLCPCB stock.

## 4. Verification evidence

* **ERC (KiCad 9 CLI), before vs after, both run inside the project directory:**

  | finding | v1.2.0 (before) | v1.3.0 (after) |
  |---|---|---|
  | `error pin_not_connected` (J2/J4 unused jack pins) | 4 | 4 |
  | `error power_pin_not_driven` (#PWR02, #PWR025, U5.VIN) | 3 | 3 |
  | `warning lib_symbol_mismatch` (D1) | 1 | 1 |
  | **total** | **8** | **8** |

  The finding multisets are **identical** — v1.3.0 introduces no new ERC finding (the
  `BreadModular_PowerMux` symbol library added in this revision also removes the 12
  "library not found" warnings the interim build had).

* **Netlist acceptance script over the `kicad-cli`-exported netlist: 299 / 299 assertions
  pass**, including per slot: `VSLOT_n` = mux `OUT` + all five `VSUPPLY_n` pins + its own two
  caps and no other slot; `SEL_n` = exactly {mux D1, header pin 2, pulldown top}; pulldown
  bottom on GND; mux `D0` on GND (manual mode); **each header appears on exactly two nets
  (`SEL_n`, `+3.3V`) — proof that no slot current flows through the header**; `5V_SYS` =
  F2/D3/C46/C47/PWR_FLAG + 12 × IN1; `+3.3V` keeps 12 × IN2 + 12 × header pin 1;
  `VBUS_IN → F1 → VBUS_PROT → FB1 → U5` chain intact; no rail-to-rail shorts.
* **Footprints**: every board symbol has a footprint assigned. The only symbols without one
  are the three DNP simulation resistors R11/R22/R23 (`on_board no`, `dnp yes`, excluded from
  the BOM). All 22 distinct footprints resolve — ERC reports **0** `footprint_link_issues`
  (the project `fp-lib-table` and all seven project libraries resolve; the new parts use
  standard KiCad `Fuse`, `Diode_SMD`, `Package_SO`, `Connector_PinHeader_2.00mm`,
  `Resistor_SMD`, `Capacitor_SMD` libraries).
* **Layout**: plotted to PDF/PNG and visually inspected; every block's interior is clear of
  pre-existing drawing elements and the field-text collisions found that way were fixed.

## 5. Parts, part numbers and sourcing close-out

All values/MPNs are as they appear in the schematic; prices are the JLCPCB 100-piece band and
stock is from the live JLCPCB parts library at the time of writing.

### 5.1 New in v1.3.0

| Ref | Part | Value / spec | Package | LCSC | Stock | Lib | ≈ $ /100 |
|---|---|---|---|---|---|---|---|
| U6…U17 | TPS2111APWR | 2:1 mux, manual select, ILIM, reverse + cross-conduction blocking, 2.8–5.5 V, 84 mΩ | TSSOP-8 | **C471060** | 2 482 | extended | 1.38 |
| F1 | BSMD1812-200-16V | PPTC 2 A hold / 4 A trip / 16 V | 1812 | **C883156** | 59 730 | extended | 0.055 |
| F2 | MF-MSMF110/16-2 | PPTC 1.1 A hold / 2.2 A trip / 16 V | 1812 | **C210834** | 24 734 | extended | 0.066 |
| D2, D3 | SMAJ5.0A/TR13 | TVS 400 W unidirectional | SMA | **C78401** | 98 557 | extended | 0.044 |
| C46 | EMK325ABJ107MM-T | 100 µF 16 V X5R (brief asked ≥100 µF/10 V) | 1210 | **C394395** | 39 609 | extended | 0.52 |
| C47, C23…C45 (odd) | CL05B104KO5NNNC | 100 nF 16 V X7R | 0402 | **C1525** | 30 M+ | basic | 0.0045 |
| C22…C44 (even) | CL05A105KA5NQNC | 1 µF 25 V X5R | 0402 | **C52923** | 2.7 M | basic | 0.0099 |
| R28…R50 (even) | 0402WGF7500TCE | 750 Ω 1 % (ILIM, ≈667 mA) | 0402 | **C25132** | 168 756 | extended | 0.0015 |
| R29…R51 (odd) | 0402WGF1003TCE | 100 kΩ 1 % (SEL pulldown) | 0402 | **C25741** | 3 M | basic | 0.0025 |
| J7…J18 | PZ200-1-02-Z | 1×02 2.00 mm vertical header, 2.8 mm body | THT 2.00 mm | **C2905948** | 2 441 | extended | 0.024 |

**Mux availability (explicit):** TPS2111APWR is an **extended** JLCPCB part, **2 482 in
stock** (≈ 206 boards at 12 pieces each) at ≈ **$1.38 / 100**. There is **no stocked
pin-compatible alternative**: `TPS2111APWRG4` is 0 stock, `TPS2110A`/`TPS2114A` (the
0.31–0.75 A-limit versions) are 0 stock, and `TPS2115ADRBR` (636 in stock) is manual-select
but a different package (SON-8) with a 0.63–1.25 A range. If this design goes to volume,
either pre-order the mux or plan a layout revision for the SON-8 part.

> **Superseded by §1a (v1.3.8, schematic only):** the twelve channels are now
> `TPS2116DRLR` (C3235557, SOT-583, 48 871 in stock, $0.2052 @500-999), which is the
> cheapest option found in the JLCPCB library — see §1a for the pin map, the two
> accepted consequences and the Phase 2 checklist. The table rows above still describe
> the **released v1.3.7 board**, which is what the fab payloads contain.

**Jumper shunts are not on the assembly BOM on purpose** — they are fitted/removed per slot
by the user, and they must not be pre-fitted (a pre-fitted shunt would force 5 V). They are
still a sourced, purchasable accessory: **LCSC `C5664`** — "2.0 short circuit cap", P = 2.00 mm,
1.5 A, open-top unshrouded shunt, matching the 1.5 A header (C2905948); **126 449 in stock,
$0.012 each**. Order 12 (one per slot) plus spares as a separate line item; a 2.54 mm shunt
will **not** fit the 2.00 mm header.

### 5.2 Sourcing close-out (was 13 `TO-VERIFY` lines — now **0**)

| Ref | Previously | Now | Verified as |
|---|---|---|---|
| 5V14 | TO-VERIFY | **C2894966** | PZ254-2-05-Z-8.5, 1×2×05 2.54 mm socket, stock 23 016 |
| INPUT1, GND1…GND12, VSUPPLY_1…VSUPPLY_12 (25 refs) | TO-VERIFY | **C2894928** | PZ254-1-05-Z-8.5, 1×05 2.54 mm socket, stock 3 591. `INPUT1`'s return pins 3/4/5 are grounded through `R57` (100 Ω 0402, `C25076`) — §10.1 |
| C2 (1 µF 0805) | TO-VERIFY | **C28323** | CL21B105KBFNNNE, 1 µF 50 V X7R 0805, basic, stock 3.1 M |
| C16 (220 nF 0402) | TO-VERIFY | **C16772** | CL05B224KO5NNNC, 220 nF 16 V X7R 0402, basic, stock 2.9 M |
| FB1, FB2 | TO-VERIFY | **C12389** | *substituted* PZ2012D800-3R0TF — **80 Ω @100 MHz ±25 %, 3 A, 40 mΩ DCR, 0805** (330 104 in stock, $0.0223). The designed `GZ2012E800TF` is **not** in the JLCPCB library (exact-part search returns 0). This substitute keeps the **same impedance class (80 Ω) and the same 0805 land**; its current rating is *higher* (3 A vs the ~1 A class of the original) and its DCR *lower*, so the DC drop and the HF attenuation are unchanged or better. Same-family alternative if a 1 A part is preferred: **C316425 GZ2012D800TF** (80 Ω, 1 A, 100 mΩ, 1 236 stock). ⚠️ This is a **part-number substitution for a pre-existing v1.2.0 part** — flagged for your sign-off; the schematic Value/MPN were synchronised to the fitted part so BOM and schematic cannot disagree. |
| J5 | TO-VERIFY | **C165948** | TYPE-C-31-M-12 (HRO), USB-C 16P receptacle, stock 218 120 |
| SW1 | TO-VERIFY | **C92589** | K2-1808SN-A4SW-01, SMD tactile switch, stock 5 505 |
| R10, R12 (10 Ω 1206) | TO-VERIFY | **C17903** | 1206W4F100JT5E, 10 Ω 1 % 1206, basic, stock 1.1 M |

Still **`NOT-JLC`** (4 BOM lines, deliberately not JLCPCB-assembled, with concrete plans):

| Ref | Part | LCSC field | Plan |
|---|---|---|---|
| J1, J2, J4, J6 | QingPu WQP-PJ366ST 3.5 mm jacks | `NOT-JLC` | THT jacks — **hand solder**. Stocked alternate for a future BOM revision: PJ-320A, **C2884926** (12 055 stock, $0.115) — verify footprint/pinout against the QingPu part before substituting. |
| RV1, RV2 | RV09 body 50 kΩ pots | `NOT-JLC` | Every RV09 variant in the JLCPCB library shows **0 stock** — hand solder / consign. |

Mechanical note for Phase 2: the 24 slot sockets are the custom
`BreadModular_MISC:Power_Connector` footprint; the stocked socket part above is the LCSC
equivalent for the hand-solder BOM, and its stack height must be confirmed against the module
mating height before ordering.

## 6. Phase 2 (PCB) constraints — not applied yet

1. **Jumper placement**: J7…J18 must sit **underneath a mated module** (hidden when a module
   is fitted), **on/over the slot power rail area and close to it**, and **not in the gap
   between the ground socket and the power socket**. Choose the low-profile (2.00 mm) header
   height so the shunt clears the module underside; the user sets the shunt *before* mating a
   module.
2. **Protection parts**: D2, F1 on the VBUS path and F2/D3/C46 on `5V_SYS` should be placed
   close to J5 / the input node, with short, wide traces (they are drawn in a free area of
   the *schematic* purely for legibility).
3. The 12 mux channels and their decoupling should be placed near their slot sockets.
4. `base.kicad_pcb`, `production/netlist.ipc`, `designators.csv`, `positions.csv` and the
   fabrication zip are **unchanged** from v1.2.0 and must be regenerated after Phase 2
   (the toolkit flow: `kicad-cli sch export bom …` regenerates `production/bom.csv`, which
   *was* refreshed here for the new parts).
5. Unchanged observation: FB1/FB2 use the `Capacitor_SMD:C_0805_2012Metric` land pattern (a
   v1.2.0 choice); an `Inductor_SMD:L_0805_2012Metric` land would be the textbook choice for a
   bead. Left as-is to avoid churn; decide in Phase 2. The fitted bead's own land pattern
   (PZ2012D800-3R0TF) is the standard 0805 chip-bead footprint, which the C_0805 land
   approximates; confirm against the vendor drawing when the land is finalised in Phase 2.

## 7. KiCad gotchas found while generating this revision (keep in mind when hand-editing)

1. **Split wires at every junction.** A wire stub that ends on the *interior* of a long wire
   (even with a junction dot) is not reliably connected by `kicad-cli`; long wires must be
   split into separate segments at the junction points. All buses in v1.3.0 are generated
   that way. This bug silently disconnected F2's input pin in an earlier build.
2. **Field text angle is relative to the symbol.** A field stored with angle 0 on a symbol
   rotated 90° is *drawn* rotated; set the field angle to 90 to get horizontal text (and KiCad
   mirrors the justification when it normalises 180°).
3. **ERC must be run inside the project directory** (with the `.kicad_pro` present) or every
   project-library footprint reports `footprint_link_issues` — a false alarm when comparing
   before/after.

## 6. Revision note

v1.3.0 covers the **schematic and BOM only**: `base.kicad_pcb` is not yet updated, placement and
routing are a separate follow-up, so the new parts (U6..U17, F1, F2, D2, D3, C22..C47, J7..J18)
currently have no PCB placement, and `production/netlist.ipc`, `designators.csv` and the fab
outputs remain stale relative to the schematic until that follow-up is done.
The text-field cleanup done in this chat (ILIM 750 R / 667 mA, the TVS residual-risk wording, and
the simulation-only sourcing fields set to `N/A-SIM`) changed no `Value`/`LCSC`/`MPN` field of any
assembled part and no connectivity: the netlist `(nets ...)` section is byte-identical.


### 6.1 Routing status

Phase 2 PCB: all **78 new parts placed/routed**; F1/F2/TVS protection, 5V_SYS,
12 mux clusters, VSLOT_1…12 and logic-only J7…J18 are synchronized to the unchanged
schematic. All five supply pins per slot are on its VSLOT; removing the headers
in a test copy leaves power connected. Original hardware, 28 mounting holes,
223.52 × 160.02 mm outline and two copper layers are unchanged.

Jumpers sit **3.80 mm above the supply row**, outside the GND↔supply gap and inside
the measured 30.48 × 68.58 mm module shadows. **Height remains unverified:**
C2905948 is 2.0 mm body + 4.0 mm pin = **6.0 mm nominal**; 2.8 mm is its solder
tail. C2894928 is a **male header, not the specified female socket**. Need the actual
socket/mated gap and fitted C5664 height; target at least 0.5 mm clearance above
the worst-case assembly. Do not order/assemble until this is confirmed.

Widths: **1.2 mm input/5V trunks, 1.0 mm slot buses, 0.8 mm input branches,
0.25 mm short escapes/logic**, sized using 35 µm external copper / IPC-2221
10 °C rise (minimum 0.172 mm at 667 mA; 0.781 mm at 2 A). New returns join a
filled B.Cu GND plane. Final KiCad DRC: **0 errors, 0 unconnected, 0 parity issues**;
59 documented library-copy warnings remain (before: 110 warnings plus two excluded
USB pad-clearance errors). IPC, designators, full/SMD BOM+CPL and all fab ZIPs are
regenerated. **1713 invariant checks pass.** Plots, warning reasons, stack-height
hold, retained slot-1 alignment discrepancy and FB1/FB2 land verification are in
`verification/README.md`. This note alone is intentionally uncommitted.

---

## 8. v1.3.1 — one slot template, twelve instances (structure only)

v1.3.1 changes **how the same circuit is drawn**, not what it is. The twelve
identical per-slot power blocks that used to be flattened onto `base.kicad_sch`
are now a single hierarchical template sheet, **`slot.kicad_sch`**, instantiated
twelve times (`Slot1` … `Slot12`). No part was added, removed, re-valued or
re-sourced, and no electrical decision was reopened.

### 8.1 What one instance contains

| part | role in the slot |
|---|---|
| `VSUPPLY_n` — 1x05 socket | the selected slot rail, on all five pins (`VSLOT_n`) |
| `GND_n` — 1x05 socket | module ground, all five pins on `GND` |
| `U(5+n)` — TPS2111APWR | 2:1 power mux: `IN1 = 5V_SYS`, `IN2 = +3.3V`, `OUT = VSLOT_n`, `D0` strapped low, `D1 = SEL_n`, 667 mA ILIM **(released v1.3.7 board; the v1.3.8/v1.3.9 schematic uses TPS2116DRLR with `MODE`/`PR1` referenced to VBUS_PROT — §1a)** |
| `R(26+2n)` — 750R | ILIM resistor (per-slot current limit) |
| `R(27+2n)` — 100k | fail-safe SEL pulldown |
| `C(20+2n)`, `C(21+2n)` — 1uF + 0.1uF | slot rail decoupling |
| `J(6+n)` — 1x02 | rail-select header: shunt fitted = `5V_SYS`, open or lost = `+3.3V` |

### 8.2 Sheet interface

Only two nets are slot specific, so the template exposes exactly two sheet pins:

* **`VSLOT`** — `U(5+n).OUT`, both decoupling caps and all five `VSUPPLY_n` pins;
* **`SEL`** — `U(5+n).D1`, `J(6+n)` pin 2 and the 100k pulldown.

The parent sheet wires each sheet pin to a short stub carrying the existing
global labels `VSLOT_n` / `SEL_n`, so the flattened net names survive unchanged.
The rails `5V_SYS`, `+3.3V` and `GND` are still global labels / power symbols
*inside* the template — the same objects that were on the flat sheet.

### 8.3 Reference designators

Reference designators are annotated per sheet instance, so every part keeps the
reference it has on the flat v1.3.0 sheet:

| instance | mux | header | ILIM | pulldown | 1uF | 0.1uF | supply | ground |
|---|---|---|---|---|---|---|---|---|
| Slot1 | U6 | J7 | R28 | R29 | C22 | C23 | VSUPPLY_1 | GND1 |
| Slot2 | U7 | J8 | R30 | R31 | C24 | C25 | VSUPPLY_2 | GND2 |
| Slot3 | U8 | J9 | R32 | R33 | C26 | C27 | VSUPPLY_3 | GND3 |
| Slot4 | U9 | J10 | R34 | R35 | C28 | C29 | VSUPPLY_4 | GND4 |
| Slot5 | U10 | J11 | R36 | R37 | C30 | C31 | VSUPPLY_5 | GND5 |
| Slot6 | U11 | J12 | R38 | R39 | C32 | C33 | VSUPPLY_6 | GND6 |
| Slot7 | U12 | J13 | R40 | R41 | C34 | C35 | VSUPPLY_7 | GND7 |
| Slot8 | U13 | J14 | R42 | R43 | C36 | C37 | VSUPPLY_8 | GND8 |
| Slot9 | U14 | J15 | R44 | R45 | C38 | C39 | VSUPPLY_9 | GND9 |
| Slot10 | U15 | J16 | R46 | R47 | C40 | C41 | VSUPPLY_10 | GND10 |
| Slot11 | U16 | J17 | R48 | R49 | C42 | C43 | VSUPPLY_11 | GND11 |
| Slot12 | U17 | J18 | R50 | R51 | C44 | C45 | VSUPPLY_12 | GND12 |

### 8.4 How the refactor was produced and checked

`tools/build_slot_template.py` identifies the flat per-slot blocks by geometric
connectivity (each block is its own electrical island), removes them from
`base.kicad_sch`, emits `slot.kicad_sch`, and instantiates it twelve times in a
4 × 3 grid of sheet symbols. It refuses to run when a slot block cannot be
isolated, when a non-slot part would be swept into a slot island, when the
template's own geometry does not resolve to the intended per-slot netlist, or
when any copied part loses its DNP / BOM / board flag, source field or pin.
`tools/verify_slot_refactor.py` then compares the exported netlists (and rejects
empty or malformed exports instead of reporting them as equal):

* **78 nets** before and after — same names, same nodes, pin functions and pin types;
* **163 components** — identical references, values, footprints, datasheet,
  LCSC, MPN and manufacturer fields;
* **ERC unchanged**: 4 `pin_not_connected`, 3 `power_pin_not_driven` and
  1 `lib_symbol_mismatch` before and after;
* **`production/bom.csv` regenerates byte-identically**, the JLCPCB `bom.csv` and
  `positions.csv` regenerate identically, and re-exported Gerbers differ from the
  committed ZIP only in their internal creation-date comment.

The differences in the exported netlist *file* are bookkeeping only: the
`(design …)` section gains the twelve sub-sheet entries, and every relocated
component's `Sheetname` / `Sheetfile`, `sheetpath` and `tstamps` fields change to
its template instance, plus 48 `Description` texts that named their own slot and
are now instance-neutral (`Slot 4 rail decoupling` → `Slot rail decoupling`).
KiCad 9 has no per-instance symbol fields, so those texts cannot stay
slot-numbered in a shared template. No net, node, pin function or pin type
changed, and no field that reaches the BOM, CPL or board changed; §8.6 lists the
complete diff line by line.

### 8.5 PCB status (deliberately untouched)

`base.kicad_pcb` is **byte-identical** (sha256
`9fc20400ad6268ae35720c288995e211e4cbe28019649b2265d493139e2dc484`;
`git diff 5d0aca0..HEAD -- modules/base/base.kicad_pcb` is empty). The board was
routed against these nets, and because the netlist is unchanged it stays valid:
`kicad-cli pcb drc --schematic-parity` still reports **0 unconnected items and 0
schematic-parity findings** (59 unchanged library-copy warnings).

What does change is how the board's stored links map onto the schematic. Each
footprint records a single symbol UUID as its schematic link, and those links
were written against the flat sheet:

* the twelve slots are now served by one shared template symbol, so all twelve
  instances carry the same symbol UUID — the one the board knows for the slot-1
  parts;
* every relocated part also moved to a new hierarchical sheet path: the linkage
  string KiCad stores is `/<sheet-uuid>/<symbol-uuid>` — the sub-sheet's own UUID
  (e.g. `1559256d-…` for `Slot1`), then the symbol's UUID, not the root UUID plus
  the `SlotN` name. `modules/4mix` uses the same two-level form (`/40a9d1d3-…/<symbol-uuid>`).
  This includes the slot-1 parts whose symbol UUID was reused.

KiCad's parity check matches footprints to symbols by reference designator, which
is why it still reports zero findings. A future "update PCB from schematic" would
therefore have to re-link all **96 relocated slot parts** (U6..U17, J7..J18,
R28..R51, C22..C45, VSUPPLY_1..12, GND1..12) deliberately — it is not a no-op
action. Nothing in v1.3.1 requires it; the routed board remains the deliverable.

### 8.6 Netlist diff evidence (appended after the v1.3.1 commit — left uncommitted)

Committed as `a32b20e` plus two review follow-up commits on this branch.
`kicad-cli sch export netlist --format kicadsexpr` before
(`verification/netlist-before.kicadsexpr`, v1.3.0 HEAD) and after
(`verification/netlist-after.kicadsexpr`, v1.3.1) compares as follows:

| section | before → after | result |
|---|---|---|
| `(nets …)` | 592 → 592 lines | **byte-identical** — the same 78 nets, 513 nodes, names, pin functions and pin types |
| `(libparts …)`, `(libraries …)` | 320 / 19 lines | byte-identical |
| `(design …)` | 20 → 212 lines | +12 sub-sheet entries (`Slot1` … `Slot12`) |
| `(components …)` | 163 refs → 163 refs | same refs; values, footprints, datasheet, LCSC, MPN, manufacturer: **0 differences** |

`diff` reports 3571 changed lines and every one of them is one of:

1. component order inside `components` (the slot parts are now listed under their
   sheet instead of inline in the root list);
2. `Sheetname` / `Sheetfile` (96 lines each) and `sheetpath` (96 lines) — inherent
   to moving the parts into sub-sheets;
3. the per-component `tstamps` symbol UUID (96 lines): the twelve instances share
   the template symbol, so slots 2…12 now carry the symbol UUID that the routed
   board knows for slot 1 (see 8.5);
4. 48 free-text `Description` texts, now instance-neutral.

Nothing else moved: no net, node, pin function, pin type, reference, value,
footprint, LCSC number or MPN. ERC (`--severity-all`) has identical counts before
and after (4 `pin_not_connected`, 3 `power_pin_not_driven`,
1 `lib_symbol_mismatch`); the `GND` `power_pin_not_driven` is now attributed to
`#PWR026` instead of `#PWR02`, a GND symbol that moved into the template.

Reproduce:

```sh
cd modules/base
git show 5d0aca0:modules/base/base.kicad_sch > /tmp/pre.kicad_sch    # pre-refactor source
python3 tools/build_slot_template.py --source /tmp/pre.kicad_sch --dry-run
kicad-cli sch export netlist --format kicadsexpr -o /tmp/after.kicadsexpr base.kicad_sch
kicad-cli sch erc --format json --severity-all -o /tmp/after-erc.json base.kicad_sch
tools/verify_slot_refactor.py --before verification/netlist-before.kicadsexpr \
    --after /tmp/after.kicadsexpr \
    --erc-before verification/erc-before.json --erc-after /tmp/after-erc.json
git diff --stat 5d0aca0..HEAD -- base.kicad_pcb    # empty: board untouched (cwd = modules/base)
sha256sum base.kicad_pcb              # 9fc20400ad6268ae35720c288995e211e4cbe28019649b2265d493139e2dc484
kicad-cli pcb drc --format json --schematic-parity --severity-all \
    -o /tmp/drc.json base.kicad_pcb   # 0 unconnected items, 0 parity findings
kicad-cli sch export bom --fields 'Reference,Footprint,${QUANTITY},Value,LCSC' \
    --labels 'Designator,Footprint,Quantity,Value,LCSC Part #' \
    --group-by 'Footprint,Value,LCSC' --ref-range-delimiter '' --exclude-dnp \
    -o /tmp/bom.csv base.kicad_sch && diff /tmp/bom.csv production/bom.csv
# v1.3.2: the only expected difference is the hand-solder override
# (production/hand-solder.json -> NOT-JLC on the socket rows); see POWER.md section 9.
```

`verification/netlist-after.kicadsexpr` is that same fresh export, kept as the
checked-in after-state **of the v1.3.1 refactor**. v1.3.2 did not touch the
schematic, so this pair and the tool are still current and still reproduce
*identical*; only the 48 instance-neutral `Description` texts and the sheet
metadata differ between the two files. The verifier rejects empty, truncated or
unbalanced exports (exit 2) instead of reporting them as equal, and the
comparison is order-insensitive (re-ordering the component blocks still reports
IDENTICAL).

---

## 9. v1.3.2 — fab-ready hand-solder lines and a calculated stack height

v1.3.2 is a **release/documentation/packaging** revision. No net, part, value,
footprint, reference designator or copper feature changed, and
`base.kicad_pcb` stays byte-identical
(`9fc20400ad6268ae35720c288995e211e4cbe28019649b2265d493139e2dc484`).

### 9.1 Scope correction: the sockets are the builder's, not JLCPCB's

The module sockets are **hand-soldered by the builder and never ordered from
JLCPCB**, so the connector gender of the base sockets is an assembly note, not an
ordering blocker. That is the whole reason behind lifting the v1.3.0/v1.3.1
"DO NOT ORDER" hold.

`jlcpcb/base/{bom.csv,positions.csv}` never contained a single through-hole
reference: `opt/kicad-jlcpcb/export.py` runs without `--include-through-hole`, so
every THT footprint is rejected with the reason *"Not an SMD footprint"*.
Counts are therefore **unchanged**: **119 SMD placements in 32 BOM rows**, out of
**163 board references**. The remaining **44** references split as:

| Group | Refs | Qty | Part to fit |
|---|---|---:|---|
| Per-slot rail socket | `VSUPPLY_1` … `VSUPPLY_12` | 12 | female 1x05 2.54 mm socket |
| Per-slot ground socket | `GND1` … `GND12` | 12 | female 1x05 2.54 mm socket |
| Auxiliary input socket | `INPUT1` | 1 | female 1x05 2.54 mm socket |
| Power-expansion socket | `5V14` (2x05) | 1 | female 2x05 2.54 mm socket |
| Rail-select jumper | `J7` … `J18` | 12 | male 1x02 2.00 mm header (`C2905948`) |
| 3.5 mm audio jacks | `J1`, `J2`, `J4`, `J6` | 4 | `WQP-PJ366ST` |
| RV09 pots | `RV1`, `RV2` | 2 | `RV09-50K` |

The same file backs the sourced per-board component estimate in
`production/cost-estimate.json` (see `production/RELEASE_STATUS.md` section 5):
**119 SMD placements in 32 BOM rows**, and for a 50-board batch **$19.94/board of
JLCPCB-assembled parts plus $2.01/board of hand-solder board parts = $21.96/board**,
dominated by the twelve TPS2111APWRs at ≈$16.45/board (the 12 shunts are a
separate $0.12/board accessory order). That subtotal covers **154 of the 163
designators**; the nine it cannot price (5V14, the four jacks, the two pots,
FB1/FB2) are listed explicitly by reference in the file.

> **v1.3.8 (schematic only, §1a):** with the twelve channels on `TPS2116DRLR`
> (C3235557, $0.2052 @500-999) and the ILIM resistors deleted, that line item becomes
> 12 × $0.2052 = **$2.46/board** instead of ≈$16.45/board — **≈$13.10/board cheaper**
> (≈$655 on a 50-board batch), plus 12 fewer placements. `production/cost-estimate.json`
> is still the released v1.3.7 estimate and must be regenerated in Phase 2.

### 9.2 Why the base sockets must be female

The module PCBs carry their power and ground connection as a **male** 1x05
2.54 mm through-hole header with the value `Conn_01x05_Pin`. Of the 28 module
PCBs in the repository, 27 were inspected and **25 mount that header on the
bottom side** (`B.Cu`), so its mating pins point down at the base:
16bit, 16bit+, 8bit, ar_env, blank, cv_math, drive, env, head_out, hihat, jacks,
jvca, kick, line_in, line_out, low, mcc, mco, midi, noise, pots, svf, usb_power,
v2ca and wave. `tools/verify_stack_height.py` records the exact coverage in
`verification/stack-height.json`: **28 module PCBs exist, 27 were inspected**
(`modules/32bit/32bit.kicad_pcb` cannot be loaded standalone by `pcbnew`), and
**25 of them mount that male header on the bottom side**. The other two — **4mix
and imix** — mount the same male header on `F.Cu` and therefore cannot mate
downwards as drawn (§9.6). Those **25 bottom-mounted male headers** are the
evidence that the base needs **female** sockets.

The legacy Phase-1 field `C2894928 / PZ254-1-05-Z-8.5` is a **male** 1x05 pin
header (HCTL, 2.5 mm insulator, 6 mm mating pin) and is wrong for every one of
those positions. It is **not** substituted in KiCad:

* the same `LCSC`/`MPN` text also lives on the routed `base.kicad_pcb` footprint
  fields, and `tools/verify_power.py` asserts schematic/PCB field parity;
* the routed board is pinned byte-identical for this release, so it may not be
  rewritten;
* deleting the parity check to allow the edit was rejected as weakening a guard.

Instead, `production/hand-solder.json` (hand-maintained, versioned, SHA-256
recorded in `production/manifest.json`) declares a per-reference BOM override
that `tools/regenerate_production.py` applies to the **generated**
`production/bom.csv`: the sockets read **`NOT-JLC`**, exactly like the jacks and
pots that already use that convention. `C2894928` and `C2894966` now appear
nowhere in the generated BOM. Every reference designator, value and footprint is
untouched and the schematic hash is unchanged.

### 9.3 Recommended hand-solder parts

* **Slot sockets — 25 per board (24 slot sockets + `INPUT1`) — `C2897368` /
  `PM254-1-05-Z-8.5` (HCTL)**, 1x05 2.54 mm female
  socket, straight pin, square holes, top entry, 3 A, 8.5 mm insulator, 11.7 mm
  overall (3.2 mm solder tail). LCSC drawing *2.54 single-row female header,
  straight pin, plastic height 8.5* (`PM254-1-N-Z-8.5-XX (L11.7)`) [source](https://www.lcsc.com/datasheet/C2897368.pdf).
  Stock 6 155, min. 5 pcs, $0.1168 @5+ / $0.0826 @150+ (2026-09-17) [source](https://www.lcsc.com/product-detail/Female-Headers_HCTL-PM254-1-05-Z-8-5_C2897368.html).
* **Shunt — `C5664` / "2.0 Short circuit cap" (BOOMELE)**, 2.00 mm open-top
  shunt, 1.5 A, **3.5 mm** tall × 4.0 mm long. Its drawing `LY-DLM201-2-021`
  rev A also offers 4.5 mm and 5.0 mm plastics heights in the same ordering code
  [source](https://www.lcsc.com/datasheet/C5664.pdf). Stock 126 400, min. 50 pcs,
  $0.0122 @50+ (2026-09-17) [source](https://www.lcsc.com/product-detail/Shunts-Jumpers_BOOMELE-Boom-Precision-Elec-C5664_C5664.html).
* **Power-expansion socket (`5V14`)** — a **straight** 2x05 2.54 mm female socket
  is required and **its part number was not selected in this pass**.
  `C2897425` / `PM254-2-05-W-8.5` is the **right-angle** (`W`) family member and
  must not be substituted for a top-entry socket.

### 9.4 Stack height, calculated from datasheet dimensions

Datum: the **base PCB top surface**. Solder tails are below the board and are
deliberately **not** counted as height (the jumper's 2.8 mm tail passes through
the 1.6 mm base PCB and protrudes 1.2 mm underneath).

| # | Feature | Height above the base top | Source |
|---|---|---:|---|
| 1 | Rail-select header `C2905948 / PZ200-1-02-Z` | insulator **2.0** + mating pin **4.0** = **6.0** | [source](https://jlcpcb.com/partdetail/HCTL-PZ200_1_02Z/C2905948) |
| 2 | Shunt `C5664` seated on (1) | 2.0 + **3.5** = 5.5 (below 1, so it does not extend the envelope) | [source](https://www.lcsc.com/datasheet/C5664.pdf) |
| 3 | **Jumper envelope** = max(1, 2) | **6.0** nominal / **6.6** worst case (X.X ±0.30 each) | |
| 4 | Recommended female socket `C2897368` | insulator **8.5** | [source](https://www.lcsc.com/datasheet/C2897368.pdf) |
| 5 | Module male header insulator (bottom mounted) | **+2.5** | [source](https://jlcpcb.com/partdetail/Hctl-PZ254_1_05_Z_85/C2894928) |
| 6 | **Module PCB underside** = (4) + (5) | **11.0** nominal / 10.4 worst case | |
| 7 | **Clearance (6) − (3)** | **5.0 mm** nominal / **3.8 mm** worst case | |

The target is **≥ 0.5 mm** above the worst-case fitted envelope, so the design
clears it by 3.3 mm of margin. Two independent lower bounds set the **minimum
socket insulator height**:

* **6.3 mm** so the socket swallows the module's worst-case 6.0 + 0.30 mm mating
  pin instead of letting it bottom out on the base PCB;
* **4.9 mm** so the module underside still clears the fitted jumper by 0.5 mm.

Because a part is bought by its nominal label and the drawing tolerance is
`X.X ±0.30`, the **assembly-note minimum to buy is a 6.6 mm-insulator socket**.
The recommended 8.5 mm part is 8.2 mm worst case, and it also covers the tallest
5.0 mm shunt option of the C5664 family: with the jumper's own tolerance applied
to the shunt side, the worst-case clearances are **3.5 mm → 3.8 mm,
4.5 mm → 3.3 mm, 5.0 mm → 2.8 mm**, all above the 0.5 mm target.

`tools/verify_stack_height.py` recomputes all of §9.4 from
`production/hand-solder.json` and refuses the release if any number disagrees or
if the clearance drops below the margin. It also transforms every module
footprint into base coordinates (module's leftmost physical ground pin onto the
base slot's leftmost ground pad) and proves that **no module bottom-side
footprint overlaps the jumper envelope in X/Y** on any of the twelve slots; the
nearest module-side body outline is 0.45 mm away in X/Y.

### 9.5 Reference designator map for the twelve slots

| Slot | Rail socket | Ground socket | Mux | ILIM | SEL | Jumper |
|---:|---|---|---|---|---|---|
| 1 | `VSUPPLY_1` | `GND1` | `U6` | `R28` | `R29` | `J7` |
| 2 | `VSUPPLY_2` | `GND2` | `U7` | `R30` | `R31` | `J8` |
| 3–11 | … | … | `U8`…`U16` | `R32`…`R48` | `R33`…`R49` | `J9`…`J17` |
| 12 | `VSUPPLY_12` | `GND12` | `U17` | `R50` | `R51` | `J18` |

### 9.6 Open assumptions

1. **No assembled stack has been measured.** §9.4 is a datasheet calculation; a
   mating trial of one base plus one module is still advised.
2. The module PCBs do not annotate a part number for their male headers. The
   assumed mechanical twin is `PZ254-1-05-Z-8.5` (2.5 mm insulator, 6.0 mm
   mating pin).
3. Header `C2905948` does not publish tolerances; the general `X.X ±0.30` of the
   C5664 / PM254 drawings is applied to every stacked dimension.
4. Slot 1's socket row is offset −0.12 mm in X / −0.10 mm in Y from the common
   module registration. Pre-existing, preserved (no copper change), to be
   re-checked in the mating trial.
5. **4mix and imix** place their power/ground male headers on `F.Cu`, where they
   cannot mate downwards with a base socket as drawn. This is a module-side
   finding, not a base defect; recording it here so it is not lost.
6. `modules/32bit/32bit.kicad_pcb` cannot be loaded standalone by `pcbnew` and
   was therefore skipped by the module inspection, and `line_in` carries only
   one of the two 1x05 power/ground connectors. Both are recorded in
   `verification/stack-height.json` (`coverage`, `exceptions`).
7. The socket drawings publish the **housing** height, not the internal contact
   depth. That the 8.5 mm housing accepts a 6.3 mm pin without bottoming out is
   an **assumption**, not a datasheet fact.
8. A top-mounted THT part's solder tail hangs below the module board. The check
   walks every top-side through-hole footprint on all 27 inspected modules
   (1 332 footprint-per-slot comparisons over 111 distinct parts) and applies the
   tail (±0.30) and module-board (±0.16) tolerances: the 1.4 mm nominal tail
   becomes 1.86 mm worst case, the nearest XY envelope gap to a jumper is
   0.45 mm, and **no** top-side THT envelope overlaps a jumper envelope anywhere.
   The 1.94 mm vertical figure is specific to the assumed 3.0 mm header tail — a
   different THT part could have a longer tail — so the module-side assembly
   should confirm tail lengths if the outlines ever get closer than 0.45 mm.
9. `tools/verify_power.py` refuses a **stale** `verification/stack-height.json`:
   the report carries SHA-256 fingerprints of the calculator itself,
   `hand-solder.json`, `fixed-geometry.json`, both schematics, the PCB, the
   independently enumerated module scope and all 27 readable module PCBs, and the
   guard is covered by `tools/verify_power.py --selftest` (9 cases: fresh report,
   changed board, changed specification, changed calculator, changed module PCB,
   dropped key, no fingerprints, uncovered module, removed module).

### 9.7 Reproduce

```sh
cd modules/base
/usr/bin/python3 tools/verify_power.py --report verification/connectivity.json   # 1718 assertions
/usr/bin/python3 tools/verify_stack_height.py --report verification/stack-height.json
/usr/bin/python3 tools/regenerate_production.py     # runs both above, then ERC/DRC/export
sha256sum base.kicad_pcb            # 9fc20400… (unchanged, copper pinned)
diff <(sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:+-]+//g' jlcpcb/gerber/base-F_Cu.gbr) \
     <(git show HEAD:modules/base/jlcpcb/gerber/base-F_Cu.gbr | sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:+-]+//g')
```

## 10. v1.3.10 — the loud-gain option is withdrawn, `INPUT1`'s return is grounded, `U3` says `TS922IDT`

Schematic-only; the full entry with the verification evidence is in `CHANGELOG` (1.3.10). The
routed `base.kicad_pcb` is still the pinned earlier revision, so all three items are Phase 2
PCB work — see §10.4 for the to-do list.

### 10.1 `INPUT1` pins 3/4/5 — the auxiliary socket's return — grounded through `R57`

`INPUT1` (`C2894928`, 1×05 2.54 mm socket) is the copy/tap input: pin 1 = `IN_L`, pin 2 =
`IN_R`. Pins 3/4/5 were tied only to each other — the floating net `Net-(INPUT1-Pin_3)`,
3 nodes, nothing else — and are now the socket's **return to `GND` through `R57` = 100 Ω 0402
(`C25076` / `0402WGF1000TCE`, UNI-ROYAL — the same part `R26` already uses, so no new BOM line
and no new sourcing: **761 000 in stock**, 62.5 mW, 50 V, ±1 %).**

| quantity | value | note |
|---|---|---|
| base input impedance, per channel | 667 kΩ | `R24`/`R5` 2 M ∥ `R17`/`R16` 1 M |
| return current at ±5 V on both channels | 15 µA | 2 × 5 V / 667 kΩ |
| return potential above `GND` | 1.5 mV = **−70 dB** | 15 µA × 100 Ω, against 5 V full scale |
| steady-state dissipation in `R57` | 0.23 nW | vs. the part's 62.5 mW / 25 mA / 2.5 V limits |
| fault current into the return at 5 V | 50 mA | 5 V / 100 Ω (unbounded at a 0 Ω tie) |
| loop current for 1 V of ground difference | 10 mA | 1 V / 100 Ω, i.e. an ESD/ground-loop limit |

100 Ω is the resistor tie the owner asked for: it bounds a fault or ESD strike into the return
and any ground loop between two patched-together mains-powered devices, at a **−70 dB** cost as
a signal reference. A hard 0 Ω tie was considered first and is marginally better as a
reference — it removes the 1.5 mV — but gives up all of that current limiting; if it is ever
preferred, a 0 Ω 0402 keeps it a real part and is a one-part change, not a re-route.
Netlist: `{INPUT1.3, INPUT1.4, INPUT1.5, R57.1}` on the return, `R57.2` on `GND`, nothing else
joining either net.

### 10.2 The loud-gain option (1.3.5 `J20`/`J21`, 1.3.7 `J24`/`U19`) is withdrawn

The loud state put the line amplifier's inverting node behind **1.68 MΩ** (`R19` 680 k + `R53`
1 M, `R18` + `R54` on the right) with an analog switch in that path, and both of its defects are
properties of that resistance, not of the switch alone:

* **DC offset.** Every leakage current at the node — switch off-state leakage, PCB leakage, and
  everything that grows with temperature — flows through the *whole* 1.68 MΩ and appears at the
  output as `I_leak × Rf`: 10 nA gives **17 mV** of offset, and leakage roughly doubles every
  10 °C. (The amplifier's own ±20 pA would be 34 nV in the same resistance; the switch dominates
  by five orders of magnitude.)
* **HF tilt.** The same resistance against the amplifier + switch + stray capacitance (a few pF)
  puts a pole at `f = 1/(2π · 1.68 MΩ · C)` ≈ **19 kHz** for 5 pF, ≈23 kHz for 4 pF — i.e.
  **2.4 … 3.3 dB of loss at 20 kHz** in the one state the option exists for.

Consequence in the schematic: `R53`, `R54`, `R56`, `C49`, `J24` and `U19` are **deleted**, the
`GAIN_SEL`/`LFB_B`/`RFB_B` nets are gone, and **`U4.2` is back on `LFB_A`** and **`U4.6` on
`RFB_A`** — the summing node carries only the 680 k feedback (`R19`/`R18`) and the 1 M input
resistor (`R17`/`R16`), so the single remaining state is
**`Rf`/`Rin` = 680 k / 1 M = 0.68 = −3.35 dB**, with no switch and no series element anywhere in
the feedback path. If the option returns in a later batch it should be **scaled ~10× down**
(`Rin` 100 k, `Rf` 68 k default / **168 k** loud — same 0.68 and 1.68 ratios, but a 168 kΩ loud
node: leakage-induced offset 10× smaller and the pole 10× higher, ≈190–250 kHz) or switched on
the **low-impedance input leg**; both are PCB changes as well.

**The mono selector is untouched and still ships fail-safe stereo.** `J23`, `U18`, `R55` (the
100 k `MONO_SEL` pulldown) and `C48` are exactly as in 1.3.7: shunt absent or lost = stereo;
shunt fitted = mono with `IN_R` discarded and the right line amplifier fed from `BUFF_IN_L`.
The 1.3.7 `J23`/`J24` assembly note now applies to `J23` only.

### 10.3 `U3` is a real `BreadModular_Analog:TS922IDT`, and the op-amps are on a plain SO-8

The 1.3.9-era swap left `TS922IDT` metadata on an `Amplifier_Operational:MCP6002-xSN` symbol and
all three op-amps on a `SOIC-8-1EP` footprint (an exposed pad the real parts do not have).

* **New project-local symbol `BreadModular_Analog:TS922IDT`** (new file
  `BreadModular_Analog.kicad_sym` + one `sym-lib-table` line), on **all three `U3` units**.
  Its pin-out is the TS922's SO-8 pin-out, which is also the MCP6002's (1 = OUT1, 2 = IN1−,
  3 = IN1+, 4 = V−, 5 = IN2+, 6 = IN2−, 7 = OUT2, 8 = V+), so connectivity is unchanged and the
  netlist just gains the right `libsource`: **`U3` = (`BreadModular_Analog`, `TS922IDT`)**,
  `C93687`, `MPN` `TS922IDT`, `Datasheet` = ST `ts922.pdf`. Still stocked: **54 286 in stock**,
  from $0.2101 @1+ (LCSC, 2026-09-18).
* **Footprint:** `U3` moves to `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`; `U2` and `U4` had the
  **same stale EP footprint** and were moved with it (all nine `U2`/`U3`/`U4` units). No
  behaviour change — the pin-out is identical; only the land pattern stops claiming pads that do
  not exist.
* The `Sim.*` fields inherited from the old symbol are the generic
  `kicad_builtin_opamp_dual` sub-circuit, not an MCP6002 model, and are unchanged.

### 10.4 Phase 2 (PCB) to-do after 1.3.10

1. **Nothing loud-gain is placed**: no `R53`/`R54`/`R56`/`C49`/`J24`/`U19` parts, and the
   board's `R53`/`R54` footprints and copper are deleted with this step.
2. **`R57`** (100 Ω 0402) is a new SMD placement at the `INPUT1` return, to be placed and routed
   with one stub onto the `INPUT1` pin-3/4/5 tie.
3. **`J23`/`U18`/`R55`/`C48`** — the mono selector, i.e. the 1.3.7 Phase-2 work, unchanged.
4. **`U2`/`U3`/`U4`** footprints → `SOIC-8_3.9x4.9mm_P1.27mm`; the exposed pad and its copper go
   away with them.
5. The earlier power items: the twelve `U6…U17` → `SOT-583-8` swap, the `R28/R30/…/R50`
   deletion, the twelve `J7…J18` pin-1 nets from `+3.3V` to `VBUS_PROT`, the `MODE`/`PR1` bench
   proof of §1a, then `kicad-cli pcb drc --schematic-parity`, `tools/verify_power.py` (drop the
   `PCB_PENDING` block), `tools/verify_stack_height.py` and `tools/regenerate_production.py`.
6. Re-baseline `verification/fixed-geometry.json` (both schematic hashes and the footprint/pad
   geometry) in the same reviewed commit — it still pins the pre-1.3.6 board, which is why
   `tools/verify_power.py` stops at `'ERC setup changed'` before it reaches any of the above.

## 11. v1.3.11 — minimal reset/power-off input-current limiting

`SW1` removes the base's 3.3 V supply, but a module with its own regulator on a
5 V slot can continue driving a **0–3.3 V** signal. U18's TS5A23157 analog pins do
not provide powered-off isolation. The parallel U2 buffer input was also connected
directly to the same external signal, so protecting only U18's pin 9 would leave
that other injection path intact.

The chosen compromise is **two series resistors, no new IC or diode network**:

```
INPUT1.1 / IN_L -- R58 10k -- IN_L_PROT -- U2.3, R24.1, R17.2
INPUT1.2 / IN_R -- R59 10k -- IN_R_PROT -- U2.5, R5.2, U18.9
```

The simulation sources V2/V3 stay on the raw `IN_L`/`IN_R` side, so they do not
bypass the new resistors. `BUFF_IN_L`, `BUFF_IN_R`, `RIN_SEL`, the U18 pin map,
J23's open=stereo / fitted=left-to-both-line-outputs behaviour, R55 and C48 are
unchanged. Headphones remain stereo. The two bias returns stay downstream of the
resistors so unpatched inputs retain their 1.65 V bias (legacy label `+2.5V`).

* **Parts:** R58/R59 use `C25744`, UNI-ROYAL `0402WGF1002TCE`, 10 kΩ ±1%, 62.5 mW,
  `Resistor_SMD:R_0402_1005Metric`. The part identity/rating is verified; no stock
  or price guarantee is implied. [source](https://jlcpcb.com/partdetail/26487-0402WGF1002TCE/C25744)
* **Current bound:** for a 3.3 V source and nonnegative receiving rail, ignoring
  clamp forward voltage gives `I <= 3.3 / 9900 = 0.334 mA` per channel, including
  the resistor's −1% tolerance. Both inputs together contribute at most about
  0.667 mA under these assumptions. This is shared among downstream paths, not
  that much current in each path. Worst-case resistor dissipation with the full
  3.3 V across it is about 1.10 mW.
* **Device basis:** TS5A23157 §6.1, note 3 permits exceeding its input/output
  voltage limits if clamp-current limits are observed; its analog-port clamp
  rating is ±50 mA. The series resistance greatly reduces stress but does not
  promise valid switch operation outside the normal supply range.
  [source](https://www.ti.com/lit/ds/symlink/ts5a23157.pdf)
* **Signal cost:** with a low-impedance source, a stiff 1.65 V bias and ideal
  buffers, `Rload = 2M || 1M = 666.7k`; the added low-frequency factor is
  `Rload / (Rload + 10k) = 0.9852`, or **−0.129 dB**. This applies to both channels
  in stereo and to the shared left source in mono. The unselected right input
  in mono sees essentially its 2 MΩ bias resistor, giving about −0.043 dB at its
  headphone buffer. No feedback/gain resistors were changed. These are calculated
  estimates, not measured frequency-response or distortion results.
* **Limits:** this is **current limiting, not power-off isolation**. Residual
  injection can raise the disabled supply; R27 and the bias divider provide a
  discharge load, but this change does not guarantee a zero-volt rail or reset
  timing. It is not protection for arbitrary bipolar/5 V signal faults, nor a
  qualified ESD/surge solution. Other ports are outside this change's scope.

Before release, bench-check reset/recovery with both inputs held at 3.3 V by a
still-powered module in both jumper states, then check audio level/response.
The PCB and production exports remain unchanged; the next PCB update must place
R58/R59 before the signal branches, without a raw-input bypass. The schematic-only
netlist/ERC regression procedure is in `verification/README.md`.
