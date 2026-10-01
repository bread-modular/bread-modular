# BASE 1.3.13 — complete bounded candidate evidence, not bench/order approval

## Scope / prior versus current review

The complete **79-path Git binary delta** of independently verified 1.3.12 was
imported into isolated workspace 265 based on `base-improvements` at `ab9fd44`.
All 79 imported files matched the source candidate and initial `--verify-only`
passed before edits. `imported-candidate.json` preserves the complete path list,
file hashes, initial source/ZIP identity and pinned before-evidence hashes.
That production preparation did not edit the original checkout or workspace 261.
The complete **103-path** production commit `4384e9cec531b8a56ffa921c44883365403e113e`
has now been guardedly fast-forwarded into the original `base-improvements`
checkout, with all 103 file bytes/hashes and every manifest hash verified before
metadata publication. Workspace 265 is unchanged; workspace 261 was not touched.

Astra's **prior 1.3.12** copper/connectivity/fabrication checks passed, but assembly
was held for J5's mouth-based CPL datum. This **1.3.13** candidate addresses that
issue and the requested hand-solder notes, three local supply bypass caps and
J23 LINE mono silk. **Astra Max targeted 1.3.13 software/layout/export confirmation
is complete: PASS**, all four findings resolved, no remaining targeted defects,
in chat `fa1ba1b6-d28a-4178-bb09-cf6a42d01a68`. `astra-confirmation.json`
records the user-supplied completed read-only review, exact source/export hashes
and scope. No advisor/other model was invoked during integration. Vendor
placement-preview/polarity/library mapping and physical/bench signoffs remain
separately UNPERFORMED.

## Current evidence / independent gates

- `drc-after.json`: real saved/refilled KiCad CLI DRC, all severities/parity;
  **0 errors / 0 unrouted / 0 parity**, **70 visible library-copy warnings only**.
  No new rule/severity suppression; zero DRC exclusions; five inherited ignored
  checks remain unchanged. All silk/mask/courtyard/clearance
  findings from the local editing iterations were actually resolved.
- `erc-after.json`: real current **7 errors + 4 warnings**, unchanged UUID/type/
  severity identities, not zero ERC. `warnings.md` explicitly justifies each.
- `netlist-after.kicadsexpr`: fresh expanded hierarchical circuit netlist.
- `connectivity.json`: **4068 assertions, 160 physical refs, 515 physical pad-net
  assignments**; full hierarchy/native fields/flags/parity, all 12 selectors,
  R57/R58/R59, mono and six added bypass pins; no PCB_PENDING exemptions.
- `bounded-improvements.json`: all **523 old schematic pin memberships/types**,
  all 164 existing component metadata (except J5's two explicit XY fields), all
  **157 old pad/anchor sets and 1109 existing copper items preserved**. Exactly
  three supply capacitors, six new supply/GND pins, six tracks and three GND vias.
  Pin-8 tracks 2.582/1.888/1.625 mm; GND return tracks 0.40/0.72/0.80 mm.
- `improvements-before.xml`, `improvements-before-erc.json`,
  `improvements-before-geometry.json`, `improvements-before-copper.json`: immutable
  imported 1.3.12 comparison evidence, not freshly copied final geometry.
- `mechanical-invariants.json`: original ab9fd44 mechanical proof remains
  **byte-identical to imported candidate**: 114 input footprint/pad sets, outline
  and all 28 holes. `bounded-improvements.json` separately extends preservation
  to every one of the 157 finished candidate's old footprints. New capacitors
  are not hidden in the old input baseline.
- `fixed-geometry.json`: final geometry/source/project/rule hashes, refreshed only
  after actual DRC/parity and bounded circuit/mechanical proof.
- `baseline-refresh.json`: original input hashes, prior pins, final checks and
  explicit bounded capacitor additions. Not permission to repin an arbitrary PCB.
- `J5-assembly-datum.md/.json` + `J5-C165948-datasheet.pdf`: pinned HRO shell
  dimensions and fixed mouth registration independently justify nominal body
  board centre (34.515,46.990), CPL (4.035,130.810), unchanged 270° top. F.Fab
  body rectangle is new non-fabrication art; pads/holes/anchor never moved.
  Legacy 7.30 mm drawing versus current HRO 7.35 mm is explicitly explained.
- `assembly-orientation.json`: native anchors, independently documented assembly
  centres, pad nets/pin-1 coordinates and actual CPL angles for 115 SMD refs.
- `manufacturing-validation.json`: **160 physical /115 SMD /35 BOM rows /44 hand-
  solder /DNP J23**, source/part/MPN/reference/position/policy checks; 11 ZIP entries,
  exact copies/CRC and every Excellon feature/end-point checked.
- `stack-height.json`: fresh calculated report, 63 assertions, 5.0/3.8 mm nominal/
  worst-case clearance; 28 readable modules, 26 bottom-mounted, 4mix/imix top-
  mounted and line_in's single connector documented. Not a mating trial.
- `library-differences.json`, `library-copy-validation.json`: all 70 warning refs
  audited against actual installed library files. **67 match pad geometry**;
  J5 contact renumbering and INPUT1/5V14 annulus flags are preserved differences.
  C50-C52 copy C15 pads exactly; metadata/reference stroke differences remain
  visible warnings. Source and compared library-file hashes are recorded.
- `render-review.json`: 13 aspect-correct review images, physical crop/pixels/
  scales/hashes, real ZIP independently parsed with recorded parser notices.
- `astra-confirmation.json`: completed targeted Astra review attribution, frozen
  103-path source commit, exact hashes, findings/check summaries and real-world holds.
- `software-checks.json`, `release-hashes.json`: executed checks and exact source/
  synchronized export identities. `../production/manifest.json` pins all current
  sources/tools/evidence/exports/docs, with honest prior/current review status.

## Recheck from isolated repository root

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B modules/base/tools/verify_bounded_improvements.py
/usr/bin/python3 -B modules/base/tools/verify_power.py --selftest
KICAD_JLCPCB_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
/usr/bin/python3 -B -m unittest discover -s modules/base/tools -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/check_kicad_libraries.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 modules/base/tools/regenerate_production.py --verify-only
```

37 exporter unit/real-CLI tests and six independent body-datum mutation tests
pass. Datums cannot be "verified" by comparing arbitrary offsets/raw anchors
back to themselves; the release acceptance tests reject zero/NaN offset, moved
anchor, rotated part or changed F.Fab body art.

`--verify-only` rechecks live DRC/parity, power/stack, bounded old pin/ERC/copper
identity, independent documented J5 datum and every published manifest hash.
It uses temporary reports and does not rewrite sources or export payloads.
After deliberately refreshing evidence/docs, `--refresh-manifest-only` runs the
same current export/source checks and refreshes hashes without re-exporting.
A matching recorded confirmation remains PASS only for the pinned release,
source and export identities; absent/stale confirmation falls back to pending.
Only the software review flag changes; vendor/bench/mating/order flags stay false.
Rewriting source/geometry still requires freeze + every mandatory gate.

## Export / optional aspect-correct views

Standalone exporter remains stdlib + native KiCad CLI. It stages private project
copies, retains excluded-from-BOM XML metadata and honors explicit finite/conflict-
checked native assembly XY fields in the **exported X-right/Y-up board frame**.
They are not footprint-local, not rotated and not bottom-mirrored. See the
exporter README and J5 datum note; no guessed library correction database.

```sh
/usr/bin/python3 -m venv --system-site-packages /tmp/base-render-env
/tmp/base-render-env/bin/python -m pip install gerbonara
PYTHONDONTWRITEBYTECODE=1 /tmp/base-render-env/bin/python modules/base/tools/regenerate_production.py --render
```

Rendering dependencies are PyGObject/Rsvg/Pillow plus optional Gerbonara. No source
PCB is saved by plotting; temporary no-pours views only expose routing. SVG root
pixel width/height AND mm viewBox change together, with <0.1% X/Y scale mismatch.
The mirrored native back and independent Gerber bottom are underside views.
Current images include front/back/audio/slot/power/routing/Gerber/drills plus
**J5-assembly.png**, **bypass-supplies.png**, **J23-legend.png**. J5 crosshair/coordinate
annotations are review overlays, not fabrication silk. `whole-board.png` copies
front.png. Gerbonara parses all 9 actual ZIP layers, **438 PTH +2 NPTH** features,
223.57 ×160.07 mm outline stroke bounds. Two G90-after-header notices are recorded,
not hidden; Excellon geometry allows only half its 0.001 mm coordinate quantum.

## One-shot migration / freeze, never arbitrary hash updates

`finalize_pcb.py` is the historical 1.3.12 board migration from exact ab9fd44 PCB
and its then-unchanged circuit netlist, not a 1.3.13 circuit regeneration tool.
`apply_bounded_improvements.py` requires exact imported 1.3.12 source hashes and
adds only C50-C52, J5 metadata/body art and requested silk (plus U2 label clearance).
It cannot be reapplied to a finished candidate and is **not validation**.

After an explicitly approved edit and real checks, the bounded freeze command is:

```sh
git show ab9fd44:modules/base/base.kicad_pcb > /tmp/base-original.kicad_pcb
/usr/bin/python3 -B modules/base/tools/freeze_release.py --bounded-improvements --source-board /tmp/base-original.kicad_pcb
```

This mode first proves the live exact bounded delta against immutable imported
1.3.12 evidence, all original outline/hole/input mechanical invariants and full
native schematic/PCB metadata/pad parity, then runs real DRC/ERC before publishing
final pins. Original project/rules/slot hashes and severities stay unchanged.
Normal export never refreezes. Do not invent a new baseline to hide a regression.

## Protection/history / packaging

`verify_input_protection.py` remains the exact historical b0bb8e7→1.3.11/1.3.12
R58/R59 migration checker; it was rerun against the exact imported XML/ERC,
with private same-stem before files/libraries. Only R58/R59 were admitted, 523
pin assignments and 162 original component metadata preserved. Its old
`routing_reviewed:false` is intentional, not zero DRC/bench proof.
`input-protection-current.json` ties that rerun to the live bounded 1.3.13 proof
and current protection topology checks. Residual powered-off backfeed remains.

Other `*-before.*`, mux/template/header-removal reports, old helper migrations,
plugin database and production backups remain **historical**, not current release
instructions. Exact original POWER rationale remains unchanged in
`../POWER-HISTORICAL-pre-1.3.12.md`. Price/stock observations are stale.

`intended-paths.json` and `changed-files.txt` enumerate the **104-path complete
combined Git delta** from `ab9fd44`, including the new review record. The inventory
separately identifies the original **103-path production payload** at
`4384e9cec531b8a56ffa921c44883365403e113e` and the **10-path metadata-only
follow-up** on `base-improvements`; original inventory/content fingerprints are
retained. The manifest pins every affected document/tool and the new record.
No source, fabrication ZIP, BOM/CPL, render, manufacturing policy, unrelated
module or library was changed by the follow-up. Existing user files were
preserved; no workspace deletion, advisors, push or order. The final metadata
commit is identified by Git HEAD, avoiding recursive self-hashes.

**Residual holds:** JLCPCB library/portal placement preview, polarity and mapping;
bench reset/startup/load/audio/headphone checks; physical mating; current
quote/stock qualification — all UNPERFORMED. Software PASS is not ordering approval.
