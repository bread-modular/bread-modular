# KiCad → JLCPCB assembly export

A standalone, offline exporter for a directory containing a KiCad project. It generates a Gerber ZIP (including drills), a grouped assembly BOM, and a pick-and-place / CPL CSV.

## Requirements

- Python **3.8+**, standard library only.
- **KiCad 9+** with `kicad-cli` available; tested with KiCad **9.0.8**.
- No pip packages, KiCad plugins, `pcbnew` Python bindings, Node, external `zip` executable, or network access.

KiCad itself is required to interpret and plot the board correctly. “No dependencies” here means **no additional third-party packages beyond Python and KiCad**, not a replacement for KiCad's plotting engine.

## Quick start

From the repository root:

```sh
python3 opt/kicad-jlcpcb/export.py modules/line_in
```

Or copy the single `export.py` file anywhere and use an absolute project path:

```sh
python3 /path/to/export.py "/path/to/My KiCad Project"
```

The default is **SMD components, on both sides**. Through-hole connectors, pots, etc. are omitted from the assembly CSVs unless explicitly requested. Both CSVs always contain the same reference-designator set.

For `modules/line_in`, output goes to:

```text
modules/line_in/jlcpcb/line_in/
  line_in-gerbers.zip
  bom.csv
  positions.csv
  export-report.json
```

Upload `line_in-gerbers.zip` as the PCB fabrication file, `bom.csv` as the assembly BOM, and `positions.csv` as the CPL / pick-and-place file. The report is for your review, not for upload.

Existing files are protected by default. Regenerate them explicitly:

```sh
python3 opt/kicad-jlcpcb/export.py modules/line_in --overwrite
```

All KiCad commands and content validation run in a fresh temporary directory before the four result files are published. `--overwrite` replaces only those four filenames, not unrelated files in the output directory. Each replacement is atomic, but publishing the entire set is not a filesystem transaction; do not run concurrent exports to the same directory.

## Add part numbers using built-in KiCad features

You do **not** need a fabrication plugin or a custom symbol library.

1. Open the project in **Schematic Editor**.
2. Hover over a symbol and press **E** to open **Symbol Properties**.
3. Add a custom field named **`LCSC`** using the fields table's add button.
4. Enter the exact JLCPCB/LCSC catalog code for that component, for example **`C12345`**. This is a syntax example only, not a recommended part. Verify package, value, tolerance, voltage/rating and stock against the intended part.
5. Leave the field's visibility off if you do not want it drawn on the schematic.
6. Optionally add **`MPN`** (manufacturer part number) and **`Manufacturer`** fields. These are retained separately in the BOM; an MPN is not an LCSC catalog code.
7. Save the schematic, run **Tools → Update PCB from Schematic** (**F8**), review and apply the changes, and save the PCB.

For many components, use **Tools → Edit Symbol Fields** (the native Symbol Fields Table) to add/fill the same `LCSC`, `MPN` and `Manufacturer` columns in bulk. KiCad copies symbol fields to their corresponding footprints when updating the PCB from the schematic. [source](https://docs.kicad.org/9.0/en/eeschema/eeschema.html)

The exporter reads native fields from the **root schematic via KiCad's BOM export** (including hierarchical sheets and multi-unit symbols), and from the **actual board footprints**. A number stored only on the schematic is therefore included even before that particular field has been copied to the PCB; synchronizing before manufacture is still strongly recommended. PCB fields provide a fallback when schematic fields are absent/blank.

If you work without a schematic, add the same native fields in the PCB Editor's **Footprint Properties** dialog and use `--pcb-only`. A project directory with no `.kicad_sch` files also falls back to PCB-only mode, with a warning.

### Recognized field names

Field names are matched ignoring case, spaces and punctuation. For example, `LCSC_Part_Number` and `LCSC Part Number` match.

| BOM output | Accepted native fields |
| --- | --- |
| `LCSC Part #` | `LCSC`, `LCSC PN`, `LCSC Part #`, `LCSC Part Number`, `LCSC Part`, `JLCPCB`, `JLCPCB PN`, `JLCPCB Part #`, `JLCPCB Part Number`, `JLCPCB Part`, `JLC`, `JLC Part #` |
| `MPN` | `MPN`, `Manufacturer Part Number`, `Manufacturer Part #`, `Mfr Part #`, `Part Number` |
| `Manufacturer` | `Manufacturer`, `Mfr` |

LCSC values must be **`C` followed by digits**; a lowercase `c` is normalized to uppercase. URLs and manufacturer numbers in an LCSC field are rejected rather than silently used as an incorrect catalog code. Empty fields and KiCad's `~` placeholder are treated as missing.

Already using a different field name? No project migration is necessary:

```sh
python3 opt/kicad-jlcpcb/export.py modules/line_in \
  --part-field "Supplier Code" --require-part-numbers
```

`--part-field` adds another recognized LCSC-code field and can be repeated. **Conflicting nonempty values** across recognized fields or between schematic and PCB stop the export. Resolve them in KiCad; the tool does not silently choose a potentially wrong part.

Components with no LCSC number remain in both CSVs with a blank `LCSC Part #` and a warning, allowing manual matching. For an export that must have every selected component's catalog number, use **`--require-part-numbers`**.

## Options and examples

```sh
# Non-default destination; relative output paths are relative to the current shell directory.
python3 opt/kicad-jlcpcb/export.py modules/line_in --output /tmp/line-in-assembly

# Directory contains multiple boards: select the filename or stem.
python3 opt/kicad-jlcpcb/export.py /path/to/project --board control.kicad_pcb

# Root schematic has a different filename (paths here are relative to project_dir).
python3 opt/kicad-jlcpcb/export.py /path/to/project \
  --board control --schematic main.kicad_sch

# Include through-hole / other electrical footprints as well as SMD.
python3 opt/kicad-jlcpcb/export.py modules/line_in --include-through-hole

# Only one assembly side; still exports all fabrication layers for the board.
python3 opt/kicad-jlcpcb/export.py modules/line_in --side bottom

# Intentionally ignore the schematic and use only board fields/flags.
python3 opt/kicad-jlcpcb/export.py /path/to/project --pcb-only

# Choose the KiCad CLI executable, e.g. on macOS.
python3 opt/kicad-jlcpcb/export.py /path/to/project \
  --kicad-cli /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli

# Full built-in help, including the native-field setup summary.
python3 opt/kicad-jlcpcb/export.py --help
```

Alternatively, set the `KICAD_CLI` environment variable. On Windows, use the appropriate Python command (`py -3` or `python`) and pass the installed `kicad-cli.exe` path if it is not on `PATH`.

## What is exported

### Gerber ZIP

- Every copper layer declared in the board, **including all inner copper layers**.
- Front/back solder mask, silkscreen and solder paste layers where present, plus `Edge.Cuts`.
- Separate **PTH and NPTH Excellon drill files**, in millimetres, with routed slots.
- Only the freshly generated Gerber and drill files, at the ZIP root. No BOM, schematic, project metadata, stale plots or unrelated files.

The script uses explicit fabrication layers instead of the board's saved plot selection. Gerber files use `.gbr` filenames identifying their layers, with X2/netlist attributes and aperture macros disabled, and soldermask openings subtracted from silkscreen. It uses KiCad's built-in `pcb export gerbers`, `pcb export drill` and `pcb export pos` commands. [source](https://docs.kicad.org/9.0/en/cli/cli.html)

### BOM (`bom.csv`)

```csv
Comment,Designator,Footprint,LCSC Part #,Quantity,Manufacturer,MPN
10k,"R1, R2",R_0603_1608Metric,C12345,2,Example Manufacturer,EXAMPLE-MPN
```

This row is illustrative, not a part recommendation. `Comment` is the PCB value; `Footprint` is the actual PCB footprint name without the library prefix. Grouping requires the same **value, footprint, LCSC code, manufacturer and MPN**. Identical values with different purchase codes are never merged. Quantity is per board. References are naturally sorted, explicitly listed and correctly CSV-quoted, not compressed to ranges.

### Pick and place (`positions.csv`)

```csv
Designator,Mid X,Mid Y,Rotation,Layer
R1,12.500000,7.250000,90.000000,top
R2,15.500000,7.250000,270.000000,bottom
```

Coordinates are in **millimetres**, layers are `top` / `bottom`, and angles are normalized to `[0, 360)`. The BOM and CPL column conventions follow JLCPCB's documented formats; `Quantity`, `Manufacturer` and `MPN` are supplemental BOM columns. [source](https://jlcpcb.com/help/article/how-to-generate-bom-and-centroid-files-from-kicad-8)

**Origin:** all three fabrication exports use the board's **drill/place origin**. Set it to a convenient board corner in KiCad before exporting if desired. With no custom origin, KiCad's default origin is used. The script preserves KiCad's Cartesian position coordinates; it does **not** mirror bottom-side X or independently translate coordinates to a bounding box.

**Centroid and rotation:** positions are KiCad's footprint anchor positions, not a newly computed body centroid. Footprint anchors and JLCPCB library orientations may need adjustment, especially for asymmetric connectors, ICs and polarized parts. No universal automatic rotation database is included. Always inspect JLCPCB's placement preview.

If a particular part needs an orientation correction, add a native field **`JLCPCB Rotation Offset`** with a signed number of degrees, e.g. `90` or `-90`. The script adds it to the KiCad-exported rotation and normalizes the result. This is **this tool's field**, not an automatic import of Fabrication Toolkit's correction settings. Check the resulting orientation in the preview on both sides. Position offsets are not implemented; correct the footprint anchor in KiCad or adjust the placement with the assembler.

### Selection and validation

Both assembly CSVs exclude a component if **either** source marks it as DNP or excluded from BOM, or if the PCB excludes it from position files. Schematic “Exclude from board” also excludes it. These flags do not remove its copper/pads from fabrication Gerbers.

- Default: only footprints with KiCad's **SMD** type; SMD connectors with mechanical through-hole pads remain eligible.
- `--include-through-hole`: also includes other footprints with electrical pads. This does not guarantee JLCPCB can assemble the selected through-hole parts; verify service/part availability.
- Pure graphics and NPTH-only mechanical footprints are omitted. Electrical test points/fiducials can still need manual exclusion using native footprint flags.
- Duplicate or unannotated electrical footprint references, missing eligible positions, malformed coordinates, invalid/conflicting part fields, and CLI failures stop the export.
- Schematic/PCB value or footprint differences are **warnings**; the physical PCB determines the BOM value/footprint. References missing from one source are also reported. This is not a complete electrical parity check.
- The report records selected counts, skipped references/reasons, missing numbers, warnings, layers and hashes of the PCB/root schematic (not every hierarchical sheet or library).
- Errors return exit status `1`; successful exports, including exports with warnings, return `0`. Argument errors use argparse's exit status `2`.

## Before ordering

Save the schematic and PCB, update the PCB from the schematic, **refill copper zones**, and run KiCad's DRC (and schematic parity/ERC as appropriate). This tool exports the saved design; it does **not** refill zones, repair outlines, run DRC/ERC, edit the project, check supplier stock, or validate the electrical suitability of a purchase code.

Review the ZIP in a Gerber viewer and check outline, layer count, copper, mask, plated/non-plated holes and slots. In JLCPCB's preview verify part matches, **pin 1 / diode and LED polarity**, placement anchors, rotations and both board sides before approving an order. Successful file export is not manufacturing sign-off.

## Tests

The unit tests use only Python's standard library and mocked CLI calls:

```sh
python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
```

The optional integration suite invokes the installed KiCad CLI on temporary project fixtures and existing repository boards; it leaves the source projects untouched:

```sh
KICAD_JLCPCB_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
```
