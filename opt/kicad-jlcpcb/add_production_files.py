#!/usr/bin/env python3
"""Add the Gerber/CSV production files for one or more Bread Modular modules.

For every selected board this tool:

  1. runs the kicad-jlcpcb exporter (export.py) into <module>/jlcpcb/<board>/
     -> <board>-gerbers.zip, bom.csv, positions.csv, export-report.json
  2. mirrors the archive to <module>/jlcpcb/production_files/GERBER-<board>.zip
     (byte-identical copy, the JLCPCB upload convention)
  3. unpacks the Gerber/drill members into <module>/jlcpcb/gerber/ and prunes
     stale board-prefixed .gbr/.drl files that are no longer in the archive
  4. verifies the mirrors and prints a per-board summary (counts, sizes, sha256)

Nothing else is written. In particular an audited `production/` payload
(hash-frozen release files, manifest.json, release docs) is never touched;
those belong to the module's own guarded release tooling (see
modules/base/tools/regenerate_production.py), not to a routine export.

Works for any current or future module: point it at a module directory, at a
.kicad_pcb file, at a module name under modules/, or use --all to sweep every
module that has a board. Directories without a board are skipped, not failed.

Usage:
  python3 opt/kicad-jlcpcb/add_production_files.py modules/base
  python3 opt/kicad-jlcpcb/add_production_files.py base new_module
  python3 opt/kicad-jlcpcb/add_production_files.py --all
  python3 opt/kicad-jlcpcb/add_production_files.py modules/base --dry-run
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MODULES = REPO / "modules"
GERBER_SUFFIXES = (".gbr", ".drl")
SKIP_DIRS = ("_", ".")


class ToolError(Exception):
    """A user-facing failure: nothing is published for the affected board."""


def load_exporter():
    """Load opt/kicad-jlcpcb/export.py without polluting sys.path."""
    script = HERE / "export.py"
    if not script.is_file():
        raise ToolError(f"Missing exporter: {script}")
    spec = importlib.util.spec_from_file_location("kicad_jlcpcb_export", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_dir_for(target):
    """Resolve a module directory, a .kicad_pcb file, or a module name."""
    path = Path(target).expanduser()
    if path.exists():
        if path.is_file():
            if path.suffix != ".kicad_pcb":
                raise ToolError(f"Not a .kicad_pcb file: {path}")
            return path.resolve().parent
        return path.resolve()
    named = (MODULES / str(target).strip("/")).resolve()
    if named.is_dir():
        return named
    raise ToolError(f"Unknown target {target!r}: not a path, a .kicad_pcb file, "
                    f"or a module name under {MODULES}")


def discover_boards(directory):
    """Boards in a project directory, ignoring KiCad autosave/backup copies."""
    return sorted(path for path in directory.glob("*.kicad_pcb")
                  if not path.name.startswith(("_autosave-", "~"))
                  and not path.stem.endswith("-save"))


def select_boards(directory, args):
    """Honour --board/--all-boards; a bare directory needs exactly one board."""
    boards = discover_boards(directory)
    if args.board:
        wanted = args.board if args.board.endswith(".kicad_pcb") else args.board + ".kicad_pcb"
        match = [path for path in boards if path.name == wanted]
        if not match:
            raise ToolError(f"Board {args.board!r} not found in {directory} "
                            f"(have: {', '.join(p.name for p in boards) or 'none'})")
        return match
    if not boards:
        raise ToolError(f"No .kicad_pcb found in {directory}")
    if len(boards) > 1 and not args.all_boards:
        raise ToolError(f"{directory} has {len(boards)} boards; pick one with --board "
                        f"or export all of them with --all-boards")
    return boards


def sweep_targets():
    """Every module directory under modules/ that contains a board."""
    if not MODULES.is_dir():
        raise ToolError(f"Module root not found: {MODULES}")
    found = []
    for entry in sorted(MODULES.iterdir()):
        if not entry.is_dir() or entry.name.startswith(SKIP_DIRS):
            continue
        if discover_boards(entry):
            found.append(entry)
    return found


def prune_stale_gerbers(gerber_dir, board_stem, keep, dry_run=False):
    """Delete board-prefixed .gbr/.drl files that are not in the current archive."""
    prefix = f"{board_stem}-"
    removed = []
    for path in sorted(gerber_dir.iterdir()) if gerber_dir.is_dir() else []:
        if not path.is_file() or path.name in keep or path.suffix not in GERBER_SUFFIXES:
            continue
        if path.name.startswith(prefix):
            removed.append(path.name)
            if not dry_run:
                path.unlink()
    return removed


def mirror_gerbers(archive, jlcpcb_root, board_stem, prune=True, dry_run=False):
    """Copy the archive to production_files/ and unpack it into gerber/.

    The JLCPCB upload convention keeps three byte-identical Gerber archives
    (jlcpcb/<board>/, jlcpcb/production_files/, and the module production ZIP),
    so the mirrors are copies, never a second export.
    """
    archive = Path(archive)
    if not archive.is_file():
        raise ToolError(f"Exporter archive missing: {archive}")
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        for info in members:
            if info.filename != Path(info.filename).name:
                raise ToolError(f"Unsafe archive member: {info.filename!r}")
            if Path(info.filename).suffix not in GERBER_SUFFIXES:
                raise ToolError(f"Unexpected archive member: {info.filename!r}")
        if not members:
            raise ToolError(f"Archive has no Gerber/drill files: {archive}")
        digests = {info.filename: hashlib.sha256(zf.read(info)).hexdigest() for info in members}

    jlcpcb_root = Path(jlcpcb_root)
    production_dir = jlcpcb_root / "production_files"
    gerber_dir = jlcpcb_root / "gerber"
    upload_copy = production_dir / f"GERBER-{board_stem}.zip"
    if dry_run:
        return {"upload_copy": upload_copy, "gerber_dir": gerber_dir,
                "extracted": sorted(digests), "pruned": [], "written": False}

    production_dir.mkdir(parents=True, exist_ok=True)
    gerber_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, upload_copy)
    if sha256(upload_copy) != sha256(archive):
        raise ToolError(f"Mirrored archive is not byte-identical: {upload_copy}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(gerber_dir)
    for name, digest in digests.items():
        target = gerber_dir / name
        if not target.is_file() or sha256(target) != digest:
            raise ToolError(f"Unpacked Gerber does not match the archive: {target}")
    pruned = prune_stale_gerbers(gerber_dir, board_stem, set(digests)) if prune else []
    return {"upload_copy": upload_copy, "gerber_dir": gerber_dir,
            "extracted": sorted(digests), "pruned": pruned, "written": True}


def plan_board(module_dir, board, args):
    jlcpcb_root = Path(args.jlcpcb_root).expanduser().resolve() if args.jlcpcb_root \
        else module_dir / "jlcpcb"
    return {"module": module_dir, "board": board, "jlcpcb_root": jlcpcb_root,
            "output": jlcpcb_root / board.stem,
            "archive": jlcpcb_root / board.stem / f"{board.stem}-gerbers.zip"}


def export_arguments(plan, args):
    """Exporter arguments for one board, via the exporter's own parser."""
    argv = [str(plan["module"]), "--board", plan["board"].name, "--overwrite",
            "-o", str(plan["output"]), "--kicad-cli", args.kicad_cli]
    if args.pcb_only:
        argv += ["--pcb-only"]
    elif args.schematic:
        argv += ["--schematic", args.schematic]
    if args.require_part_numbers:
        argv += ["--require-part-numbers"]
    return argv


def run_board(module_dir, board, exporter, args):
    plan = plan_board(module_dir, board, args)
    if args.dry_run:
        print(f"[dry-run] {board.name} -> {plan['archive'].parent}")
        print(f"[dry-run] upload copy  -> {plan['jlcpcb_root'] / 'production_files' / ('GERBER-%s.zip' % board.stem)}")
        print(f"[dry-run] loose Gerber -> {plan['jlcpcb_root'] / 'gerber'}")
        return {"plan": plan, "dry_run": True}

    report = exporter.export_project(exporter.argument_parser().parse_args(export_arguments(plan, args)))
    result = {"plan": plan, "report": report, "dry_run": False}
    if args.loose_gerbers:
        result["mirror"] = mirror_gerbers(plan["archive"], plan["jlcpcb_root"], board.stem,
                                          prune=not args.keep_stale_gerbers)
    return result


def describe(result, args):
    if result.get("dry_run"):
        return
    plan, report = result["plan"], result["report"]
    print(f"  source PCB : {plan['board']}  ({sha256(plan['board'])[:16]})")
    print(f"  assembly   : {report['component_count']} components, "
          f"{report['bom_row_count']} BOM rows, "
          f"{len(report['missing_part_numbers'])} missing LCSC numbers")
    for name in (f"{plan['board'].stem}-gerbers.zip", "bom.csv", "positions.csv", "export-report.json"):
        path = plan["output"] / name
        print(f"  {path}  {path.stat().st_size} B  {sha256(path)[:12]}")
    mirror = result.get("mirror")
    if mirror:
        print(f"  {mirror['upload_copy']}  {len(mirror['extracted'])} members")
        print(f"  {mirror['gerber_dir']}  unpacked {len(mirror['extracted'])} Gerber/drill files"
              + (f", pruned {len(mirror['pruned'])}: {', '.join(mirror['pruned'])}" if mirror["pruned"] else ""))
    elif not args.loose_gerbers:
        print("  loose Gerber mirrors skipped (--no-loose-gerbers)")
    production = plan["module"] / "production"
    if (production / "manifest.json").is_file():
        print(f"  note: audited release payload left untouched: {production}")


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*", help="module directory, .kicad_pcb file, or module name "
                                                   "(default with --all: every module under modules/)")
    parser.add_argument("--all", action="store_true", help="export every module under modules/ that has a board")
    parser.add_argument("--all-boards", action="store_true", help="export every board in a target directory")
    parser.add_argument("--board", help="board filename (or stem) when a directory holds several boards")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--schematic", help="root schematic when it differs from the PCB name")
    group.add_argument("--pcb-only", action="store_true", help="read PCB fields only, not schematic fields")
    parser.add_argument("--allow-missing-part-numbers", dest="require_part_numbers", action="store_false",
                        help="do not fail when an assembly part has no LCSC number")
    parser.add_argument("--no-loose-gerbers", dest="loose_gerbers", action="store_false",
                        help="write only the ZIP + CSVs, skip production_files/ and gerber/ mirrors")
    parser.add_argument("--keep-stale-gerbers", action="store_true",
                        help="do not prune Gerber/drill files that are no longer in the archive")
    parser.add_argument("--jlcpcb-root", metavar="DIR",
                        help="write the jlcpcb/ tree under DIR instead of the module directory")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and write nothing")
    parser.add_argument("--kicad-cli", default=None, help="KiCad CLI executable (default: KICAD_CLI or kicad-cli)")
    parser.set_defaults(require_part_numbers=True, loose_gerbers=True)
    return parser


def main(argv=None):
    args = argument_parser().parse_args(argv)
    if args.kicad_cli is None:
        import os
        args.kicad_cli = os.environ.get("KICAD_CLI", "kicad-cli")
    if args.all and args.targets:
        print("Error: --all takes no targets", file=sys.stderr)
        return 1

    try:
        exporter = load_exporter()
    except ToolError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    try:
        directories = sweep_targets() if args.all or not args.targets else [module_dir_for(t) for t in args.targets]
    except ToolError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    exported, skipped, failed = [], [], []
    for directory in directories:
        try:
            boards = select_boards(directory, args)
        except ToolError as error:
            if args.all or not args.targets:
                print(f"Skipping {directory}: {error}")
                skipped.append(directory)
                continue
            print(f"Error: {error}", file=sys.stderr)
            failed.append(directory)
            continue
        for board in boards:
            print(f"{directory.name}/{board.name}")
            try:
                result = run_board(directory, board, exporter, args)
            except (exporter.ExportError, ToolError, OSError, UnicodeError) as error:
                print(f"  ERROR: {error}", file=sys.stderr)
                failed.append(board)
                continue
            describe(result, args)
            exported.append(board)

    print(f"\n{len(exported)} board(s) exported, {len(skipped)} module(s) skipped, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
