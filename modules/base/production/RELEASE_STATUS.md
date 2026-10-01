# BASE 1.3.13 — bounded improvement candidate; NOT order authorization

## Review status and scope

Astra's completed **1.3.12** independent review passed copper/connectivity/
fabrication but placed assembly on **HOLD for J5's mouth-based CPL datum**.
This 1.3.13 candidate addresses the four requested issues; **focused independent
confirmation of these fixes is pending**. Only the requested worker was used,
with no advisors or other models. Work is isolated on workspace **265**, based
on `base-improvements` at `ab9fd44`, never editing original checkout or 261.
The complete independently round-tripped **79-path binary delta** was imported,
all 79 files matched the source candidate exactly and initial `--verify-only`
passed before edits. `../verification/imported-candidate.json` records that proof.

The only circuit additions are three populated 100 nF supply bypass capacitors:
**C50/U2, C51/U3, C52/U4**. Exact sourced C1525 / CL05B104KO5NNNC / Samsung / 0402
and native fields copied from C15. Their 2.582 / 1.888 / 1.625 mm pin-8 supply
tracks and 0.40 / 0.72 / 0.80 mm GND returns end at adjacent 0.4 mm drill vias.
C14/C15/C20 remain on the **+2.5V bias**, not repurposed. This is good local
bypassing practice, **not a fix for proven oscillation or bench-proven stability**.

- **J5**: HRO C165948 drawing supports 8.94 × 7.35 mm nominal shell centre.
  Body board datum **(34.515,46.990)**, assembly-only board-Cartesian XY fields
  **(+3.675,0) mm**, expected CPL **(4.035,130.810), 270°, top**. Anchor/pads/drills
  never move. F.Fab-only shell art documents this independently of the anchor.
  No guessed library rotation correction. `../verification/J5-assembly-datum.md`
  explains current drawing vs legacy 7.30 mm graphics and exact axes/tests.
- **Hand-solder instructions**: J7–J18.1 correctly **VBUS_PROT**; stereo-footprint
  output jacks and ground-only J2/J4 described accurately. Coverage derived from
  current stack report: **28 inspected / 26 bottom / 2 top (4mix/imix)**.
  Exclusions unchanged; historical price/stock observations explicitly stale.
- **J23 silk**: `J23 LINE MONO` / `OPEN=STEREO`; shunt fitted selects LINE mono
  through U18, not a blanket headphone-mono promise. DNP policy unchanged.

## Exact final source and export identity

| Path relative to `modules/base` | SHA-256 |
|---|---|
| `base.kicad_pcb` | `dae64cad273575d4709ee02587e594065267a2a7ad567d833ef9f52a0bb562d0` |
| `base.kicad_sch` | `672d7c896413578cf9a2b8afd7ecc9e3eb631a03e0b3a65efae2f4676fe817ab` |
| `slot.kicad_sch` | `76d098af20c61ec651943f95069bd292694ae9cb9cbfdf1ed3593b1eee8740b1` |

All three fabrication ZIP copies have SHA-256:
`3c7f69c2c7b750161fc85158ed65d419ccb4bab6caa4bb250927cd59229c645f`.
Source/export details are machine-readable in `../verification/release-hashes.json`
and `manifest.json`. Version and PCB silk are 1.3.13; slot/project/rules are
byte-identical to the reviewed authority. The complete original POWER rationale
is retained unchanged under `../POWER-HISTORICAL-pre-1.3.12.md`.

## Current upload set / actual derived counts

Only `../jlcpcb/base/base-gerbers.zip`, `bom.csv`, `positions.csv` in that directory
are the JLCPCB upload set. **115 populated SMD placements / 35 grouped BOM rows**.
ZIP: 9 Gerbers + separate PTH/NPTH Excellon; **438 PTH + 2 NPTH drill/slot features**.
`base.zip`, `../jlcpcb/production_files/GERBER-base.zip` and all loose Gerber/drill
files are byte-identical copies, not different revisions.

Production BOM/CPL/designators/assembly-policy inventory **160 physical refs =
115 SMD + 44 hand-solder + 1 DNP J23**, exactly THREE populated capacitors
more than 1.3.12. DNP remains physically accounted for, excluded from assembly.
The full physical CPL also uses J5's documented body datum; native anchors are
retained separately in geometry and orientation evidence. Legacy male socket
fields are not buying instructions: female sockets are builder-supplied and
explicitly NOT-JLC in the physical BOM. J23 is not added to the hand-solder list.
Old plugin `jlcpcb/project.db` and production backups are historical, not order data.

## Genuinely completed software checks

- Real saved/refilled KiCad CLI DRC with parity/all severities: **0 errors,
  0 unrouted, 0 parity**, **70 visible library-copy warnings only**.
  No severity suppression/exclusions. 67/70 installed pad sets match; J5
  contact renumbering and INPUT1/5V14 annulus flags remain intentional/preserved.
- Power verifier: **4068 assertions, 160 footprints, 515 physical pad-net
  assignments**, no PCB_PENDING. All owner power/input/audio decisions retained.
- Bounded delta proof: **all 523 old schematic pin memberships/types retained**,
  only six added supply/GND pins; all 164 old component metadata retained except
  J5's two deliberate native fields. **All 157 old pad/anchor sets, all 1109 old
  copper items, outline and all 28 mounting holes unchanged**.
- ERC identities unchanged: **7 errors + 4 warnings**, explicitly explained in
  `../verification/warnings.md`; not zero ERC.
- Stack: **63 assertions; 5.0 mm nominal / 3.8 mm calculated worst case**; nine
  freshness-mutation selftest cases PASS. Not a physical mating trial.
- Exporter: **37 unit + real CLI integration tests PASS**, including actual BASE
  J5/body-CPL and three-cap inventory. **Six independent datum mutation tests PASS**.
- Libraries: **47 projects / 7 libraries / 2914 loads / 528 custom references PASS**.
- Original R58/R59 protection verifier rerun: PASS to exact imported 1.3.12 XML;
  bounded live proof extends that unchanged input topology to 1.3.13. Current
  report distinguishes historical delta from current full-source validation.
- Exact BOM/CPL eligibility/parts/positions/policy/references, drills/slots, ZIP
  CRC/entries/copies/source hashes checked. **13 aspect-correct review renders**
  include new J5, bypass and J23 views; real ZIP independently parsed by Gerbonara.

## Residual release holds — not hidden by generated files

Targeted Astra confirmation, **JLCPCB library/portal placement preview**, bench
reset/startup/load/audio/headphone checks, physical socket/module/shunt mating,
current quote/stock qualification and order authorization are **unperformed**.
No push, merge or order. One complete package commit is authorized **only on the
isolated workspace branch**; the original base branch stays at ab9fd44.

Accepted limitations unchanged: no per-slot ILIM; shared rails/upstream limits;
TVS/surge qualification gap; residual powered-off backfeed with R58/R59; module
header PN/contact-depth assumptions; slot-1 offset preserved; 4mix/imix top-side
headers cannot mate downward as drawn; line_in has only one matching connector.
`cost-estimate.json` is explicitly **STALE**, not a current quote.

## Recheck

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 modules/base/tools/regenerate_production.py --verify-only
KICAD_JLCPCB_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
/usr/bin/python3 -B -m unittest discover -s modules/base/tools -p 'test_*.py' -v
```

`--refresh-manifest-only` revalidates exact current exports and updates final
published hashes after intentionally refreshed docs/evidence; it does not refill,
re-export or authorize ordering. `--verify-only` never regenerates payloads.
