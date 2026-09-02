"""CLI tests: path-traversal rejection, apply whitelist safety, rollback, restore.

Run with:  python3 -m unittest tools.nudge_lib.tests.test_cli -v
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
TOOLS = os.path.dirname(LIB)
if LIB not in sys.path:
    sys.path.insert(0, LIB)
CLI_PATH = os.path.join(TOOLS, "nudge")


def _load_cli():
    spec = importlib.util.spec_from_loader(
        "nudge_cli", importlib.machinery.SourceFileLoader("nudge_cli", CLI_PATH))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


cli = _load_cli()


def _sha(b):
    return hashlib.sha256(b).hexdigest()


class ResolveModuleTest(unittest.TestCase):
    def test_rejects_traversal_values(self):
        for bad in ["../evil", "/abs/path", "a/b", "a\\b", "a..b", "..", ".", "", "8bit/../drive"]:
            with self.assertRaises(cli.NudgeError, msg=f"module {bad!r} should be rejected"):
                cli.resolve_module(bad)

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "ts-modules" / "src"
            src.mkdir(parents=True)
            outside = root / "outside"
            outside.mkdir()
            (src / "evil").symlink_to(outside, target_is_directory=True)
            old = cli.TS_MODULES
            cli.TS_MODULES = root / "ts-modules"
            try:
                with self.assertRaises(cli.NudgeError):
                    cli.resolve_module("evil")
            finally:
                cli.TS_MODULES = old


class ValidateConfigTest(unittest.TestCase):
    def test_entry_traversal_rejected(self):
        for entry in ["../evil.tsx", "/abs.tsx", "a/b.tsx", "..", ".", "a..b.tsx"]:
            with self.assertRaises(cli.NudgeError, msg=f"entry {entry!r} should be rejected"):
                cli.validate_config({"components": {}, "entry": entry})

    def test_valid_entry_ok(self):
        cli.validate_config({"components": {}, "entry": "8bit.circuit.tsx"})

    def test_bad_axes_rejected(self):
        for axes in [[], ["z"], ["x", "z"], "x"]:
            with self.assertRaises(cli.NudgeError):
                cli.validate_config({"components": {"C1": {"axes": axes}}})

    def test_negative_step_rejected(self):
        with self.assertRaises(cli.NudgeError):
            cli.validate_config({"components": {"C1": {"step": -0.4}}})
        with self.assertRaises(cli.NudgeError):
            cli.validate_config({"components": {"C1": {"range": 0}}})

    def test_bad_max_iterations_rejected(self):
        with self.assertRaises(cli.NudgeError):
            cli.validate_config({"components": {}, "search": {"maxIterations": 0}})
        with self.assertRaises(cli.NudgeError):
            cli.validate_config({"components": {}, "search": {"maxIterations": 1.5}})

    def test_overlap_rejected(self):
        with self.assertRaises(cli.NudgeError):
            cli.validate_config({"components": {"C1": {}}, "neverMove": ["C1"]})


class ApplyTest(unittest.TestCase):
    def _mk(self, content, best, components, never):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        tsx = Path(d.name) / "m.circuit.tsx"
        tsx.write_bytes(content)
        paths = {"module": "m", "tsx": tsx, "state_dir": Path(d.name) / "state"}
        cfg = {"components": components, "neverMove": never}
        h = _sha(content)
        state = {"solved": True, "best": best,
                 "original_sha256": h, "applied_sha256": h}
        return paths, cfg, state

    def test_apply_refuses_neverMove(self):
        paths, cfg, state = self._mk(
            b'<c name="D1" pcbX={1.0}/>',
            {"U2": {"pcbX": 3.0}}, {"D1": {}}, ["U2"])
        orig = cli.load_state
        cli.load_state = lambda p: state
        try:
            with self.assertRaises(cli.NudgeError):
                cli.cmd_apply(paths, cfg, SimpleNamespace(json=False))
        finally:
            cli.load_state = orig

    def test_apply_refuses_non_whitelisted(self):
        paths, cfg, state = self._mk(
            b'<c name="D1" pcbX={1.0}/>',
            {"XYZ": {"pcbX": 3.0}}, {"D1": {}}, [])
        orig = cli.load_state
        cli.load_state = lambda p: state
        try:
            with self.assertRaises(cli.NudgeError):
                cli.cmd_apply(paths, cfg, SimpleNamespace(json=False))
        finally:
            cli.load_state = orig

    def test_apply_refuses_unsolved_state(self):
        paths, cfg, state = self._mk(
            b'<c name="D1" pcbX={1.0}/>',
            {"D1": {"pcbX": 3.0}}, {"D1": {}}, [])
        state["solved"] = False
        orig = cli.load_state
        cli.load_state = lambda p: state
        try:
            with self.assertRaises(cli.NudgeError):
                cli.cmd_apply(paths, cfg, SimpleNamespace(json=False))
        finally:
            cli.load_state = orig

    def test_apply_writes_only_whitelisted(self):
        content = b'D1x={1.0} U2x={5.0}'
        paths, cfg, state = self._mk(
            content, {"D1": {"pcbX": 3.0}}, {"D1": {}}, ["U2"])
        positions = {
            "D1": {"pcbX": {"value": 1.0, "start": 5, "end": 8}},
            "U2": {"pcbX": {"value": 5.0, "start": 14, "end": 17}},
        }
        orig_load_state = cli.load_state
        orig_load_positions = cli.load_positions
        cli.load_state = lambda p: state
        cli.load_positions = lambda p: (content, positions)
        try:
            cli.cmd_apply(paths, cfg, SimpleNamespace(json=False))
        finally:
            cli.load_state = orig_load_state
            cli.load_positions = orig_load_positions
        # D1 changed, U2 (neverMove) untouched.
        self.assertEqual(paths["tsx"].read_bytes(), b'D1x={3.0} U2x={5.0}')


class RollbackTest(unittest.TestCase):
    def _mk(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        tsx = Path(d.name) / "m.circuit.tsx"
        tsx.write_bytes(b"ORIGINAL")
        paths = {"module": "m", "tsx": tsx,
                 "state_dir": Path(d.name) / "state",
                 "dist_circuit": Path(d.name) / "circuit.json"}
        cfg = {"components": {"C1": {"axes": ["x"], "step": 0.4}},
               "entry": "m.circuit.tsx", "search": {}, "build": {}}
        args = SimpleNamespace(strategy="greedy", max_iters=None, time_budget=None,
                               verbose=False, json=False, no_apply=False)
        return paths, cfg, args

    def _patch(self, raiser):
        cli.load_positions = lambda p: (
            p.read_bytes(), {"C1": {"pcbX": {"value": 0.0, "start": 0, "end": 0}}})
        cli.build_and_classify = lambda p, c, bust_cache=False: {
            "score": (0, 1, 0), "broken": False,
            "classes": {"unknown": 0}, "implicated": {"C1": 1}}
        cli.search.run_search = raiser

    def _unpatch(self):
        cli.load_positions = self._orig_load_positions
        cli.build_and_classify = self._orig_build
        cli.search.run_search = self._orig_run_search

    def setUp(self):
        self._orig_load_positions = cli.load_positions
        self._orig_build = cli.build_and_classify
        self._orig_run_search = cli.search.run_search

    def tearDown(self):
        self._unpatch()

    def _run_expecting(self, exc_type):
        paths, cfg, args = self._mk()
        with self.assertRaises(exc_type):
            cli.cmd_run(paths, cfg, args)
        return paths

    def test_rollback_on_exception(self):
        def bad(*a, **k):
            a[4](b"CORRUPTED")
            raise RuntimeError("boom")
        self._patch(bad)
        paths = self._run_expecting(RuntimeError)
        self.assertEqual(paths["tsx"].read_bytes(), b"ORIGINAL")

    def test_rollback_on_keyboard_interrupt(self):
        def bad(*a, **k):
            a[4](b"CORRUPTED")
            raise KeyboardInterrupt
        self._patch(bad)
        paths = self._run_expecting(KeyboardInterrupt)
        self.assertEqual(paths["tsx"].read_bytes(), b"ORIGINAL")


class SignalRollbackSubprocessTest(unittest.TestCase):
    """Send SIGTERM to a child that is mid-mutation and confirm it restores."""

    def test_sigterm_restores(self):
        with tempfile.TemporaryDirectory() as d:
            tsx = Path(d) / "m.circuit.tsx"
            tsx.write_text("ORIGINAL")
            state = Path(d) / "state"
            script = f'''
import importlib.util, importlib.machinery, sys, os, signal, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, {LIB!r})
spec = importlib.util.spec_from_loader("cli", importlib.machinery.SourceFileLoader("cli", {CLI_PATH!r}))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tsx = Path({str(tsx)!r})
paths = {{"module": "m", "tsx": tsx, "state_dir": Path({str(state)!r}), "dist_circuit": Path({str(Path(d)/"circuit.json")!r})}}
cfg = {{"components": {{"C1": {{"axes": ["x"], "step": 0.4}}}}, "entry": "m.circuit.tsx", "search": {{}}, "build": {{}}}}
args = SimpleNamespace(strategy="greedy", max_iters=None, time_budget=None, verbose=False, json=False, no_apply=False)
m.load_positions = lambda p: (p.read_bytes(), {{"C1": {{"pcbX": {{"value": 0.0, "start": 0, "end": 0}}}}}})
m.build_and_classify = lambda p, c, bust_cache=False: {{"score": (0,1,0), "broken": False, "classes": {{"unknown": 0}}, "implicated": {{"C1": 1}}}}
def bad(*a, **k):
    a[4](b"CORRUPTED")
    os.kill(os.getpid(), signal.SIGTERM)
    time.sleep(30)
m.search.run_search = bad
try:
    m.cmd_run(paths, cfg, args)
    print("NO_EXCEPTION")
except KeyboardInterrupt:
    pass
except BaseException as e:
    print("EXC:" + type(e).__name__)
print("FILE=" + tsx.read_text())
'''
            proc = subprocess.run([sys.executable, "-c", script],
                                  capture_output=True, text=True, timeout=30)
            out = proc.stdout
            self.assertIn("FILE=ORIGINAL", out, f"stdout={out!r} stderr={proc.stderr!r}")
            self.assertEqual(tsx.read_text(), "ORIGINAL")


class RestoreTest(unittest.TestCase):
    def _mk(self, backup, recorded_sha):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        state_dir = Path(d.name) / "state"
        state_dir.mkdir()
        (state_dir / "original.tsx").write_bytes(backup)
        tsx = Path(d.name) / "m.circuit.tsx"
        tsx.write_bytes(b"CURRENT")
        return {"module": "m", "tsx": tsx, "state_dir": state_dir}, recorded_sha

    def test_restore_ok(self):
        paths, sha = self._mk(b"BACKUP", _sha(b"BACKUP"))
        orig = cli.load_state
        cli.load_state = lambda p: {"original_sha256": sha}
        try:
            cli.cmd_restore(paths, SimpleNamespace(json=False))
        finally:
            cli.load_state = orig
        self.assertEqual(paths["tsx"].read_bytes(), b"BACKUP")

    def test_restore_rejects_hash_mismatch(self):
        paths, _ = self._mk(b"BACKUP", _sha(b"DIFFERENT"))
        orig = cli.load_state
        cli.load_state = lambda p: {"original_sha256": _sha(b"DIFFERENT")}
        try:
            with self.assertRaises(cli.NudgeError):
                cli.cmd_restore(paths, SimpleNamespace(json=False))
        finally:
            cli.load_state = orig
        # Refusing to restore means the current file is left untouched.
        self.assertEqual(paths["tsx"].read_bytes(), b"CURRENT")


class BustCacheTest(unittest.TestCase):
    def test_bust_cache_keeps_tracked_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "ts-modules" / "src" / "m"
            src.mkdir(parents=True)
            (src / "m.routed.json").write_text("[]")
            (src / "m.sig").write_text("sig")
            (root / "ts-modules" / ".tscircuit").mkdir(parents=True)
            old = cli.TS_MODULES
            cli.TS_MODULES = root / "ts-modules"
            try:
                cli._bust_cache("m")
                self.assertTrue((src / "m.routed.json").exists())
                self.assertTrue((src / "m.sig").exists())
            finally:
                cli.TS_MODULES = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
