"""Search driver tests: `max_iters` is a hard TOTAL build cap across all phases.

Run with:  python3 -m unittest tools.nudge_lib.tests.test_search -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import search  # noqa: E402


def _harness(strategy, max_iters):
    calls = {"builds": 0}
    positions = {
        "C1": {"pcbX": {"value": 0.0}, "pcbY": {"value": 0.0}},
        "C2": {"pcbX": {"value": 0.0}, "pcbY": {"value": 0.0}},
    }
    config = {
        "components": {
            "C1": {"axes": ["x", "y"], "step": 0.4},
            "C2": {"axes": ["x", "y"], "step": 0.4},
        },
        "search": {"maxIterations": 1000},
    }

    def splice(content, pos, name, axis, value):
        return content

    def write(content):
        pass

    def build_score():
        calls["builds"] += 1
        # Always non-solved and non-broken so the search keeps evaluating.
        return {"score": (0, 1, 0), "broken": False,
                "classes": {"unknown": 0}, "implicated": {"C1": 1}}

    def relocate():
        return positions

    result = search.run_search(
        config,
        b"initial",
        positions,
        build_score(),  # initial_analysis (one build, outside the search budget)
        write,
        build_score,
        relocate,
        splice,
        strategy=strategy,
        max_iters=max_iters,
    )
    return calls, result


class TestBuildBudget(unittest.TestCase):
    def test_greedy_capped(self):
        calls, result = _harness("greedy", max_iters=5)
        self.assertEqual(result["builds"], 5)          # hit the cap exactly
        self.assertLessEqual(result["builds"], 5)
        self.assertFalse(result["solved"])

    def test_grid_capped(self):
        # grid used to evaluate the whole neighborhood in one pass, blowing the cap.
        calls, result = _harness("grid", max_iters=5)
        self.assertEqual(result["builds"], 5)
        self.assertLessEqual(result["builds"], 5)

    def test_random_capped(self):
        calls, result = _harness("random", max_iters=5)
        self.assertLessEqual(result["builds"], 5)
        self.assertEqual(result["builds"], 5)

    def test_cap_zero_builds_when_already_solved(self):
        def build_score():
            raise AssertionError("should not build when baseline is already clean")

        positions = {"C1": {"pcbX": {"value": 0.0}, "pcbY": {"value": 0.0}}}
        config = {"components": {"C1": {"axes": ["x"], "step": 0.4}},
                  "search": {}}
        clean = {"score": (0, 0, 0), "broken": False,
                 "classes": {"unknown": 0}, "implicated": {}}
        result = search.run_search(
            config, b"x", positions, clean,
            lambda c: None, build_score, lambda: positions,
            lambda c, p, n, a, v: c,
            strategy="greedy", max_iters=10)
        self.assertEqual(result["builds"], 0)
        self.assertTrue(result["solved"])
        self.assertTrue(result["early_exit"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
