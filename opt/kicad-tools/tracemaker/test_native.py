"""Opt-in actual PCB API save→freeze/block/compare/native judge→CLI polish.

Synthetic only. No engine executed, provisioned, installed or assumed compatible.
The name-only engine handoff is deliberately tested as blocked, NOT an end-to-end pass.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import trial as t
import validate as judge

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from automation import apply, inspect, plan
spec = importlib.util.spec_from_file_location('tracemaker_synthetic_fixture', TOOLS / 'automation/tests/fixtures.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


@unittest.skipUnless(os.environ.get('KICAD_TRACEMAKER_NATIVE') == '1',
                     'set KICAD_TRACEMAKER_NATIVE=1 with matching KiCad/pcbnew 10.0.x; no engine needed')
class NativeHandoffTests(unittest.TestCase):
    def test_actual_saved_output_safe_freeze_block_and_authorized_cli_polish(self):
        scratch = TOOLS / 'tracemaker-native.tmp'; scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='synthetic hybrid with spaces ', dir=scratch) as temporary:
            root = Path(temporary).resolve()
            source, _ = fixture.fixture(root)
            before = fixture.hashes(source)
            placement_uuid = fixture.uid('hybrid-placement-route')
            operations = {'schema_version': 1, 'operations': [
                {'op': 'move_footprint', 'target': {'ref': 'R2'}, 'at': [30, 21]},
                {'op': 'delete_item', 'uuid': fixture.uid('route'), 'expected_kind': 'track'},
                {'op': 'add_polyline', 'uuid': placement_uuid, 'net': 'SIGNAL', 'layer': 'F.Cu',
                 'width_mm': 0.25, 'start': {'pad': {'ref': 'R1', 'number': '1'}},
                 'end': {'pad': {'ref': 'R2', 'number': '1'}}, 'waypoints': []}]}
            p = plan(operations, project_dir=source, python='/usr/bin/python3', kicad_cli='/usr/bin/kicad-cli')
            candidate = root / 'NEW placed candidate'
            result = apply(p, candidate, python='/usr/bin/python3', kicad_cli='/usr/bin/kicad-cli')
            self.assertEqual(result['status'], 'accepted', result['errors'])
            self.assertTrue(result['checks']['parity']['equal']); self.assertEqual(fixture.hashes(source), before)
            completion = json.loads((candidate / 'completion.json').read_text())
            board = candidate / completion['board']
            raw = board.read_text()
            self.assertFalse(any(n[3][0] == 'net' for n in t.nodes(raw)), 'actual native encoding changed; re-review engine contract')
            self.assertIn('(net "SIGNAL")', raw)
            frozen = root / 'NEW frozen'
            t.freeze(board, frozen)
            self.assertEqual((frozen / board.name).read_bytes(), board.read_bytes())
            self.assertTrue((frozen / 'Auto.pretty/R.kicad_mod').is_file())
            self.assertTrue((frozen / 'Auto.kicad_sym').is_file())
            hashes = t.frozen(frozen)
            for operation in ('strip', 'run'):
                with self.assertRaisesRegex(ValueError, 'handoff BLOCKED'):
                    if operation == 'strip':
                        t.strip(frozen, board.name, root / 'strip denied', ['SIGNAL'])
                    else:
                        t.run(frozen, board.name, root / 'engine denied', 'absent engine', t.REVIEWED_ENGINE_SHA256, 'absent deps', 'route')
            self.assertFalse((root / 'strip denied').exists()); self.assertFalse((root / 'engine denied').exists())
            self.assertEqual(t.frozen(frozen), hashes)
            self.assertTrue(t.compare(frozen / board.name, board)['passed'])
            judged = root / 'NEW native baseline'
            checked = judge.check(frozen, board.name, judged)
            self.assertEqual(checked['drc']['active_errors'], 0, checked)
            self.assertEqual(checked['drc']['counts'], {'violations': 0, 'unconnected_items': 0, 'schematic_parity': 0})
            self.assertTrue(checked['assets_unchanged'])
            self.assertEqual(checked['snapshot_command']['exit_code'], 0)
            canonical = judged / 'canonical.kicad_pcb'
            independently_judged = root / 'NEW independent no-op'
            judge.check(frozen, board.name, independently_judged, candidate=board)
            self.assertTrue(t.compare(canonical, independently_judged / 'canonical.kicad_pcb', semantic=True)['passed'])
            inventory = json.loads((judged / 'snapshot.json').read_text())
            self.assertEqual(sorted(inventory['net_partition']), ['SIGNAL'])

            # Actual CLI, unrelated cwd and explicit selected delete/replacement + vias.
            cwd = root / 'Unrelated working directory with spaces'; cwd.mkdir()
            view = inspect(project_dir=frozen, python='/usr/bin/python3')
            track = next(i for i in view['items'] if i['kind'] == 'track')
            via1, via2 = fixture.uid('hybrid-via1'), fixture.uid('hybrid-via2')
            polish = {'schema_version': 1, 'operations': [
                {'op': 'delete_item', 'uuid': track['uuid'], 'expected_kind': 'track'},
                {'op': 'add_via', 'uuid': via1, 'net': 'SIGNAL', 'at': [22, 20], 'diameter_mm': 0.7, 'drill_mm': 0.3},
                {'op': 'add_via', 'uuid': via2, 'net': 'SIGNAL', 'at': [28, 21], 'diameter_mm': 0.7, 'drill_mm': 0.3},
                {'op': 'add_polyline', 'uuid': fixture.uid('hybrid-front1'), 'net': 'SIGNAL', 'layer': 'F.Cu', 'width_mm': 0.25,
                 'start': {'pad': {'ref': 'R1', 'number': '1'}}, 'end': {'uuid': via1}},
                {'op': 'add_polyline', 'uuid': fixture.uid('hybrid-back'), 'net': 'SIGNAL', 'layer': 'B.Cu', 'width_mm': 0.25,
                 'start': {'uuid': via1}, 'end': {'uuid': via2}, 'waypoints': [[24, 20], [26, 21]]},
                {'op': 'add_polyline', 'uuid': fixture.uid('hybrid-front2'), 'net': 'SIGNAL', 'layer': 'F.Cu', 'width_mm': 0.25,
                 'start': {'uuid': via2}, 'end': {'pad': {'ref': 'R2', 'number': '1'}}}]}
            requests = root / 'Requests'; requests.mkdir()
            plans = root / 'Plans'; plans.mkdir()
            ops_path = requests / 'polish operations.json'; ops_path.write_text(json.dumps(polish))
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}; env.pop('PYTHONPATH', None)
            def cli(*args):
                r = subprocess.run(['/usr/bin/python3', '-B', str(TOOLS / 'kicad_tools.py'), *map(str, args)],
                                   cwd=cwd, env=env, capture_output=True, text=True, timeout=240)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                return json.loads(r.stdout)
            cli('pcb', 'inspect', '--project-dir', frozen, '--pcbnew-python', '/usr/bin/python3')
            plan_data = cli('pcb', 'plan', '--project-dir', frozen, '--ops', ops_path,
                            '--pcbnew-python', '/usr/bin/python3', '--kicad-cli', '/usr/bin/kicad-cli')
            plan_path = plans / 'polish plan.json'; plan_path.write_text(json.dumps(plan_data))
            polished = root / 'NEW polished candidate'
            polish_result = cli('pcb', 'apply', '--plan', plan_path, '--output', polished,
                                '--pcbnew-python', '/usr/bin/python3', '--kicad-cli', '/usr/bin/kicad-cli')
            self.assertEqual(polish_result['status'], 'accepted', polish_result['errors'])
            self.assertTrue(polish_result['checks']['parity']['equal'])
            polished_board = polished / polish_result['board']
            # Expected intentional deletion: original immutable comparison is NOT the edited acceptance gate.
            self.assertFalse(t.compare(frozen / board.name, polished_board, ['SIGNAL'])['passed'])
            final_frozen = root / 'NEW authorized polish baseline'; t.freeze(polished_board, final_frozen)
            final_native = root / 'NEW polished native'; final = judge.check(final_frozen, board.name, final_native)
            self.assertEqual(final['drc']['counts'], {'violations': 0, 'unconnected_items': 0, 'schematic_parity': 0})
            final_inventory = json.loads((final_native / 'snapshot.json').read_text())
            self.assertEqual(len(final_inventory['vias']), 2)
            self.assertEqual(inventory['net_partition'], final_inventory['net_partition'])
            self.assertEqual(inventory['footprints'], final_inventory['footprints'])
            self.assertEqual(inventory['outline_nm'], final_inventory['outline_nm'])
            cli('check', '--project-dir', final_frozen, '--reports', root / 'NEW full ERC DRC parity', '--kicad-cli', '/usr/bin/kicad-cli')
            self.assertEqual(t.frozen(frozen), hashes); self.assertEqual(fixture.hashes(source), before)
            print(json.dumps({'synthetic_only': True, 'native_version': inventory['kicad_version'],
                              'engine_route': 'NOT RUN: verified name-only adapter blocker; upstream support untested',
                              'placement_freeze_native_validation_cli_polish': 'passed', 'final_vias': 2,
                              'final_drc_parity_opens': final['drc']['counts'], 'sources_unchanged': True}))


if __name__ == '__main__':
    unittest.main()
