import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from schematic.api import (Error, apply_plan, digest, inspect_sheet, plan_edits, strict_json, Context, load_sheet)
from native import read_netlist, source_blocks
from synthetic import create, snapshot, uid, wire, junction, label

H = [[15.24, 25.4], [35.56, 25.4]]
V = [[25.4, 15.24], [25.4, 35.56]]
X = [25.4, 25.4]


def request(*edits, crossings=None):
    r = {"schema_version": 1, "grid_mm": 1.27, "edits": list(edits)}
    if crossings is not None:
        r["crossings"] = crossings
    return r


def add_wire(points):
    return {"op": "add_wire", "points": points}


def add_label(at, text):
    return {"op": "add_local_label", "at": at, "text": text}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schematic synthetic ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = create(self.root)
        self.output = self.root / "NEW output"

    def plan(self, edits):
        return plan_edits(self.source, self.output, edits)

    def rejected(self, edits, message=None):
        with self.assertRaises((Error, ValueError)) as ctx:
            self.plan(edits)
        if message:
            self.assertIn(message, str(ctx.exception))
        self.assertFalse(self.output.exists())


class Safety(Fixture):
    def test_inspect_and_plan_are_write_free(self):
        before = snapshot(self.root)
        with patch('subprocess.run', side_effect=AssertionError('plan must not invoke native')):
            info = inspect_sheet(self.source)
            plan = self.plan(request(add_wire(H)))
        self.assertEqual(len(info['symbols']), 5)
        self.assertEqual(plan['added_block_count'], 1)
        self.assertFalse(plan['native_checks_run'])
        self.assertEqual(snapshot(self.root), before)
        self.assertNotIn('board', info)

    def test_unknown_fields_versions_and_symbol_edits(self):
        for r in [dict(request(add_wire(H)), unknown=True), dict(request(add_wire(H)), schema_version=True),
                  dict(request(add_wire(H)), schema_version=2), request(dict(add_wire(H), width=2)),
                  request({'op': 'set_property', 'uuid': uid('R1'), 'name': 'Value', 'value': 'x'}),
                  request({'op': 'add_global_label', 'at': X, 'text': 'bad'}), request({'op': 'add_symbol'})]:
            self.rejected(r)

    def test_grid_coordinates_and_polyline_shapes(self):
        for points in [[[15.24, 25.4], [35.561, 25.4]], [[True, 0], [2.54, 0]], [['0', 0], [2.54, 0]],
                       [[0, 0], [2.54, 2.54]], [[0, 0], [0, 0]], [[float('inf'), 0], [2.54, 0]]]:
            self.rejected(request(add_wire(points)))
        self.rejected(dict(request(add_wire(H)), grid_mm=0))
        self.assertEqual(self.plan(request(add_wire([[15.24,25.4],[20.32,25.4],[20.32,30.48],[35.56,30.48],[35.56,25.4]])))['added_block_count'], 4)

    def test_crossing_semantics_and_overlaps(self):
        self.rejected(request(add_wire(H), add_wire(V)), 'Ambiguous')
        plan = self.plan(request(add_wire(H), add_wire(V), crossings=[{'at': X, 'mode': 'no_join'}]))
        self.assertEqual(plan['added_block_count'], 2)
        self.rejected(request(add_wire(H), add_wire([X, V[1]]), crossings=[{'at': X, 'mode': 'no_join'}]), 'T-join')
        self.rejected(request(add_wire(H), add_wire(H)), 'overlapping')
        self.rejected(request(add_wire(H), crossings=[{'at': X, 'mode': 'no_join'}]), 'Unused')
        self.rejected(request(add_wire(H), {'op':'add_junction','at':X}), 'three')
        self.rejected(request(add_wire(H), add_wire(V), add_label(X, 'CROSS'), crossings=[{'at': X, 'mode': 'no_join'}]))

    def test_labels_reject_bus_variable_duplicate_or_unknown_fields(self):
        for text in ["+5V", "-12V", "3V3"]:
            self.assertEqual(self.plan(request(add_label(H[0], text)))["added_block_count"], 1)
        for text in ['BUS[0..3]', '${NOTE}', 'bad\nname', '', '~{bad}', 'A/B']:
            self.rejected(request(add_label(H[0], text)))
        self.rejected(request(add_label(H[0], 'A'), add_label(H[0], 'B')))
        self.rejected(request(dict(add_label(H[0], 'A'), angle=45)))

    def test_missing_context_hierarchy_repeated_instances(self):
        pro = self.source.with_suffix('.kicad_pro')
        pro.rename(pro.with_suffix('.hidden'))
        self.rejected(request(add_wire(H)), 'context')
        pro.with_suffix('.hidden').rename(pro)
        original = self.source.read_bytes()
        for extra in ['(sheet (uuid "' + uid('sheet') + '"))', '(bus)', '(bus_entry)', '(global_label "X")', '(hierarchical_label "X")']:
            self.source.write_bytes(original.rstrip()[:-1] + extra.encode() + b')')
            self.rejected(request(add_wire(H)), 'flat')
        self.source.write_bytes(original.replace(('(path "/'+uid('root')+'" (reference "R1")').encode(), ('(path "/'+uid('root')+'/'+uid('child')+'" (reference "R1")').encode()))
        self.rejected(request(add_wire(H)), 'Hierarchy')

    def test_missing_uuid_is_malformed_not_silently_generated(self):
        original = self.source.read_bytes()
        malformed_wire = '(wire (pts (xy 15.24 25.4) (xy 35.56 25.4)) (stroke (width 0) (type default)))'
        self.source.write_bytes(original.rstrip()[:-1] + malformed_wire.encode() + b')')
        self.rejected(request(add_label(H[0], 'SIGNAL')), 'uuid')

    def test_duplicate_uuid_and_no_connect_conflict(self):
        original = self.source.read_bytes()
        self.source.write_bytes(original.replace(uid('R2').encode(), uid('R1').encode()))
        self.rejected(request(add_wire(H)), 'Duplicate')
        self.source.write_bytes(original.rstrip()[:-1] + f'(no_connect (at {H[0][0]} {H[0][1]}) (uuid "{uid("nc")}"))'.encode() + b')')
        self.rejected(request(add_wire(H)), 'no_connect')

    def test_stale_source_context_and_plan_checksum_fail_before_writes(self):
        plan = self.plan(request(add_wire(H)))
        self.source.write_bytes(self.source.read_bytes() + b'\n')
        with self.assertRaisesRegex(Error, 'Stale'):
            apply_plan(plan)
        self.assertFalse(self.output.exists())
        plan = self.plan(request(add_wire(H)))
        pro = self.source.with_suffix('.kicad_pro')
        pro.write_bytes(pro.read_bytes() + b'\n')
        with self.assertRaisesRegex(Error, 'Stale'):
            apply_plan(plan)
        self.assertFalse(self.output.exists())
        plan = self.plan(request(add_wire(H)))
        plan['candidate_sha256'] = '0' * 64
        with self.assertRaisesRegex(Error, 'checksum'):
            apply_plan(plan)
        self.assertFalse(self.output.exists())

    def test_existing_output_source_tree_and_alias_rejections(self):
        self.output.mkdir()
        with self.assertRaisesRegex(Error, 'NEW'):
            self.plan(request(add_wire(H)))
        self.output.rmdir()
        with self.assertRaises(Error):
            plan_edits(self.source, self.source.parent / 'nested output', request(add_wire(H)))
        alias = self.root / 'alias'
        alias.symlink_to(self.source.parent, target_is_directory=True)
        with self.assertRaises(Error):
            plan_edits(self.source, alias / 'new', request(add_wire(H)))
        with self.assertRaisesRegex(Error, 'aliases'):
            plan_edits(alias / self.source.name, self.output, request(add_wire(H)))
        os.link(self.source, self.root / 'hardlinked.kicad_sch')
        self.rejected(request(add_wire(H)), 'aliases')

    def test_strict_json_and_cli_errors(self):
        for raw in ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises((Error, ValueError)):
                strict_json(raw)
        result = subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1] / 'cli.py'),'plan','--input',str(self.source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'error')

    def test_plan_uuid_uniqueness_strict_plan_and_no_overwrite_at_apply(self):
        plan = self.plan(request(add_wire(H), add_label(H[0], 'SIGNAL')))
        self.assertEqual(len(plan['allocated_uuids']), len(set(plan['allocated_uuids'])))
        self.assertFalse(set(plan['allocated_uuids']) & load_sheet(self.source)['ids'])
        self.output.mkdir()
        with self.assertRaisesRegex(Error, 'NEW'):
            apply_plan(plan)
        self.output.rmdir()
        for change in [{'unknown': 1}, {'schema_version': True}, {'added_block_count': True},
                       {'allocated_uuids': [uid('R1'),uid('R2')]},
                       {'allocated_uuids': [plan['allocated_uuids'][0]] * 2}]:
            tampered = copy.deepcopy(plan)
            tampered.update(change)
            tampered['plan_sha256'] = digest({k:v for k,v in tampered.items() if k!='plan_sha256'})
            with self.assertRaises((Error, ValueError)):
                apply_plan(tampered)
            self.assertFalse(self.output.exists())

    def test_missing_library_custom_worksheet_malformed_and_bom(self):
        library = self.source.parent / 'Test.kicad_sym'
        saved_library = library.read_bytes()
        library.unlink()
        self.rejected(request(add_wire(H)), 'dependency')
        library.write_bytes(saved_library)
        pro = self.source.with_suffix('.kicad_pro')
        original_pro = pro.read_bytes()
        pro.write_text(json.dumps({'schematic': {'drawing_sheet_file': 'unresolved.kicad_wks'}}))
        self.rejected(request(add_wire(H)), 'drawing-sheet')
        pro.write_bytes(original_pro)
        original = self.source.read_bytes()
        self.source.write_bytes(original[:-3])
        self.rejected(request(add_wire(H)), 'Malformed')
        self.source.write_bytes(b'\xef\xbb\xbf' + original)
        self.rejected(request(add_wire(H)), 'BOM')

    def test_stale_library_or_new_context_table_and_missing_native(self):
        plan = self.plan(request(add_wire(H)))
        library = self.source.parent/'Test.kicad_sym'
        library.write_bytes(library.read_bytes()+b'\n')
        with self.assertRaisesRegex(Error, 'Stale'):
            apply_plan(plan)
        plan = self.plan(request(add_wire(H)))
        (self.source.parent/'fp-lib-table').write_text('(fp_lib_table (version 7))')
        with self.assertRaisesRegex(Error, 'Stale'):
            apply_plan(plan)
        plan = self.plan(request(add_wire(H)))
        with self.assertRaisesRegex(Error, 'required'):
            apply_plan(plan, kicad_cli='nonexistent-kicad-for-test')
        self.assertFalse(self.output.exists())

    def test_repeated_project_instances_are_rejected(self):
        original = self.source.read_text()
        first = '(path "/' + uid('root') + '" (reference "R1") (unit 1))'
        self.source.write_text(original.replace(first, first+' '+first, 1))
        self.rejected(request(add_wire(H)), 'Hierarchy')
        self.source.write_text(original.replace('(project "fixture"', '(project "other-project"', 1))
        self.rejected(request(add_wire(H)), 'same-stem')


@unittest.skipUnless(os.environ.get('KICAD_SCHEMATIC_INTEGRATION') == '1' and shutil.which('kicad-cli'), 'set KICAD_SCHEMATIC_INTEGRATION=1 with native KiCad 10+')
class Native(Fixture):
    def apply(self, edits):
        before = snapshot(self.source.parent)
        original_text = self.source.read_bytes().decode('utf-8')
        original_blocks = [original_text[a:b] for _,a,b in source_blocks(original_text)]
        plan = self.plan(edits)
        result = apply_plan(plan)
        self.assertNotEqual(result['status'], 'operational_error', result)
        self.assertTrue(result['source_unchanged'])
        self.assertTrue(result['native_force_save_reload_verified'])
        self.assertEqual(snapshot(self.source.parent), before)
        self.assertFalse(result['accepted'])
        self.assertTrue(result['copied_context_unchanged'])
        new_text = (self.output/self.source.name).read_bytes().decode('utf-8')
        new_blocks = [new_text[a:b] for _,a,b in source_blocks(new_text)]
        self.assertEqual(new_blocks[:len(original_blocks)], original_blocks)
        return result, read_netlist(self.output / 'reports' / 'after.xml')

    def test_native_pin_join_and_exact_delta_and_erc(self):
        result, net = self.apply(request(add_wire(H)))
        self.assertEqual(net['pins'][('R1','2')], net['pins'][('R2','1')])
        changes = result['connectivity_delta']['changed_pins']
        self.assertTrue(any(p['ref']=='R1' and p['pin']=='2' for p in changes))
        self.assertGreater(result['erc']['before']['total_including_exclusions'], 0)
        self.assertGreater(result['erc']['after']['total_including_exclusions'], 0)
        self.assertEqual(result['status'], 'draft_erc_findings')
        self.assertTrue((self.output / 'fixture.kicad_pro').is_file())
        self.assertEqual((self.output/'fixture.kicad_pro').read_bytes(), self.source.with_suffix('.kicad_pro').read_bytes())
        with self.assertRaises(Error):
            apply_plan(self.plan(request(add_wire(H))))

    def test_native_explicit_crossing_no_join(self):
        result, net = self.apply(request(add_wire(H), add_wire(V), crossings=[{'at':X, 'mode':'no_join'}]))
        self.assertEqual(net['pins'][('R1','2')], net['pins'][('R2','1')])
        self.assertEqual(net['pins'][('R3','1')], net['pins'][('R4','2')])
        self.assertNotEqual(net['pins'][('R1','2')], net['pins'][('R3','1')])

    def test_native_crossing_junction_joins_four_pin_sets(self):
        _, net = self.apply(request(add_wire(H), add_wire(V), {'op':'add_junction','at':X}))
        self.assertEqual(len({net['pins'][p] for p in [('R1','2'),('R2','1'),('R3','1'),('R4','2')]}), 1)

    def test_native_existing_crossing_junction_delta(self):
        old = self.source.parent
        shutil.rmtree(old)
        self.source = create(self.root, [wire(*H, 'h'), wire(*V, 'v')])
        result, net = self.apply(request({'op':'add_junction','at':X}))
        self.assertEqual(net['pins'][('R1','2')], net['pins'][('R3','1')])
        self.assertGreaterEqual(len(result['connectivity_delta']['changed_pins']), 2)

    def test_native_label_join_and_three_pin_symbol(self):
        result, net = self.apply(request(add_label(H[0], 'LOCAL_JOIN'), add_label([58.42,25.4], 'LOCAL_JOIN')))
        self.assertEqual(net['pins'][('R1','2')], '/LOCAL_JOIN')
        self.assertEqual(net['pins'][('U1','1')], '/LOCAL_JOIN')
        self.assertEqual(len([p for p in net['pins'] if p[0]=='U1']), 3)

    def test_native_polyline_shared_endpoint_join(self):
        points = [H[0], [20.32,25.4], [20.32,30.48], [35.56,30.48], H[1]]
        _, net = self.apply(request(add_wire(points)))
        self.assertEqual(net['pins'][('R1','2')], net['pins'][('R2','1')])

    def test_native_lossless_spans_crlf_and_source_bytes(self):
        shutil.rmtree(self.source.parent)
        self.source = create(self.root, crlf=True)
        original = self.source.read_bytes()
        old_text = original.decode('utf-8-sig')
        old_blocks = [old_text[a:b] for _,a,b in source_blocks(old_text)]
        self.apply(request(add_wire(H)))
        saved = (self.output / self.source.name).read_bytes()
        self.assertTrue(saved.startswith(b'(kicad_sch'))
        self.assertEqual(saved.count(b'\r\n'), original.count(b'\r\n')+1)
        new_text = saved.decode('utf-8-sig')
        blocks = [new_text[a:b] for _,a,b in source_blocks(new_text)]
        self.assertEqual(blocks[:len(old_blocks)], old_blocks)
        self.assertEqual(self.source.read_bytes(), original)

    def test_native_explicit_t_junction(self):
        _, net = self.apply(request(add_wire(H), add_wire([V[0],X]), {'op':'add_junction','at':X}))
        self.assertEqual(net['pins'][('R1','2')], net['pins'][('R3','1')])

    def test_native_clear_schematic_status_still_not_accepted(self):
        points = [[10.16,25.4],[15.24,25.4],[35.56,25.4],[40.64,25.4],
                  [25.4,15.24],[25.4,10.16],[25.4,40.64],[25.4,35.56],
                  [58.42,25.4],[63.5,25.4],[60.96,27.94]]
        result, net = self.apply(request(*(add_label(p, 'ALL_PINS') for p in points)))
        self.assertEqual(len(net['nets']), 1)
        self.assertEqual(result['status'], 'draft_schematic_checks_clear', result['erc']['after'])
        self.assertFalse(result['accepted'])

    def test_native_external_context_and_pretty_directory_uri(self):
        external = self.root / 'External native libraries'
        external.mkdir()
        library = self.source.parent/'Test.kicad_sym'
        library.rename(external/library.name)
        (self.source.parent/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Test") (type "KiCad") (uri '+json.dumps(str(external/library.name))+') (options "") (descr "Synthetic")))')
        pretty = external/'Test.pretty'
        pretty.mkdir()
        (pretty/'Two.kicad_mod').write_text('(footprint "Two" (version 20241229) (generator "pcbnew") (layer "F.Cu") (pad "1" smd rect (at -1 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask")) (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask")))')
        (self.source.parent/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "Test") (type "KiCad") (uri '+json.dumps(str(pretty))+') (options "") (descr "Synthetic")))')
        external_before = snapshot(external)
        result, _ = self.apply(request(add_wire(H)))
        self.assertEqual(len(result['context_rebindings']), 2)
        self.assertEqual(snapshot(external), external_before)
        for table_name in ('sym-lib-table','fp-lib-table'):
            table = (self.output/table_name).read_text()
            self.assertIn('${KIPRJMOD}/context/', table)
            self.assertNotIn(str(external), table)
        self.assertTrue((self.output/'context'/external.name/'Test.pretty'/'Two.kicad_mod').is_file())

    def test_cli_end_to_end_from_unrelated_working_directory(self):
        script = Path(__file__).resolve().parents[1]/'cli.py'
        edits = self.root/'edits.json'
        edits.write_text(json.dumps(request(add_wire(H))))
        pcb = self.source.with_suffix('.kicad_pcb')
        pcb.write_text('(kicad_pcb (version 20241229) (generator "pcbnew"))')
        before = snapshot(self.source.parent)
        def cli(*args):
            return subprocess.run([sys.executable,'-B',str(script),*map(str,args)], cwd=self.root, capture_output=True,text=True,timeout=60)
        info = cli('inspect','--input',self.source)
        self.assertEqual(info.returncode, 0, info.stdout+info.stderr)
        self.assertEqual(json.loads(info.stdout)['schema_version'], 1)
        planned = cli('plan','--input',self.source,'--edits',edits,'--output-dir',self.output)
        self.assertEqual(planned.returncode, 0, planned.stdout+planned.stderr)
        self.assertFalse(self.output.exists())
        stored = self.root/'plan.json'
        stored.write_text(planned.stdout)
        applied = cli('apply','--plan',stored)
        self.assertEqual(applied.returncode, 1, applied.stdout+applied.stderr)
        result = json.loads(applied.stdout)
        self.assertEqual(result['status'], 'draft_erc_findings')
        self.assertEqual(snapshot(self.source.parent), before)
        self.assertFalse((self.output/pcb.name).exists())
        retried = cli('apply','--plan',stored)
        self.assertEqual(retried.returncode, 2)
        self.assertEqual(json.loads(retried.stdout)['status'], 'error')

    def test_native_failure_is_machine_readable_and_not_accepted(self):
        self.source.write_text(self.source.read_text().rstrip()[:-1] + '(unsupported_native_fixture_construct))\n')
        before = snapshot(self.source.parent)
        result = apply_plan(self.plan(request(add_wire(H))))
        self.assertEqual(result['status'], 'operational_error')
        self.assertTrue(result['source_unchanged'])
        self.assertFalse(result['accepted'])
        self.assertTrue(result['errors'])
        self.assertNotEqual(result['commands'][-1]['returncode'], 0)
        self.assertEqual(snapshot(self.source.parent), before)
        self.assertEqual(json.loads((self.output/'result.json').read_text())['status'], 'operational_error')


if __name__ == '__main__':
    unittest.main()
