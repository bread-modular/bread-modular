#!/usr/bin/env python3
"""
Generate compile_commands.json for clang tooling using PlatformIO metadata.

PlatformIO already emits a rich build description into
.pio/build/<env>/idedata.json. This script reuses that information so that
clangd (and other clang-based tooling) can understand the project without
having to install PlatformIO or rerun a full build on this machine.
"""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Iterable, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env",
        default="ATtiny1616",
        help="PlatformIO environment name (defaults to %(default)s)",
    )
    parser.add_argument(
        "--output",
        default="compile_commands.json",
        help="Destination file for the generated database (defaults to %(default)s)",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        default=["src", "lib"],
        help="Source directories to scan for translation units",
    )
    return parser.parse_args()


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    idedata_path = root / ".pio" / "build" / args.env / "idedata.json"
    if not idedata_path.exists():
        raise SystemExit(
            f"Could not find {idedata_path}. Build the '{args.env}' environment first."
        )

    idedata = json.loads(idedata_path.read_text())
    compiler = Path(idedata["cxx_path"])
    cxx_flags = idedata.get("cxx_flags", [])
    defines = [f"-D{value}" for value in idedata.get("defines", [])]
    include_groups = idedata.get("includes", {})
    includes = []
    for key in ("build", "compatlib", "toolchain"):
        includes.extend(include_groups.get(key, []))
    includes = [f"-I{path}" for path in _dedupe(includes)]

    clang_build_dir = root / ".pio" / "build" / args.env / "clang"
    clang_build_dir.mkdir(parents=True, exist_ok=True)

    compile_db = []
    source_dirs = [root / Path(entry) for entry in args.sources]
    translation_units: List[Path] = []
    for directory in source_dirs:
        if directory.is_dir():
            translation_units.extend(directory.rglob("*.cpp"))

    for tu in sorted(set(translation_units)):
        rel = tu.relative_to(root)
        output_obj = clang_build_dir / rel.with_suffix(".o")
        output_obj.parent.mkdir(parents=True, exist_ok=True)
        command = (
            [str(compiler)]
            + cxx_flags
            + defines
            + includes
            + ["-c", str(tu), "-o", str(output_obj)]
        )
        compile_db.append(
            {
                "directory": str(root),
                "file": str(tu),
                "output": str(output_obj),
                "command": " ".join(shlex.quote(part) for part in command),
            }
        )

    output_path = root / args.output
    output_path.write_text(json.dumps(compile_db, indent=2))


if __name__ == "__main__":
    main()
