#!/usr/bin/python3
"""Assert board/schematic parity, protected geometry and logic-only jumpers.

Run from any directory with KiCad's system Python. Does not modify the PCB.
KiCad DRC (including zones/shorts) remains a separate, mandatory check.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pcbnew as p

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path)
parser.add_argument('--selftest', action='store_true',
                    help='exercise the stack-report freshness guard and exit')
args = parser.parse_args()
checks = 0

def check(ok, message):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(message)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

STACK_FINGERPRINT_KEYS = {'calculator', 'hand-solder.json', 'fixed-geometry.json',
                          'base.kicad_pcb', 'base.kicad_sch', 'slot.kicad_sch',
                          'module_scope', 'module_pcbs'}

def stack_inputs(base, root):
    """Recompute every fingerprint independently of what the report claims."""
    scope = sorted(path.parent.name for path in (root/'modules').glob('*/*.kicad_pcb')
                   if path.parent.name != 'base')
    readable = {}
    for name in scope:
        candidate = root/'modules'/name/f'{name}.kicad_pcb'
        if candidate.is_file() and p.LoadBoard(str(candidate)) is not None:
            readable[name] = digest(candidate)
    return {'calculator': digest(base/'tools/verify_stack_height.py'),
            'hand-solder.json': digest(base/'production/hand-solder.json'),
            'fixed-geometry.json': digest(base/'verification/fixed-geometry.json'),
            'base.kicad_pcb': digest(base/'base.kicad_pcb'),
            'base.kicad_sch': digest(base/'base.kicad_sch'),
            'slot.kicad_sch': digest(base/'slot.kicad_sch'),
            'module_scope': {'enumerated': scope},
            'module_pcbs': readable}


def stale_stack_inputs(stack_report, base, root=None):
    """Return the fingerprint keys that no longer match the files on disk."""
    root = root or ROOT
    want = stack_report.get('input_sha256')
    if not want:
        return ['<no input_sha256 fingerprints in the stack report>']
    missing = sorted(STACK_FINGERPRINT_KEYS - set(want))
    if missing:
        return [f'<report is missing fingerprints: {missing}>']
    have = stack_inputs(base, root)
    stale = [key for key in sorted(STACK_FINGERPRINT_KEYS)
             if key != 'module_scope' and have[key] != want[key]]
    # module coverage: every enumerated module must be accounted for, either
    # inspected or explicitly reported unreadable.
    scope = want['module_scope']
    accounted = set(scope.get('inspected', [])) | set(scope.get('unreadable', []))
    if set(scope.get('enumerated', [])) != accounted:
        stale.append('module_scope')
    if sorted(scope.get('enumerated', [])) != sorted(have['module_scope']['enumerated']):
        stale.append('module_scope')
    if sorted(want['module_pcbs']) != sorted(scope.get('inspected', [])):
        stale.append('module_pcbs')
    if set(have['module_scope']['enumerated']) - set(have['module_pcbs']):
        # an enumerated module that cannot be read is fine only if the report says so
        unreadable = set(scope.get('unreadable', []))
        if set(have['module_scope']['enumerated']) - set(have['module_pcbs']) - unreadable:
            stale.append('module_scope')
    return stale

stack_report_path = BASE / 'verification/stack-height.json'
stack = json.loads(stack_report_path.read_text()) if stack_report_path.is_file() else None
if stack is None:
    raise SystemExit('verification/stack-height.json is missing: run tools/verify_stack_height.py first.')

if args.selftest:
    def mutated(**changes):
        return dict(stack, input_sha256=dict(stack['input_sha256'], **changes))
    fingerprints = stack['input_sha256']
    scope = fingerprints['module_scope']
    first_module = sorted(fingerprints['module_pcbs'])[0]
    cases = {
        'current report': (stack, False),
        'changed board': (mutated(**{'base.kicad_pcb': '0'*64}), True),
        'changed specification': (mutated(**{'hand-solder.json': '0'*64}), True),
        'changed calculator': (mutated(**{'calculator': '0'*64}), True),
        'changed module PCB': (mutated(module_pcbs=dict(fingerprints['module_pcbs'], **{first_module: '0'*64})), True),
        'dropped fingerprint key': (dict(stack, input_sha256={k: v for k, v in fingerprints.items() if k != 'calculator'}), True),
        'no fingerprints at all': (dict(stack, input_sha256={}), True),
        'added module without coverage': (mutated(module_scope=dict(scope, enumerated=scope['enumerated'] + ['a-new-module'])), True),
        'removed module': (mutated(module_scope=dict(scope, enumerated=scope['enumerated'][1:], inspected=scope['inspected'][1:],
                                                     unreadable=[n for n in scope['unreadable'] if n != scope['enumerated'][0]])), True),
    }
    for label, (report, should_be_stale) in cases.items():
        stale_keys = stale_stack_inputs(report, BASE)
        check(bool(stale_keys) == should_be_stale,
              f'freshness guard {"misses" if should_be_stale else "rejects"} the case: {label}')
    print(f'SELFTEST PASS: {checks} assertions; the stack-report freshness guard accepts the current report and '
          f'rejects a changed board, a changed specification, a changed calculator, a changed module PCB, a dropped key, '
          f'no fingerprints, an uncovered module and a removed module.')
    raise SystemExit(0)

def pos(q):
    return [q.x, q.y]

def mm(q):
    return [p.ToMM(q.x), p.ToMM(q.y)]

def pad_data(f):
    return {d.m_Uuid.AsString(): {
        'position': pos(d.GetPosition()), 'size': pos(d.GetSize()),
        'drill': pos(d.GetDrillSize()), 'shape': int(d.GetShape()),
        'orientation': d.GetOrientationDegrees(), 'layers': list(d.GetLayerSet().Seq())
    } for d in f.Pads()}

board_path = BASE / 'base.kicad_pcb'
sch_path = BASE / 'base.kicad_sch'
baseline = json.loads((BASE / 'verification/fixed-geometry.json').read_text())
project = json.loads((BASE/'base.kicad_pro').read_text())
check(project['board']['design_settings']['rules'] == baseline['project_design_rules'], 'Global DRC minima changed')
check(project['board']['design_settings']['rule_severities'] == baseline['project_rule_severities'], 'DRC severities changed')
check(project['board']['design_settings']['drc_exclusions'] == [], 'DRC exclusions must remain empty')
check(project['erc'] == baseline['project_erc'], 'ERC setup changed')
check(project['schematic'] == baseline['project_schematic'], 'Schematic project setup changed')
check(hashlib.sha256(sch_path.read_bytes()).hexdigest() == baseline['schematic_sha256'],
      'Merged schematic changed (including text): explicitly forbidden by this task')
check(hashlib.sha256((BASE/'slot.kicad_sch').read_bytes()).hexdigest() == baseline['slot_schematic_sha256'],
      'Slot template schematic changed')
# The routed board is the release deliverable: it must stay byte-identical.
check(hashlib.sha256(board_path.read_bytes()).hexdigest() == baseline['routed_pcb_sha256'],
      'Routed base.kicad_pcb changed: copper must not move')
check(baseline['pcb_sha256'] != baseline['routed_pcb_sha256'],
      'The pinned pre-upgrade and routed board hashes must stay distinct')
b = p.LoadBoard(str(board_path))
fps = {f.GetReference(): f for f in b.GetFootprints()}
check(b.GetCopperLayerCount() == baseline['copper_layers'] == 2, 'Layer count changed')
for ref, before in baseline['footprints'].items():
    check(ref in fps, f'Lost fixed footprint {ref}')
    f = fps[ref]
    check([f.m_Uuid.AsString(), pos(f.GetPosition()), f.GetOrientationDegrees(), f.GetLayer()] ==
          [before['uuid'], before['position'], before['angle'], before['layer']], f'Moved {ref}')
    check(pad_data(f) == before['pads'], f'Changed physical pad geometry of {ref}')
edges = {d.m_Uuid.AsString(): [pos(d.GetStart()), pos(d.GetEnd()), int(d.GetShape())]
         for d in b.GetDrawings() if d.GetLayer() == p.Edge_Cuts}
check(edges == baseline['edges'], 'Board outline changed')
holes = {d.m_Uuid.AsString(): [pos(d.GetPosition()), d.GetWidth(p.F_Cu), d.GetDrillValue()]
         for d in b.GetTracks() if d.GetClass() == 'PCB_VIA' and d.GetDrillValue() > p.FromMM(1)}
check(holes == baseline['mounting_holes'], 'Mounting holes changed')

with tempfile.TemporaryDirectory(prefix='base-netlist-') as tmp:
    xmlfile = Path(tmp) / 'base.xml'
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                    '-o', str(xmlfile), str(sch_path)], check=True)
    root = ET.parse(xmlfile).getroot()
components = {c.attrib['ref']: c for c in root.find('components')
              if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
check(set(components) == set(fps), 'Missing or extra PCB footprints')
expected = {(v.attrib['ref'], v.attrib['pin']): n.attrib['name']
            for n in root.find('nets') for v in n if v.attrib['ref'] in fps}
actual = collections.defaultdict(set)
for ref, f in fps.items():
    c = components[ref]
    check(f.GetValue() == c.findtext('value'), f'{ref}: stale value')
    ident = str(f.GetFPID().GetLibNickname()) + ':' + str(f.GetFPID().GetLibItemName())
    check(ident == c.findtext('footprint'), f'{ref}: footprint differs from schematic')
    for key in ['LCSC', 'MPN', 'Manufacturer']:
        val = c.findtext(f"fields/field[@name='{key}']")
        if val:
            check(f.GetFieldText(key) == val, f'{ref}: stale {key}')
    for d in f.Pads():
        pair = (ref, d.GetNumber())
        check(d.GetNetname() == expected.get(pair, ''), f'{pair}: incorrect pad net')
        if d.GetNetname():
            actual[d.GetNetname()].add(pair)
check(set(expected) <= {pair for nodes in actual.values() for pair in nodes}, 'Missing schematic pin')
check(set(map(str, b.GetNetsByName().keys())) - {''} == set(expected.values()), 'Ghost/stale board net')
required = {'5V_SYS', 'VBUS_PROT', 'VBUS_IN'} | {f'{prefix}_{n}' for n in range(1, 13) for prefix in ['VSLOT', 'SEL']}
check(required <= set(actual), 'Missing power-upgrade nets')

slots = []
for n in range(1, 13):
    u, j, ri, rs = f'U{n+5}', f'J{n+6}', f'R{26+2*n}', f'R{27+2*n}'
    c1, c2, supply = f'C{20+2*n}', f'C{21+2*n}', f'VSUPPLY_{n}'
    check(actual[f'VSLOT_{n}'] == {(supply, str(k)) for k in range(1, 6)} |
          {(u, '7'), (c1, '1'), (c2, '1')}, f'VSLOT_{n}: wrong current path')
    check(actual[f'SEL_{n}'] == {(u, '2'), (j, '2'), (rs, '1')}, f'SEL_{n}: incorrect select')
    check(actual[f'Net-({u}-ILIM)'] == {(u, '4'), (ri, '1')}, f'{u}: incorrect ILIM')
    check(fps[ri].GetValue() == '750' and fps[rs].GetValue() == '100k', f'{u}: resistor values')
    check({(u, '1'), (u, '3'), (u, '5'), (ri, '2'), (rs, '2'), (c1, '2'), (c2, '2')} <= actual['GND'], f'{u}: returns/manual mode')
    check((u, '8') in actual['5V_SYS'] and (u, '6') in actual['+3.3V'], f'{u}: input reversal')
    jpads = list(fps[j].Pads())
    check({d.GetNumber(): d.GetNetname() for d in jpads} == {'1': '+3.3V', '2': f'SEL_{n}'}, f'{j}: not logic only')
    # Each jumper pin is a single trace endpoint (a leaf), not a series bus.
    for d in jpads:
        connections = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and
                       (t.GetStart() == d.GetPosition() or t.GetEnd() == d.GetPosition())]
        check(len(connections) == 1 and connections[0].GetWidth() == p.FromMM(.25), f'{j}.{d.GetNumber()}: not a logic-only leaf')
    sp = sorted(fps[supply].Pads(), key=lambda d: d.GetPosition().x)
    gx, gy = mm(sorted(fps[f'GND{n}'].Pads(), key=lambda d: d.GetPosition().x)[0].GetPosition())
    sx, sy = mm(sp[0].GetPosition())
    # All four inspected module boards share this exact outline relative to
    # their bottom-mounted ground header's leftmost pin.
    shadow = [gx-8.89, gy-55.88, gx+21.59, gy+12.7]
    box = fps[j].GetBoundingBox(False, False)
    bounds = [p.ToMM(box.GetLeft()), p.ToMM(box.GetTop()), p.ToMM(box.GetRight()), p.ToMM(box.GetBottom())]
    check(shadow[0] < bounds[0] < bounds[2] < shadow[2] and
          shadow[1] < bounds[1] < bounds[3] < shadow[3], f'{j}: not hidden by module outline')
    check(bounds[3] < sy < gy, f'{j}: in prohibited GND-to-power gap')
    check(abs(mm(fps[j].GetPosition())[1] - sy + 3.8) < .00001, f'{j}: no longer hugs rail')
    slots.append({'slot': n, 'jumper': j, 'jumper_anchor_mm': mm(fps[j].GetPosition()),
                  'jumper_envelope_mm': bounds, 'module_shadow_mm': shadow,
                  'rail_y_mm': sy, 'gnd_y_mm': gy,
                  'existing_socket_misalignment_mm': [round(sx-gx, 4), round(sy-(gy-45.72), 4)]})
for ref, pin, net in [('F1','2','VBUS_IN'),('F1','1','VBUS_PROT'),('F2','1','VBUS_PROT'),
                       ('F2','2','5V_SYS'),('D2','1','VBUS_PROT'),('D3','1','5V_SYS'),
                       ('D2','2','GND'),('D3','2','GND'),('FB1','1','VBUS_PROT'),
                       ('FB1','2','LDO_VIN'),('U5','1','LDO_VIN')]:
    check((ref, pin) in actual[net], f'Protection topology: {ref}.{pin}')
for name in ['16bit', '8bit', 'mcc', 'wave']:
    mod = p.LoadBoard(str(ROOT / 'modules' / name / f'{name}.kicad_pcb'))
    pts = [mm(v) for d in mod.GetDrawings() if d.GetLayer() == p.Edge_Cuts for v in [d.GetStart(), d.GetEnd()]]
    check([min(a[0] for a in pts), min(a[1] for a in pts), max(a[0] for a in pts), max(a[1] for a in pts)] ==
          [46.99, 40.64, 77.47, 109.22], f'{name}: changed module outline')
    check(any(mm(d.GetPosition()) == [55.88,96.52] and d.GetNetname() == 'GND'
              for f in mod.GetFootprints() for d in f.Pads()), f'{name}: changed registration')
stale = stale_stack_inputs(stack, BASE)
check(not stale, f'verification/stack-height.json is stale for {stale}: re-run tools/verify_stack_height.py')
check(stack.get('clearance_ok') is True,
      'verification/stack-height.json reports insufficient clearance')
report = {'assertions_passed': checks,
          'stack_report_inputs_fresh': True, 'pcb_sha256': hashlib.sha256(board_path.read_bytes()).hexdigest(),
          'routed_pcb_sha256_pinned': baseline['routed_pcb_sha256'],
          'schematic_sha256': baseline['schematic_sha256'], 'footprints': len(fps), 'new_footprints': len(fps)-len(baseline['footprints']),
          'unchanged_original_footprints': len(baseline['footprints']), 'unchanged_mounting_holes': len(holes),
          'copper_layers': 2, 'slots': slots,
          # derived from the current stack report, never asserted here
          'stack_height_verified': bool(stack['clearance_ok']),
          'stack_clearance_nominal_mm': stack['clearance_nominal_mm'],
          'stack_clearance_worst_case_mm': stack['clearance_worst_case_mm'],
          'release_status': 'fab-ready (see production/RELEASE_STATUS.md; the datasheet stack calculation is in verification/stack-height.json)',
          'hand_solder_override': 'The sockets keep their legacy C2894928 schematic/PCB field because this board is pinned byte-identical; the generated production/bom.csv carries NOT-JLC for them (production/hand-solder.json).',
          'physical_validation_pending': ['No assembled stack has been measured: a mating trial of one base plus one module is still advised.',
                                          'Module-side male header part number is not annotated on the module PCBs.',
                                          'Module 4mix and imix place their power headers on F.Cu and cannot mate downwards as drawn.']}
if args.report:
    args.report.write_text(json.dumps(report, indent=2)+'\n')
print(f'PASS: {checks} assertions; {len(fps)} footprints; 12 logic-only leaf jumpers; fixed geometry preserved.')
print(f'STACK HEIGHT: clearance {stack["clearance_nominal_mm"]} mm nominal / {stack["clearance_worst_case_mm"]} mm worst case; no assembled stack measured yet.')
