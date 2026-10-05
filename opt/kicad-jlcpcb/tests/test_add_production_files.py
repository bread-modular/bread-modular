"""Dependency-free unit tests and opt-in real KiCad integration tests for add_production_files.py.

Unit tests never touch a real module; integration tests are skipped unless
KICAD_JLCPCB_INTEGRATION=1 and write only into a temporary --jlcpcb-root.
"""

import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "add_production_files.py"
REPO = SCRIPT.parents[2]
spec = importlib.util.spec_from_file_location("jlc_production", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def arguments(*extra):
    return tool.argument_parser().parse_args([*extra])


def write_board(directory, stem):
    path = Path(directory) / f"{stem}.kicad_pcb"
    path.write_text("(kicad_pcb (version 20241229) (generator \"pcbnew\"))\n", encoding="utf-8")
    return path


def archive(path, names=("demo-F_Cu.gbr", "demo-B_Cu.gbr", "demo-PTH.drl"), extra=None):
    path = Path(path)
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            zf.writestr(name, f"payload {name}\n")
        for name, data in (extra or []):
            zf.writestr(name, data)
    return path


class ModuleResolution(unittest.TestCase):
    def test_directory_file_and_module_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = write_board(tmp, "demo")
            self.assertEqual(tool.module_dir_for(tmp), Path(tmp).resolve())
            self.assertEqual(tool.module_dir_for(board), Path(tmp).resolve())
        self.assertEqual(tool.module_dir_for("base"), REPO / "modules" / "base")

    def test_rejects_unknown_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "notes.txt"
            other.write_text("x", encoding="utf-8")
            with self.assertRaises(tool.ToolError):
                tool.module_dir_for(other)
        with self.assertRaises(tool.ToolError):
            tool.module_dir_for("no_such_module_9f3a")


class BoardSelection(unittest.TestCase):
    def test_discovery_ignores_autosave_and_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_board(tmp, "demo")
            write_board(tmp, "_autosave-demo")
            write_board(tmp, "demo-save")
            (Path(tmp) / "~demo.kicad_pcb").write_text("", encoding="utf-8")
            self.assertEqual([p.name for p in tool.discover_boards(Path(tmp))], ["demo.kicad_pcb"])

    def test_single_board_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = write_board(tmp, "demo")
            self.assertEqual(tool.select_boards(Path(tmp), arguments()), [board])

    def test_ambiguity_requires_board_or_all_boards(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_board(tmp, "alpha")
            write_board(tmp, "beta")
            with self.assertRaises(tool.ToolError):
                tool.select_boards(Path(tmp), arguments())
            self.assertEqual(len(tool.select_boards(Path(tmp), arguments("--all-boards"))), 2)
            self.assertEqual([p.name for p in tool.select_boards(Path(tmp), arguments("--board", "beta"))],
                             ["beta.kicad_pcb"])
            self.assertEqual([p.name for p in tool.select_boards(Path(tmp), arguments("--board", "alpha.kicad_pcb"))],
                             ["alpha.kicad_pcb"])
            with self.assertRaises(tool.ToolError):
                tool.select_boards(Path(tmp), arguments("--board", "gamma"))

    def test_empty_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(tool.ToolError):
                tool.select_boards(Path(tmp), arguments())


class Mirroring(unittest.TestCase):
    def test_mirrors_archive_and_prunes_only_stale_board_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jlcpcb"
            gerber = root / "gerber"
            gerber.mkdir(parents=True)
            (gerber / "demo-Old.gbr").write_text("stale", encoding="utf-8")
            (gerber / "demo-PTH-drl_map.pdf").write_text("legacy map", encoding="utf-8")
            (gerber / "other.gbr").write_text("unrelated", encoding="utf-8")
            source = archive(Path(tmp) / "demo-gerbers.zip")

            result = tool.mirror_gerbers(source, root, "demo")

            self.assertEqual(result["pruned"], ["demo-Old.gbr"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             hashlib.sha256(result["upload_copy"].read_bytes()).hexdigest())
            self.assertEqual(result["upload_copy"].name, "GERBER-demo.zip")
            self.assertEqual(sorted(p.name for p in gerber.iterdir()),
                             ["demo-B_Cu.gbr", "demo-F_Cu.gbr", "demo-PTH-drl_map.pdf", "demo-PTH.drl", "other.gbr"])

    def test_keep_stale_gerbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jlcpcb"
            (root / "gerber").mkdir(parents=True)
            (root / "gerber" / "demo-Old.gbr").write_text("stale", encoding="utf-8")
            source = archive(Path(tmp) / "demo-gerbers.zip")
            tool.mirror_gerbers(source, root, "demo", prune=False)
            self.assertTrue((root / "gerber" / "demo-Old.gbr").is_file())

    def test_dry_run_prune_keeps_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            gerber = Path(tmp)
            (gerber / "demo-Old.gbr").write_text("stale", encoding="utf-8")
            removed = tool.prune_stale_gerbers(gerber, "demo", keep=set(), dry_run=True)
            self.assertEqual(removed, ["demo-Old.gbr"])
            self.assertTrue((gerber / "demo-Old.gbr").is_file())

    def test_rejects_foreign_members_and_missing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = archive(Path(tmp) / "nested.zip", names=("sub/demo-F_Cu.gbr",))
            with self.assertRaises(tool.ToolError):
                tool.mirror_gerbers(nested, Path(tmp) / "jlcpcb", "demo")
            foreign = archive(Path(tmp) / "foreign.zip", extra=[("notes.txt", "x")])
            with self.assertRaises(tool.ToolError):
                tool.mirror_gerbers(foreign, Path(tmp) / "jlcpcb", "demo")
            empty = Path(tmp) / "empty.zip"
            with zipfile.ZipFile(empty, "w"):
                pass
            with self.assertRaises(tool.ToolError):
                tool.mirror_gerbers(empty, Path(tmp) / "jlcpcb", "demo")
            with self.assertRaises(tool.ToolError):
                tool.mirror_gerbers(Path(tmp) / "absent.zip", Path(tmp) / "jlcpcb", "demo")


class CommandLine(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_board(tmp, "demo")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = tool.main([tmp, "--dry-run"])
            self.assertEqual(status, 0)
            self.assertIn("[dry-run] demo.kicad_pcb", out.getvalue())
            self.assertFalse((Path(tmp) / "jlcpcb").exists())
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["demo.kicad_pcb"])

    def test_all_takes_no_targets(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tool.main(["--all", "base"]), 1)

    def test_unknown_target_fails_without_starting_the_exporter(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tool.main(["no_such_module_9f3a"]), 1)

    def test_exporter_arguments_honour_flags(self):
        plan = {"module": Path("/module"), "board": Path("/module/demo.kicad_pcb"), "output": Path("/out/demo")}
        self.assertIn("--require-part-numbers", tool.export_arguments(plan, arguments()))
        relaxed = tool.export_arguments(plan, arguments("--allow-missing-part-numbers"))
        self.assertNotIn("--require-part-numbers", relaxed)
        self.assertIn("--pcb-only", tool.export_arguments(plan, arguments("--pcb-only")))
        self.assertIn("root.kicad_sch", tool.export_arguments(plan, arguments("--schematic", "root.kicad_sch")))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            arguments("--pcb-only", "--schematic", "root.kicad_sch")


@unittest.skipUnless(os.environ.get("KICAD_JLCPCB_INTEGRATION"),
                     "set KICAD_JLCPCB_INTEGRATION=1 to run real kicad-cli exports")
class Integration(unittest.TestCase):
    def test_exports_a_real_module_into_a_temporary_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                status = tool.main(["base", "--allow-missing-part-numbers", "--jlcpcb-root", tmp])
            self.assertEqual(status, 0, out.getvalue())
            root = Path(tmp)
            package = root / "base"
            archive_path = package / "base-gerbers.zip"
            self.assertTrue(archive_path.is_file())
            self.assertTrue((package / "bom.csv").is_file())
            self.assertTrue((package / "positions.csv").is_file())
            self.assertTrue((package / "export-report.json").is_file())
            upload = root / "production_files" / "GERBER-base.zip"
            self.assertEqual(hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                             hashlib.sha256(upload.read_bytes()).hexdigest())
            loose = sorted(p.name for p in (root / "gerber").iterdir())
            with zipfile.ZipFile(archive_path) as zf:
                self.assertEqual(sorted(zf.namelist()), loose)
            json_report = (package / "export-report.json").read_text(encoding="utf-8")
            self.assertIn("source_sha256", json_report)


if __name__ == "__main__":
    unittest.main()
