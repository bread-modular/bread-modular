# `32bit-5v` verification artefacts

All commands were run from the repository root with **KiCad 10.0.6**
(`kicad-cli` 9.x cannot parse this board's KiCad 10 format).

| File | What it is |
|---|---|
| `erc-32bit-baseline.json` | `kicad-cli sch erc --severity-all modules/32bit/32bit.kicad_sch` |
| `erc-32bit-5v.json` | same for `modules/32bit-5v/32bit-5v.kicad_sch` |
| `drc-32bit-baseline.json` | `kicad-cli pcb drc --severity-all --schematic-parity modules/32bit/32bit.kicad_pcb` |
| `drc-32bit-5v.json` | same for `modules/32bit-5v/32bit-5v.kicad_pcb` |
| `netlist-32bit-baseline.kicadsexpr` | `kicad-cli sch export netlist --format kicadsexpr modules/32bit/32bit.kicad_sch` |
| `netlist-32bit-5v.kicadsexpr` | same for the new module |
| `netlist-proof.json` | machine-readable result of the 15 acceptance checks |

## Result summary

| Check | Original | `32bit-5v` |
|---|---|---|
| ERC findings | 55 (35 error / 20 warning) | 54 (34 error / 20 warning) — **no new finding**, one removed |
| ERC `net_conflict` / shorted-net findings | 0 | **0** |
| DRC violations | 102 (2 error / 100 warning) | 105 (2 error / 103 warning) |
| DRC unconnected items | 0 | **0** |
| DRC schematic parity issues | 62 (all warning) | 4 (all warning) |

The three extra DRC entries are `lib_footprint_mismatch` warnings on the three
new footprints (their bottom-side silkscreen was stripped and their fields hidden
so that the back side does not produce ~40 silkscreen/text findings); the same
warning class already fires on 53 of the pre-existing footprints. Four
`silk_over_copper` entries on `V_SUPPLY1`'s pads are the *same* pre-existing
findings, re-labelled from `+3V3` to `+5V`. The two DRC **errors** and the four
remaining parity `net_conflict`s are pre-existing (the J5 USB-C pad pair listed in
the project's DRC exclusions, and the four J5 B-side pads this symbol/footprint
pair has never had pins for).

## Netlist acceptance proof (`netlist-proof.json`, 15/15 pass)

* `+5V` (schematic **and** board) = {`V_SUPPLY1`.1, .2, .3, .4, .5, `U5`.1 (VI),
  `C40`.1} — and nothing else, so the 5V net is confined to the socket, the
  regulator input and its input capacitor.
* `+3V3` keeps every load the original rail drove (`C6`, `C8`, `FB1`, `R10`,
  `R12`, `R15`, `R3`, `U3` pin 8) and gained exactly `U5`.3 (VO) and `C41`.1.
  The five `V_SUPPLY1` pins are the only nodes that left it.
* `+3V3_ESP32` and `+3V3_8388` are byte-for-byte identical node sets.
* `GND` gained exactly `U5`.2, `C40`.2, `C41`.2 and lost nothing.

## Regulator orientation (independent of the netlist)

```
U5 origin (60.90, 57.60), layer B.Cu, orientation 180 deg
  pad 1  net=+5V   at=(64.05,55.30) size 2.0x1.5   <- IN, top of the lead column
  pad 2  net=GND   at=(64.05,57.60) size 2.0x1.5   <- GND lead (via inside)
  pad 2  net=GND   at=(57.75,57.60) size 2.0x3.8   <- exposed TAB = GND
  pad 3  net=+3V3  at=(64.05,59.90) size 2.0x1.5   <- OUT, bottom of the lead column
  GND vias inside the tab pad: (57.90,57.80) (57.90,58.60) (57.90,59.20), 0.6/0.3
  GND via in the GND lead pad: (64.05,57.60), 0.6/0.3  (also returns C40's ground)
  GND via for C41's ground:    (65.50,63.00), 0.6/0.3
  +3V3 regulator-output via:   (57.50,52.25), 0.5/0.3  (inside the In1 pour
                               keep-out under V_SUPPLY1, so it cannot short to
                               the In1 GND plane; it hands the rail to F.Cu and
                               to the In2.Cu distribution trunk)
  -- six new vias in total, all confirmed by a board-vs-board via set difference
```

So pin 1 (IN, +5V) is the top pad, pin 3 (OUT, +3V3) is the bottom pad, and the
exposed tab — pin 2 — is ground, carrying the three thermal vias into the
`In1.Cu` plane (confirmed visually on a B.Cu plot of the module).
