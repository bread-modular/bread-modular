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
args = parser.parse_args()
checks = 0

def check(ok, message):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(message)

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
report = {'assertions_passed': checks, 'pcb_sha256': hashlib.sha256(board_path.read_bytes()).hexdigest(),
          'schematic_sha256': baseline['schematic_sha256'], 'footprints': len(fps), 'new_footprints': len(fps)-len(baseline['footprints']),
          'unchanged_original_footprints': len(baseline['footprints']), 'unchanged_mounting_holes': len(holes),
          'copper_layers': 2, 'slots': slots, 'stack_height_verified': False,
          'mechanical_hold': 'Actual female socket/assembled gap and C5664 shunt height not established; C2894928 is a male header, not the socket claimed in Phase 1.'}
if args.report:
    args.report.write_text(json.dumps(report, indent=2)+'\n')
print(f'PASS: {checks} assertions; {len(fps)} footprints; 12 logic-only leaf jumpers; fixed geometry preserved.')
print('MECHANICAL HOLD: stack height is NOT verified. See verification/README.md.')
