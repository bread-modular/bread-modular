# `32bit-5v` verification artefacts

> **Current authority:** the routed board at `74db23e` supersedes the old routing
> status below. [Basic/Economy sourcing evidence](basic-economy/README.md) contains
> the fresh baseline/final DRC/ERC, 222-pin/metadata/geometry proof and release HOLD.
> `final-drc.json`, `final-erc.json`, `final-netlist.xml` and `production/manifest.json`
> are regenerated from that reviewed native source. Lower sections retain historical
> schematic-only revision evidence, not current placement/parity claims.

Every artefact here was produced with **KiCad 10.0.6** (`kicad-cli` 9.x cannot parse
this board's KiCad 10 format). The reproduction commands in this file are run **from the
`modules/32bit-5v` directory** (they are shown in full below; nothing needs the
repository root).

The current module revision is **1.1.2** — a *schematic-only* trim of the ESP32 rail
(the five legacy 100uF bulk caps `C9`..`C13` removed, `C1` 0.1uF + `C2` 10uF kept).
1.1.1 was likewise schematic-only (the `AP7361C-33E-13` → `AP2112K-3.3` regulator
swap). `32bit-5v.kicad_pcb` has not been touched in either revision, so board
artefacts (DRC, parity, CPL) still belong to the 1.1.0 board. Schematic-vs-board parity
has **not been re-run** since then; the expected mismatch list is `U5` (wrong footprint),
`C42` (in the schematic, never placed), `C41` (net mismatch) and the five `C9`..`C13`
still on the board — see the parity row below, which distinguishes measurements from
expectations.

## Files

| File | Revision | What it is |
|---|---|---|
| `erc-32bit-baseline.json` | 1.1.0 | `kicad-cli sch erc --severity-all modules/32bit/32bit.kicad_sch` |
| `erc-32bit-5v-1.1.1-pre-1244ad0.json` | 1.1.1 shipped | the ERC report that was committed with the 1.1.1 revision (generated **before** commit `1244ad0` changed the schematic) — kept for the record |
| `erc-32bit-5v-1.1.1.json` | 1.1.1 source (`1244ad0`) | a fresh run against the source revision that 1.1.2 starts from: the **pre-trim** baseline of the trim diff |
| `erc-32bit-5v.json` | **1.1.2** | the current module ERC report |
| `drc-32bit-baseline.json` | 1.1.0 | `kicad-cli pcb drc --severity-all --schematic-parity modules/32bit/32bit.kicad_pcb` |
| `drc-32bit-5v.json` | 1.1.0 | same for the module board (board unchanged in 1.1.1 and 1.1.2) |
| `netlist-32bit-baseline.kicadsexpr` | 1.1.0 | `kicad-cli sch export netlist --format kicadsexpr modules/32bit/32bit.kicad_sch` |
| `netlist-32bit-5v-1.1.0.kicadsexpr` | 1.1.0 | chain start: the pre-swap module netlist |
| `netlist-32bit-5v-1.1.1-as-released.kicadsexpr` | 1.1.1 shipped (`4af97a8`) | the netlist that the 1.1.1 artefacts were built from |
| `netlist-32bit-5v-1.1.1.kicadsexpr` | 1.1.1 source (`1244ad0`) | the **pre-trim** netlist (input to the trim proof) |
| `netlist-32bit-5v.kicadsexpr` | **1.1.2** | the current module netlist |
| `netlist-proof.json` | 1.1.0 | the original 15 acceptance checks (historical) |
| `netlist-proof-ldo-swap.json` | 1.1.1 | **19/19** acceptance checks for the regulator swap (1.1.0 → 1.1.1-as-released) |
| `check_ldo_swap_netlist.py` | 1.1.1 | regenerates `netlist-proof-ldo-swap.json` |
| `proof-bulk-cap-trim.json` | **1.1.2** | **20/20** acceptance checks for the ESP32 bulk-cap trim, plus the 3-link chain from 1.1.0 |
| `check_bulk_cap_trim.py` | **1.1.2** | regenerates `proof-bulk-cap-trim.json` |
| `ldo-BCu.png` | 1.1.0 | B.Cu plot of the **old** (SOT-223) regulator placement — stale by design |

## Result summary

| Check | Original `32bit` | `32bit-5v` 1.1.0 | 1.1.1 shipped (`4af97a8`) | 1.1.1 source (`1244ad0`) | `32bit-5v` 1.1.2 |
|---|---|---|---|---|---|
| ERC findings (`--severity-all`) | 55 (35/20) | 54 (34/20) | 54 (34/20) | 56 (35/21) | **56 (35/21) — identical to the 1.1.1 source, finding for finding** |
| ERC `net_conflict` / shorted-net findings | 0 | 0 | 0 | 0 | **0** |
| DRC violations | 102 (2/100) | 105 (2/103) | not re-run (board untouched) | not re-run | not re-run (board untouched) |
| DRC unconnected items | 0 | 0 | board untouched | board untouched | board untouched |
| DRC schematic parity issues | 62 (warning) | 4 (warning) | **expected, not measured**: `U5` footprint mismatch + `C42` present in the schematic but absent from the board | **expected, not measured**: additionally the `C41` net differs (board `+3V3`, schematic floating) | **expected, not measured**: `U5` + `C42` + `C41` + the five `C9`..`C13` still on the board |
| Netlist acceptance | — | 15/15 | 19/19 (regulator swap) | *not reproducible — `C41`, see below* | **20/20 (bulk-cap trim)** |

Only the `32bit-5v` 1.1.0 parity figure (4 warnings, in `drc-32bit-5v.json`) is a
*measurement*. Parity has not been re-run since, so every later entry in that row is an
**expectation**, not a result — including the `C42` mismatch that v1.1.1 already
introduced and that the earlier revision notes did not list.

The ERC totals are quoted **normalised per finding** (severity + type + affected item
descriptions + item positions). The 54 → 56 step is *not* a v1.1.2 effect: it happened
in commit `1244ad0`, which changed the schematic without refreshing these artefacts. The
difference against the shipped report is exactly two findings, both `C41`:

```
+1 error    pin_not_connected          Symbol C41 Pin 1
+1 warning  unconnected_wire_endpoint  Vertical Wire, length 0.0254 mm
```

Comparing `erc-32bit-5v-1.1.1.json` against `erc-32bit-5v.json` (the trim pair) yields
**zero** differences, so v1.1.2 introduces no new and no changed finding.

## Pre-existing defect found while building the 1.1.2 fixtures: `C41` is disconnected

Commit `1244ad0` re-placed `C41` (22uF, the LDO output bulk) from (525.78, 29.21) to
(464.82, 33.02) and left its top stub — wire `(464.82, 29.21) → (464.82, 26.67)` —
ending in mid-air. The `+3V3` trunk it should meet stops at `x = 444.5`, and the nearest
`+3V3` copper is the horizontal run at `y = 24.13` from `U5` `VOUT` (459.74, 24.13) to
the `+3V3` power symbol (467.36, 24.13). Consequences in the fixtures:

* the netlist gains the auto-named net `unconnected-(C41-Pad1)`, and `+3V3` loses
  `('C41','1')` — this is why `check_ldo_swap_netlist.py` reports **16/19** (not 19/19)
  when it is re-run against the `1244ad0` source instead of the shipped
  `netlist-32bit-5v-1.1.1-as-released.kicadsexpr`;
* ERC gains the `pin_not_connected` error and the `unconnected_wire_endpoint` warning
  listed above.

**It is not fixed in v1.1.2** — it is a separate, pre-existing issue and the owner is
mid-flight in that schematic area. It is modelled as its own link in the chain proof
(so the history stays exact). The remediation is one wire `(464.82, 26.67) →
(464.82, 24.13)` plus a junction at (464.82, 24.13), written up in `POWER.md` §5 and §6
item 8, and it should be done **before board synchronisation or manufacture**: `C8`
10uF + `C6` 0.1uF keep the rail decoupled so the module is expected to run, but the
regulator is missing 22uF of its documented output bulk and that has not been validated.
Note that fixing `C41` does not make `check_ldo_swap_netlist.py` pass against a 1.1.2
netlist — that proof is bound to the frozen 1.1.0 → 1.1.1-as-released pair, and 1.1.2
also has `+3V3_ESP32` without `C9`..`C13`.

## Netlist acceptance proofs

### 1.1.1 regulator swap — `netlist-proof-ldo-swap.json` (19/19)

Reproduce from the frozen artefacts:

```
python3 verification/check_ldo_swap_netlist.py \
    verification/netlist-32bit-5v-1.1.0.kicadsexpr \
    verification/netlist-32bit-5v-1.1.1-as-released.kicadsexpr
```

(The pre/post argument is the **frozen netlist artefact** — do not feed it back through
`kicad-cli sch export netlist`, that command takes a schematic.)

It checks that `+5V` is confined to the socket, the regulator's VIN/EN and `C40`/`C42`;
that `+3V3` moved only the regulator's own pin (`VO` 3 → `VOUT` 5) and still drives
every 1.1.0 load; that `+3V3_ESP32`/`+3V3_8388` were untouched; that `GND` gained only
`C42`.2; that `AP7361C` appears nowhere; and that `U5`'s Value / Footprint / Datasheet /
Description / LCSC / MPN / Manufacturer are identical to the base module's `U5`.

### 1.1.2 bulk-cap trim — `proof-bulk-cap-trim.json` (20/20)

Reproduce with:

```
python3 verification/check_bulk_cap_trim.py \
    verification/netlist-32bit-5v-1.1.1.kicadsexpr \
    verification/netlist-32bit-5v.kicadsexpr \
    verification/erc-32bit-5v-1.1.1.json \
    verification/erc-32bit-5v.json \
    --v110 verification/netlist-32bit-5v-1.1.0.kicadsexpr \
    --v111rel verification/netlist-32bit-5v-1.1.1-as-released.kicadsexpr
```

What it checks:

* **component delta** — exactly five components removed, and they are `C9`..`C13`, all
  `100uf` on `Capacitor_SMD:C_1206_3216Metric`; nothing added; **every surviving
  component's value, footprint and fields are unchanged** (nothing else rode along);
* **net delta** — the net count is unchanged (77), and for *every* net the 1.1.2 node set
  equals the 1.1.1 set minus only the `C9`..`C13` pins. Only `+3V3_ESP32` and `GND`
  changed; `+3V3_ESP32` is exactly {`C1`.1, `C2`.1, `FB1`.1, `U1`.2}; `+3V3_8388`,
  `+3V3` and `+5V` are untouched;
* **ERC delta** — the normalised finding sets before and after are equal element for
  element, so "56 → 56" cannot hide a swapped finding;
* **chain** — each hop is applied to the previous hop's result and compared against that
  revision's frozen netlist:
  1.1.0 + regulator swap == 1.1.1-as-released;
  1.1.1-as-released + the `1244ad0` `C41` disconnect (the pre-existing defect, unchanged
  here) == 1.1.1 source;
  1.1.1 source + the trim == 1.1.2.

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
  -- six vias, all of which the hand-off removes together with the SOT-223
```

The v1.1.1 `U5` is a **SOT-23-5** (`VIN` 1, `GND` 2, `EN` 3, `NC` 4, `VOUT` 5) and
still has to be placed and routed by the owner — see `POWER.md` §6 for the hand-off
table, which in 1.1.2 also covers deleting the five `C9`..`C13` 1206 footprints and
placing `C1`/`C2` tight to `U1` pin 2.

The `production/` exports (`bom.csv`, `positions.csv`, `designators.csv`,
`netlist.ipc`, `32bit-5v.zip`) are still the 1.1.0 board's and must be regenerated after
the routing pass.
