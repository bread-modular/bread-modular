#!/usr/bin/python3
"""Bounded native sourcing-delta proof. No catalog client/exporter or finalizer.

Run from repository root with /usr/bin/python3 -B. CLI checks use private copies;
source files, native waivers and severity settings are never rewritten.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
EVIDENCE = BASE / 'verification/basic-economy'
sys.path.insert(0, str(ROOT / 'opt/kicad-jlcpcb'))
import export as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def graph(path):
    return {frozenset((i.get('ref'), i.get('pin')) for i in net)
            for net in ET.parse(path).getroot().find('nets')}


def findings(report, kind):
    data = json.loads(Path(report).read_text())
    entries = data['violations'] if kind == 'drc' else [
        v for s in data['sheets'] for v in s['violations']]
    normalized = Counter(json.dumps({k: v for k, v in item.items()
                                    if k not in ('excluded',)}, sort_keys=True)
                         for item in entries)
    return data, entries, normalized


def run_checks():
    with tempfile.TemporaryDirectory(prefix='32bit-sourcing-proof-') as work:
        src = Path(work) / '32bit-5v'
        shutil.copytree(BASE, src, symlinks=False,
                        ignore=shutil.ignore_patterns('production', 'verification',
                                                     'jlcpcb', 'previews', 'code', 'tools'))
        commands = [
            ['pcb', 'drc', '--format', 'json', '--all-track-errors',
             '--schematic-parity', '--severity-all', '-o',
             EVIDENCE / 'final-drc.json', src / '32bit-5v.kicad_pcb'],
            ['sch', 'erc', '--format', 'json', '--severity-all', '-o',
             EVIDENCE / 'final-erc.json', src / '32bit-5v.kicad_sch'],
            ['sch', 'export', 'netlist', '--format', 'kicadxml', '-o',
             EVIDENCE / 'final-netlist.xml', src / '32bit-5v.kicad_sch'],
        ]
        for args in commands:
            result = subprocess.run(['kicad-cli', *map(str, args)],
                                    capture_output=True, text=True)
            (EVIDENCE / ('final-' + args[0] + '-' + args[1] + '.log')).write_text(
                result.stdout + result.stderr)
            assert result.returncode == 0, result.stdout + result.stderr


def verify(run_cli=True):
    baseline = json.loads((EVIDENCE / 'baseline/manifest.json').read_text())
    delta = json.loads((EVIDENCE / 'metadata-update.json').read_text())
    commit = baseline['source_commit']
    assert commit == '74db23e0aaec4286caaf95eb2c00461ab0999e3e'
    changed = delta['updated_fields']
    parsed = {}
    for filename, kind in [('32bit-5v.kicad_pcb', 'footprint'),
                           ('32bit-5v.kicad_sch', 'symbol')]:
        before_text = subprocess.check_output(
            ['git', 'show', commit + ':modules/32bit-5v/' + filename], text=True)
        assert hashlib.sha256(before_text.encode()).hexdigest() == baseline['source_sha256'][filename]
        before = shared.parse_sexpr(before_text)
        after = shared.parse_sexpr((BASE / filename).read_text())
        parsed[filename] = after
        def without_reviewed_fields(root):
            root = deepcopy(root)
            for node in shared.children(root, kind):
                props = {p[1]: p[2] for p in shared.children(node, 'property')}
                ref = props.get('Reference')
                if ref in changed:
                    node[:] = [c for c in node if not (
                        isinstance(c, list) and c and c[0] == 'property'
                        and c[1] in changed[ref])]
            return root
        assert without_reviewed_fields(before) == without_reviewed_fields(after), (
            filename + ': unreviewed geometry, copper, datum, pin, value, footprint, '
            'flag, outline, mechanical or circuitry change')
    # All rule/settings/library files retain the actual routed baseline, not main/base.
    for name, expected in baseline['source_sha256'].items():
        if name not in ('32bit-5v.kicad_pcb', '32bit-5v.kicad_sch'):
            assert sha(BASE / name) == expected, 'unreviewed source change: ' + name
    if run_cli:
        run_checks()
    pcb = parsed['32bit-5v.kicad_pcb']
    fps, _, copper = shared.read_board(BASE / '32bit-5v.kicad_pcb')
    symbols = shared.read_xml_symbols(EVIDENCE / 'final-netlist.xml')
    assert len(fps) == 61 and copper == ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
    smd = {r for r, f in fps.items() if 'smd' in f['attrs']}
    manual = set(fps) - smd
    assert len(smd) == 55 and manual == {'GND1', 'V_SUPPLY1', 'INPUT1', 'OUTPUT1', 'RV1', 'RV2'}
    assert all(fps[r]['layer'] == 'F.Cu' for r in smd)
    assert {r for r, f in fps.items() if f['layer'] == 'B.Cu'} == {'GND1', 'V_SUPPLY1', 'INPUT1', 'OUTPUT1'}
    for ref, fields in changed.items():
        assert ref in symbols and ref in fps
        assert symbols[ref]['Value'] == fps[ref]['fields']['Value']
        assert symbols[ref]['Footprint'] == fps[ref]['footprint']
        for name, expected in fields.items():
            assert symbols[ref].get(name) == fps[ref]['fields'].get(name) == expected, (ref, name)
    assert graph(EVIDENCE / 'baseline/netlist.xml') == graph(EVIDENCE / 'final-netlist.xml')
    tree = ET.parse(EVIDENCE / 'final-netlist.xml').getroot()
    sch_pins = {(i.get('ref'), i.get('pin')): n.get('name')
                for n in tree.find('nets') for i in n}
    pcb_pins = {}
    for fp in shared.children(pcb, 'footprint'):
        props = {p[1]: p[2] for p in shared.children(fp, 'property')}
        ref = props.get('Reference')
        if ref not in fps:
            continue
        for pad in shared.children(fp, 'pad'):
            if not pad[1] or pad[2] == 'np_thru_hole':
                continue
            net = shared.child(pad, 'net')
            # KiCad 10 stores (net "name"); legacy files have (net id "name").
            assert len(net) in (0, 2, 3), ('unsupported pad net schema', ref, pad[1], net)
            value = net[-1] if net else ''
            key = (ref, pad[1])
            assert key not in pcb_pins or pcb_pins[key] == value, key
            pcb_pins[key] = value
    pin_mismatches = [(r, p, net, sch_pins.get((r, p), ''))
                      for (r, p), net in pcb_pins.items()
                      if net != sch_pins.get((r, p), '')]
    assert not pin_mismatches, pin_mismatches
    # The current routed-baseline symbol already uses combined USB lands; unlike
    # the obsolete original-netlist.xml, its live XML needs no alias exception.
    missing_pins = sorted((r, p) for r, p in sch_pins if r in fps and (r, p) not in pcb_pins)
    assert not missing_pins, missing_pins
    counts = {}
    for kind in ('drc', 'erc'):
        old, _, old_findings = findings(EVIDENCE / ('baseline/' + kind + '.json'), kind)
        current, entries, now_findings = findings(EVIDENCE / ('final-' + kind + '.json'), kind)
        assert old_findings == now_findings, kind + ': new/changed baseline finding'
        assert not any(i['severity'] == 'error' or i.get('excluded') for i in entries)
        counts[kind] = dict(Counter(v['type'] for v in entries))
        if kind == 'drc':
            assert not current['unconnected_items'] and not current['schematic_parity']
    pro = json.loads((BASE / '32bit-5v.kicad_pro').read_text())
    assert not pro['board']['design_settings']['drc_exclusions']
    refill = json.loads((EVIDENCE / 'refill.json').read_text())
    assert refill['refill_executed'] and refill['saved_fill_semantically_identical']
    assert refill['source_pcb_sha256'] == sha(BASE / '32bit-5v.kicad_pcb')
    result = {
        'source_commit': commit, 'status': 'bounded_native_delta_pass', 'order_ready': False,
        'source_sha256': {n: sha(BASE / n) for n in baseline['source_sha256']},
        'physical_refs': 61, 'smd_refs': 55, 'smd_side': 'top', 'manual_refs': sorted(manual),
        'metadata_refs': len(changed), 'pcb_pin_count': len(pcb_pins), 'pin_mismatches': [],
        'combined_usb_aliases_without_separate_lands': missing_pins,
        'graph_unchanged': True, 'geometry_copper_datum_and_unaffected_circuitry_unchanged': True,
        'native_waivers_and_severities_unchanged': True, 'drc_errors': 0, 'erc_errors': 0,
        'opens': 0, 'parity': 0, 'warning_types': counts,
        'refill': refill, 'advisor': 'OFF',
        'limitations': ['Not a bias/ESR/pulse, thermal, physical-fit or assembly/order approval.']
    }
    (EVIDENCE / 'native-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, indent=2))
