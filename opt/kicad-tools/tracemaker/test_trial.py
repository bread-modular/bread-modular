"""Unit tests for trusted preparation and raw-data rejection, no engine required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import trial as t
import validate as v

BASE = '''(kicad_pcb (version 20240108) (net 0 "") (net 1 "SIG") (net 2 "OTHER")
(footprint "lib:a" (uuid "fp") (at 1 2 90) (layer "B.Cu")
 (property "Reference" "RV1 (pot)" (uuid "field"))
 (pad "1" smd custom (uuid "pad") (net 1 "SIG") (primitives (gr_poly (pts (xy 0 0))))))
(segment (start 1 1) (end 2 2) (width 0.2) (layer "F.Cu") (net 1) (uuid "track"))
(segment (start 2 2) (end 3 3) (width 0.2) (layer "F.Cu") (net 2) (uuid "other"))
(via (at 2 3) (size 4) (drill 3.2) (layers "F.Cu" "B.Cu") (net 0) (uuid "hole")))'''
NEW = '(segment (start 2 2) (end 3 3) (width 0.2) (layer "B.Cu") (net 1) (uuid "new"))'
VIA = '(via (at 2 2) (size 0.7) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1) (uuid "new-via"))'


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / "before.kicad_pcb"; self.a.write_text(BASE)
        self.b = self.root / "after.kicad_pcb"

    def compare(self, text, nets=("SIG",)):
        self.b.write_text(text)
        return t.compare(self.a, self.b, nets)

    def test_quoted_parentheses_and_noop(self):
        self.assertEqual(len(t.nodes(BASE)), 8)
        self.assertTrue(self.compare(BASE)["passed"])

    def test_add_only_authorized_copper(self):
        self.assertTrue(self.compare(BASE[:-1] + NEW + VIA + ")")["passed"])
        self.assertFalse(self.compare(BASE[:-1] + NEW.replace('(net 1)', '(net 2)') + ")")["passed"])
        self.assertFalse(self.compare(BASE[:-1] + NEW + ")", ())["passed"])

    def test_never_remove_mechanics_or_other_copper(self):
        for n in t.nodes(BASE):
            self.assertFalse(self.compare(BASE[:n[0]] + BASE[n[1]:])["passed"])

    def test_reject_position_side_pad_or_custom_geometry_change(self):
        for old, new in [('(at 1 2 90)', '(at 1 3 90)'), ('(layer "B.Cu")', '(layer "F.Cu")'),
                         ('(net 1 "SIG")', '(net 2 "OTHER")'), ('(xy 0 0)', '(xy 1 0)')]:
            self.assertFalse(self.compare(BASE.replace(old, new))["passed"])

    def test_minimum_vias_and_unique_nested_uuids(self):
        for via in [VIA.replace('0.7', '0.6'), VIA.replace('0.3', '0.2'),
                    VIA.replace('"B.Cu"', '"In1.Cu"'), VIA.replace('"new-via"', '"pad"')]:
            self.assertFalse(self.compare(BASE[:-1] + via + ")")["passed"])

    def test_malformed_board(self):
        for text in [BASE[:-1], BASE + ")", '(other (version 1))']:
            with self.assertRaises(ValueError):
                t.nodes(text)

    def test_frozen_changes_and_symlinks_fail(self):
        f = self.root / "frozen"; f.mkdir(); (f / "a").write_text("data"); t.seal(f)
        self.assertTrue(t.frozen(f))
        (f / "a").write_text("change")
        with self.assertRaises(ValueError): t.frozen(f)
        (f / "link").symlink_to(self.a)
        with self.assertRaises(ValueError): t.seal(f)

    def test_strip_records_exact_uuid_only(self):
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(BASE); t.seal(f)
        out = self.root / "stripped"
        m = t.strip(f, "board.kicad_pcb", out, ["SIG"])
        self.assertEqual([x["uuid"] for x in m["removed_segments"]], ["track"])
        self.assertEqual(m["removed_vias"], [])
        self.assertIn('(uuid "hole")', (out / "board.kicad_pcb").read_text())
        self.assertEqual((f / "board.kicad_pcb").read_text(), BASE)

    def assert_strip_rejected_without_writes(self, frozen, pcb_name, output):
        before = {str(p.relative_to(self.root)): p.read_bytes() if p.is_file() else None
                  for p in self.root.rglob("*")}
        with patch.object(t, "fresh", side_effect=AssertionError("must not create output")), \
             patch.object(Path, "write_text", side_effect=AssertionError("must not write")):
            with self.assertRaises(ValueError):
                t.strip(frozen, pcb_name, output, ["SIG"])
        self.assertFalse(output.exists())
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() if p.is_file() else None
                                  for p in self.root.rglob("*")})

    def test_strip_rejects_invalid_pcb_names_before_reads_or_writes(self):
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(BASE)
        (f / "nested").mkdir(); (f / "nested/board.kicad_pcb").write_text(BASE)
        (f / "board.txt").write_text(BASE); t.seal(f)
        names = [str(self.a), "../before.kicad_pcb", "nested/board.kicad_pcb",
                 "missing.kicad_pcb", "board.txt"]
        for i, name in enumerate(names):
            with self.subTest(name=name), \
                 patch.object(t, "frozen", side_effect=AssertionError("must validate before reads")), \
                 patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
                self.assert_strip_rejected_without_writes(f, name, self.root / f"denied-{i}")

    def test_shared_pcb_validation_for_run_and_check(self):
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(BASE); t.seal(f)
        before = t.tree(self.root)
        for name in [str(self.a), "../before.kicad_pcb", "nested/board.kicad_pcb", "missing.kicad_pcb"]:
            with self.subTest(name=name), \
                 patch.object(t, "sha", side_effect=AssertionError("must validate before reads")), \
                 patch.object(t, "frozen", side_effect=AssertionError("must validate before reads")), \
                 patch.object(t, "fresh", side_effect=AssertionError("must not create output")):
                with self.assertRaises(ValueError):
                    t.run(f, name, self.root / "run-denied", "unused-engine", "unused-digest", "unused-deps")
                with self.assertRaises(ValueError):
                    v.check(f, name, self.root / "check-denied")
        self.assertEqual(before, t.tree(self.root))
        self.assertFalse((self.root / "run-denied").exists())
        self.assertFalse((self.root / "check-denied").exists())

    def test_strip_rejects_locked_selected_segments(self):
        for i, lock in enumerate(["locked", "(locked)", "(locked yes)"]):
            with self.subTest(lock=lock):
                f = self.root / f"frozen-{i}"; f.mkdir()
                (f / "board.kicad_pcb").write_text(BASE.replace('(uuid "track")', f'{lock} (uuid "track")'))
                t.seal(f)
                self.assert_strip_rejected_without_writes(f, "board.kicad_pcb", self.root / f"denied-{i}")

    def test_strip_rejects_selected_segments_in_any_group(self):
        for i, lock in enumerate(["", "(locked yes)", "(locked no)"]):
            with self.subTest(lock=lock):
                f = self.root / f"frozen-{i}"; f.mkdir()
                groups = ('(group "unrelated" (id "first") (members "other"))'
                          f'(group "inner" (id "inner") {lock} (members "track"))'
                          '(group "outer" (id "outer") (members "inner"))')
                (f / "board.kicad_pcb").write_text(BASE[:-1] + groups + ")")
                t.seal(f)
                self.assert_strip_rejected_without_writes(f, "board.kicad_pcb", self.root / f"denied-{i}")

    def test_strip_preserves_unselected_locked_grouped_segments(self):
        text = BASE.replace('(uuid "other")', '(locked yes) (uuid "other")')
        text = text[:-1] + '(group "other" (id "group") (members "other"))' + ")"
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(text); t.seal(f)
        out = self.root / "stripped"; result = t.strip(f, "board.kicad_pcb", out, ["SIG"])
        self.assertEqual([x["uuid"] for x in result["removed_segments"]], ["track"])
        self.assertEqual((f / "board.kicad_pcb").read_text(), text)
        remaining = [n[2] for n in t.nodes((out / "board.kicad_pcb").read_text())]
        for node in t.nodes(text):
            if t.child(node[3], "uuid") != ["track"]:
                self.assertIn(node[2], remaining)

    def test_strip_allows_explicitly_unlocked_selected_segment(self):
        f = self.root / "frozen"; f.mkdir()
        text = BASE.replace('(uuid "track")', '(locked no) (uuid "track")')
        (f / "board.kicad_pcb").write_text(text); t.seal(f)
        out = self.root / "stripped"; result = t.strip(f, "board.kicad_pcb", out, ["SIG"])
        self.assertEqual([x["uuid"] for x in result["removed_segments"]], ["track"])
        self.assertEqual((f / "board.kicad_pcb").read_text(), text)

    def test_symlink_library_boundary(self):
        project = self.root / "project"; project.mkdir(); pcb = project / "b.kicad_pcb"; pcb.write_text(BASE)
        lib = self.root / "trusted"; lib.mkdir(); pretty = lib / "lib.pretty"; pretty.mkdir()
        (pretty / "a.kicad_mod").write_text('(footprint "a")')
        (project / "footprints").symlink_to(lib)
        with self.assertRaises(ValueError): t.freeze(pcb, self.root / "deny")
        good = self.root / "good"; t.freeze(pcb, good, lib)
        self.assertFalse((good / "footprints").is_symlink())
        self.assertEqual((good / "footprints/lib.pretty/a.kicad_mod").read_text(), '(footprint "a")')

    def test_output_alias_or_existing_rejected(self):
        with self.assertRaises(ValueError): t.fresh(self.a)
        with self.assertRaises(ValueError): t.fresh(self.root / "nested", self.root)

    def test_native_rejects_raw_mutation_before_invoking_anything(self):
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(BASE); t.seal(f)
        self.b.write_text(BASE.replace('(at 1 2 90)', '(at 1 3 90)'))
        with patch.object(t, "bounded", side_effect=AssertionError("must not invoke native")):
            with self.assertRaises(ValueError): v.check(f, "board.kicad_pcb", self.root / "rejected", self.b)

    def test_diagnostic_fingerprints_preserve_severity_exclusion_and_identity(self):
        a = {"violations": [{"type": "warning", "severity": "warning", "items": [{"uuid": "pad"}]}]}
        b = json.loads(json.dumps(a)); b["date"] = "different"
        self.assertEqual(v.fingerprints(a), v.fingerprints(b))
        b["violations"][0]["items"][0]["uuid"] = "other"
        self.assertNotEqual(v.fingerprints(a), v.fingerprints(b))


if __name__ == "__main__":
    unittest.main()
