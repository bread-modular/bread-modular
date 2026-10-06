from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kicad_tools import parser
from native import Error
from project import Plan, new_output, select_project
from fixtures import create_project, snapshot


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="portable project tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = create_project(self.root)

    def selection(self, *extra):
        return select_project(parser().parse_args(["doctor", "--project-dir", str(self.project), *extra]))

    def test_shallow_selection_and_repeated_hierarchy_dependency_closure(self):
        hidden = self.project / ".history"
        hidden.mkdir()
        (hidden / "broken.kicad_pcb").write_text("malformed ignored history")
        for name in ("code", "vendor"):
            (self.project / name).mkdir()
            (self.project / name / "unused.kicad_sch").write_text("malformed ignored")
        plan = Plan(self.selection())
        self.assertEqual(len(plan.sheets), 2)
        self.assertEqual(len(plan.files), 9)
        self.assertNotIn(hidden / "broken.kicad_pcb", plan.files)
        self.assertIn(self.project / "gadget.kicad_dru", plan.files)
        (self.project / "other.kicad_pcb").write_text("(kicad_pcb)")
        with self.assertRaises(Error):
            self.selection()
        self.assertEqual(self.selection("--board", "gadget.kicad_pcb").board.name, "gadget.kicad_pcb")

    def test_manifest_paths_are_relative_to_config_not_cwd(self):
        config = self.root / "profile.json"
        config.write_text(json.dumps({"schema_version": 1, "project_dir": "Synthetic project", "board": "Synthetic project/gadget.kicad_pcb",
                                      "root_schematic": "Synthetic project/gadget.kicad_sch", "dependencies": ["Synthetic project/Test.pretty"]}))
        args = parser().parse_args(["doctor", "--config", str(config)])
        self.assertEqual(Plan(select_project(args)).project.board, self.project / "gadget.kicad_pcb")
        for data in ({"schema_version": 99}, {"schema_version": True}, {"schema_version": 1, "extra": "typo"}):
            config.write_text(json.dumps(data))
            with self.assertRaises(Error):
                select_project(args)

    def test_missing_sheet_cycle_and_missing_variable_fail_before_writes(self):
        leaf = self.project / "sheets with spaces/child.kicad_sch"
        leaf.unlink()
        with self.assertRaisesRegex(Error, "Unresolved"):
            Plan(self.selection())
        leaf.write_text('(kicad_sch (sheet (property "Sheetfile" "../gadget.kicad_sch")))')
        with self.assertRaisesRegex(Error, "Cyclic"):
            Plan(self.selection())
        leaf.write_text('(kicad_sch (sheet (property "Sheetfile" "${MISSING_TOOLKIT_VARIABLE}/x.kicad_sch")))')
        with self.assertRaisesRegex(Error, "variable"):
            Plan(self.selection())

    def test_regular_and_symlink_tables_are_equally_accepted(self):
        normal = Plan(self.selection())
        table = self.project / "fp-lib-table"
        source = self.root / "external-fp-lib-table"
        table.rename(source)
        table.symlink_to(source)
        plan = Plan(self.selection())
        self.assertEqual(len(normal.files), len(plan.files))
        source.unlink()
        with self.assertRaisesRegex(Error, "Unresolved"):
            Plan(self.selection())

    def test_missing_library_nonlocal_plugin_and_unbounded_directory_fail(self):
        table = self.project / "fp-lib-table"
        for uri, kind in (("${KIPRJMOD}/missing.pretty", "KiCad"), ("https://example.invalid/library", "KiCad"), ("${KIPRJMOD}/Test.pretty", "Github")):
            with self.subTest(uri=uri, kind=kind):
                table.write_text(f'(fp_lib_table (lib (name "X") (type "{kind}") (uri "{uri}")))')
                with self.assertRaises(Error):
                    Plan(self.selection())
        table.unlink()
        plan = Plan(self.selection())
        with self.assertRaisesRegex(Error, "explicit .pretty"):
            plan.dependency(self.project)
        with mock.patch("project.MAX_FILES", 1):
            with self.assertRaisesRegex(Error, "bound"):
                Plan(self.selection())

    def test_private_stage_copies_rules_and_libraries_no_source_links(self):
        before = snapshot(self.project)
        plan = Plan(self.selection())
        with tempfile.TemporaryDirectory(prefix="private stage ") as temp:
            board, sch, changes = plan.stage(Path(temp))
            self.assertTrue(changes)
            self.assertFalse(any(p.is_symlink() for p in Path(temp).rglob("*")))
            for suffix in (".kicad_pcb", ".kicad_dru", ".kicad_pro"):
                self.assertEqual(board.with_suffix(suffix).read_bytes(), (self.project / ("gadget" + suffix)).read_bytes())
            board.write_text("native write stays private")
            (board.parent / "Test.pretty/R.kicad_mod").write_text("private lib mutation")
        self.assertEqual(snapshot(self.project), before)
        plan.verify_sources(plan.snapshot())

    def test_external_absolute_dependencies_rebound_in_staged_copies_only(self):
        root = self.root / "external test"
        project = create_project(root, external_sheet=True, absolute_paths=True)
        args = parser().parse_args(["doctor", "--project-dir", str(project)])
        plan = Plan(select_project(args))
        before = snapshot(root)
        with tempfile.TemporaryDirectory(prefix="external stage ") as temp:
            board, schematic, _ = plan.stage(Path(temp))
            text = schematic.read_text()
            self.assertNotIn(str(root), text)
            self.assertIn(str(Path(temp)), text)
            self.assertNotIn(str(root), (board.parent / "fp-lib-table").read_text())
        self.assertEqual(snapshot(root), before)

    def test_reports_refuse_sources_overwrite_and_symlink_alias(self):
        plan = Plan(self.selection())
        for output in (self.project / "results", self.project / "gadget.kicad_pcb", self.project / "Test.pretty/results"):
            with self.assertRaises(Error):
                new_output(output, plan)
        alias = self.root / "source alias"
        alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(Error):
            new_output(alias / "oops", plan)
        fresh = self.root / "separate reports"
        self.assertEqual(new_output(fresh, plan), fresh)
        self.assertFalse(fresh.exists())

    def test_invalid_project_variables_and_dependency_tree_fail_cleanly(self):
        pro = self.project / "gadget.kicad_pro"
        for data in ([], {"text_variables": []}, {"text_variables": {"NUMBER": 1}}):
            with self.subTest(data=data):
                pro.write_text(json.dumps(data))
                with self.assertRaisesRegex(Error, "project JSON"):
                    Plan(self.selection())
        pro.write_text("{}")
        native = self.project / "vendor/local.kicad_sym"
        native.parent.mkdir()
        native.write_text("(kicad_symbol_lib)")
        plan = Plan(self.selection())
        with self.assertRaisesRegex(Error, "history/code/vendor"):
            plan.dependency(native)

    def test_empty_native_roots_fail_with_actionable_errors(self):
        for filename in ("gadget.kicad_pcb", "gadget.kicad_sch", "fp-lib-table"):
            path = self.project / filename
            old = path.read_bytes()
            path.write_text("()")
            with self.subTest(filename=filename), self.assertRaises(Error):
                Plan(self.selection())
            path.write_bytes(old)

    def test_source_hash_change_is_detected(self):
        plan = Plan(self.selection())
        before = plan.snapshot()
        (self.project / "gadget.kicad_dru").write_text("changed rule")
        with self.assertRaisesRegex(Error, "SOURCE CHANGED"):
            plan.verify_sources(before)


if __name__ == "__main__":
    unittest.main()
