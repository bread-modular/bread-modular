# BASE 1.3.14 — historical selector completion audit

**Superseded source/export hashes:** the subsequent footprint-library repair is
recorded in `../footprint-library/`. It resolved all 61 DRC library-copy warnings
without changing physical geometry, routing, placements or pin nets. Use its
summary for the current saved sources and JLCPCB export.

This folder preserves the earlier completed schematic/library repair snapshot.
Its `summary.json` binds that run's reports and artifacts to that run's source
hashes, not the current library-relinked sources. It is not manufacturing approval.

## Completed repairs

- All twelve instances now contain SW2–SW13, Q1–Q12, D4–D15 and R62–R73.
  Missing required symbol angles had made native KiCad silently omit the new
  symbols. Copied supply/LED labels were also wrong; these now match the PCB.
- Removed the old jumper's disconnected wire stubs, marked switch pin 1 as an
  intentional no-connect, corrected R29-group descriptions and replaced obsolete
  shunt notes. The new circuit drawing has been visually inspected.
- Registered the selector symbol/footprint libraries. The footprint contains no
  board-specific nets/path. Linked all 48 slot footprints to real symbol UUIDs so
  a future schematic-to-PCB update can identify the existing placements.
- The saved input still contained the old dangling +3.3V branch. Removed only
  this dead-end branch: 2 vias and 4 segments, listed exactly in `summary.json`.
  Refilled native zones; retained every one of the 201 footprint/pad/part/silk
  geometries, all other copper, outline, root schematic and project rules.
- The user's saved D16 orientation and R74 placement were preserved. Those two
  rows differ from the previous stale CPL; no placement was changed by this repair.

## Results and remaining findings

| Check | Result |
| --- | --- |
| Native hierarchical XML vs PCB | 201 physical refs, 636 exact ref/pin/net matches |
| Slot instances / repaired PCB links | 12 / 48 |
| DRC errors / unconnected / schematic parity | 0 / 0 / 0 |
| DRC warnings | 61 existing `lib_footprint_mismatch` warnings |
| ERC | 7 existing root-sheet errors + 4 existing library warnings |
| New ERC findings / selector-sheet ERC findings | 0 / 0 |
| JLCPCB BOM / CPL | 35 rows / 169 top-side placements, identical ref sets |
| Missing LCSC / schematic fallback warnings | 0 / 0 |
| Gerber archive / mirrors | 11 valid members; byte-identical mirrors |
| Native drill geometry vs exported drills | 520 PTH features (500 round, 20 slots), 28 NPTH |

Drill coordinates match within half the 0.001 mm export resolution; diameters and
feature multiplicities match. ERC errors are the existing J2/J4 unused pins and
power-driver findings; library warnings are retained, not hidden by changing rules.
See the full reports for identities and the older `../warnings.md` for historical
engineering context. This is deliberately **not described as ERC clean**.

## Evidence

- `summary.json`: source/artifact hashes, results, precise removed copper and limits.
- `native-netlist.xml`, `pin-net-parity.json`: all 636 compared physical pin nets;
  seven explicit off-board simulation components are recorded separately.
- `drc.json`, `erc.json`: final full native reports, all severities.
- `resume-baseline-drc.json`, `resume-baseline-erc.json`: actual saved input at resume,
  not an invented pre-migration baseline. Two old jumper-wire ERC warnings resolved.
- `slot-template.svg` / `.png`, `slot-12.svg`: actual native hierarchy renders.
- `export.log`: actual final export command, output and warnings.
- `jlcpcb-basic-parts.json`: earlier live JLCPCB sourcing evidence. C20917, C2286
  and C11702 were Basic; switch C431540 was Extended as explicitly allowed.
  No component substitutions occurred in this completion pass. Stock is not reserved.

The original routing-polish and LED-move before/after reports were unavailable.
The sibling folders contain current geometry/preservation evidence only, and do
not reconstruct earlier segment counts, module coverage or mechanical tests.

## Reproduce native checks safely

From the repository root, check private source copies rather than allow CLI
project caches to touch the working tree:

```sh
work=$(mktemp -d /tmp/base-selector-check.XXXXXX)
cp modules/base/*.kicad_* "$work/"
cp modules/base/fp-lib-table modules/base/sym-lib-table "$work/"
ln -s "$(realpath modules/base/footprints)" "$work/footprints"
kicad-cli sch export netlist --format kicadxml -o "$work/netlist.xml" "$work/base.kicad_sch"
kicad-cli sch erc --severity-all --format json -o "$work/erc.json" "$work/base.kicad_sch"
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --format json -o "$work/drc.json" "$work/base.kicad_pcb"
```

After reviewing/saving/refilling any changed PCB, regenerate the fabrication set:

```sh
python3 -B opt/kicad-tools/jlcpcb/add_production_files.py base
```

Upload `../../jlcpcb/base/base-gerbers.zip`, `bom.csv` and `positions.csv` from that
same directory. Review JLCPCB's package/polarity/placement preview, switch default
positions and the outstanding bench/mating checks before ordering. Nothing was
committed or ordered by this completion pass.
