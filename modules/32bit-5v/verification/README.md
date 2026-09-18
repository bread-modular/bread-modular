# `32bit-5v` verification artefacts

All commands were run from the repository root with **KiCad 10.0.6**
(`kicad-cli` 9.x cannot parse this board's KiCad 10 format).

The current module revision is **1.1.1** — a *schematic-only* regulator swap
(`AP7361C-33E-13` → `AP2112K-3.3`, the base module's part). `32bit-5v.kicad_pcb`
was deliberately **not** touched, so board artefacts (DRC, parity, CPL) still
belong to the 1.1.0 board and the schematic-vs-board parity check now reports the
expected `U5` mismatch until the owner's routing pass is done.

| File | Revision | What it is |
|---|---|---|
| `erc-32bit-baseline.json` | 1.1.0 | `kicad-cli sch erc --severity-all modules/32bit/32bit.kicad_sch` |
| `erc-32bit-5v.json` | **1.1.1** | same command on `modules/32bit-5v/32bit-5v.kicad_sch` (regenerated after the swap) |
| `drc-32bit-baseline.json` | 1.1.0 | `kicad-cli pcb drc --severity-all --schematic-parity modules/32bit/32bit.kicad_pcb` |
| `drc-32bit-5v.json` | 1.1.0 | same for the module board (board unchanged in 1.1.1) |
| `netlist-32bit-baseline.kicadsexpr` | 1.1.0 | `kicad-cli sch export netlist --format kicadsexpr modules/32bit/32bit.kicad_sch` |
| `netlist-32bit-5v-1.1.0.kicadsexpr` | 1.1.0 | the pre-swap module netlist (input to the swap proof) |
| `netlist-32bit-5v.kicadsexpr` | **1.1.1** | the current module netlist |
| `netlist-proof.json` | 1.1.0 | the original 15 acceptance checks (historical) |
| `netlist-proof-ldo-swap.json` | **1.1.1** | 19 acceptance checks for the regulator swap |
| `check_ldo_swap_netlist.py` | **1.1.1** | regenerates `netlist-proof-ldo-swap.json` (see below) |
| `ldo-BCu.png` | 1.1.0 | B.Cu plot of the **old** (SOT-223) regulator placement — stale by design |

## Result summary

| Check | Original `32bit` | `32bit-5v` 1.1.0 | `32bit-5v` 1.1.1 |
|---|---|---|---|
| ERC findings (`--severity-all`) | 55 (35 error / 20 warning) | 54 (34/20) | **54 (34/20) — no new finding, no new kind** |
| ERC `net_conflict` / shorted-net findings | 0 | **0** | **0** |
| DRC violations | 102 (2 error / 100 warning) | 105 (2/103) | not re-run (board untouched) |
| DRC unconnected items | 0 | **0** | board untouched |
| DRC schematic parity issues | 62 (all warning) | 4 (all warning) | **+1 expected `U5` mismatch** (SOT-223 on the board, SOT-23-5 in the schematic) |
| Netlist acceptance | — | 15/15 pass | **19/19 pass** |

The v1.1.0 DRC deltas are unchanged and are explained in `POWER.md` §4 (three
`lib_footprint_mismatch` warnings on the new footprints, four re-labelled
`silk_over_copper` entries on `V_SUPPLY1`, and the pre-existing J5 USB-C findings).
The v1.1.1 parity mismatch is the deliberate, owner-owned consequence of doing the
regulator swap in the schematic only.

## Netlist acceptance proof for the swap (`netlist-proof-ldo-swap.json`, 19/19 pass)

Reproduce with:

```
cd modules/32bit-5v
kicad-cli sch export netlist --format kicadsexpr -o /tmp/post.net 32bit-5v.kicad_sch
python3 verification/check_ldo_swap_netlist.py \
    verification/netlist-32bit-5v-1.1.0.kicadsexpr /tmp/post.net
```

What it checks:

* `+5V` = {`V_SUPPLY1`.1, .2, .3, .4, .5, `U5` VIN(1), `U5` EN(3), `C40`.1,
  `C42`.1} — and nothing else, so the 5V net is confined to the socket, the
  regulator's input **and enable** pins and its two input capacitors. Versus
  1.1.0 it gained exactly `U5`.EN(3) and `C42`.1.
* `+3V3` lost only `U5`.3 (the old `VO` pin) and gained only `U5`.5 (the new
  `VOUT` pin) — every load of 1.1.0 is still driven (`C6`, `C8`, `FB1`, `R10`,
  `R12`, `R15`, `R3`, `U3` pin 8, `C41`).
* `+3V3_ESP32` and `+3V3_8388` are node-for-node unchanged; `GND` gained only
  `C42`.2 and lost nothing.
* the string `AP7361C` appears nowhere in the netlist.
* `U5`'s Value / Footprint / Datasheet / Description / LCSC / MPN / Manufacturer
  are **identical to the base module's `U5`** (the check reads them straight out of
  `modules/base/base.kicad_sch`), so both boards order the same part.

## Regulator orientation (v1.1.0, for reference only — the board still shows this)

```
U5 origin (60.90, 57.60), layer B.Cu, orientation 180 deg
  pad 1  net=+5V   at=(64.05,55.30) size 2.0x1.5   <- IN, top of the lead column
  pad 2  net=GND   at=(64.05,57.60) size 2.0x1.5   <- GND lead (via inside)
  pad 2  net=GND   at=(57.75,57.60) size 2.0x3.8   <- exposed TAB = GND
  pad 3  net=+3V3  at=(64.05,59.90) size 2.0x1.5   <- OUT, bottom of the lead column
  GND vias inside the tab pad: (57.90,57.80) (57.90,58.60) (57.90,59.20), 0.6/0.3
  GND via in the GND lead pad: (64.05,57.60), 0.6/0.3  (also returns C40's ground)
  GND via for C41's ground:    (65.50,63.00), 0.6/0.3
  +3V3 regulator-output via:   (57.50,52.25), 0.5/0.3
  -- six vias, all of which the 1.1.1 hand-off removes together with the SOT-223
```

The v1.1.1 `U5` is a **SOT-23-5** (`VIN` 1, `GND` 2, `EN` 3, `NC` 4, `VOUT` 5) and
still has to be placed and routed by the owner — see `POWER.md` §6 for the hand-off
table.
