#!/usr/bin/python3
"""Independent read/check of this HOLD production snapshot. No export/catalog I/O."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
EVIDENCE = BASE / 'verification/basic-economy'
sys.path.insert(0, str(ROOT / 'opt/kicad-jlcpcb'))
import export as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    manifest = json.loads((BASE / 'production/manifest.json').read_text())
    assert manifest['release_status'] == 'HOLD' and manifest['order_ready'] is False
    for name, digest in manifest['source_sha256'].items():
        assert sha(BASE / name) == digest, ('source hash', name)
    for name, digest in manifest['outputs_sha256'].items():
        assert sha(BASE / name) == digest, ('output hash', name)
    for name, digest in manifest['tool_sha256'].items():
        assert sha(ROOT / name) == digest, ('common-tool hash', name)
    reviewed_path = BASE / manifest['reviewed_source']
    assert sha(reviewed_path) == manifest['reviewed_source_sha256']
    native = json.loads((EVIDENCE / 'native-proof.json').read_text())
    assert native['drc_errors'] == native['erc_errors'] == native['opens'] == native['parity'] == 0
    assert native['graph_unchanged'] and native['geometry_copper_datum_and_unaffected_circuitry_unchanged']
    board, _, copper = shared.read_board(BASE / '32bit-5v.kicad_pcb')
    smd = {r for r, f in board.items() if 'smd' in f['attrs']}
    assert len(board) == 61 and len(smd) == 55
    assert copper == ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
    manual = set(board) - smd
    assert manual == {'GND1', 'V_SUPPLY1', 'INPUT1', 'OUTPUT1', 'RV1', 'RV2'}
    for sub, expected in [('assembly', smd), ('full', set(board))]:
        bom = shared.read_csv(BASE / 'production' / sub / 'bom.csv', shared.BOM_HEADER)
        pos = shared.read_csv(BASE / 'production' / sub / 'positions.csv', shared.CPL_HEADER)
        references = []
        for row in bom:
            refs = [r.strip() for r in row['Designator'].split(',')]
            assert int(row['Quantity']) == len(refs)
            references.extend(refs)
            for ref in refs:
                fp = board[ref]
                assert row['Comment'] == fp['fields']['Value']
                assert row['Footprint'] == fp['footprint'].split(':')[-1]
                assert row['LCSC Part #'] == fp['fields'].get('LCSC', '')
                assert row['MPN'] == fp['fields'].get('MPN', '')
                assert row['Manufacturer'] == fp['fields'].get('Manufacturer', '')
        assert len(references) == len(set(references)) and set(references) == expected
        assert {p['Designator'] for p in pos} == expected and len(pos) == len(expected)
        if sub == 'assembly':
            assert all(p['Layer'] == 'top' for p in pos)
            original = subprocess.check_output(['git', 'show', '74db23e:modules/32bit-5v/production/assembly/positions.csv'])
            current_cpl = (BASE / 'production/assembly/positions.csv').read_bytes()
            # The integrated shared exporter normalizes CSV CRLF to LF; require
            # every other byte (all refs, coordinates, angles, sides) unchanged.
            assert original.replace(b'\r\n', b'\n') == current_cpl
    assert sha(BASE / 'production/32bit-5v.zip') == sha(BASE / 'production/assembly/32bit-5v-gerbers.zip')
    assert sha(BASE / 'production/32bit-5v.zip') == sha(BASE / 'jlcpcb/production_files/GERBER-32bit-5v.zip')
    assert sha(BASE / 'production/32bit-5v.zip') == sha(BASE / 'jlcpcb/32bit-5v/32bit-5v-gerbers.zip')
    for name in ('bom.csv', 'positions.csv', 'export-report.json'):
        assert sha(BASE / 'production/assembly' / name) == sha(BASE / 'jlcpcb/32bit-5v' / name)
    with zipfile.ZipFile(BASE / 'production/32bit-5v.zip') as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) == 13
        for name in names:
            assert archive.read(name) == (BASE / 'production/gerbers' / name).read_bytes()
            assert archive.read(name) == (BASE / 'jlcpcb/gerber' / name).read_bytes()
        for name in ('F_Cu', 'In1_Cu', 'In2_Cu', 'B_Cu'):
            assert '32bit-5v-' + name + '.gbr' in names
    comp = json.loads((EVIDENCE / 'gerber-baseline-comparison.json').read_text())
    assert comp['member_set_equal'] and not comp['different_members_ignoring_creation_date']
    assert comp['assembly_zip_sha256'] == sha(BASE / 'production/32bit-5v.zip')
    audit = json.loads((EVIDENCE / 'final-audit.json').read_text())
    assert not audit['catalog_and_requirements_pass'] and not audit['order_ready']
    assert len(audit['components']) == 55 and set(audit['manual']) == manual
    assert 'U1' not in audit['excluded'] and 'U1' not in audit['manual']
    for name, digest in audit['input_sha256'].items():
        assert sha(BASE / name) == digest, ('actual audit input', name)
    summary = json.loads((EVIDENCE / 'catalog/final-live-summary.json').read_text())
    assert summary['catalog_only_basic_economy_rc_pass']
    assert summary['rc_refs'] == 45 and summary['rc_codes'] == 16
    assert summary['catalog_requests'] == 23 and summary['request_budget'] == 24
    assert summary['quantity_basis'] == {'boards': 1, 'requested_order_quantity': None, 'attrition_included': False}
    assert summary['max_complete_economy_boards'] == 0 and not summary['order_ready']
    rc = [r for r in summary['parts'] if r['classification'] == 'Basic']
    assert sum(r['per_board'] for r in rc) == 45
    assert all(r['componentProductType'] in (0, 1) and r['stock_suffices_one_board'] for r in rc)
    assert summary['max_passive_sets_stock_only_no_attrition'] == min(r['stock'] // r['per_board'] for r in rc)
    assert summary['max_known_component_sets_stock_only_no_attrition'] == min(r['stock'] // r['per_board'] for r in summary['parts'])
    mcu = next(r for r in summary['parts'] if 'U1' in r['refs'])
    assert mcu['code'] == 'C3013946' and mcu['mpn'] == board['U1']['fields']['Value']
    assert mcu['componentProductType'] == 2 and mcu['economy_eligible'] is False
    raw_hashes = set()
    for path in (EVIDENCE / 'catalog/final-raw').glob('*.json'):
        record = json.loads(path.read_text())
        assert hashlib.sha256(record['raw_response'].encode()).hexdigest() == record['sha256']
        raw_hashes.add(record['sha256'])
    assert len(raw_hashes) == 23
    for row in summary['parts']:
        assert row['evidence']['mode'] == 'live' and row['evidence']['sha256'] in raw_hashes
    output_name = 'verification/basic-economy/production-proof.json'
    result = {'status': 'matched_HOLD_snapshot_verified', 'order_ready': False,
              'physical_refs': 61, 'assembly_refs': 55, 'manual_refs': sorted(manual),
              'copper_layers': copper, 'zip_members': 13, 'catalog_codes': 23,
              'R_C_Basic_Economy_refs': 45, 'quantity_basis_boards': 1,
              'geometry_and_CPL_unchanged_from_routed_baseline': True,
              'manifest_source_count': len(manifest['source_sha256']),
              'manifest_output_count_excluding_this_proof': len(set(manifest['outputs_sha256']) - {output_name}),
              'strict_audit_pass': False, 'MCU_Standard_only_HOLD': True, 'D1_code_unknown_HOLD': True}
    (BASE / output_name).write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
