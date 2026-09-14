#!/usr/bin/env python3
"""Export a KiCad board directory for JLCPCB. Python stdlib + kicad-cli only."""

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict


PART_FIELDS = (
    "LCSC", "LCSC PN", "LCSC Part #", "LCSC Part Number", "LCSC Part",
    "JLCPCB", "JLCPCB PN", "JLCPCB Part #", "JLCPCB Part Number", "JLCPCB Part",
    "JLC", "JLC Part #",
)
MPN_FIELDS = ("MPN", "Manufacturer Part Number", "Manufacturer Part #", "Mfr Part #", "Part Number")
MANUFACTURER_FIELDS = ("Manufacturer", "Mfr")
ROTATION_FIELDS = ("JLCPCB Rotation Offset",)
BOM_HEADER = ("Comment", "Designator", "Footprint", "LCSC Part #", "Quantity", "Manufacturer", "MPN")
CPL_HEADER = ("Designator", "Mid X", "Mid Y", "Rotation", "Layer")
SCH_FIELDS = "Reference,Value,Footprint,${DNP},${EXCLUDE_FROM_BOM},${EXCLUDE_FROM_BOARD},*"
SCH_LABELS = "Reference,Value,Footprint,__DNP,__EXCLUDE_FROM_BOM,__EXCLUDE_FROM_BOARD"
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()"]+')


class ExportError(Exception):
    """An actionable error suitable for printing without a traceback."""


def normalized(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def natural_key(text):
    return tuple((1, int(p)) if p.isdigit() else (0, p.lower())
                 for p in re.split(r"(\d+)", text))


def clean(value):
    value = value.strip()
    return "" if value == "~" else value


def parse_sexpr(text):
    """Read KiCad S-expressions without pcbnew or a third-party parser."""
    root = []
    stack = [root]
    end = 0
    escapes = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}
    for match in TOKEN.finditer(text):
        if text[end:match.start()].strip():
            raise ExportError("Malformed KiCad file (invalid quoted string).")
        end = match.end()
        token = match.group()
        if token == "(":
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif token == ")":
            if len(stack) == 1:
                raise ExportError("Malformed KiCad file (unexpected closing parenthesis).")
            stack.pop()
        else:
            if token.startswith('"'):
                token = re.sub(r"\\(.)", lambda m: escapes.get(m[1], m[0]), token[1:-1])
            stack[-1].append(token)
    if text[end:].strip() or len(stack) != 1 or len(root) != 1 or not isinstance(root[0], list):
        raise ExportError("Malformed KiCad file (unbalanced expressions).")
    return root[0]


def children(node, name):
    return [child for child in node if isinstance(child, list) and child and child[0] == name]


def child(node, name):
    return next(iter(children(node, name)), [])


def atom(node, name, default=""):
    item = child(node, name)
    return item[1] if len(item) > 1 else default


def read_board(path):
    root = parse_sexpr(path.read_text(encoding="utf-8-sig"))
    if not root or root[0] != "kicad_pcb":
        raise ExportError(f"Not a modern KiCad PCB: {path}")
    layers = [entry[1] for entry in child(root, "layers")[1:]
              if isinstance(entry, list) and len(entry) > 1]
    copper = [name for name in layers if name.endswith(".Cu")]
    if not {"F.Cu", "B.Cu", "Edge.Cuts"}.issubset(layers):
        raise ExportError("Board must contain F.Cu, B.Cu and Edge.Cuts layers.")
    plot_layers = copper + [name for name in (
        "F.Mask", "B.Mask", "F.SilkS", "B.SilkS", "F.Paste", "B.Paste", "Edge.Cuts"
    ) if name in layers]
    footprints = {}
    for fp in children(root, "footprint") + children(root, "module"):
        fields = {p[1]: p[2] for p in children(fp, "property") if len(p) >= 3}
        # KiCad 6/7 boards store reference/value as fp_text instead of properties.
        for text in children(fp, "fp_text"):
            if len(text) >= 3 and text[1] in ("reference", "value"):
                fields.setdefault(text[1].capitalize(), text[2])
        ref = fields.get("Reference", "").strip()
        pads = children(fp, "pad")
        has_pads = any(len(p) > 2 and p[2] in ("smd", "thru_hole", "connect") for p in pads)
        if not has_pads:
            continue  # Logos, fiducials without electrical pads, NPTH-only mounting holes.
        if not ref or "?" in ref or re.search(r"[,\s]", ref):
            raise ExportError(f"Missing, unannotated or invalid footprint reference: {ref!r}")
        if ref in footprints:
            raise ExportError(f"Duplicate PCB reference: {ref}")
        footprints[ref] = {
            "fields": fields, "footprint": fp[1],
            "attrs": set(child(fp, "attr")[1:]), "layer": atom(fp, "layer"),
        }
    return footprints, plot_layers, copper


def read_csv(path, required):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(required).issubset(reader.fieldnames or []):
            raise ExportError(f"Unexpected KiCad CSV columns in {path.name}: {reader.fieldnames}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ExportError(f"Duplicate CSV column names in {path.name}; rename conflicting custom fields.")
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ExportError(f"Malformed CSV row in {path.name}")
    return rows


def indexed(rows, key):
    result = {}
    for row in rows:
        ref = row[key].strip()
        if not ref or ref in result:
            raise ExportError(f"Missing or duplicate reference in KiCad export: {ref!r}")
        result[ref] = row
    return result


def field_value(ref, sources, aliases, label, transform=clean):
    """Merge native fields; conflicting nonempty values are unsafe for purchasing."""
    names = {normalized(a) for a in aliases}
    found = []
    for source, fields in sources:
        for name, value in fields.items():
            if normalized(name) in names and clean(value):
                found.append((f"{source}:{name}", transform(value)))
    values = {value for _, value in found}
    if len(values) > 1:
        details = ", ".join(f"{name}={value!r}" for name, value in found)
        raise ExportError(f"{ref}: conflicting {label} fields ({details}). Sync the schematic/PCB fields.")
    return found[0][1] if found else ""


def flag(value):
    return value.strip().lower() not in ("", "0", "no", "false", "~")


def number(value, label):
    try:
        result = float(value)
    except ValueError:
        raise ExportError(f"Invalid {label}: {value!r}") from None
    if not math.isfinite(result):
        raise ExportError(f"Non-finite {label}: {value!r}")
    return result


def decimal(value):
    # Avoid negative zero; keep mm precision from the KiCad position export.
    return f"{0.0 if abs(value) < 0.0000005 else value:.6f}"


def assembly_rows(footprints, positions, symbols, args):
    parts, placements, excluded, warnings = [], [], {}, []
    missing_numbers, pcb_only_refs = [], []
    for ref in sorted(footprints, key=natural_key):
        fp = footprints[ref]
        attrs = fp["attrs"]
        symbol = symbols.get(ref, {}) if symbols is not None else {}
        reason = None
        if "dnp" in attrs or flag(symbol.get("__DNP", "")):
            reason = "Do not populate"
        elif "exclude_from_bom" in attrs or flag(symbol.get("__EXCLUDE_FROM_BOM", "")):
            reason = "Excluded from BOM"
        elif "exclude_from_pos_files" in attrs:
            reason = "Excluded from position files"
        elif flag(symbol.get("__EXCLUDE_FROM_BOARD", "")):
            reason = "Excluded from board in schematic"
        elif not args.include_through_hole and "smd" not in attrs:
            reason = "Not an SMD footprint (use --include-through-hole)"
        elif args.side != "both" and fp["layer"] != {"top": "F.Cu", "bottom": "B.Cu"}[args.side]:
            reason = "Other assembly side"
        if reason:
            excluded[ref] = reason
            continue
        if ref not in positions:
            raise ExportError(f"{ref}: eligible footprint missing from KiCad position export.")
        pos = positions[ref]
        if pos["Side"] not in ("top", "bottom"):
            raise ExportError(f"{ref}: unexpected position side: {pos['Side']!r}")
        if fp["layer"] != {"top": "F.Cu", "bottom": "B.Cu"}[pos["Side"]]:
            raise ExportError(f"{ref}: PCB/position side mismatch.")
        if symbols is not None and not symbol:
            pcb_only_refs.append(ref)
        for key in ("Value", "Footprint"):
            pcb_value = fp["footprint"] if key == "Footprint" else fp["fields"].get(key, "")
            if clean(symbol.get(key, "")) and clean(symbol[key]) != clean(pcb_value):
                warnings.append(f"{ref}: schematic {key} {symbol[key]!r} differs from PCB {pcb_value!r}; using PCB.")
        sources = (("schematic", symbol), ("PCB", fp["fields"]))
        part = field_value(ref, sources, PART_FIELDS + tuple(args.part_field), "LCSC part number",
                           lambda value: clean(value).upper())
        if part and not re.fullmatch(r"C[0-9]+", part):
            raise ExportError(f"{ref}: LCSC part number must be C followed by digits, not {part!r}. Use MPN for manufacturer numbers.")
        if not part:
            missing_numbers.append(ref)
        mpn = field_value(ref, sources, MPN_FIELDS, "MPN")
        manufacturer = field_value(ref, sources, MANUFACTURER_FIELDS, "manufacturer")
        offset = field_value(ref, sources, ROTATION_FIELDS, "rotation offset",
                             lambda value: number(value, f"{ref} rotation offset"))
        angle = (number(pos["Rot"], f"{ref} rotation") + (offset or 0.0)) % 360
        # KiCad already exports Cartesian Y and both sides in a common top-view frame.
        # Do not flip bottom X or invent a package-specific orientation correction.
        placements.append((ref, decimal(number(pos["PosX"], f"{ref} X")),
                           decimal(number(pos["PosY"], f"{ref} Y")),
                           decimal(angle), pos["Side"]))
        parts.append((ref, pos["Val"], pos["Package"], part, manufacturer, mpn))
    if missing_numbers:
        message = "Missing LCSC part numbers: " + ", ".join(missing_numbers)
        if args.require_part_numbers:
            raise ExportError(message + ". Add a native LCSC field in KiCad.")
        warnings.append(message + ". Match these parts manually before ordering.")
    if pcb_only_refs:
        warnings.append("Not found in schematic; using PCB fields: " + ", ".join(pcb_only_refs))
    if symbols is not None:
        absent = [ref for ref, row in symbols.items() if ref not in footprints
                  and clean(row.get("Footprint", ""))
                  and not any(flag(row.get(key, "")) for key in
                              ("__DNP", "__EXCLUDE_FROM_BOM", "__EXCLUDE_FROM_BOARD"))]
        if absent:
            warnings.append("Schematic components absent from PCB assembly footprints: " + ", ".join(sorted(absent, key=natural_key)))
    groups = defaultdict(list)
    for ref, value, package, part, manufacturer, mpn in parts:
        groups[(value, package, part, manufacturer, mpn)].append(ref)
    bom = [(value, ", ".join(refs), package, part, len(refs), manufacturer, mpn)
           for (value, package, part, manufacturer, mpn), refs in groups.items()]
    if not placements:
        warnings.append("No assembly components selected; BOM and positions CSVs contain headers only.")
    return bom, placements, excluded, warnings, missing_numbers


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def run_cli(cli, arguments, cwd):
    command = [cli] + [str(arg) for arg in arguments]
    env = dict(os.environ, LC_ALL="C", LANG="C")
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise ExportError(f"KiCad command failed ({result.returncode}): {command!r}\n"
                          f"{result.stdout}{result.stderr}")
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.stdout.strip()


def select_inputs(args):
    directory = Path(args.project_dir).expanduser().resolve()
    if not directory.is_dir():
        raise ExportError(f"Project directory does not exist: {directory}")
    if args.board:
        board = (directory / args.board).resolve()
        if board.suffix != ".kicad_pcb":
            board = board.with_name(board.name + ".kicad_pcb")
    else:
        boards = sorted(path for path in directory.glob("*.kicad_pcb")
                        if not path.name.startswith(("_autosave-", "~")) and not path.stem.endswith("-save"))
        if len(boards) != 1:
            raise ExportError(f"Expected one .kicad_pcb in {directory}, found {len(boards)}. "
                              "Select one with --board NAME.kicad_pcb. " + ", ".join(p.name for p in boards))
        board = boards[0]
    if not board.is_file():
        raise ExportError(f"PCB file does not exist: {board}")
    schematic = None
    if not args.pcb_only:
        schematic = (directory / args.schematic).resolve() if args.schematic else board.with_suffix(".kicad_sch")
        if not schematic.is_file():
            if args.schematic or list(directory.glob("*.kicad_sch")):
                raise ExportError(f"Matching schematic not found: {schematic}. Use --schematic ROOT.kicad_sch or --pcb-only.")
            schematic = None
    output = Path(args.output).expanduser().resolve() if args.output else directory / "jlcpcb" / board.stem
    return board, schematic, output


def export_project(args):
    board, schematic, output = select_inputs(args)
    cli = shutil.which(os.path.expanduser(args.kicad_cli))
    if not cli:
        raise ExportError("kicad-cli not found. Install KiCad and add its CLI to PATH, or use --kicad-cli PATH. No pip packages are needed.")
    version = run_cli(cli, ["version"], board.parent)
    match = re.search(r"\b(\d+)\.\d+", version)
    if not match or int(match[1]) < 9:
        raise ExportError(f"This exporter requires KiCad CLI 9 or newer; found {version!r}.")
    footprints, layers, copper = read_board(board)
    names = [f"{board.stem}-gerbers.zip", "bom.csv", "positions.csv", "export-report.json"]
    if output.exists() and not output.is_dir():
        raise ExportError(f"Output path is not a directory: {output}")
    for name in names:
        dest = output / name
        if dest.is_symlink() or (dest.exists() and (not args.overwrite or not dest.is_file())):
            raise ExportError(f"Refusing to replace {dest}. Use a different --output or --overwrite for existing export files.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".jlcpcb-export-", dir=output.parent) as temporary:
        work = Path(temporary)
        symbols = None
        if schematic:
            run_cli(cli, ["sch", "export", "bom", "--fields", SCH_FIELDS, "--labels", SCH_LABELS,
                          "--group-by", "", "--include-excluded-from-bom", "--filter", "",
                          "--field-delimiter", ",", "--string-delimiter", '"',
                          "--ref-delimiter", ",", "--ref-range-delimiter", "",
                          "--output", work / "schematic.csv", schematic], schematic.parent)
            symbols = indexed(read_csv(work / "schematic.csv", SCH_LABELS.split(",")), "Reference")
        run_cli(cli, ["pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                      "--use-drill-file-origin", "--output", work / "raw-positions.csv", board], board.parent)
        positions = indexed(read_csv(work / "raw-positions.csv",
                                     ("Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side")), "Ref")
        bom, cpl, excluded, warnings, missing = assembly_rows(footprints, positions, symbols, args)
        if not schematic:
            warnings.insert(0, "PCB-only export: schematic fields and exclusion flags were not read.")
        warnings.append("Export is not a DRC or assembly approval: refill zones and save before export; review Gerbers, holes, part matches, centroids and rotations in JLCPCB's preview.")
        gerbers = work / "gerbers"
        gerbers.mkdir()
        run_cli(cli, ["pcb", "export", "gerbers", "--layers", ",".join(layers),
                      "--use-drill-file-origin", "--no-protel-ext", "--no-x2", "--no-netlist",
                      "--disable-aperture-macros", "--subtract-soldermask",
                      "--output", str(gerbers) + os.sep, board], board.parent)
        run_cli(cli, ["pcb", "export", "drill", "--format", "excellon", "--drill-origin", "plot",
                      "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
                      "--excellon-oval-format", "route", "--excellon-separate-th",
                      "--output", str(gerbers) + os.sep, board], board.parent)
        plots = sorted(gerbers.glob("*.gbr"))
        drills = sorted(gerbers.glob("*.drl"))
        if len(plots) != len(layers) or not drills or any(p.stat().st_size == 0 for p in plots + drills):
            raise ExportError("KiCad did not produce the expected nonempty Gerber/drill files; no export published.")
        with zipfile.ZipFile(work / names[0], "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in plots + drills:
                archive.write(path, arcname=path.name)
        write_csv(work / "bom.csv", BOM_HEADER, bom)
        write_csv(work / "positions.csv", CPL_HEADER, cpl)
        report = {
            "generator": "bread-modular/kicad-jlcpcb", "kicad_version": version,
            "board": str(board), "schematic": str(schematic) if schematic else None,
            "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (board, schematic) if p},
            "layers": layers, "copper_layer_count": len(copper),
            "origin": "KiCad drill/place origin", "units": "mm", "side": args.side,
            "include_through_hole": args.include_through_hole,
            "component_count": len(cpl), "bom_row_count": len(bom),
            "excluded": excluded, "missing_part_numbers": missing, "warnings": warnings,
            "files": names[:3],
        }
        (work / "export-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        # Publish only after every command/validation succeeds. Never zip stale output files.
        output.mkdir(parents=True, exist_ok=True)
        for name in names:
            os.replace(work / name, output / name)
    for message in warnings:
        print(f"Warning: {message}", file=sys.stderr)
    print(f"Exported {len(cpl)} components in {len(bom)} BOM rows ({len(copper)} copper layers):")
    for name in names:
        print(f"  {output / name}")
    return report


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Native part fields: add LCSC = C12345 in KiCad Symbol Properties (E),\n"
                                            "or Tools > Edit Symbol Fields. Use the actual catalog code, not this example.\n"
                                            "Update PCB from Schematic (F8), save, then export. See README.md.\n"
                                            "MPN and Manufacturer fields are preserved separately; no plugins needed.")
    parser.add_argument("project_dir", help="directory containing the KiCad project")
    parser.add_argument("--board", help="PCB filename (or stem); required if the directory has multiple boards")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--schematic", help="root schematic filename/path when it differs from the PCB name")
    group.add_argument("--pcb-only", action="store_true", help="read only PCB footprint fields, not schematic fields")
    parser.add_argument("-o", "--output", help="output directory (default: PROJECT_DIR/jlcpcb/BOARD_NAME)")
    parser.add_argument("--overwrite", action="store_true", help="replace only the four named exporter files after successful generation")
    parser.add_argument("--include-through-hole", action="store_true", help="include non-SMD electrical footprints in both BOM and CPL")
    parser.add_argument("--side", choices=("top", "bottom", "both"), default="both", help="assembly side (default: both); does not filter Gerbers")
    parser.add_argument("--part-field", action="append", default=[], metavar="NAME", help="additional native field containing an LCSC C-number (repeatable)")
    parser.add_argument("--require-part-numbers", action="store_true", help="fail if any selected assembly component lacks an LCSC number")
    parser.add_argument("--kicad-cli", default=os.environ.get("KICAD_CLI", "kicad-cli"), help="KiCad CLI executable (default: KICAD_CLI or kicad-cli)")
    return parser


def main(argv=None):
    args = argument_parser().parse_args(argv)
    try:
        export_project(args)
    except (ExportError, OSError, UnicodeError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
