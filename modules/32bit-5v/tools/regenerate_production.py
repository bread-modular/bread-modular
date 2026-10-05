#!/usr/bin/python3
"""Guarded, user-approved Standard JLCPCB package generation using shared tools.

--generate-package runs fresh bounded native checks and exports the actual source.
Recorded Basic/service identity is checked offline; there are NO supplier queries.
Existing engineering is user-accepted, not newly qualified or order-accepted.
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
from catalog import CatalogError, utc_now
from bom_audit import board_components, package_match
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


def service_eligible(part, service):
    """Selected-service check only; never relabel the recorded Economy evidence."""
    if service == 'STANDARD':
        return part['component_product_type'] in (0, 2)
    if service == 'ECONOMY':
        return part['component_product_type'] in (0, 1) and part['economy_eligible'] is True
    raise ValueError('unknown assembly service')


def recorded_bindings(components, parts, smd, service):
    """Exact native identities + strict Basic/Economy R/C; no stock/order claim."""
    rc = []
    for comp in components:
        if comp['ref'] not in smd or not comp['code']:
            continue
        part = parts[comp['code']]
        assert comp['code'] == part['code'] and comp['mpn'] == part['mpn'], comp['ref']
        assert service_eligible(part, service), comp['ref'] + ': selected service incompatible'
        if comp['ref'][0] in ('R', 'C'):
            assert part['classification'] == 'Basic', comp['ref'] + ': actual Basic required'
            assert part['economy_eligible'] is True, comp['ref'] + ': recorded passive Economy required'
            assert package_match(comp['footprint'], part['package']) is True, comp['ref']
            rc.append(comp)
    assert len(rc) == 45 and len({c['code'] for c in rc}) == 16
    assert {c['ref'] for c in components if c['ref'] in smd and not c['code']} == {'D1'}
    return rc


def normalized_fabrication(data):
    # ONLY dated header lines ignored; all artwork, copper and drill data retained.
    return '\n'.join(line for line in data.decode().splitlines() if not (
        'TF.CreationDate' in line or 'FILE_CREATION_DATE' in line or
        line.startswith('G04 Created by KiCad') or line.startswith('; DRILL file KiCad'))).encode()


def prepare(review_preparation):
    reviewed_path = EVIDENCE / 'reviewed-source.json'
    reviewed = json.loads(reviewed_path.read_text())
    assert reviewed['release_status'] == 'PACKAGE_GENERATION_APPROVED' and reviewed['advisor'] == 'OFF'
    assert reviewed['selected_assembly_service'] == 'STANDARD'
    assert reviewed['package_generation_approval']['existing_engineering_user_accepted'] is True
    assert reviewed['source_base_commit'] == '74db23e0aaec4286caaf95eb2c00461ab0999e3e'
    for name, digest in reviewed['source_sha256'].items():
        assert sha(BASE / name) == digest, 'reviewed source/evidence changed: ' + name
    for name, digest in reviewed['common_tool_sha256'].items():
        assert sha(ROOT / name) == digest, 'reviewed common tool changed: ' + name
    if not review_preparation:
        raise RuntimeError('Explicit package generation required; use --generate-package. '
                           'No files published; authenticated order acceptance remains unverified.')
    proof = verify()
    b = p.LoadBoard(str(PCB))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    assert len(fps) == len(b.GetFootprints()) == reviewed['physical_refs'] == 61
    assert b.GetCopperLayerCount() == 4
    assert fps['U4'].GetValue() == 'ES8388'
    assert str(fps['U4'].GetFPID().GetLibItemName()) == 'ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias'
    assert fps['U1'].GetValue() == 'ESP32-S3-WROOM-1U-N16R8'
    assert str(fps['U1'].GetFPID().GetLibItemName()) == 'ESP32-S3-WROOM-1U'
    assert [r for r, f in fps.items() if 'AP2112' in f.GetValue()] == ['U5']
    assert shared.read_board(PCB)[0]['U5']['fields']['MPN'] == 'AP2112K-3.3TRG1'
    assert {str(pad.GetNumber()): pad.GetNetname() for pad in fps['U5'].Pads() if str(pad.GetNumber()) != '4'} == {
        '1': '+5V', '2': 'GND', '3': '+5V', '5': '+3V3'}
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
                'status': 'supplier_identity_incomplete', 'package_generation_blocked': False,
                'strict_export_pass': False, 'error': str(error),
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
        # No supplier queries: exact current native bindings are compared to the
        # unchanged dated catalog. The old conservative Economy audit is historical,
        # not an application approval or a blocker to user-authorized generation.
        parts = json.loads((EVIDENCE / 'catalog/final-live-parts.json').read_text())
        native_components = board_components(PCB, EVIDENCE / 'final-netlist.xml')
        recorded_bindings(native_components, parts, smd, 'STANDARD')
        historical = json.loads((EVIDENCE / 'final-audit.json').read_text())
        audit = {
            'status': 'FILES_GENERATED_NOT_ORDER_ACCEPTED', 'order_ready': False,
            'selected_assembly_service': 'STANDARD',
            'mcu_service_status': 'ACCEPTED FOR SELECTED SERVICE',
            'existing_engineering_user_accepted': True,
            'engineering_qualification_evidence': 'unchanged/unverified; user acceptance is not testing',
            'package_generation_approval': reviewed['package_generation_approval'],
            'manual': historical['manual'], 'excluded': historical['excluded'],
            'quantity_basis': {'requested_order_quantity': None, 'attrition_included': False,
                               'generation_is_quantity_independent': True},
            'missing_assembly_supplier_codes': ['D1'],
            'D1_caveat': 'Original assembled D1 row/code retained exactly; match manually during JLC upload; no identity invented.',
            'recorded_Basic_Economy_RC_refs': 45, 'recorded_Basic_Economy_RC_codes': 16,
            'supplier_requests': 0, 'live_stock_or_authenticated_order_acceptance': 'not checked',
            'historical_economy_audit': 'verification/basic-economy/final-audit.json',
            'remaining_order_gates': reviewed['remaining_order_gates'],
            'input_sha256': {
                '32bit-5v.kicad_pcb': sha(PCB), '32bit-5v.kicad_sch': sha(BASE / '32bit-5v.kicad_sch'),
                'production/assembly/bom.csv': sha(stage / 'assembly/bom.csv'),
                'production/assembly/positions.csv': sha(stage / 'assembly/positions.csv'),
                'production/assembly/export-report.json': sha(stage / 'assembly/export-report.json'),
                'verification/standard-service-policy.json': sha(VERIFY / 'standard-service-policy.json'),
                'verification/basic-economy/audit-requirements.json': sha(EVIDENCE / 'audit-requirements.json'),
                'verification/basic-economy/catalog/final-live-parts.json': sha(EVIDENCE / 'catalog/final-live-parts.json')}
        }
        # Native inputs are unchanged: preserve EVERY existing BOM/CPL byte and D1
        # row while freshly regenerating fabrication from the actual current source.
        for sub in ('assembly', 'full'):
            for name in ('bom.csv', 'positions.csv'):
                assert (stage / sub / name).read_bytes() == (PROD / sub / name).read_bytes(), (sub, name)
        comparison = json.loads((EVIDENCE / 'gerber-baseline-comparison.json').read_text())
        with zipfile.ZipFile(assembly_zip) as archive:
            assert set(archive.namelist()) == set(comparison['normalized_member_sha256'])
            for name in archive.namelist():
                digest = hashlib.sha256(normalized_fabrication(archive.read(name))).hexdigest()
                assert digest == comparison['normalized_member_sha256'][name]['baseline'], ('new fabrication geometry', name)
                comparison['normalized_member_sha256'][name]['new'] = digest
        comparison['assembly_zip_sha256'] = sha(assembly_zip)
        (EVIDENCE / 'gerber-baseline-comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
        (EVIDENCE / 'package-review.json').write_text(json.dumps(audit, indent=2) + '\n')
        assert 'U1' not in audit['manual'] and 'U1' not in audit['excluded']
        # Only after all native, selected-service/Basic, byte-preservation and archive guards succeed.
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
        'release_status': 'FILES_GENERATED_NOT_ORDER_ACCEPTED', 'order_ready': False, 'source_base_commit': reviewed['source_base_commit'],
        'selected_assembly_service': 'STANDARD', 'mcu_service_status': 'ACCEPTED FOR SELECTED SERVICE',
        'package_generation_approval': reviewed['package_generation_approval'],
        'package_review': 'verification/basic-economy/package-review.json',
        'source_branch': '32bit-5v', 'workspace_branch': subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
        'generated_at_utc': utc_now(), 'tool_version': p.GetBuildVersion(),
        'common_tools_commits': reviewed['common_tools_commits'], 'advisor': 'OFF',
        'reviewed_source': str(reviewed_path.relative_to(BASE)), 'reviewed_source_sha256': sha(reviewed_path),
        'generation_command': '/usr/bin/python3 -B modules/32bit-5v/tools/regenerate_production.py --generate-package',
        'export_pipeline': 'shared export.py API (top assembly + full inventory); shared add_production_files.mirror_gerbers API',
        'pcba_status': 'User-approved STANDARD upload package generated; assembled MCU accepted for selected service; 45 actual Basic R/C retained; D1 needs upload matching; no order acceptance',
        'physical_refs': 61, 'smd_refs': 55, 'smd_side': 'top', 'manual_refs': sorted(manual),
        'physical_sides': {'top': 57, 'bottom': 4}, 'copper_layers': ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'],
        'quantity_basis': audit['quantity_basis'], 'catalog_summary': 'verification/basic-economy/catalog/final-live-summary.json',
        'conservative_audit': 'verification/basic-economy/final-audit.json',
        'conservative_audit_scope': 'historical Economy alternative-service/application-evidence audit, not selected Standard generation blocker',
        'catalog_summary_scope': 'dated historical observation; Economy capacity zero applies ONLY to hypothetical Economy, not selected Standard',
        'native_proof': proof,
        'unresolved_gates': [], 'remaining_order_gates': reviewed['remaining_order_gates'],
        'accepted_existing_engineering_reviews': reviewed['accepted_existing_engineering_reviews'],
        'archive_files': names,
        'source_sha256': {**reviewed['source_sha256'], 'tools/regenerate_production.py': sha(Path(__file__)),
                          'tools/verify_sourcing.py': sha(BASE / 'tools/verify_sourcing.py')},
        'outputs_sha256': {}, 'tool_sha256': dict(reviewed['common_tool_sha256']),
        'historical_evidence_note': 'Old POWER/verification routing statements and Astra handoffs are historical; no new advisor approval. Current routed baseline and bounded native proof control.',
        'gerber_review': 'Fresh 4Cu/drills generated; all 13 artwork/drill members match routed baseline ignoring ONLY dated header lines. Prior rendered previews are historical. Authenticated placement/manufacturing/order acceptance unverified.'
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
    # Supported full-generation closeout: validate hashes before writing the new proof,
    # then bind that generated proof and verify the now-stable manifest again.
    from verify_production import verify as verify_outputs
    verify_outputs()
    manifest['outputs_sha256']['verification/basic-economy/production-proof.json'] = sha(EVIDENCE / 'production-proof.json')
    (PROD / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verify_outputs()
    print('Generated STANDARD package: 4Cu, 55 top SMD, 61 physical refs, 6 unchanged manual refs; '
          '45 actual Basic R/C; 0 supplier queries; D1 upload matching required; no order acceptance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-preparation', action='store_true', help='legacy alias for explicit offline package generation')
    parser.add_argument('--generate-package', action='store_true', help='user-approved Standard package; no supplier queries')
    args = parser.parse_args()
    try:
        prepare(args.review_preparation or args.generate_package)
    except (AssertionError, RuntimeError, CatalogError, shared.ExportError) as error:
        print('HOLD/guard failure: ' + str(error), file=sys.stderr)
        sys.exit(1)
