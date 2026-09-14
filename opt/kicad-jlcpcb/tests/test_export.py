"""Dependency-free unit tests and opt-in real KiCad integration tests."""

import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import uuid
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "export.py"
REPO = SCRIPT.parents[2]
spec = importlib.util.spec_from_file_location("jlc_export", SCRIPT)
jlc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jlc)


def arguments(*extra):
    return jlc.argument_parser().parse_args([".", *extra])


def footprint(ref="R1", attrs=("smd",), layer="F.Cu", **fields):
    return {"fields": {"Reference": ref, "Value": "10k", **fields},
            "footprint": "Test:R", "attrs": set(attrs), "layer": layer}


def position(ref="R1", **overrides):
    return {"Ref": ref, "Val": "10k", "Package": "R", "PosX": "1.25", "PosY": "-2.5",
            "Rot": "-90", "Side": "top", **overrides}


def board_text(entries=None, inner=False):
    if entries is None:
        entries = [("R1", "smd", "F.Cu", '(property "LCSC" "C123")')]
    layers = '(0 "F.Cu" signal) (2 "B.Cu" signal)'
    if inner:
        layers = '(0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal)'
    layers += ''' (13 "F.Paste" user) (15 "B.Paste" user)
        (5 "F.SilkS" user) (7 "B.SilkS" user)
        (1 "F.Mask" user) (3 "B.Mask" user) (25 "Edge.Cuts" user)'''
    footprints = []
    for i, (ref, attrs, side, props) in enumerate(entries):
        pad = '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask"))'
        if side == "B.Cu":
            pad = pad.replace('"F.', '"B.')
        if "through_hole" in attrs:
            pad = '(pad "1" thru_hole circle (at 0 0) (size 2 2) (drill 1) (layers "*.Cu" "*.Mask"))'
        footprints.append(f'''(footprint "Test:R" (layer "{side}") (at {12+i*3} 18 -90)
            (property "Reference" "{ref}" (at 0 0 0) (layer "F.SilkS") (effects (font (size 1 1))))
            (property "Value" "10k" (at 0 0 0) (layer "F.Fab") (effects (font (size 1 1))))
            {props} (attr {attrs}) {pad})''')
    return f'''(kicad_pcb (version 20241229) (generator "pcbnew")
        (general (thickness 1.6)) (paper "A4") (layers {layers})
        (setup (pad_to_mask_clearance 0) (aux_axis_origin 10 20))
        {" ".join(footprints)}
        (footprint "Test:MountingHole" (layer "F.Cu") (at 12 25)
            (property "Reference" "H1" (at 0 0 0) (layer "F.SilkS") (effects (font (size 1 1))))
            (attr exclude_from_bom exclude_from_pos_files)
            (pad "" np_thru_hole circle (at 0 0) (size 2 2) (drill 2) (layers "*.Cu" "*.Mask")))
        (gr_rect (start 10 10) (end 50 30) (stroke (width 0.05) (type default))
            (fill none) (layer "Edge.Cuts")))'''


def native_field(name, value):
    return f'(property {json.dumps(name)} {json.dumps(value)} (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))'


def schematic_text(root_id, components, paths=None, project="assembly"):
    lib = '''(lib_symbols (symbol "Test:R" (pin_names (offset 0))
        (in_bom yes) (on_board yes)
        (property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
        (property "Value" "10k" (at 0 0 0) (effects (font (size 1.27 1.27))))
        (symbol "R_1_1"
            (pin passive line (at -2.54 0 0) (length 2.54)
                (name "~" (effects (font (size 1.27 1.27))))
                (number "1" (effects (font (size 1.27 1.27))))))))'''
    symbols = []
    for ref, fields, flags in components:
        instances = paths or [(f"/{root_id}", ref)]
        path_text = " ".join(f'(path "{p}" (reference "{r}") (unit 1))' for p, r in instances)
        symbols.append(f'''(symbol (lib_id "Test:R") (at 50 50 0) (unit 1)
            (in_bom {flags.get('in_bom', 'yes')}) (on_board {flags.get('on_board', 'yes')})
            (dnp {flags.get('dnp', 'no')}) (uuid "{uuid.uuid4()}")
            {native_field('Reference', ref)} {native_field('Value', '10k')}
            {native_field('Footprint', 'Test:R')}
            {" ".join(native_field(k, v) for k, v in fields.items())}
            (instances (project "{project}" {path_text})))''')
    return f'''(kicad_sch (version 20250114) (generator "eeschema")
        (uuid "{root_id}") (paper "A4") {lib} {" ".join(symbols)})'''


class ParsingTests(unittest.TestCase):
    def test_sexpr_escaped_strings_and_unicode(self):
        self.assertEqual(jlc.parse_sexpr(r'(root (field "a (b) \"c\" \\ Ω") (x -1.2))'),
                         ["root", ["field", 'a (b) "c" \\ Ω'], ["x", "-1.2"]])

    def test_malformed_sexpr(self):
        for text in ('(root', '(root))', '(root "bad)', '(root) (extra)', '"not a board"'):
            with self.subTest(text=text), self.assertRaises(jlc.ExportError):
                jlc.parse_sexpr(text)

    def test_board_fields_layers_and_mechanical_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.kicad_pcb"
            path.write_text(board_text(inner=True))
            fps, layers, copper = jlc.read_board(path)
            self.assertEqual(list(fps), ["R1"])
            self.assertEqual(fps["R1"]["fields"]["LCSC"], "C123")
            self.assertEqual(len(copper), 4)
            self.assertIn("In2.Cu", layers)

    def test_duplicate_and_unannotated_board_references_fail(self):
        for entries in ([('R1', 'smd', 'F.Cu', ''), ('R1', 'smd', 'F.Cu', '')],
                        [('R?', 'smd', 'F.Cu', '')]):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "test.kicad_pcb"
                path.write_text(board_text(entries))
                with self.assertRaises(jlc.ExportError):
                    jlc.read_board(path)

    def test_csv_quotes_unicode_and_bom(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bom.csv"
            row = ('10k, 1% Ω "precision"', 'R1, R2', 'R', 'C123', 2, '', '')
            jlc.write_csv(path, jlc.BOM_HEADER, [row])
            rows = jlc.read_csv(path, jlc.BOM_HEADER)
            self.assertEqual(rows[0]["Comment"], row[0])
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_bad_csv_and_duplicate_references_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.csv"
            for content in ('Ref,Ref\nR1,R2\n', 'Ref,Val\nR1\n', 'Ref\nR1,extra\n'):
                path.write_text(content)
                with self.assertRaises(jlc.ExportError):
                    jlc.read_csv(path, ['Ref'])
        with self.assertRaises(jlc.ExportError):
            jlc.indexed([position(), position()], "Ref")

    def test_input_discovery_ambiguity_and_explicit_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ('one', 'two', '_autosave-one'):
                (directory / (name + '.kicad_pcb')).touch()
            args = jlc.argument_parser().parse_args([temp])
            with self.assertRaisesRegex(jlc.ExportError, 'found 2'):
                jlc.select_inputs(args)
            args.board = 'one'
            board, sch, output = jlc.select_inputs(args)
            self.assertEqual(board.name, 'one.kicad_pcb')
            self.assertIsNone(sch)
            self.assertEqual(output, directory / 'jlcpcb' / 'one')
            (directory / 'root.kicad_sch').touch()
            with self.assertRaisesRegex(jlc.ExportError, '--schematic'):
                jlc.select_inputs(args)
            args.schematic = 'root.kicad_sch'
            self.assertEqual(jlc.select_inputs(args)[1].name, 'root.kicad_sch')


class AssemblyTests(unittest.TestCase):
    def assemble(self, fps=None, positions=None, symbols=None, *flags):
        return jlc.assembly_rows(fps or {'R1': footprint(LCSC='C123')},
                                 positions or {'R1': position()}, symbols, arguments(*flags))

    def test_schematic_only_fields_and_mpn(self):
        symbol = {'LCSC_Part_Number': 'c123', 'MPN': 'PART-X', 'Manufacturer': 'ACME'}
        bom, cpl, _, _, _ = self.assemble({'R1': footprint()}, symbols={'R1': symbol})
        self.assertEqual(bom[0][3:], ('C123', 1, 'ACME', 'PART-X'))
        self.assertEqual(cpl[0], ('R1', '1.250000', '-2.500000', '270.000000', 'top'))

    def test_blank_schematic_field_falls_back_to_pcb(self):
        bom, *_ = self.assemble(symbols={'R1': {'LCSC': '~'}})
        self.assertEqual(bom[0][3], 'C123')

    def test_conflicting_part_codes_fail(self):
        with self.assertRaisesRegex(jlc.ExportError, 'conflicting LCSC'):
            self.assemble(symbols={'R1': {'LCSC PN': 'C999'}})
        with self.assertRaisesRegex(jlc.ExportError, 'conflicting LCSC'):
            self.assemble({'R1': footprint(LCSC='C123', **{'JLCPCB Part #': 'C456'})})

    def test_invalid_catalog_numbers_fail_not_mpn(self):
        for code in ('MCP6002', 'https://lcsc.com/C123', 'C12, C34', 'C12\n3'):
            with self.subTest(code=code), self.assertRaisesRegex(jlc.ExportError, 'C followed by digits'):
                self.assemble({'R1': footprint(LCSC=code)})
        bom, _, _, warnings, missing = self.assemble({'R1': footprint(MPN='MCP6002')})
        self.assertEqual(bom[0][3], '')
        self.assertEqual(bom[0][-1], 'MCP6002')
        self.assertEqual(missing, ['R1'])
        self.assertTrue(warnings)

    def test_custom_catalog_field(self):
        result = self.assemble({'R1': footprint(**{'Supplier Code': 'C42'})}, None, None,
                               '--part-field', 'Supplier Code', '--require-part-numbers')
        self.assertEqual(result[0][0][3], 'C42')

    def test_require_numbers_fails(self):
        with self.assertRaisesRegex(jlc.ExportError, 'Missing LCSC'):
            self.assemble({'R1': footprint()}, None, None, '--require-part-numbers')

    def test_grouping_is_natural_and_part_sensitive(self):
        fps = {ref: footprint(ref, LCSC=code) for ref, code in
               [('R10', 'C1'), ('R2', 'C1'), ('R1', 'C2'), ('R3', '')]}
        pos = {ref: position(ref) for ref in fps}
        bom, cpl, *_ = self.assemble(fps, pos)
        self.assertEqual([row[0] for row in cpl], ['R1', 'R2', 'R3', 'R10'])
        self.assertEqual(len(bom), 3)
        self.assertEqual(next(row for row in bom if row[3] == 'C1')[1], 'R2, R10')
        self.assertEqual(next(row for row in bom if row[3] == 'C1')[4], 2)

    def test_grouping_is_mpn_sensitive(self):
        fps = {'R1': footprint(LCSC='C1', MPN='A'), 'R2': footprint('R2', LCSC='C1', MPN='B')}
        bom, *_ = self.assemble(fps, {ref: position(ref) for ref in fps})
        self.assertEqual(len(bom), 2)

    def test_all_native_exclusions_apply_to_both_csvs(self):
        for attr in ('dnp', 'exclude_from_bom', 'exclude_from_pos_files'):
            with self.subTest(attr=attr):
                bom, cpl, excluded, *_ = self.assemble({'R1': footprint(attrs=('smd', attr))})
                self.assertEqual((bom, cpl), ([], []))
                self.assertIn('R1', excluded)
        for field in ('__DNP', '__EXCLUDE_FROM_BOM', '__EXCLUDE_FROM_BOARD'):
            with self.subTest(field=field):
                bom, cpl, excluded, *_ = self.assemble(symbols={'R1': {field: field}})
                self.assertEqual((bom, cpl), ([], []))
                self.assertIn('R1', excluded)

    def test_through_hole_and_side_filters(self):
        fps = {'R1': footprint(attrs=('through_hole',), layer='B.Cu', LCSC='C1')}
        pos = {'R1': position(Side='bottom')}
        self.assertEqual(self.assemble(fps, pos)[1], [])
        result = self.assemble(fps, pos, None, '--include-through-hole')
        self.assertEqual(result[1][0][1:3], ('1.250000', '-2.500000'))
        self.assertEqual(self.assemble(fps, pos, None, '--include-through-hole', '--side', 'top')[1], [])

    def test_rotation_offset_is_additive_on_both_sides(self):
        for side, layer in [('top', 'F.Cu'), ('bottom', 'B.Cu')]:
            fps = {'R1': footprint(layer=layer, LCSC='C1', **{'JLCPCB Rotation Offset': '-90'})}
            result = self.assemble(fps, {'R1': position(Side=side)})
            self.assertEqual(result[1][0][3], '180.000000')

    def test_bad_position_and_offset_values_fail(self):
        for key, value in [('PosX', 'nan'), ('PosY', 'inf'), ('Rot', 'bad'), ('Side', 'back')]:
            with self.subTest(key=key), self.assertRaises(jlc.ExportError):
                self.assemble(positions={'R1': position(**{key: value})})
        with self.assertRaises(jlc.ExportError):
            self.assemble({'R1': footprint(**{'JLCPCB Rotation Offset': 'nan'})})

    def test_missing_positions_fail_but_excluded_missing_positions_do_not(self):
        with self.assertRaisesRegex(jlc.ExportError, 'missing from KiCad position'):
            self.assemble(positions={'R2': position('R2')})
        self.assemble({'R1': footprint(attrs=('smd', 'exclude_from_pos_files'))}, {'R2': position('R2')})

    def test_value_and_footprint_mismatch_warn_and_use_actual_board(self):
        bom, _, _, warnings, _ = self.assemble(symbols={'R1': {'Value': '20k', 'Footprint': 'Other:X'}})
        self.assertEqual(bom[0][0], '10k')
        self.assertEqual(bom[0][2], 'R')
        self.assertEqual(len(warnings), 2)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jlc test with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / 'assembly.kicad_pcb').write_text(board_text())
        self.args = jlc.argument_parser().parse_args([str(self.directory), '--require-part-numbers'])
        self.calls = []

    def fake_cli(self, cli, args, cwd):
        self.calls.append(args)
        if args == ['version']:
            return '9.0.8'
        output = Path(args[args.index('--output') + 1])
        if args[:3] == ['pcb', 'export', 'pos']:
            jlc.write_csv(output, position().keys(), [position().values()])
        elif args[:3] == ['pcb', 'export', 'gerbers']:
            for layer in args[args.index('--layers') + 1].split(','):
                (output / ('assembly-' + layer.replace('.', '_') + '.gbr')).write_text('G04 test*\nM02*')
            (output / 'ignored.gbrjob').write_text('{}')
        elif args[:3] == ['pcb', 'export', 'drill']:
            (output / 'assembly-PTH.drl').write_text('M48\nMETRIC\nM30')
            (output / 'assembly-NPTH.drl').write_text('M48\nMETRIC\nM30')
        else:
            self.fail(str(args))
        return ''

    def run_export(self):
        with mock.patch.object(jlc.shutil, 'which', return_value='/fake/kicad-cli'), \
             mock.patch.object(jlc, 'run_cli', side_effect=self.fake_cli), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return jlc.export_project(self.args)

    def test_complete_pipeline_outputs_and_common_origin(self):
        before = (self.directory / 'assembly.kicad_pcb').read_bytes()
        report = self.run_export()
        output = self.directory / 'jlcpcb' / 'assembly'
        self.assertEqual(report['component_count'], 1)
        self.assertEqual(len(list(output.iterdir())), 4)
        with zipfile.ZipFile(output / 'assembly-gerbers.zip') as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), 11)
            self.assertTrue(all('/' not in name and name.endswith(('.gbr', '.drl')) for name in archive.namelist()))
        for call in self.calls[1:]:
            if call[2] == 'drill':
                self.assertEqual(call[call.index('--drill-origin') + 1], 'plot')
                self.assertIn('--excellon-separate-th', call)
            else:
                self.assertIn('--use-drill-file-origin', call)
        self.assertEqual(before, (self.directory / 'assembly.kicad_pcb').read_bytes())

    def test_overwrite_is_explicit_and_leaves_unrelated_files(self):
        self.run_export()
        with self.assertRaisesRegex(jlc.ExportError, 'Refusing to replace'):
            self.run_export()
        output = self.directory / 'jlcpcb' / 'assembly'
        (output / 'notes.txt').write_text('keep me')
        self.args.overwrite = True
        self.run_export()
        self.assertEqual((output / 'notes.txt').read_text(), 'keep me')

    def test_command_failure_preserves_old_export(self):
        self.run_export()
        output = self.directory / 'jlcpcb' / 'assembly'
        original = {p.name: p.read_bytes() for p in output.iterdir()}
        self.args.overwrite = True
        original_cli = self.fake_cli

        def fail(cli, args, cwd):
            if args[:3] == ['pcb', 'export', 'drill']:
                raise jlc.ExportError('simulated drill failure')
            return original_cli(cli, args, cwd)

        self.fake_cli = fail
        with self.assertRaisesRegex(jlc.ExportError, 'simulated drill failure'):
            self.run_export()
        self.assertEqual(original, {p.name: p.read_bytes() for p in output.iterdir()})
        self.assertFalse(list(output.parent.glob('.jlcpcb-export-*')))

    def test_missing_cli_and_old_cli_errors(self):
        with mock.patch.object(jlc.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(jlc.ExportError, 'kicad-cli not found'):
                jlc.export_project(self.args)
        self.fake_cli = lambda *args: '8.0.0'
        with self.assertRaisesRegex(jlc.ExportError, '9 or newer'):
            self.run_export()


@unittest.skipUnless(os.environ.get('KICAD_JLCPCB_INTEGRATION') == '1' and shutil.which('kicad-cli'),
                     'set KICAD_JLCPCB_INTEGRATION=1 with kicad-cli installed')
class KiCadIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jlc real integration ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def run_export(self, directory=None, *flags):
        args = jlc.argument_parser().parse_args([str(directory or self.directory), *flags])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return jlc.export_project(args)

    def assert_csv_parity(self, output):
        bom = jlc.read_csv(output / 'bom.csv', jlc.BOM_HEADER)
        cpl = jlc.read_csv(output / 'positions.csv', jlc.CPL_HEADER)
        bom_refs = [r.strip() for row in bom for r in row['Designator'].split(',')]
        self.assertEqual(sorted(bom_refs), sorted(row['Designator'] for row in cpl))
        self.assertEqual(len(bom_refs), sum(int(row['Quantity']) for row in bom))
        return bom, cpl

    def test_repository_boards_two_four_layers_and_existing_lcsc(self):
        for rel, count in [('opt/Breakouts/MCP6002', 2), ('modules/line_in', 2), ('modules/4mix', 4)]:
            with self.subTest(project=rel):
                source = REPO / rel
                before = {p: hashlib.sha256(p.read_bytes()).digest() for p in source.glob('*.kicad_*')}
                output = self.directory / source.name
                report = self.run_export(source, '--output', str(output))
                self.assertEqual(report['copper_layer_count'], count)
                bom, cpl = self.assert_csv_parity(output)
                self.assertTrue(cpl)
                with zipfile.ZipFile(next(output.glob('*.zip'))) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertTrue(any(n.endswith('-NPTH.drl') for n in archive.namelist()))
                    if count == 4:
                        self.assertTrue(any('In1_Cu' in n for n in archive.namelist()))
                        self.assertTrue(any('In2_Cu' in n for n in archive.namelist()))
                if source.name == 'line_in':
                    self.assertTrue(any(row['LCSC Part #'] == 'C7377' for row in bom))
                self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).digest() for p in before})

    def test_native_fields_exclusions_mixed_sides_and_nonzero_origin(self):
        entries = [
            ('R1', 'smd', 'F.Cu', ''),
            ('R2', 'smd', 'B.Cu', ''),
            ('R3', 'smd dnp', 'F.Cu', ''),
            ('R4', 'smd exclude_from_bom', 'F.Cu', ''),
            ('R5', 'smd exclude_from_pos_files', 'F.Cu', ''),
            ('R6', 'through_hole', 'F.Cu', ''),
            ('R7', 'smd', 'F.Cu', ''),
            ('R8', 'smd', 'F.Cu', ''),
            ('R9', 'smd', 'F.Cu', ''),
        ]
        (self.directory / 'assembly.kicad_pcb').write_text(board_text(entries))
        comps = [(ref, {'LCSC PN': 'C123', 'MPN': 'PART-X', 'Manufacturer': 'ACME'}, {})
                 for ref, *_ in entries]
        comps[1][1]['JLCPCB Rotation Offset'] = '90'
        comps[6][2]['dnp'] = 'yes'
        comps[7][2]['in_bom'] = 'no'
        comps[8][2]['on_board'] = 'no'
        (self.directory / 'assembly.kicad_sch').write_text(schematic_text(str(uuid.uuid4()), comps))
        report = self.run_export(None, '--require-part-numbers')
        self.assertEqual(report['component_count'], 2)
        output = self.directory / 'jlcpcb' / 'assembly'
        bom, cpl = self.assert_csv_parity(output)
        self.assertEqual(bom[0]['LCSC Part #'], 'C123')
        self.assertEqual(bom[0]['MPN'], 'PART-X')
        self.assertEqual(bom[0]['Quantity'], '2')
        self.assertEqual([(r['Mid X'], r['Mid Y']) for r in cpl], [('2.000000', '2.000000'), ('5.000000', '2.000000')])
        self.assertEqual(cpl[1]['Layer'], 'bottom')
        self.assertEqual(cpl[1]['Rotation'], '0.000000')
        self.assertEqual(len(report['excluded']), 7)
        report = self.run_export(None, '--overwrite', '--include-through-hole', '--require-part-numbers')
        self.assertEqual(report['component_count'], 3)
        self.assert_csv_parity(output)
        with zipfile.ZipFile(output / 'assembly-gerbers.zip') as archive:
            pth = archive.read('assembly-PTH.drl').decode()
            npth = archive.read('assembly-NPTH.drl').decode()
            self.assertRegex(pth, r'X17\.0*Y2\.0*\n')
            self.assertRegex(npth, r'X2\.0*Y-5\.0*\n')
            copper = archive.read('assembly-F_Cu.gbr').decode()
            self.assertIn('X2000000Y2000000', copper)

    def test_repeated_hierarchical_sheet_part_numbers(self):
        root, leaf, first, second = [str(uuid.uuid4()) for _ in range(4)]
        paths = [(f'/{root}/{first}', 'R1'), (f'/{root}/{second}', 'R2')]
        (self.directory / 'child.kicad_sch').write_text(schematic_text(leaf, [('R1', {'LCSC': 'C4321'}, {})], paths))
        sheets = []
        for i, sheet_id in enumerate((first, second)):
            sheets.append(f'''(sheet (at {20+i*50} 20) (size 30 30)
                (stroke (width 0) (type default)) (fill (color 0 0 0 0))
                (uuid "{sheet_id}")
                {native_field('Sheetname', 'channel' + str(i+1))}
                {native_field('Sheetfile', 'child.kicad_sch')}
                (instances (project "assembly" (path "/{root}" (page "{i+2}")))))''')
        (self.directory / 'assembly.kicad_sch').write_text(f'''(kicad_sch
            (version 20250114) (generator "eeschema") (uuid "{root}") (paper "A4")
            (lib_symbols) {" ".join(sheets)})''')
        (self.directory / 'assembly.kicad_pcb').write_text(board_text([
            ('R1', 'smd', 'F.Cu', ''), ('R2', 'smd', 'B.Cu', '')]))
        report = self.run_export(None, '--require-part-numbers')
        self.assertEqual(report['component_count'], 2)
        bom, _ = self.assert_csv_parity(self.directory / 'jlcpcb' / 'assembly')
        self.assertEqual(bom[0]['Designator'], 'R1, R2')
        self.assertEqual(bom[0]['LCSC Part #'], 'C4321')


if __name__ == '__main__':
    unittest.main()
