"""Classifier tests: fail-closed on unknown/real error types + coverage.

Run with:  python3 -m unittest tools.nudge_lib.tests.test_classify -v
(or from the repo root: python3 -m unittest discover -s tools/nudge-lib/tests -v)
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)  # tools/nudge-lib
if LIB not in sys.path:
    sys.path.insert(0, LIB)
REPO_ROOT = os.path.abspath(os.path.join(LIB, "..", ".."))

import classify  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_real_incomplete_types(self):
        # The obsolete `not_connected_error` is gone; current checks emit these.
        elems = [
            {"type": "pcb_port_not_connected_error", "message": "x"},
            {"type": "pcb_trace_missing_error", "message": "x"},
        ]
        r = classify.analyze(elems)
        self.assertEqual(r["classes"]["incomplete"], 2)
        self.assertEqual(r["score"], (0, 0, 2))
        self.assertFalse(classify.is_solved(r))

    def test_placement_error_is_placement(self):
        # `placement_error` no longer exists; the current type is `pcb_placement_error`.
        r = classify.analyze([{"type": "pcb_placement_error", "message": "x"}])
        self.assertEqual(r["classes"]["placement"], 1)
        self.assertEqual(r["score"], (0, 1, 0))
        self.assertFalse(classify.is_solved(r))

    def test_component_outside_board_is_placement(self):
        r = classify.analyze([{"type": "pcb_component_outside_board_error", "message": "x"}])
        self.assertEqual(r["classes"]["placement"], 1)

    def test_unknown_fails_closed(self):
        # An unrecognized *_error type must be counted, never silently dropped.
        r = classify.analyze([{"type": "pcb_brand_new_error", "message": "x"}])
        self.assertEqual(r["classes"]["unknown"], 1)
        self.assertEqual(r["score"], (0, 1, 0))
        self.assertFalse(classify.is_solved(r))

    def test_broken_not_solved_even_with_clean_score(self):
        # Only a broken (source-bug) error: score is (0,0,0) but broken is set.
        r = classify.analyze([{"type": "pcb_missing_footprint_error", "message": "x"}])
        self.assertEqual(r["score"], (0, 0, 0))
        self.assertTrue(r["broken"])
        self.assertFalse(classify.is_solved(r))

    def test_clean_is_solved(self):
        r = classify.analyze([{"type": "pcb_component", "pcb_component_id": "x"}])
        self.assertTrue(classify.is_solved(r))

    def test_is_solved_accepts_bare_tuple(self):
        self.assertTrue(classify.is_solved((0, 0, 0)))
        self.assertFalse(classify.is_solved((0, 1, 0)))

    def test_coverage_complete(self):
        self.assertEqual(classify.check_coverage(), [])

    def test_known_types_count(self):
        # circuit-json@0.0.479 declares exactly 30 *_error types.
        self.assertEqual(len(classify.KNOWN_ERROR_TYPES), 30)

    def test_plated_hole_id_resolves_component(self):
        elems = [
            {"type": "source_component", "source_component_id": "sc_R1", "name": "R1"},
            {"type": "pcb_component", "pcb_component_id": "pc_R1", "source_component_id": "sc_R1"},
            {"type": "pcb_plated_hole", "pcb_plated_hole_id": "ph_1", "pcb_component_id": "pc_R1"},
            {"type": "pcb_pad_trace_clearance_error", "pcb_plated_hole_id": "ph_1", "message": "x"},
        ]
        r = classify.analyze(elems)
        self.assertEqual(r["implicated"], {"R1": 1})


class TestCoverageAgainstInstalledSchema(unittest.TestCase):
    """Cross-check the mapping against the installed circuit-json error union."""

    def test_schema_error_types_are_all_mapped(self):
        schema = os.path.join(
            REPO_ROOT, "ts-modules", "node_modules", "circuit-json", "dist", "index.d.mts")
        if not os.path.exists(schema):
            self.skipTest("circuit-json schema not installed")
        with open(schema, encoding="utf-8") as fh:
            text = fh.read()
        found = {t[1:-1] for t in re.findall(r'"[a-z][a-z0-9_]*_error"', text)}
        # Every `*_error` type declared by the installed schema must be mapped.
        self.assertEqual(found, set(classify.KNOWN_ERROR_TYPES),
                         "schema error types diverge from classify.KNOWN_ERROR_TYPES")
        # And every mapped type must classify to a real class (not unknown/None).
        self.assertEqual(classify.check_coverage(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
