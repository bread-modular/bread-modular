"""Verify shared project footprint libraries using KiCad's Python loader.

/usr/bin/python3 tests/check_kicad_libraries.py [--drc]
Requires pcbnew; --drc also runs kicad-cli on every board and checks shared
library resolution errors, reporting global-library issues separately. Reports live
in a temporary directory and PCB/project files are never rewritten.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import tempfile

import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drc", action="store_true")
    args = parser.parse_args()
    projects = [ROOT / p for p in subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z", "*.kicad_pro"], text=True
    ).split("\0") if p]
    assert projects, "No projects found"
    entries = re.findall(
        r'\(lib \(name "([^"]+)"\)\(type "KiCad"\)\(uri "([^"]+)"\)',
        (ROOT / "opt/fp-lib-table").read_text(),
    )
    assert entries and len(dict(entries)) == len(entries), "Missing or duplicate libraries"
    loaded = references = 0
    for project in projects:
        directory = project.parent
        for filename, target in [("fp-lib-table", "opt/fp-lib-table"),
                                 ("footprints", "opt/footprints")]:
            link = directory / filename
            assert link.is_symlink() and not Path(link.readlink()).is_absolute(), link
            assert link.resolve(strict=True) == ROOT / target, link
        names = {}
        for name, uri in entries:
            path = Path(uri.replace("${KIPRJMOD}", str(directory)))
            assert path.is_dir(), (project, name, path)
            assert path.resolve().is_relative_to(ROOT / "opt"), path
            names[name] = set(pcbnew.FootprintEnumerate(str(path)))
            assert names[name], (project, name, "empty library")
            for footprint in names[name]:
                assert pcbnew.FootprintLoad(str(path), footprint), (project, name, footprint)
                loaded += 1
        # Retain the nicknames already used by the boards AND schematics.
        for suffix in (".kicad_pcb", ".kicad_sch"):
            design = project.with_suffix(suffix)
            if not design.exists():
                continue
            for value in re.findall(
                r'\((?:footprint|property\s+"Footprint")\s+"([^"\n]+)"',
                design.read_text(),
            ):
                library, _, name = value.partition(":")
                if library.startswith("BreadModular_") or library in names:
                    assert name in names.get(library, set()), (design, value)
                    references += 1
    print(f"PASS: {len(projects)} projects, {len(entries)} libraries, "
          f"{loaded} KiCad footprint loads, {references} custom footprint references.")

    if args.drc:
        cli_version = subprocess.check_output(["kicad-cli", "--version"], text=True).strip()
        cli_major = int(cli_version.split(".")[0])
        compatible = []
        for project in projects:
            board = project.with_suffix(".kicad_pcb")
            if not board.exists():
                print(f"SKIP board DRC: {project.relative_to(ROOT)} has no PCB; library loads passed.")
                continue
            match = re.search(r'\(generator_version "(\d+)\.[^"]*"\)', board.read_text())
            if match and int(match[1]) > cli_major:
                print(f"SKIP board DRC: {project.relative_to(ROOT)} needs newer KiCad "
                      f"(generator {match[1]}, installed {cli_version}); library loads passed.")
            else:
                compatible.append(project)
        with tempfile.TemporaryDirectory(prefix="kicad-library-check-") as temp:
            def check(project):
                board = project.with_suffix(".kicad_pcb")
                assert board.exists(), board
                report = Path(temp) / ("__".join(project.relative_to(ROOT).parts) + ".json")
                result = subprocess.run(
                    ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                     "-o", str(report), str(board)],
                    capture_output=True, text=True, timeout=180,
                )
                assert result.returncode == 0, (board, result.stdout, result.stderr)
                data = json.loads(report.read_text())
                issues = [v for v in data["violations"] if v["type"] == "lib_footprint_issues"]
                shared_issues = [v for v in issues if any(
                    f"'{name}'" in v["description"] for name, _ in entries
                )]
                assert not shared_issues, (board, shared_issues)
                return str(project.relative_to(ROOT)), issues

            global_issues = 0
            with ThreadPoolExecutor(max_workers=2) as pool:
                for result, issues in pool.map(check, compatible):
                    print(f"PASS KiCad shared-library resolution: {result}")
                    for issue in issues:
                        print(f"  NOTE global library: {issue['description']}")
                        global_issues += 1
        print(f"PASS: KiCad DRC reported no missing/unloadable shared footprint libraries "
              f"on {len(compatible)}/{len(projects)} compatible boards.")
        if global_issues:
            print(f"NOTE: {global_issues} global-library footprint issues remain outside the shared opt libraries.")


if __name__ == "__main__":
    main()
