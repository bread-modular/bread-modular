"""Bounded facade/context/bundle regressions; no engine or downloads required."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import trial as t
import validate as judge
from test_trial import BASE, NEW

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import bundle
import kicad_tools as facade
spec = importlib.util.spec_from_file_location("tracemaker_dispatch", Path(__file__).with_name("run.py"))
dispatch = importlib.util.module_from_spec(spec); spec.loader.exec_module(dispatch)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="TraceMaker tests with spaces ")
        self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(script), *map(str, args)], cwd=self.root,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=60)

    def project(self):
        source = self.root / "source"; source.mkdir()
        pcb = source / "board.kicad_pcb"; pcb.write_text(BASE)
        pcb.with_suffix(".kicad_sch").write_text('(kicad_sch (version 20250114))')
        return source, pcb

    def test_help_discovery_and_exact_standalone_passthrough(self):
        top = self.run_cli(TOOLS / "kicad_tools.py", "--help")
        self.assertIn("tracemaker", top.stdout)
        self.assertIn("--include-tracemaker", self.run_cli(TOOLS / "kicad_tools.py", "bundle", "--help").stdout)
        help_result = self.run_cli(TOOLS / "kicad_tools.py", "tracemaker", "--help")
        for name in ("freeze", "strip", "run", "compare", "validate", "doctor"):
            self.assertIn(name, help_result.stdout)
        for args, script in ((["strip", "--help"], "trial.py"), (["run", "--help"], "trial.py"),
                             (["compare", "--bad-option"], "trial.py"), (["validate", "--help"], "validate.py"),
                             (["run", "route", "missing input", "board.kicad_pcb", "NEW out", "--engine", "absent",
                               "--sha256", "unused", "--deps", "absent"], "trial.py")):
            direct = self.run_cli(Path(__file__).with_name(script), *(args[1:] if args[0] == "validate" else args))
            through = self.run_cli(TOOLS / "kicad_tools.py", "tracemaker", *args)
            self.assertEqual((direct.returncode, direct.stdout, direct.stderr),
                             (through.returncode, through.stdout, through.stderr))
        self.assertFalse((self.root / "NEW out").exists())

    def test_dispatch_streams_args_exit_and_no_generic_imports(self):
        before = dict(sys.modules)
        for name in dispatch.COMMANDS:
            with patch.object(dispatch.subprocess, "run", return_value=SimpleNamespace(returncode=19)) as run:
                self.assertEqual(dispatch.main([name, "--", "path with spaces", "--unknown"]), 19)
                suffix = ["--", "path with spaces", "--unknown"]
                if name != "validate": suffix.insert(0, name)
                self.assertEqual(run.call_args.args[0], [sys.executable, "-B", str(dispatch.HERE / dispatch.COMMANDS[name]), *suffix])
                self.assertEqual(run.call_args.kwargs, {})
        for module in ("pcbnew", "api", "native_snapshot"):
            self.assertIs(sys.modules.get(module), before.get(module))

    def test_missing_controller_platform_doctor_and_spawn_no_writes(self):
        with patch.object(dispatch, "HERE", self.root), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dispatch.main(["freeze", "absent", "NEW"]), 2)
        with patch.object(dispatch.sys, "platform", "unsupported"), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dispatch.main(["compare", "a", "b"]), 2)
        with patch.object(dispatch.subprocess, "run", side_effect=OSError("spawn unavailable")), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dispatch.main(["freeze", "absent", "NEW"]), 2)
        before = t.tree(self.root)
        with patch.object(dispatch.subprocess, "run", side_effect=AssertionError("doctor must not execute")), contextlib.redirect_stdout(io.StringIO()) as out:
            dispatch.main(["doctor"])
        self.assertFalse(json.loads(out.getvalue())["engine_executed"])
        self.assertEqual(before, t.tree(self.root))

    def test_name_only_and_mixed_encodings_block_before_any_writes(self):
        name_only = '(kicad_pcb (version 20260101) (footprint "a" (pad "1" smd rect (net "SIG"))) (segment (net "SIG") (uuid "a")))'
        mixed = BASE.replace('(net 1) (uuid "track")', '(net "SIG") (uuid "track")')
        for i, text in enumerate((name_only, mixed, BASE.replace('(net 2 "OTHER")', '(net 1 "OTHER")'))):
            f = self.root / f"frozen-{i}"; f.mkdir(); (f / "board.kicad_pcb").write_text(text); t.seal(f)
            before = t.tree(f)
            with patch.object(t, "fresh", side_effect=AssertionError("no writes")), self.assertRaises(ValueError):
                t.strip(f, "board.kicad_pcb", self.root / "denied", ["SIG"])
            with patch.object(t, "fresh", side_effect=AssertionError("no writes")), self.assertRaises(ValueError):
                t.run(f, "board.kicad_pcb", self.root / "denied", "absent", t.REVIEWED_ENGINE_SHA256, "absent")
            self.assertEqual(before, t.tree(f)); self.assertFalse((self.root / "denied").exists())

    def test_exact_segment_selection_and_foreign_duplicate_uuid_rejection(self):
        f = self.root / "frozen"; f.mkdir()
        (f / "board.kicad_pcb").write_text(BASE[:-1] + NEW + ")"); t.seal(f)
        report = t.strip(f, "board.kicad_pcb", self.root / "selected", ["SIG"], segment_uuids=["track"])
        self.assertEqual(report["authorized_segment_uuids"], ["track"])
        self.assertIn(NEW, (self.root / "selected/board.kicad_pcb").read_text())
        for selected in (["other"], ["track", "track"], ["missing"]):
            with patch.object(t, "fresh", side_effect=AssertionError("no writes")), self.assertRaises(ValueError):
                t.strip(f, "board.kicad_pcb", self.root / "denied", ["SIG"], segment_uuids=selected)

    def test_freeze_complete_local_closure_and_missing_dependencies(self):
        source, pcb = self.project()
        pretty = source / "lib.pretty"; pretty.mkdir(); (pretty / "a.kicad_mod").write_text('(footprint "a")')
        (source / "fp-lib-table").write_text(f'(fp_lib_table (lib (name "lib") (type "KiCad") (uri {json.dumps(str(pretty))})))')
        child = source / "child.kicad_sch"; child.write_text('(kicad_sch)')
        pcb.with_suffix('.kicad_sch').write_text('(kicad_sch (sheet (property "Sheetfile" "child.kicad_sch")))')
        before = t.tree(source); out = self.root / "frozen"
        t.freeze(pcb, out)
        self.assertEqual(before, t.tree(source)); self.assertEqual(pcb.read_bytes(), (out / pcb.name).read_bytes())
        self.assertTrue((out / "child.kicad_sch").is_file()); self.assertTrue((out / "lib.pretty/a.kicad_mod").is_file())
        self.assertIn('${KIPRJMOD}/lib.pretty', (out / "fp-lib-table").read_text())
        child.unlink()
        with patch.object(t, "fresh", side_effect=AssertionError("missing hierarchy must precede writes")), self.assertRaises(ValueError):
            t.freeze(pcb, self.root / "denied")
        child.write_text('(kicad_sch)'); (pretty / "a.kicad_mod").unlink()
        with patch.object(t, "fresh", side_effect=AssertionError("missing library must precede writes")), self.assertRaises(ValueError):
            t.freeze(pcb, self.root / "denied")

    def test_external_closure_requires_explicit_boundary_and_rebases(self):
        source, pcb = self.project()
        pretty = self.root / "external.pretty"; pretty.mkdir(); (pretty / "a.kicad_mod").write_text('(footprint "a")')
        (source / "fp-lib-table").write_text(f'(fp_lib_table (lib (name "lib") (type "KiCad") (uri {json.dumps(str(pretty))})))')
        with patch.object(t, "fresh", side_effect=AssertionError("no writes")), self.assertRaises(ValueError):
            t.freeze(pcb, self.root / "denied")
        t.freeze(pcb, self.root / "frozen", self.root)
        self.assertTrue((self.root / "frozen/_dependencies/external.pretty/a.kicad_mod").is_file())
        self.assertIn('${KIPRJMOD}/_dependencies/external.pretty', (self.root / 'frozen/fp-lib-table').read_text())

    def test_runtime_missing_and_unreviewed_digest_rejected_before_writes(self):
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(BASE); t.seal(f)
        with patch.object(t, "runtime_ready"), patch.object(t, "fresh", side_effect=AssertionError("no writes")):
            for digest, deps in (("unreviewed", "absent"), (t.REVIEWED_ENGINE_SHA256, "absent")):
                with self.assertRaises(ValueError): t.run(f, "board.kicad_pcb", self.root / "denied", "absent", digest, deps)
        with patch.object(t.sys, "platform", "unsupported"), self.assertRaises(ValueError): t.runtime_ready()

    def test_bundle_none_either_both_hashes_links_relocation_rebundle(self):
        routing_present = (bundle.ROOT / 'opt/kicad-routing/run.py').is_file()
        for router, trace in ((False, False), (False, True), (True, False), (True, True)):
            if router and not routing_present: continue
            dst = self.root / f"copy with spaces {router}-{trace}"
            dry = bundle.bundle(dst, True, router, include_tracemaker=trace)
            self.assertFalse(dst.exists())
            result = bundle.bundle(dst, include_routing=router, include_tracemaker=trace)
            self.assertEqual(dry["manifest"], result["manifest"])
            self.assertEqual(len(result["manifest"]["symlinks"]), 3)
            for name, digest in result["manifest"]["files_sha256"].items():
                self.assertEqual(hashlib.sha256((dst / name).read_bytes()).hexdigest(), digest)
                self.assertFalse(any(p in name.split('/') for p in ('experiments', 'modules', 'deps', 'HOME', 'config', 'vendor')))
            self.assertEqual((dst / 'opt/kicad-tools/tracemaker/trial.py').exists(), trace)
            self.assertFalse(any(p.suffix in ('.kicad_pcb', '.deb', '.so') for p in dst.rglob('*')))
            with self.assertRaises(Exception): bundle.bundle(dst, include_tracemaker=trace)
            moved = dst.with_name(dst.name + ' relocated'); shutil.move(dst, moved)
            again = moved.with_name(moved.name + ' rebundled')
            rebound = bundle.bundle(again, include_routing=router, root=moved, include_tracemaker=trace)
            self.assertEqual(result['manifest']['files_sha256'], rebound['manifest']['files_sha256'])
            for link in bundle.COMPATIBILITY_LINKS:
                self.assertEqual(os.readlink(moved / link), os.readlink(again / link))
            facade_path = moved / 'opt/kicad-tools/kicad_tools.py'
            help_result = self.run_cli(facade_path, 'tracemaker', '--help')
            self.assertEqual(help_result.returncode, 0 if trace else 2)
            if trace:
                self.assertIn('validate', help_result.stdout)
                self.assertEqual(self.run_cli(facade_path, 'tracemaker', 'validate', '--help').returncode, 0)

    def test_bundle_rejects_optional_symlink_substitution_and_missing_payload(self):
        src = self.root / 'distribution'; bundle.bundle(src, include_tracemaker=True)
        controller = src / 'opt/kicad-tools/tracemaker/trial.py'
        controller.unlink(); controller.symlink_to(Path(__file__).with_name('trial.py'))
        with self.assertRaises(Exception): bundle.bundle(self.root / 'denied', root=src, include_tracemaker=True)
        self.assertFalse((self.root / 'denied').exists())
        controller.unlink(); (src / 'opt/kicad-tools/tracemaker/run.py').unlink()
        with self.assertRaises(Exception): bundle.bundle(self.root / 'denied', root=src, include_tracemaker=True)

    def test_native_missing_runtime_and_unknown_schema_reject_without_writes(self):
        f = self.root / "frozen"; f.mkdir(); (f / "board.kicad_pcb").write_text(BASE); t.seal(f)
        with patch.object(judge, "native_prerequisites", side_effect=ValueError("missing pcbnew")), patch.object(t, "fresh", side_effect=AssertionError("no writes")):
            with self.assertRaises(ValueError): judge.check(f, "board.kicad_pcb", self.root / "denied")
        with self.assertRaises(ValueError): judge.summary({})
        self.assertFalse((self.root / "denied").exists())

    def test_optional_source_substituted_during_copy_is_rejected(self):
        src = self.root / "source distribution"; bundle.bundle(src, include_tracemaker=True)
        original_copy = bundle.shutil.copyfile
        def replace(source, target):
            result = original_copy(source, target)
            if Path(source).name == "trial.py": Path(source).write_text("substituted")
            return result
        with patch.object(bundle.shutil, "copyfile", side_effect=replace), self.assertRaises(Exception):
            bundle.bundle(self.root / "denied", root=src, include_tracemaker=True)
        self.assertFalse((self.root / "denied").exists())

    def test_standalone_provision_manifest_pins_exact_packages(self):
        data = json.loads(Path(__file__).with_name('provision.json').read_text())
        self.assertEqual(data['pin'], t.PIN); self.assertEqual(data['engine_sha256'], t.REVIEWED_ENGINE_SHA256)
        self.assertEqual(len(data['packages']), 8); self.assertEqual(len(data['signed_indexes']), 3)
        self.assertTrue(all(len(p['SHA256']) == 64 and p['SHA256'] == p['actual_sha256'] for p in data['packages']))


if __name__ == '__main__':
    unittest.main()
