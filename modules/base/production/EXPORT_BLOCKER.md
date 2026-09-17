# Production export is blocked — the tracked outputs are still v1.3.2

`tools/regenerate_production.py` refuses to run, and it was **deliberately left
that way**: moving the pin would not make it produce valid exports. The tracked
`production/` and `jlcpcb/` outputs still describe the **v1.3.2** board, so they
predate 1.3.3 (680 k), 1.3.4 (`R25` removed, `R52` added, `R5`/`R24` to 2 M) and
1.3.5 (`R53`/`R54` + `J20`/`J21`). Read this file and
[`RELEASE_STATUS.md`](RELEASE_STATUS.md) before ordering anything.

Current state (branch tip `base-improvements`; the `R18`/`R19` field fix is commit
`d9991d9`, this document the commit after it — neither touches copper):

| file | SHA-256 | note |
|---|---|---|
| `../base.kicad_pcb` | `18823a8bab09c6af…` | 168 footprints, 0 unconnected |
| `../base.kicad_sch` | `b98bced23e106ae2…` | `VERSION` = 1.3.5 |
| pinned in `../verification/fixed-geometry.json` | `9fc20400ad6268ae…` | **the v1.3.2 board** |

## 1. What the pin protects

`verification/fixed-geometry.json` → `routed_pcb_sha256` freezes the routed
deliverable **byte-for-byte**. `regenerate_production.py` checks it first
(line 42) and aborts with

```
Refusing production export: base.kicad_pcb changed
(18823a8b… != pinned 9fc20400ad6268ae35720c288995e211e4cbe28019649b2265d493139e2dc484).
Copper must not move.
```

before it writes anything. `tools/verify_power.py:147` re-asserts the same hash
(and `verify_power.py:149` asserts the pin differs from the older
`pcb_sha256`), and the hash is echoed into `production/manifest.json` as
`routed_pcb_sha256_pinned`. The intent is simple: **the export must be made from
the exact board that was verified, and copper must not move between verification
and ordering.** The pin was set deliberately in `cd66a7b` / `183abf4` (both
carry the `9fc20400…` board) and has never been moved.

It is genuinely stale: five later commits touch `base.kicad_pcb` —
`fe218cf` (re-route), `1b9d03c` (5 V indicator), and then `466c7de`, `66518ff`
and `4d93a12`, which edit footprint/value/part fields. (`466c7de`, `66518ff`,
`4d93a12` and `fe218cf` also change `base.kicad_sch`.) So the pin is five
commits, and three value changes, behind — and it is the pin, not the copper,
that is out of date.

## 2. Why re-baselining the pin would **not** be enough

`regenerate_production.py` lines 56–59 run

```
kicad-cli pcb drc --format json --schematic-parity --severity-all -o … base.kicad_pcb
```

and then refuse if `unconnected_items` **or `schematic_parity`** is non-empty, or
if any violation has error severity. Under the toolchain installed here
(**KiCad 10.0.6**; it is the only `kicad-cli` on the machine, `dpkg` shows
`kicad 10.0.6~ubuntu26.04.1`) that gate cannot pass:

| board | 0 unconnected | schematic parity | violations |
|---|---|---|---|
| current (`18823a8b…`, + the part-number fix) | yes | **145** | 82, all warning |
| the pinned v1.3.2 board (`9fc20400…`) | yes | **158** | 61, all warning |

Every parity finding is `footprint_symbol_field_mismatch`. On the current board
all 145 are `Field 'Datasheet' differs (PCB: '~', Schematic: '')`; on the pinned
board 158 = 80 × `Datasheet` + 48 × `Description`. The checked-in
`verification/drc-after.json`, which records **0 parity findings**, was produced
by **KiCad 9.0.8** (`"kicad_version": "9.0.8"`) — the same version recorded in
`../jlcpcb/base/export-report.json`. The project's own `CHANGELOG` already says
so in the 1.3.3 section: *"the KiCad 10.0.6 baseline carries … 146
`Datasheet '~' vs ''` parity warnings that are also present on the unmodified
board; KiCad 9.0.8 recorded 0 parity items."*

So moving the pin would carry the script only as far as the DRC gate, where it
would abort — **unless the parity guard itself is weakened**. That guard is a
release gate; relaxing it in order to ship is exactly the move the pin exists to
prevent. (Note also that a run is not trivially reversible: it rewrites
`verification/stack-height.json`, `verification/connectivity.json`,
`verification/drc-after.json`, all of `production/`, `jlcpcb/base/` and
`jlcpcb/gerber/`, and only writes `manifest.json` at the very end.)

## 3. A second, independent pipeline break: the three solder jumpers

The script also assumes **every physical footprint is both on the BOM and in the
CPL**:

* line 108 — `bomrefs != refs` → `SystemExit('Production BOM differs')`
* line 101 — `{r['Ref'] for r in positions} != refs` → `fail('Production CPL /
  footprint reference mismatch')`

On the v1.3.2 board that held (163 = 163). On the current board it does not:
`J19`, `J20` and `J21` are bare-copper solder jumpers, deliberately carrying
`in_bom no` in the schematic and footprint attributes
`FP_EXCLUDE_FROM_BOM | FP_EXCLUDE_FROM_POS_FILES | FP_SMD` (`attr = 14`), so:

| set | refs |
|---|---|
| board footprints | **168** |
| `kicad-cli sch export bom` (− DNP) | **165** (missing `J19`, `J20`, `J21`) |
| `kicad-cli pcb export pos` (− DNP) | **165** (missing `J19`, `J20`, `J21`) |

Both invariants therefore fail today, independently of the pin and of the KiCad
version. The exporter is also called with `--require-part-numbers`, and the
jumpers have no LCSC/MPN, so where they end up in the JLCPCB assembly list is a
real (small) decision, not something to guess.

## 4. What is actually wrong with the tracked outputs

* `production/bom.csv` line 30 and `jlcpcb/base/bom.csv` row 24 still read
  `"R18,R19" … 330k … C23137` (row 25: `"R24,R25" … 10k … C25744`): these are the
  **v1.3.2** exports, made before the 1.3.3 value change, so they carry the 330 k
  value *and* the 330 k part. `production/cost-estimate.json` prices `C23137`.
  A fresh export of the current schematic would instead read `680k / C23137`,
  i.e. after 1.3.3 the value and the part number disagreed with each other —
  that part number is `C25822` in `base.kicad_sch` / `base.kicad_pcb` since
  commit `d9991d9`.
* They still list `R25` and `R5` = 1 M and are missing `R52`, `R53`, `R54` and
  `J20`/`J21`, and `R24` is still 10 k.
* `manifest.json` / `RELEASE_STATUS.md` still say `release_version 1.3.2`,
  163 references, 119 JLCPCB placements, 32 JLCPCB BOM rows.
* `RELEASE_STATUS.md` is the order-time document. It is **stale and must not be
  trusted** until the pipeline below is re-run.

## 5. Steps the owner must take before ordering

1. **Pick the release toolchain.** Either run the guarded pipeline on
   **KiCad 9.0.8** (the version that produced the v1.3.2 release and the only one
   that reports 0 parity findings), or — if KiCad 10 is to be the release
   toolchain — decide explicitly that symbol↔footprint `Datasheet`/`Description`
   differences are acceptable for this design, express that as a DRC
   severity/exclusion setting in `base.kicad_dru` / `base.kicad_pro`, and only
   then touch the pin. Do **not** edit the guard in
   `tools/regenerate_production.py` to get past it.
2. **Freeze the copper.** Re-run `kicad-cli pcb drc --schematic-parity` on the
   final board and confirm 0 unconnected items and no error-severity findings;
   then re-baseline `verification/fixed-geometry.json` (`pcb_sha256`,
   `routed_pcb_sha256`, `schematic_sha256`, `slot_schematic_sha256` and the
   per-footprint/pad geometry) in **one deliberate, reviewed commit**.
3. **Teach the pipeline about non-placed designators.** `J19`/`J20`/`J21` are
   excluded from the BOM and the position files by design; the `bomrefs == refs`
   and `pos refs == refs` invariants in `tools/regenerate_production.py` must be
   re-expressed as "physical ± non-placed" (and the JLCPCB exclusion list must
   stay equal to the hand-solder list + the three jumpers) before the export can
   run at all.
4. **Regenerate and verify**, then confirm by hand:
   * `production/bom.csv` contains `"R18,R19" …, 680k, C25822` and no `C23137`
     anywhere outside `verification/` history;
   * BOM ref set == CPL ref set == board refs − {`J19`,`J20`,`J21`};
   * `production/positions.csv` places 165 refs, `manifest.json` totals match,
     `release_version` = the current `VERSION` (1.3.5);
   * the gerber ZIPs under `production/`, `jlcpcb/base/` and
     `jlcpcb/production_files/` are identical;
   * `production/hand-solder.csv` still lists its 44 refs and
     `C2894928` / `C2894966` appear on no assembly line.
5. **Refresh the order-time docs** (`RELEASE_STATUS.md`, stock warnings,
   `cost-estimate.json --refresh`) — the component prices and stock figures
   there are a v1.3.2 snapshot.
6. Only then place the order, and still do the one-base-plus-one-module mating
   trial called out in section 6 of `RELEASE_STATUS.md`.

## 6. What was deliberately **not** changed here

* `verification/fixed-geometry.json` — pin untouched.
* `production/` and `jlcpcb/` outputs — untouched; no hand-editing of generated
  files (that would desynchronise them from `manifest.json` without being
  correct).
* No regeneration attempt past the guard; `tools/regenerate_production.py` was
  run once, read-only, to capture the exact refusal.
* `CHANGELOG` — untouched. Its 1.3.3 entry ("implemented … value properties
  only") is the origin of the stale `R18`/`R19` part number that was corrected in
  the preceding commit `d9991d9`.
