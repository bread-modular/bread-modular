#!/usr/bin/python3
"""Guarded 32bit-5v production REVIEW preparation, using the shared tools.

Default refuses the reviewed HOLD snapshot before any publication. Explicit
--review-preparation generates matched fabrication/inventory data, never clears
catalog/application/order holds. No historical /tmp handoff or finalizer runs.
"""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
import pcbnew as p

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
PROD = BASE / 'production'
VERIFY = BASE / 'verification'
EVIDENCE = VERIFY / 'basic-economy'
PCB = BASE / '32bit-5v.kicad_pcb'
sys.path.insert(0, str(ROOT / 'opt/kicad-jlcpcb'))
import export as shared
import add_production_files as mirrors
from catalog import Catalog, CatalogError, utc_now
from bom_audit import audit_components, board_components, supply_failures
from passive_planner import suggest
from verify_sourcing import verify, sha


def rows(path):
    return shared.read_csv(Path(path), ())


def refs(data):
    result = [r.strip() for row in data for r in row['Designator'].split(',')]
    assert len(result) == len(set(result)), 'duplicate CSV references'
    assert all(int(row['Quantity']) == len(row['Designator'].split(',')) for row in data)
    return set(result)


def outcsv(path, data):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


def prepare(review_preparation):
    reviewed_path = EVIDENCE / 'reviewed-source.json'
    reviewed = json.loads(reviewed_path.read_text())
    assert reviewed['release_status'] == 'HOLD' and reviewed['advisor'] == 'OFF'
    assert reviewed['source_base_commit'] == '74db23e0aaec4286caaf95eb2c00461ab0999e3e'
    for name, digest in reviewed['source_sha256'].items():
        assert sha(BASE / name) == digest, 'reviewed source/evidence changed: ' + name
    if not review_preparation:
        raise RuntimeError('Reviewed release is HOLD; use --review-preparation only for '
                           'explicit non-order-ready review artifacts. No files published.')
    proof = verify()
    b = p.LoadBoard(str(PCB))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    assert len(fps) == len(b.GetFootprints()) == reviewed['physical_refs'] == 61
    assert b.GetCopperLayerCount() == 4
    assert fps['U4'].GetValue() == 'ES8388'
    assert str(fps['U4'].GetFPID().GetLibItemName()) == 'ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias'
    assert fps['U1'].GetValue() == 'ESP32-S3-WROOM-1U-N16R8'
    assert str(fps['U1'].GetFPID().GetLibItemName()) == 'ESP32-S3-WROOM-1U'
    assert not any(f.IsDNP() or f.IsExcludedFromBOM() or f.IsExcludedFromPosFiles() for f in fps.values())
    smd = {r for r, f in fps.items() if f.GetAttributes() & p.FP_SMD}
    manual = set(fps) - smd
    assert smd == set(reviewed['smd_refs']) and len(smd) == 55
    assert manual == set(reviewed['manual_refs']) and len(manual) == 6
    assert all(fps[r].GetLayer() == p.F_Cu for r in smd)
    assert {r for r, f in fps.items() if f.GetLayer() == p.B_Cu} == {'GND1', 'V_SUPPLY1', 'INPUT1', 'OUTPUT1'}
    with tempfile.TemporaryDirectory(prefix='32bit-production-review-') as temp:
        stage = Path(temp)
        assembly_args = [str(BASE), '--side', 'top', '-o', str(stage / 'assembly')]
        # Demonstrate strict export remains blocked rather than quietly ignoring gaps.
        try:
            shared.export_project(shared.argument_parser().parse_args(
                assembly_args + ['--require-part-numbers']))
        except shared.ExportError as error:
            assert 'D1' in str(error) and reviewed['assembly_supplier_gaps'] == ['D1'], str(error)
            (EVIDENCE / 'strict-export-hold.json').write_text(json.dumps({
                'status': 'HOLD', 'strict_export_pass': False, 'error': str(error),
                'missing_refs': ['D1'], 'no_strict_outputs_published': True
            }, indent=2) + '\n')
        else:
            raise AssertionError('Unexpected strict-export pass; reviewed source needs rebinding')
        reports = {}
        for sub, args, selected in [
            ('assembly', ['--side', 'top'], smd),
            ('full', ['--include-through-hole'], set(fps))
        ]:
            report = shared.export_project(shared.argument_parser().parse_args(
                [str(BASE), '-o', str(stage / sub), *args]))
            reports[sub] = report
            bom = rows(stage / sub / 'bom.csv')
            positions = rows(stage / sub / 'positions.csv')
            assert refs(bom) == {r['Designator'] for r in positions} == selected
            assert len(positions) == len({r['Designator'] for r in positions})
            assert report['copper_layer_count'] == 4
            assert report['source_sha256'][str(PCB)] == sha(PCB)
            expected_gaps = ['D1'] if sub == 'assembly' else sorted(manual | {'D1'}, key=shared.natural_key)
            assert set(report['missing_part_numbers']) == set(expected_gaps)
            origin = b.GetDesignSettings().GetAuxOrigin()
            for q in positions:
                fp = fps[q['Designator']]
                point = fp.GetPosition()
                assert abs(float(q['Mid X']) - p.ToMM(point.x - origin.x)) < .000002
                assert abs(float(q['Mid Y']) + p.ToMM(point.y - origin.y)) < .000002
                assert q['Layer'] == ('bottom' if fp.GetLayer() == p.B_Cu else 'top')
                assert abs((float(q['Rotation']) - fp.GetOrientationDegrees() + 180) % 360 - 180) < .000002
            u4 = next(q for q in bom if 'U4' in q['Designator'].split(','))
            assert u4['Comment'] == u4['MPN'] == 'ES8388'
            assert u4['Manufacturer'] == 'Everest Semiconductor'
        assembly_zip = stage / 'assembly/32bit-5v-gerbers.zip'
        with zipfile.ZipFile(assembly_zip) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)) and all(Path(n).name == n for n in names)
            for layer in ['F_Cu', 'In1_Cu', 'In2_Cu', 'B_Cu', 'F_Mask', 'B_Mask',
                          'F_Paste', 'B_Paste', 'F_Silkscreen', 'B_Silkscreen', 'Edge_Cuts']:
                assert any(layer in n and n.endswith('.gbr') for n in names), layer
            assert any('PTH' in n and 'NPTH' not in n and n.endswith('.drl') for n in names)
            assert any('NPTH' in n and n.endswith('.drl') for n in names)
        supplier = Catalog(cache_dir=EVIDENCE / 'catalog/final-raw', timeout=15, max_requests=24)
        native_components = board_components(PCB, EVIDENCE / 'final-netlist.xml')
        expected_mpns = {}
        for comp in native_components:
            if comp['ref'] not in smd or not comp['code']:
                continue
            assert comp['code'] not in expected_mpns or expected_mpns[comp['code']] == comp['mpn']
            expected_mpns[comp['code']] = comp['mpn']
        # Prefetch each distinct code once. If a query is ambiguous, stop here:
        # the auditor must not repeat failed uncached lookups for every reference.
        for code, mpn in sorted(expected_mpns.items()):
            if code == 'C11702':
                # Observed code-prefix query includes >20 unrelated longer codes.
                # One documented public exact-MPN search, common parser unchanged;
                # match BOTH exact C-code and native MPN before memoizing its result.
                found = supplier.search(mpn, limit=12)
                matches = [part for part in found['parts'] if part['code'] == code and part['mpn'] == mpn]
                assert not found['truncated'] and len(matches) == 1, 'C11702 exact-MPN search ambiguous'
                supplier.memo[code] = matches[0]
            else:
                supplier.lookup(code)
        assert supplier.requests == len(expected_mpns) == 23
        (EVIDENCE / 'catalog/final-live-parts.json').write_text(json.dumps(supplier.memo, indent=2) + '\n')
        audit = audit_components(
            native_components, supplier,
            json.loads((EVIDENCE / 'audit-requirements.json').read_text()),
            boards=1, side='top', cpl=stage / 'assembly/positions.csv',
            export_report=reports['assembly'], strict_live=True)
        audit['source_branch'] = '32bit-5v'
        audit['source_baseline_commit'] = reviewed['source_base_commit']
        audit['quantity_basis'] = {'boards': 1, 'requested_order_quantity': None, 'attrition_included': False}
        audit['input_sha256'] = {
            '32bit-5v.kicad_pcb': sha(PCB), '32bit-5v.kicad_sch': sha(BASE / '32bit-5v.kicad_sch'),
            'production/assembly/bom.csv': sha(stage / 'assembly/bom.csv'),
            'production/assembly/positions.csv': sha(stage / 'assembly/positions.csv'),
            'production/assembly/export-report.json': sha(stage / 'assembly/export-report.json'),
            'verification/basic-economy/audit-requirements.json': sha(EVIDENCE / 'audit-requirements.json')}
        assert not audit['catalog_and_requirements_pass'] and not audit['order_ready']
        (EVIDENCE / 'final-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
        grouped = collections.defaultdict(list)
        for comp in audit['components']:
            if comp.get('catalog'):
                grouped[comp['catalog']['code']].append(comp)
        summary = []
        for code, components in sorted(grouped.items()):
            part = components[0]['catalog']
            passive = part['kind'] in ('R', 'C')
            supply = supply_failures(part, len(components), strict_live=True, basic=passive)
            if passive:
                assert not supply, (code, supply)
                assert all(any(c['check'] == 'exact MPN' and c['status'] == 'pass' for c in x['checks']) for x in components)
                assert all(any(c['check'] == 'package/footprint' and c['status'] == 'pass' for c in x['checks']) for x in components)
            summary.append({'code': code, 'mpn': part['mpn'], 'package': part['package'],
                'refs': [c['ref'] for c in components], 'per_board': len(components),
                'classification': part['classification'], 'componentProductType': part['component_product_type'],
                'economy_eligible': part['economy_eligible'], 'stock': part['stock'],
                'stock_suffices_one_board': part['stock'] >= len(components),
                'max_boards_stock_only_no_attrition': part['stock'] // len(components),
                'supply_failures': supply, 'evidence': part['evidence']})
        rc = [s for s in summary if supplier.memo[s['code']]['kind'] in ('R', 'C')]
        assert sum(s['per_board'] for s in rc) == 45 and len(rc) == 16
        catalog = {'source_branch': '32bit-5v', 'source_baseline_commit': reviewed['source_base_commit'],
            'generated_at_utc': utc_now(), 'catalog_requests': supplier.requests, 'request_budget': 24,
            'quantity_basis': audit['quantity_basis'], 'catalog_only_basic_economy_rc_pass': True,
            'rc_refs': 45, 'rc_codes': 16, 'max_passive_sets_stock_only_no_attrition': min(s['max_boards_stock_only_no_attrition'] for s in rc),
            'max_known_component_sets_stock_only_no_attrition': min(s['max_boards_stock_only_no_attrition'] for s in summary),
            'max_complete_economy_boards': 0, 'complete_stock_capacity': 'unknown: D1 exact MPN/code unresolved',
            'complete_economy_blockers': ['U1 C3013946 componentProductType=2 Standard-only; choice pending', 'D1 exact color/MPN/code unresolved'],
            'parts': summary, 'full_audit_pass': False, 'order_ready': False,
            'remaining_order_gates': audit['remaining_order_gates']}
        (EVIDENCE / 'catalog/final-live-summary.json').write_text(json.dumps(catalog, indent=2) + '\n')
        (EVIDENCE / 'catalog/final-live-parts.json').write_text(json.dumps(supplier.memo, indent=2) + '\n')
        final_plans = []
        for group in json.loads((EVIDENCE / 'passive-plan.json').read_text()):
            result = suggest([supplier.memo[group['new_code']]], group['target'], boards=1,
                             replacements_per_board=len(group['refs']), max_parts=1,
                             max_candidates=1, max_results=1, strict_live=True)
            assert result['candidates'], (group['refs'], result)
            final_plans.append({'refs': group['refs'], 'code': group['new_code'], 'planner': result})
        (EVIDENCE / 'final-passive-planner.json').write_text(json.dumps(final_plans, indent=2) + '\n')
        assert 'U1' not in audit['manual'] and 'U1' not in audit['excluded']
        # Only after all native, selection, archive and live-catalog guards succeed.
        for sub in ('assembly', 'full'):
            shutil.copytree(stage / sub, PROD / sub, dirs_exist_ok=True)
        for name in ('bom.csv', 'positions.csv'):
            shutil.copyfile(PROD / 'full' / name, PROD / name)
        shutil.copyfile(PROD / 'assembly/32bit-5v-gerbers.zip', PROD / '32bit-5v.zip')
        allpos = {q['Designator']: q for q in rows(PROD / 'positions.csv')}
        manual_rows = []
        for ref in sorted(manual):
            fp, q = fps[ref], allpos[ref]
            manual_rows.append({'Designator': ref, 'Quantity': 1, 'Value': fp.GetValue(),
                'Footprint': str(fp.GetFPID().GetLibNickname()) + ':' + str(fp.GetFPID().GetLibItemName()),
                'Layer': q['Layer'], 'Mid X': q['Mid X'], 'Mid Y': q['Mid Y'], 'Rotation': q['Rotation'],
                'Assembly': audit['manual'][ref]})
        outcsv(PROD / 'manual-assembly.csv', manual_rows)
        (PROD / 'designators.csv').write_text(''.join(f'{ref}:1\n' for ref in sorted(fps)), encoding='utf-8-sig')
        ipc_src = stage / 'ipc-source'
        ipc_src.mkdir()
        for name in ('32bit-5v.kicad_pcb', '32bit-5v.kicad_pro'):
            shutil.copyfile(BASE / name, ipc_src / name)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'ipcd356', '-o', str(PROD / 'netlist.ipc'),
                        str(ipc_src / PCB.name)], check=True)
        mirror = mirrors.mirror_gerbers(PROD / '32bit-5v.zip', BASE / 'jlcpcb', PCB.stem)
        # Same archive and CSV/report snapshot, not a second independently dated export.
        shutil.copytree(PROD / 'assembly', BASE / 'jlcpcb/32bit-5v', dirs_exist_ok=True)
        with zipfile.ZipFile(PROD / '32bit-5v.zip') as archive:
            (PROD / 'gerbers').mkdir(exist_ok=True)
            for name in names:
                (PROD / 'gerbers' / name).write_bytes(archive.read(name))
        for name in ('final-drc.json', 'final-erc.json', 'final-netlist.xml'):
            shutil.copyfile(EVIDENCE / name, VERIFY / name)
    manifest = {
        'release_status': 'HOLD', 'order_ready': False, 'source_base_commit': reviewed['source_base_commit'],
        'source_branch': '32bit-5v', 'workspace_branch': subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
        'generated_at_utc': utc_now(), 'tool_version': p.GetBuildVersion(),
        'common_tools_commits': reviewed['common_tools_commits'], 'advisor': 'OFF',
        'reviewed_source': str(reviewed_path.relative_to(BASE)), 'reviewed_source_sha256': sha(reviewed_path),
        'generation_command': '/usr/bin/python3 -B modules/32bit-5v/tools/regenerate_production.py --review-preparation',
        'export_pipeline': 'shared export.py API (top assembly + full inventory); shared add_production_files.mirror_gerbers API',
        'pcba_status': 'HOLD: 45 R/C catalog Basic+Economy; full conservative audit fails; U1 Standard-only; D1 missing exact MPN/code',
        'physical_refs': 61, 'smd_refs': 55, 'smd_side': 'top', 'manual_refs': sorted(manual),
        'physical_sides': {'top': 57, 'bottom': 4}, 'copper_layers': ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'],
        'quantity_basis': audit['quantity_basis'], 'catalog_summary': 'verification/basic-economy/catalog/final-live-summary.json',
        'conservative_audit': 'verification/basic-economy/final-audit.json', 'native_proof': proof,
        'unresolved_gates': reviewed['unresolved_gates'], 'archive_files': names,
        'source_sha256': {**reviewed['source_sha256'], 'tools/regenerate_production.py': sha(Path(__file__)),
                          'tools/verify_sourcing.py': sha(BASE / 'tools/verify_sourcing.py')},
        'outputs_sha256': {}, 'tool_sha256': {},
        'historical_evidence_note': 'Old POWER/verification routing statements and Astra handoffs are historical; no new advisor approval. Current routed baseline and bounded native proof control.',
        'gerber_review': 'All 4 copper present and native geometry preserved; rendered-art/assembler preview and manufacturing signoff remain separate HOLD gates.'
    }
    for directory in (PROD, BASE / 'jlcpcb', EVIDENCE):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and path != PROD / 'manifest.json':
                manifest['outputs_sha256'][str(path.relative_to(BASE))] = sha(path)
    for name in ('final-drc.json', 'final-erc.json', 'final-netlist.xml'):
        manifest['outputs_sha256']['verification/' + name] = sha(VERIFY / name)
    for name in ('export.py', 'add_production_files.py', 'assembly.py', 'catalog.py', 'bom_audit.py', 'passive_planner.py', 'ASSEMBLY.md'):
        manifest['tool_sha256']['opt/kicad-jlcpcb/' + name] = sha(ROOT / 'opt/kicad-jlcpcb' / name)
    (PROD / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Published HOLD review snapshot: 4Cu, 55 top SMD, 61 physical refs, 6 unchanged manual refs; '
          f'45 R/C Basic+Economy; {supplier.requests} bounded live exact lookups; no order readiness.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-preparation', action='store_true')
    args = parser.parse_args()
    try:
        prepare(args.review_preparation)
    except (AssertionError, RuntimeError, CatalogError, shared.ExportError) as error:
        print('HOLD/guard failure: ' + str(error), file=sys.stderr)
        sys.exit(1)
