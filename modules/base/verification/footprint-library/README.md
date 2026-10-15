# BASE 1.3.14 — footprint-library synchronization

This is the current source-bound check following the selector completion audit.
`summary.json` identifies the exact PCB, hierarchy, project rules, local libraries
and JLCPCB outputs. The older `../selectors/` evidence is retained as history.

## Repair

All 61 `lib_footprint_mismatch` warnings were traced to 14 footprint families.
The differences include older fab/courtyard primitives and model paths,
intentional silk-to-fab changes, J5's USB-C power-only pad numbering and shell
outline, and the saved socket annulus/courtyard definitions. Updating the board
wholesale from the generic library would discard some intentional modifications.

Instead, the existing variants are stored in the explicitly named project-local
`BreadModular_Base` library. Native KiCad compared all 61 repaired instances to
these 14 sanitized definitions. Only their PCB library IDs and the corresponding
schematic Footprint fields changed; every other board/schematic byte was proved
unchanged by reversing only those exact tokens. No part selections, footprints'
physical geometry, placements, pad nets, copper, zone fills or rules were changed.

`../../fp-lib-table` is now a regular project-local file. The shared
`opt/fp-lib-table` and all original shared/installed libraries were left intact,
so this repair does not change any other module. See
`../../local-footprints/README.md` for the variants and maintenance notes.

## Verified results

| Check | Result |
| --- | --- |
| DRC errors / warnings | 0 / 0 |
| Unconnected items / schematic parity | 0 / 0 |
| DRC with native in-memory zone refill | Also 0 / 0 / 0 / 0 |
| Exact physical ref/pin/net comparison | 636 matches across 201 components |
| Expanded schematic nets / part fields | Unchanged, except authorized Footprint IDs |
| ERC | Same 7 errors + 4 symbol-library warnings; no new findings |
| DRC/ERC ignores, exclusions and rules | Unchanged; not suppressed |
| BOM / CPL | 35 rows / 169 placements; both byte-identical to input |
| Gerber/drill members | All 11 identical except the two timestamp headers per file |
| ZIP/loose-file mirrors | Exact matches |

The unchanged ERC findings are described in `../warnings.md`. This is a clean
PCB DRC result, not a claim of zero schematic ERC or manufacturing approval.

## Evidence

- `summary.json`: source/output hashes, preservation and export-equivalence results.
- `reference-map.json`, `library-manifest.json`: all 61 old/new assignments and
  the 14 source-family differences. No board nets/procurement fields in the library.
- `drc.json`, `drc-refilled.json`, `erc.json`: full native reports, all severities.
- `before-drc.json`, `before-erc.json`: actual input reports, including the 61 warnings.
- `native-netlist.xml`, `before-native-netlist.xml`: native expanded hierarchy.
- `export.log`: the actual shared JLCPCB exporter command and output.

## Recheck without touching the working project

From the repository root:

```sh
work=$(mktemp -d /tmp/base-library-check.XXXXXX)
cp modules/base/*.kicad_* "$work/"
cp modules/base/fp-lib-table modules/base/sym-lib-table "$work/"
cp -a modules/base/local-footprints "$work/"
ln -s "$(realpath modules/base/footprints)" "$work/footprints"
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --format json -o "$work/drc.json" "$work/base.kicad_pcb"
kicad-cli sch erc --severity-all --format json -o "$work/erc.json" "$work/base.kicad_sch"
kicad-cli sch export netlist --format kicadxml -o "$work/netlist.xml" "$work/base.kicad_sch"
```

Current JLCPCB files remain `../../jlcpcb/base/base-gerbers.zip`, `bom.csv` and
`positions.csv`. Restart/reload the KiCad project and its library table before
saving an already-open editor. Nothing was committed or ordered.
