"""Opt-in synthetic native handoff and real external CPU hybrid loop.

Tests never provision/download. Engine execution needs explicit paths AND digest.
All design artifacts are disposable; optional summaries contain counts/log hashes only.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import trial as t

TOOLS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tracemaker_synthetic_fixture', TOOLS / 'automation/tests/fixtures.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
ZERO = {'violations': 0, 'unconnected_items': 0, 'schematic_parity': 0}
INVARIANTS = ('footprints', 'net_partition', 'outline_nm', 'copper_layers', 'zones')


class HybridProof:
    def hybrid(self, root, runtime=None):
        source, _ = fixture.fixture(root)
        # Initialize the DISPOSABLE fixture once, before any baseline/plan/seal.
        # Explicit real board minima avoid the engine's missing-rules/zero-default warning.
        # These bytes and the fixture's original .dru are immutable through every stage.
        project = source / 'synthetic.kicad_pro'
        settings = json.loads(project.read_text())
        settings['board'] = {'design_settings': {'rules': {
            'min_clearance': 0.2, 'min_track_width': 0.15,
            'min_via_diameter': 0.7, 'min_through_hole_diameter': 0.3}}}
        project.write_text(json.dumps(settings, indent=2) + '\n')
        before = fixture.hashes(source)
        cwd = root / 'Unrelated working directory with spaces'; cwd.mkdir()
        logs = root / 'logs'; logs.mkdir()
        requests = root / 'Requests'; requests.mkdir()
        plans = root / 'Plans'; plans.mkdir()
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}; env.pop('PYTHONPATH', None)
        commands = []

        def cli(*args, expected=0):
            argv = ['/usr/bin/python3', '-B', str(TOOLS / 'kicad_tools.py'), *map(str, args)]
            r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=240)
            log = logs / f'{len(commands):02d}-{args[0]}.log'; log.write_text(r.stdout + r.stderr)
            commands.append({'command': list(map(str, args[:2])), 'exit_code': r.returncode,
                             'log_sha256': t.sha(log)})
            self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
            return json.loads(r.stdout)

        def native(frozen, output, **kwargs):
            args = ['tracemaker', 'validate', frozen, 'synthetic.kicad_pcb', output]
            for key, value in kwargs.items(): args += ['--' + key.replace('_', '-'), value]
            result = cli(*args)
            self.assertTrue(result['assets_unchanged']); self.assertTrue(result['native_commands_ok'])
            self.assertEqual(result['drc']['active_errors'], 0)
            self.assertEqual(result['drc']['counts'], ZERO)
            return result, json.loads((output / 'snapshot.json').read_text())

        def freeze(board, output):
            cli('tracemaker', 'freeze', board, output)
            self.assertEqual((output / board.name).read_bytes(), board.read_bytes())
            self.assertTrue((output / 'Auto.pretty/R.kicad_mod').is_file())
            self.assertTrue((output / 'Auto.kicad_sym').is_file())
            for suffix in ('.kicad_pro', '.kicad_dru'):
                self.assertEqual((output / ('synthetic' + suffix)).read_bytes(), (source / ('synthetic' + suffix)).read_bytes())
            return t.frozen(output)

        def full(project, output):
            result = cli('check', '--project-dir', project, '--reports', output, '--kicad-cli', '/usr/bin/kicad-cli')
            self.assertTrue(result['source_unchanged'])
            report = json.loads((output / 'summary.json').read_text())
            self.assertTrue(report['ref_pin_net_parity']['equal'])
            self.assertTrue(all(c['returncode'] == 0 for c in report['commands']))
            commands.append({'command': ['full-check-summary'], 'summary_sha256': t.sha(output / 'summary.json')})
            self.assertEqual(result['errors'], [])
            self.assertEqual(result['status'], 'no_findings_in_requested_checks')
            self.assertEqual(result['findings']['erc']['total_including_exclusions'], 0)
            self.assertEqual(result['findings']['drc']['total_including_exclusions'], 0)
            return result

        def engine(action, sealed, output):
            result = cli('tracemaker', 'run', action, sealed, 'synthetic.kicad_pcb', output,
                         '--engine', runtime['engine'], '--sha256', runtime['sha256'], '--deps', runtime['deps'],
                         *(['--experimental', '--only-net', 'SIGNAL'] if action == 'route' else []))
            self.assertEqual(result['exit_code'], 0); self.assertIsNone(result['cap_reason'])
            self.assertTrue(result['input_unchanged']); self.assertEqual(result['engine_pin'], t.PIN)
            self.assertIn('--unshare-all', result['argv']); self.assertIn('--clearenv', result['argv'])
            report = json.loads((output / (action + '.json')).read_text())
            if action == 'drc':
                self.assertEqual(report['violations'], [])
                self.assertEqual(report['unconnected_items'], [])
                self.assertEqual(report['warnings'], [])
            if action == 'route':
                self.assertGreater(report['routed'], 0)
                self.assertEqual(report['routed'], report['connections'])
            commands.append({'command': ['engine', action], 'exit_code': result['exit_code'],
                             'log_sha256': t.sha(output / (action + '.log')),
                             'report_sha256': t.sha(output / (action + '.json'))})
            return report

        cli('pcb', 'inspect', '--project-dir', source, '--pcbnew-python', '/usr/bin/python3')
        initial = root / 'NEW initial freeze'; freeze(source / 'synthetic.kicad_pcb', initial)
        _, initial_inventory = native(initial, root / 'NEW initial native')
        # Move core R2 deliberately. Moves do NOT drag traces: explicitly replace its route.
        placement_uuid = fixture.uid('hybrid-placement-route')
        placement = {'schema_version': 1, 'operations': [
            {'op': 'move_footprint', 'target': {'ref': 'R2'}, 'at': [30, 21]},
            {'op': 'delete_item', 'uuid': fixture.uid('route'), 'expected_kind': 'track'},
            {'op': 'add_polyline', 'uuid': placement_uuid, 'net': 'SIGNAL', 'layer': 'F.Cu',
             'width_mm': 0.25, 'start': {'pad': {'ref': 'R1', 'number': '1'}},
             'end': {'pad': {'ref': 'R2', 'number': '1'}}, 'waypoints': []}]}

        def apply_ops(project, operations, name):
            ops = requests / (name + ' operations.json'); ops.write_text(json.dumps(operations))
            plan = cli('pcb', 'plan', '--project-dir', project, '--ops', ops,
                       '--pcbnew-python', '/usr/bin/python3', '--kicad-cli', '/usr/bin/kicad-cli')
            plan_path = plans / (name + ' plan.json'); plan_path.write_text(json.dumps(plan))
            candidate = root / ('NEW ' + name + ' candidate')
            result = cli('pcb', 'apply', '--plan', plan_path, '--output', candidate,
                         '--pcbnew-python', '/usr/bin/python3', '--kicad-cli', '/usr/bin/kicad-cli')
            self.assertEqual(result['status'], 'accepted', result['errors'])
            self.assertTrue(result['checks']['parity']['equal'])
            completion = json.loads((candidate / 'completion.json').read_text())
            self.assertEqual(completion['board'], result['board'])
            commands.append({'command': ['recorded-plan', name], 'plan_sha256': t.sha(plan_path),
                             'completion_sha256': t.sha(candidate / 'completion.json')})
            return candidate / completion['board']

        board = apply_ops(source, placement, 'placed')
        self.assertIn('(net "SIGNAL")', board.read_text())
        self.assertFalse(any(n[3][0] == 'net' for n in t.nodes(board.read_text())))
        placed = root / 'NEW placed freeze'; placed_hashes = freeze(board, placed)
        placed_report = root / 'NEW placed native'; _, inventory = native(placed, placed_report)
        # Exactly one intended placement change; every pad property other than translation is unchanged.
        for original, moved in zip(initial_inventory['footprints'], inventory['footprints']):
            expected = json.loads(json.dumps(original))
            if original['reference'] == 'R2':
                expected['position_nm'][1] += 1000000
                for pad in expected['pads']: pad['position_nm'][1] += 1000000
            self.assertEqual(moved, expected)
        for key in INVARIANTS[1:]: self.assertEqual(initial_inventory[key], inventory[key])
        self.assertEqual(sorted(inventory['net_partition']), ['SIGNAL'])
        full(placed, root / 'NEW placed full checks')
        # Positive strict native named-net copper removal, selecting the exact inspected UUID.
        stripped = root / 'NEW stripped'
        manifest = cli('tracemaker', 'strip', placed, board.name, stripped,
                       '--net', 'SIGNAL', '--segment-uuid', placement_uuid)
        self.assertEqual(manifest['authorized_segment_uuids'], [placement_uuid])
        self.assertEqual([r['uuid'] for r in manifest['removed_segments']], [placement_uuid])
        stripped_hashes = t.frozen(stripped)
        strip_native = root / 'NEW stripped native'
        opens = cli('tracemaker', 'validate', stripped, board.name, strip_native, expected=2)
        self.assertGreater(opens['drc']['counts']['unconnected_items'], 0)
        self.assertEqual(opens['drc']['counts']['violations'], 0)
        self.assertEqual(opens['drc']['counts']['schematic_parity'], 0)
        stripped_inventory = json.loads((strip_native / 'snapshot.json').read_text())
        for key in INVARIANTS: self.assertEqual(inventory[key], stripped_inventory[key])
        self.assertEqual(stripped_inventory['tracks'], [])
        router_summary = {'executed': False}
        polish_input = placed
        if runtime:
            self.assertEqual(runtime['sha256'], t.REVIEWED_ENGINE_SHA256)
            self.assertEqual(t.sha(runtime['engine']), runtime['sha256'])
            self.assertTrue(Path(runtime['deps']).is_dir())
            inspected = engine('inspect', stripped, root / 'NEW engine inspect')
            self.assertEqual(inspected['min_track_width'], 150000)
            self.assertEqual(inspected['nets'], ['SIGNAL'])
            output = root / 'NEW engine route'; routed = engine('route', stripped, output)
            raw = cli('tracemaker', 'compare', stripped / board.name, output / board.name, '--net', 'SIGNAL')
            self.assertTrue(raw['passed']); self.assertGreater(len(raw['additions']), 0)
            # Complete closed candidate, not engine output alone, copied WITHOUT changing routed bytes.
            complete = root / 'NEW complete engine candidate'; shutil.copytree(stripped, complete)
            shutil.copy2(output / board.name, complete / board.name); t.seal(complete)
            complete_hashes = t.frozen(complete)
            engine_drc = engine('drc', complete, root / 'NEW engine candidate drc')
            checked = root / 'NEW engine native'
            accepted = cli('tracemaker', 'validate', stripped, board.name, checked, '--candidate', output / board.name,
                           '--net', 'SIGNAL', '--baseline-report', placed_report / 'drc.json')
            self.assertTrue(accepted['passed_drc_relative_to_baseline']); self.assertTrue(accepted['assets_unchanged'])
            self.assertTrue(accepted['native_commands_ok']); self.assertEqual(accepted['new_native_diagnostics'], [])
            self.assertEqual(accepted['drc']['counts'], ZERO)
            canonical = cli('tracemaker', 'compare', strip_native / 'canonical.kicad_pcb',
                            checked / 'canonical.kicad_pcb', '--semantic', '--net', 'SIGNAL')
            self.assertTrue(canonical['passed'])
            routed_inventory = json.loads((checked / 'snapshot.json').read_text())
            for key in INVARIANTS: self.assertEqual(inventory[key], routed_inventory[key])
            self.assertEqual(inventory['vias'], routed_inventory['vias'])
            self.assertGreater(len(routed_inventory['tracks']), 0)
            full(complete, root / 'NEW engine full checks')
            polish_input = complete
            self.assertEqual(t.frozen(complete), complete_hashes)
            router_summary = {'executed': True, 'pin': t.PIN, 'binary_sha256': runtime['sha256'],
                              'deliberate_opens': opens['drc']['counts']['unconnected_items'],
                              'added_copper': len(raw['additions']), 'native_counts': accepted['drc']['counts'],
                              'inspect': inspected, 'route': routed, 'drc': engine_drc}

        # Fresh inspection, explicit delete/replacement, two ordinary vias and chosen waypoints.
        view = cli('pcb', 'inspect', '--project-dir', polish_input, '--pcbnew-python', '/usr/bin/python3')
        tracks = [i for i in view['items'] if i['kind'] == 'track']
        self.assertGreater(len(tracks), 0)
        via1, via2 = fixture.uid('hybrid-via1'), fixture.uid('hybrid-via2')
        polish = {'schema_version': 1, 'operations': [
            *[{'op': 'delete_item', 'uuid': track['uuid'], 'expected_kind': 'track'} for track in tracks],
            {'op': 'add_via', 'uuid': via1, 'net': 'SIGNAL', 'at': [22, 20], 'diameter_mm': 0.7, 'drill_mm': 0.3},
            {'op': 'add_via', 'uuid': via2, 'net': 'SIGNAL', 'at': [28, 21], 'diameter_mm': 0.7, 'drill_mm': 0.3},
            {'op': 'add_polyline', 'uuid': fixture.uid('hybrid-front1'), 'net': 'SIGNAL', 'layer': 'F.Cu', 'width_mm': 0.25,
             'start': {'pad': {'ref': 'R1', 'number': '1'}}, 'end': {'uuid': via1}},
            {'op': 'add_polyline', 'uuid': fixture.uid('hybrid-back'), 'net': 'SIGNAL', 'layer': 'B.Cu', 'width_mm': 0.25,
             'start': {'uuid': via1}, 'end': {'uuid': via2}, 'waypoints': [[24, 20], [26, 21]]},
            {'op': 'add_polyline', 'uuid': fixture.uid('hybrid-front2'), 'net': 'SIGNAL', 'layer': 'F.Cu', 'width_mm': 0.25,
             'start': {'uuid': via2}, 'end': {'pad': {'ref': 'R2', 'number': '1'}}}]}
        polished_board = apply_ops(polish_input, polish, 'polished')
        self.assertFalse(t.compare(polish_input / board.name, polished_board, ['SIGNAL'])['passed'])
        final_frozen = root / 'NEW authorized polish baseline'; final_hashes = freeze(polished_board, final_frozen)
        final, final_inventory = native(final_frozen, root / 'NEW polished native')
        self.assertEqual(len(final_inventory['vias']), 2)
        for via in final_inventory['vias']:
            self.assertEqual((via['diameter_nm'], via['drill_nm'], via['net']), (700000, 300000, 'SIGNAL'))
        self.assertEqual({tuple(v['position_nm']) for v in final_inventory['vias']}, {(22000000,20000000),(28000000,21000000)})
        for key in INVARIANTS: self.assertEqual(inventory[key], final_inventory[key])
        full(final_frozen, root / 'NEW final full checks')
        if runtime:
            router_summary['final_drc'] = engine('drc', final_frozen, root / 'NEW engine polished drc')
        # Positive inline-via strip contract only; no extra routing candidate or mechanical hole removal.
        via_probe = root / 'NEW named via authorization'
        via_manifest = cli('tracemaker', 'strip', final_frozen, board.name, via_probe, '--net', 'SIGNAL',
                           '--regenerate-signal-vias', '--via-uuid', via1,
                           '--segment-uuid', final_inventory['tracks'][0]['uuid'])
        self.assertEqual(via_manifest['removed_vias'][0]['net'], 'SIGNAL')
        self.assertNotIn('net_code', via_manifest['removed_vias'][0])
        self.assertEqual(t.frozen(final_frozen), final_hashes)
        self.assertEqual(t.frozen(placed), placed_hashes); self.assertEqual(t.frozen(stripped), stripped_hashes)
        self.assertEqual(fixture.hashes(source), before)
        summary = {'synthetic_only': True, 'native_version': inventory['kicad_version'],
                   'router': router_summary, 'final_vias': 2, 'final_drc_parity_opens': final['drc']['counts'],
                   'mechanical_placement_net_invariants': True, 'rules_unchanged_all_stages': True, 'sources_unchanged': True, 'source_hashes': before, 'commands': commands}
        if runtime:
            # Compact proof, no design files or full engine report dumps in retained summaries.
            for key in ('drc', 'final_drc'):
                summary['router'][key]['finding_counts'] = {k: len(summary['router'][key][k])
                                                          for k in ('violations','unconnected_items','warnings')}
            for key in ('inspect', 'route', 'drc', 'final_drc'):
                summary['router'][key] = {k: v for k, v in summary['router'][key].items()
                                          if not isinstance(v, (list, dict)) or k == 'finding_counts'}
        summary_path = os.environ.get('KICAD_TRACEMAKER_SUMMARY') if runtime else None
        if summary_path:
            self.assertFalse(Path(summary_path).exists()); t.write_json(summary_path, summary)
        print(json.dumps(summary))

    def temporary_hybrid(self, runtime=None):
        scratch = TOOLS / 'tracemaker-native.tmp'; scratch.mkdir(exist_ok=True)
        retained = os.environ.get('KICAD_TRACEMAKER_ARTIFACTS') if runtime else None
        if retained:
            root = Path(retained).absolute(); root.mkdir(); self.hybrid(root, runtime)
        else:
            with tempfile.TemporaryDirectory(prefix='synthetic hybrid with spaces ', dir=scratch) as temporary:
                self.hybrid(Path(temporary).resolve(), runtime)


@unittest.skipUnless(os.environ.get('KICAD_TRACEMAKER_NATIVE') == '1',
                     'set KICAD_TRACEMAKER_NATIVE=1 with matching CLI/pcbnew 10.0.x; no engine needed')
class NativeHandoffTests(HybridProof, unittest.TestCase):
    def test_actual_inline_save_freeze_strip_native_and_cli_polish(self):
        self.temporary_hybrid()


@unittest.skipUnless(os.environ.get('KICAD_TRACEMAKER_ENGINE_NATIVE') == '1',
                     'external CPU engine opt-in; explicit ENGINE/DEPS/SHA256 required, never provisioned by tests')
class EngineHybridTests(HybridProof, unittest.TestCase):
    def test_real_cpu_route_closes_opens_then_cli_polish(self):
        runtime = {k: os.environ.get('KICAD_TRACEMAKER_' + k.upper()) for k in ('engine', 'deps', 'sha256')}
        self.assertTrue(all(runtime.values()), 'explicit external engine/deps/digest paths required')
        self.temporary_hybrid(runtime)


if __name__ == '__main__':
    unittest.main()
