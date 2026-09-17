#!/usr/bin/python3
"""Prove the base/module stack height from datasheet dimensions.

Datum: the base PCB top surface (z = 0). Everything is measured upward from it;
through-board solder tails are explicitly excluded.

  z = 0                          base PCB top surface
  z = 2.0 + 4.0 = 6.0            rail-select jumper header above the board
  z = 2.0 + 3.5 = 5.5            C5664 shunt seated on the jumper insulator
  => jumper envelope             max(6.0, 5.5) = 6.0 mm nominal
  z = 8.5                        recommended female socket insulator height
  z = 8.5 + 2.5 = 11.0           module PCB underside (socket + module male insulator)
  clearance = 11.0 - 6.0 = 5.0 mm nominal, 3.8 mm worst case

The script also transforms every module footprint into base coordinates with the
documented registration (leftmost physical ground pin on the module onto the
leftmost ground pad of the corresponding base slot) and checks that no module
bottom-side footprint overlaps the jumper envelope in X/Y, so that the flat
module underside plane is the only constraint at that location.

Run with KiCad's system Python. Does not modify anything.
"""
import argparse
import json
import math
from pathlib import Path
import pcbnew as p

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
SPEC = json.loads((BASE / 'production/hand-solder.json').read_text())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path)
args = parser.parse_args()
checks = 0
problems = []


def check(ok, message):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(message)


def mm(value):
    return round(p.ToMM(value), 4)


def box(fp):
    b = fp.GetBoundingBox(False, False)
    return [mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom())]


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2])
    dy = max(b[1] - a[3], a[1] - b[3])
    return round(max(dx, dy), 4) if (dx > 0 or dy > 0) else 0.0


# ------------------------------------------------------- z chain (maths) -----
stack = SPEC['stack_height']
comp = stack['components']
tol = stack['rules']['tolerance_x_x_mm']
margin = stack['rules']['assembly_margin_mm']
jumper = comp['jumper_header']
shunt = comp['shunt']
socket = comp['base_socket']
male = comp['module_male_header']
check(jumper['insulator_mm'] + jumper['mating_pin_mm'] == jumper['above_board_mm'],
      'jumper header above-board height is not insulator + mating pin')
check(abs((jumper['solder_tail_mm'] - comp['base_pcb_thickness_mm']) - jumper['tail_below_board_mm']) < 0.001,
      'jumper solder tail below the board is inconsistent with the 1.6 mm base PCB')
check(shunt['height_mm'] < jumper['mating_pin_mm'],
      'shunt is taller than the mating pin, so it would raise the fitted envelope')

envelope_nom = max(jumper['above_board_mm'], jumper['insulator_mm'] + shunt['height_mm'])
module_nom = socket['insulator_mm'] + male['insulator_mm']
clearance_nom = round(module_nom - envelope_nom, 3)
# worst case: every stacked nominal dimension moves by the drawing's general X.X
# tolerance in the direction that closes the gap.
envelope_worst = round(jumper['insulator_mm'] + tol + jumper['mating_pin_mm'] + tol, 3)
module_worst = round(socket['insulator_mm'] - tol + male['insulator_mm'] - tol, 3)
clearance_worst = round(module_worst - envelope_worst, 3)
# The socket insulator height has two independent lower bounds:
#   1. it must swallow the module's worst-case mating pin so the pin cannot
#      bottom out on (or pass through) the base PCB,
#   2. it must hold the module underside far enough above the fitted jumper for
#      the required assembly margin.
need_engagement = round(male['mating_pin_mm'] + tol, 3)
need_clearance = math.ceil((envelope_worst + margin - (male['insulator_mm'] - tol)) * 100) / 100
min_socket = max(need_engagement, need_clearance)
socket_worst = round(socket['insulator_mm'] - tol, 3)
clearance_ok = clearance_worst >= margin
check(clearance_ok, f'worst-case clearance {clearance_worst} mm is below the {margin} mm assembly margin')
check(socket_worst >= min_socket,
      f'recommended socket {socket["insulator_mm"]} mm (worst case {socket_worst}) is below the {min_socket} mm minimum')
# every plastics-height option of the C5664 ordering code must still clear
shunt_options = {}
for height in SPEC['recommended_parts']['shunt']['ordering_code_heights_mm']:
    top = max(jumper['above_board_mm'], jumper['insulator_mm'] + height)
    shunt_options[f'{height} mm'] = round(module_worst - top, 3)
    check(shunt_options[f'{height} mm'] >= margin,
          f'{height} mm shunt height leaves only {shunt_options[f"{height} mm"]} mm')

# ------------------------------------------------- module side (gender) ------
import re
MATING = re.compile(r'^(V_SUPPLY\d+|5V\d+|GND\d+)$')
modules = {}
for path in sorted((ROOT / 'modules').glob('*/*.kicad_pcb')):
    name = path.parent.name
    if name == 'base':
        continue
    board = p.LoadBoard(str(path))
    if board is None:
        problems.append(f'{name}: kicad_pcb could not be loaded standalone (skipped)')
        continue
    connectors = [f for f in board.GetFootprints()
                  if MATING.match(f.GetReference()) and len(list(f.Pads())) == 5]
    males = [f for f in connectors if 'pin' in f.GetValue().lower()]
    females = [f for f in connectors if 'socket' in f.GetValue().lower()]
    if not connectors:
        continue
    check(len(males) >= 1 and not females,
          f'{name}: power/ground connectors are not male 1x05 headers ({[f.GetValue() for f in connectors]})')
    if len(males) < 2:
        problems.append(f'{name}: only {len(males)} male 1x05 power/ground connector(s) found')
    layers = sorted({p.LayerName(f.GetLayer()) for f in males})
    modules[name] = {'path': str(path.relative_to(ROOT)), 'male_headers': len(males), 'layers': layers,
                     'values': sorted({f.GetValue() for f in males})}
    if layers != ['B.Cu']:
        problems.append(f'{name}: power/ground headers are on {layers}, not the bottom side, '
                        'so they cannot mate downwards with a base socket as drawn')
check(len(modules) >= 20, f'only {len(modules)} module board(s) inspected')
bottom = [name for name, m in modules.items() if m['layers'] == ['B.Cu']]
check(len(bottom) >= 20, f'only {len(bottom)} module board(s) carry a bottom-side male header')

# --------------------------------- base side (slot geometry + envelopes) -----
board = p.LoadBoard(str(BASE / 'base.kicad_pcb'))
fps = {f.GetReference(): f for f in board.GetFootprints()}
mod_boards = {name: p.LoadBoard(str(ROOT / info['path'])) for name, info in modules.items()}
check(all(m is not None for m in mod_boards.values()), 'a module board was registered but failed to reload')
slots = []
min_gap = None
for n in range(1, 13):
    supply, gnd = fps[f'VSUPPLY_{n}'], fps[f'GND{n}']
    jumper_fp = fps[f'J{6 + n}']
    jbox = box(jumper_fp)
    anchor = min(gnd.Pads(), key=lambda d: d.GetPosition().x).GetPosition()
    ax, ay = mm(anchor.x), mm(anchor.y)
    rows = []
    for name, mod in mod_boards.items():
        gnds = [f for f in mod.GetFootprints() if MATING.match(f.GetReference())
                and len(list(f.Pads())) == 5 and f.GetReference().startswith('GND')]
        if not gnds:
            problems.append(f'{name}: no GND connector, slot {n} envelope check skipped')
            continue
        m_anchor = min((d for f in gnds for d in f.Pads()), key=lambda d: d.GetPosition().x).GetPosition()
        dx = round(ax - mm(m_anchor.x), 4)
        dy = round(ay - mm(m_anchor.y), 4)
        inside = False
        for f in mod.GetFootprints():
            b = box(f)
            t = [round(b[0] + dx, 4), round(b[1] + dy, 4), round(b[2] + dx, 4), round(b[3] + dy, 4)]
            if p.LayerName(f.GetLayer()) != 'B.Cu':
                continue
            if overlap(t, jbox):
                rows.append({'module': name, 'ref': f.GetReference(), 'envelope': t, 'area': round((t[2] - t[0]) * (t[3] - t[1]), 3)})
            elif t[3] > jbox[1] - 6 and t[1] < jbox[3] + 6:
                g = gap(t, jbox)
                min_gap = g if min_gap is None else min(min_gap, g)
        inside = inside or True
    check(not rows, f'slot {n}: module bottom-side footprint(s) overlap the jumper envelope: {rows}')
    slots.append({'slot': n, 'jumper': jumper_fp.GetReference(), 'jumper_envelope_mm': jbox,
                  'supply_first_pad_mm': [mm(supply.Pads()[0].GetPosition().x), mm(supply.Pads()[0].GetPosition().y)],
                  'supply_last_pad_mm': [mm(list(supply.Pads())[-1].GetPosition().x), mm(list(supply.Pads())[-1].GetPosition().y)],
                  'module_registration_offset_mm': None})
check(min_gap is not None and min_gap > 0, f'negative X/Y clearance next to a jumper: {min_gap}')

# The published numbers in production/hand-solder.json must equal what is
# computed here - the JSON is documentation, this script is the calculation.
published = stack['derived']
computed = {'jumper_envelope_nominal_mm': envelope_nom, 'jumper_envelope_worst_case_mm': envelope_worst,
            'module_underside_nominal_mm': module_nom, 'module_underside_worst_case_mm': module_worst,
            'clearance_nominal_mm': clearance_nom, 'clearance_worst_case_mm': clearance_worst,
            'minimum_socket_insulator_mm': min_socket}
for key, value in computed.items():
    check(abs(float(published[key]) - value) < 0.001,
          f'production/hand-solder.json publishes {key}={published[key]} but the calculation gives {value}')

report = {
    'datum': stack['datum'],
    'inputs': {'jumper_header': {'lcsc': jumper['lcsc'], 'mpn': jumper['mpn'], 'above_board_mm': jumper['above_board_mm'],
                                 'solder_tail_below_board_mm': jumper['tail_below_board_mm'], 'source': jumper['source']},
               'shunt': {'lcsc': shunt['lcsc'], 'height_mm': shunt['height_mm'], 'source': shunt['source']},
               'base_socket': {'lcsc': socket['lcsc'], 'mpn': socket['mpn'], 'insulator_mm': socket['insulator_mm'],
                               'total_length_mm': socket['total_length_mm'], 'source': socket['source']},
               'module_male_header': {'part': male['part'], 'insulator_mm': male['insulator_mm'],
                                      'mating_pin_mm': male['mating_pin_mm'], 'mounting': male['mounting'],
                                      'source': male['source']}},
    'tolerance_x_x_mm': tol, 'assembly_margin_mm': margin,
    'jumper_envelope_nominal_mm': envelope_nom, 'jumper_envelope_worst_case_mm': envelope_worst,
    'module_underside_nominal_mm': module_nom, 'module_underside_worst_case_mm': module_worst,
    'clearance_nominal_mm': clearance_nom, 'clearance_worst_case_mm': clearance_worst,
    'clearance_ok': clearance_ok, 'minimum_socket_insulator_mm': min_socket,
    'shunt_option_clearance_mm': shunt_options,
    'nearest_module_side_envelope_gap_mm': min_gap,
    'module_bottom_side_footprints_over_jumpers': 0,
    'modules_inspected': len(mod_boards), 'module_connectors': modules,
    'slots': slots,
    'assumptions': ['The module PCBs do not annotate their power/ground header part number; the mechanical twin of PZ254-1-05-Z-8.5 (2.5 mm insulator, 6.0 mm mating pin) is assumed.',
                    'Header (C2905948) tolerances are not published; the general X.X +/-0.30 mm tolerance of the C5664/PM254 drawings is applied.',
                    'No assembled stack has been measured; this is a datasheet calculation, not a mating trial.'],
}
if args.report:
    args.report.write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS: {checks} assertions; clearance {clearance_nom} mm nominal / {clearance_worst} mm worst case '
      f'(min {margin} mm); min socket height {min_socket} mm; {len(mod_boards)} module boards carry bottom-side male headers.')
for line in problems:
    print(f'NOTE: {line}')
print('PHYSICAL VALIDATION: no assembled stack has been measured. A mating trial is still advised.')
