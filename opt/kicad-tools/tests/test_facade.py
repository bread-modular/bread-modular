"""Final facade isolation, capabilities and explicit payload regressions."""
import contextlib
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
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle
import kicad_tools as tools


class FacadeTests(unittest.TestCase):
    def test_each_controller_exact_subprocess_flags_returncode_and_no_imports(self):
        before = dict(sys.modules)
        for name, relative in tools.DELEGATES.items():
            args = ['--', 'plan', '--input', 'path with spaces', '--unknown-option']
            with mock.patch.object(Path, 'is_file', return_value=True), mock.patch.object(tools.subprocess, 'run', return_value=SimpleNamespace(returncode=9)) as run:
                self.assertEqual(tools.main([name, *args]), 9)
            expected = tools.HERE / relative
            if name == 'route':
                expected = tools.HERE.parent / 'kicad-routing/run.py'
            self.assertEqual(run.call_args.args[0], [sys.executable, '-B', str(expected), *args[1:]])
            self.assertEqual(run.call_args.kwargs, {})  # inherited streams/cwd; no capture/reparse
        for name in ('automation', 'schematic', 'general_native', 'api', 'pcbnew'):
            self.assertIs(sys.modules.get(name), before.get(name))

    def test_missing_controllers_and_spawn_failure_are_json_exit_two(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(tools, 'HERE', Path(temp)):
            for name in tools.DELEGATES:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(tools.main([name, '--help']), 2)
                self.assertIn('unavailable', json.loads(out.getvalue())['error'])
        with mock.patch.object(tools.subprocess, 'run', side_effect=OSError('deliberate spawn failure')):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(tools.main(['pcb', '--help']), 2)
            self.assertIn('spawn failure', json.loads(out.getvalue())['error'])

    def test_complete_explicit_component_payloads_and_no_runtime_permission(self):
        # Observation only: copying still uses the fixed literal allowlists.
        for directory in ('automation', 'schematic'):
            actual = {p.relative_to(tools.HERE).as_posix() for p in (tools.HERE / directory).rglob('*')
                      if p.is_file() and p.suffix in ('.py', '.md')}
            self.assertTrue(actual)
            self.assertLessEqual(actual, set(bundle.TOOLKIT_FILES))
        routing = tools.HERE.parent / 'kicad-routing'
        if (routing / 'run.py').is_file():
            actual = {p.relative_to(bundle.ROOT).as_posix() for p in routing.rglob('*')
                      if p.is_file() and p.suffix in ('.py', '.md')
                      and not any(part.endswith('.tmp') for part in p.relative_to(routing).parts)}
            self.assertLessEqual(actual, set(bundle.ROUTING_FILES))
        self.assertEqual(len(bundle.COMPATIBILITY_LINKS), 3)
        self.assertFalse(any('work.tmp' in p or 'runtime.tmp' in p for p in bundle.ROUTING_ALLOWED))
        self.assertNotIn('opt/kicad-routing/arbitrary.json', bundle.ROUTING_ALLOWED)

    def test_relocated_help_and_nonzero_json_match_standalone_no_original_checkout(self):
        with tempfile.TemporaryDirectory(prefix='facade relocation with spaces ') as temp:
            root = Path(temp)
            copied = root / 'Copied toolkit'; bundle.bundle(copied)
            moved = root / 'Relocated toolkit'; shutil.move(copied, moved)
            cwd = root / 'Unrelated cwd'; cwd.mkdir()
            env = dict(os.environ, NO_COLOR='1', PYTHONDONTWRITEBYTECODE='1')
            env.pop('PYTHONPATH', None)
            facade = moved / 'opt/kicad-tools/kicad_tools.py'
            def run(script, *args):
                return subprocess.run([sys.executable, '-B', str(script), *args], cwd=cwd,
                                      env=env, capture_output=True, text=True, timeout=60)
            help_result = run(facade, '--help')
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            for name in tools.DELEGATES:
                self.assertIn(name, help_result.stdout)
            for name in ('pcb', 'schematic', 'export', 'assembly'):
                script = moved / 'opt/kicad-tools' / tools.DELEGATES[name]
                direct = run(script, '--help'); via = run(facade, name, '--help')
                self.assertEqual((via.returncode, via.stdout, via.stderr),
                                 (direct.returncode, direct.stdout, direct.stderr))
                if name in ('pcb', 'schematic'):
                    for operation in ('inspect', 'plan', 'apply'):
                        self.assertIn(operation, via.stdout)
                    args = ('inspect', '--project-dir', str(root/'Missing input')) if name == 'pcb' else (
                        'inspect', '--input', str(root/'Missing.kicad_sch'))
                    direct = run(script, *args); via = run(facade, name, *args)
                    self.assertEqual((via.returncode, via.stdout, via.stderr),
                                     (direct.returncode, direct.stdout, direct.stderr))
                    self.assertEqual(via.returncode, 2)
                    self.assertIn('error', json.loads(via.stdout))
            absent = run(facade, 'route', '--help')
            self.assertEqual(absent.returncode, 2)
            self.assertIn('unavailable', json.loads(absent.stdout)['error'])
            code = ('import sys,json; sys.path.insert(0,sys.argv[1]); '
                    'from automation import inspect,plan,apply,validate; '
                    'from schematic import inspect_sheet,plan_edits,apply_plan; '
                    'print(json.dumps({"pcb":inspect.__module__,"schematic":inspect_sheet.__module__}))')
            api = run('-c', code, str(moved/'opt/kicad-tools'))
            self.assertEqual(api.returncode, 0, api.stderr)
            self.assertEqual(json.loads(api.stdout), {'pcb':'automation.api', 'schematic':'schematic.api'})

    def test_route_real_help_doctor_and_nonzero_preserve_streams(self):
        if not (tools.HERE.parent/'kicad-routing/run.py').is_file():
            self.skipTest('optional routing sibling unavailable')
        with tempfile.TemporaryDirectory(prefix='route facade unrelated cwd ') as cwd:
            env = dict(os.environ, NO_COLOR='1', PYTHONDONTWRITEBYTECODE='1')
            env.pop('PYTHONPATH', None)
            for args in (['--help'], ['doctor'], ['inspect-project', '--snapshot', '/nonexistent/synthetic-input', '--pcb', 'Absent.kicad_pcb']):
                runs = [subprocess.run([sys.executable, '-B', str(script), *prefix, *args],
                                      cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
                        for script, prefix in ((tools.HERE.parent/'kicad-routing/run.py', []),
                                               (tools.HERE/'kicad_tools.py', ['route']))]
                self.assertEqual((runs[0].returncode, runs[0].stdout, runs[0].stderr),
                                 (runs[1].returncode, runs[1].stdout, runs[1].stderr))
                if args[0] == 'doctor':
                    self.assertEqual(json.loads(runs[1].stdout)['operation'], 'doctor')
                elif args[0] != '--help':
                    self.assertNotEqual(runs[1].returncode, 0)
                    self.assertIn('error', json.loads(runs[1].stderr))


if __name__ == '__main__':
    unittest.main()
