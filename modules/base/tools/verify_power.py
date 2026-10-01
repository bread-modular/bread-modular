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

# This release has NO schematic-ahead exemptions. Frozen final geometry and
# independently preserved input mechanical geometry are different evidence sets.
baseline = json.loads((BASE/'verification/fixed-geometry.json').read_text())
mechanical = json.loads((BASE/'verification/mechanical-invariants.json').read_text())
project = json.loads((BASE/'base.kicad_pro').read_text())
check(project['board']['design_settings']['rules'] == baseline['project_design_rules'], 'Global DRC minima changed')
check(project['board']['design_settings']['rule_severities'] == baseline['project_rule_severities'], 'DRC severities changed')
check(project['board']['design_settings']['drc_exclusions'] == [], 'DRC exclusions must remain empty')
check(project['erc'] == baseline['project_erc'], 'ERC setup changed')
check((BASE/'VERSION').read_text().strip() == baseline['release_version'], 'Release VERSION changed')
check(project['schematic'] == baseline['project_schematic'], 'Schematic project setup changed')
for name, key in [('base.kicad_sch','schematic_sha256'), ('slot.kicad_sch','slot_schematic_sha256'),
                  ('base.kicad_pcb','routed_pcb_sha256'), ('base.kicad_pro','project_sha256'),
                  ('base.kicad_dru','custom_rules_sha256')]:
    check(digest(BASE/name) == baseline[key], f'{name}: frozen release input changed')
check(digest(BASE/'verification/mechanical-invariants.json') == baseline['mechanical_invariants_sha256'],
      'Independent mechanical invariants changed')
b = p.LoadBoard(str(board_path))
fps = {f.GetReference(): f for f in b.GetFootprints()}
check(len(fps) == len(list(b.GetFootprints())), 'Duplicate PCB reference')
check(b.GetCopperLayerCount() == baseline['copper_layers'] == 2, 'Layer count changed')
for ref, before in baseline['footprints'].items():
    check(ref in fps, f'Lost frozen footprint {ref}')
    f = fps[ref]
    check([f.m_Uuid.AsString(), pos(f.GetPosition()), f.GetOrientationDegrees(), f.GetLayer()] ==
          [before['uuid'], before['position'], before['angle'], before['layer']], f'Moved frozen {ref}')
    check(pad_data(f) == before['pads'], f'Changed frozen pad geometry of {ref}')
for ref, before in mechanical['footprints'].items():
    check(ref in fps, f'Lost mechanically preserved {ref}')
    f = fps[ref]
    check([f.m_Uuid.AsString(), pos(f.GetPosition()), f.GetOrientationDegrees(), f.GetLayer()] ==
          [before['uuid'], before['position'], before['angle'], before['layer']], f'Moved input hardware {ref}')
    have = pad_data(f)
    if ref in ['U2','U3','U4']:
        have = {d.m_Uuid.AsString(): have[d.m_Uuid.AsString()] for d in f.Pads() if d.GetNumber() in list('12345678')}
    check(have == before['pads'], f'Changed preserved physical pads of {ref}')
edges = {d.m_Uuid.AsString(): [pos(d.GetStart()), pos(d.GetEnd()), int(d.GetShape())]
         for d in b.GetDrawings() if d.GetLayer() == p.Edge_Cuts}
check(edges == baseline['edges'] == mechanical['edges'], 'Board outline changed')
holes = {d.m_Uuid.AsString(): [pos(d.GetPosition()), d.GetWidth(p.F_Cu), d.GetDrillValue()]
         for d in b.GetTracks() if d.GetClass() == 'PCB_VIA' and d.GetDrillValue() > p.FromMM(1)}
check(holes == baseline['mounting_holes'] == mechanical['mounting_holes'], 'Mounting holes changed')
check(pos(b.GetDesignSettings().GetAuxOrigin()) == [p.FromMM(30.48),p.FromMM(177.8)], 'Manufacturing origin changed')
check(len(b.Zones()) == 3 and all(z.IsFilled() for z in b.Zones()), 'Zones not saved filled')
with tempfile.TemporaryDirectory(prefix='base-netlist-') as tmp:
    xmlfile = Path(tmp)/'base.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xmlfile),str(sch_path)],check=True)
    root = ET.parse(xmlfile).getroot()
components = {c.attrib['ref']: c for c in root.find('components')
              if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
check(set(components) == set(fps), f'Physical schematic/PCB ref mismatch: {set(components)^set(fps)}')
expected = {(v.attrib['ref'],v.attrib['pin']): n.attrib['name']
            for n in root.find('nets') for v in n if v.attrib['ref'] in fps}
actual = collections.defaultdict(set)
for ref, f in fps.items():
    c = components[ref]
    check(f.GetValue() == c.findtext('value'), f'{ref}: stale value')
    ident = str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName())
    check(ident == c.findtext('footprint'), f'{ref}: footprint differs from schematic')
    fields = {q.attrib['name']:q.text or '' for q in c.findall('fields/field')}
    for key in set(fields)-{'Reference','Value','Footprint'}:
        have = f.GetFieldText(key) if f.HasField(key) else ''
        check(have == fields.get(key,''), f'{ref}: stale {key}')
    props = {q.attrib['name'] for q in c.findall('property')}
    check(f.IsDNP() == ('dnp' in props), f'{ref}: DNP differs')
    check(f.IsExcludedFromBOM() == ('exclude_from_bom' in props), f'{ref}: BOM flag differs')
    for d in f.Pads():
        pair = ref,d.GetNumber()
        check(d.GetNetname() == expected.get(pair,''), f'{pair}: incorrect pad net')
        if d.GetNetname(): actual[d.GetNetname()].add(pair)
check(set(expected) == {pair for nodes in actual.values() for pair in nodes}, 'Missing/extra schematic pin')
board_nets = set(map(str,b.GetNetsByName().keys()))-{''}
check(board_nets == set(expected.values()), f'Ghost/missing board nets: {board_nets^set(expected.values())}')
for t in b.GetTracks():
    check(not t.GetNetname() or t.GetNetname() in actual, f'Ghost copper: {t.GetNetname()}')
required = {'5V_SYS','VBUS_PROT','VBUS_IN','MONO_SEL','IN_L_PROT','IN_R_PROT'} | {f'{prefix}_{n}' for n in range(1,13) for prefix in ['VSLOT','SEL']}
check(required <= set(actual), 'Missing power/mono/protection nets')
removed = {'J20','J21','J22','J24','U19','R25','R52','R53','R54','R56','C49'} | {f'R{n}' for n in range(28,51,2)}
check(not removed & set(fps), f'Obsolete footprints: {removed & set(fps)}')
check(not any(n in board_nets for n in ['GAIN_SEL','LFB_B','RFB_B']) and not any('-ILIM)' in n for n in board_nets), 'Obsolete gain/ILIM nets')
slots = []
for n in range(1,13):
    u,j,rs,c1,c2,supply = f'U{n+5}',f'J{n+6}',f'R{27+2*n}',f'C{20+2*n}',f'C{21+2*n}',f'VSUPPLY_{n}'
    check(actual[f'VSLOT_{n}'] == {(supply,str(k)) for k in range(1,6)} | {(u,'2'),(u,'7'),(c1,'1'),(c2,'1')}, f'VSLOT_{n}: current path')
    check(actual[f'SEL_{n}'] == {(u,'4'),(j,'2'),(rs,'1')}, f'SEL_{n}: select map')
    check({(u,'1'),(rs,'2'),(c1,'2'),(c2,'2')} <= actual['GND'], f'{u}: returns')
    check((u,'3') in actual['5V_SYS'] and (u,'6') in actual['+3.3V'] and (u,'5') in actual['VBUS_PROT'], f'{u}: supply/MODE')
    nc = f'unconnected-({u}-ST-Pad8)'
    check(actual[nc] == {(u,'8')} and not any(t.GetNetname() == nc for t in b.GetTracks()) and not any(z.GetNetname() == nc for z in b.Zones()), f'{u}: ST copper connected')
    check(fps[u].GetValue() == 'TPS2116DRLR' and len(list(fps[u].Pads())) == 8 and fps[u].GetFieldText('LCSC') == 'C3235557', f'{u}: part')
    check(fps[rs].GetValue() == '100k', f'{u}: pulldown')
    check({d.GetNumber():d.GetNetname() for d in fps[j].Pads()} == {'1':'VBUS_PROT','2':f'SEL_{n}'}, f'{j}: not logic-only')
    for d in fps[j].Pads():
        connections = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and (t.GetStart() == d.GetPosition() or t.GetEnd() == d.GetPosition())]
        check(len(connections) == 1 and connections[0].GetWidth() == p.FromMM(.25), f'{j}.{d.GetNumber()}: not a logic-only leaf')
    sp = sorted(fps[supply].Pads(),key=lambda d:d.GetPosition().x)
    gx,gy = mm(sorted(fps[f'GND{n}'].Pads(),key=lambda d:d.GetPosition().x)[0].GetPosition())
    sx,sy = mm(sp[0].GetPosition())
    shadow = [gx-8.89,gy-55.88,gx+21.59,gy+12.7]
    box = fps[j].GetBoundingBox(False,False)
    bounds = [p.ToMM(box.GetLeft()),p.ToMM(box.GetTop()),p.ToMM(box.GetRight()),p.ToMM(box.GetBottom())]
    check(shadow[0] < bounds[0] < bounds[2] < shadow[2] and shadow[1] < bounds[1] < bounds[3] < shadow[3], f'{j}: outside module shadow')
    check(bounds[3] < sy < gy and abs(mm(fps[j].GetPosition())[1]-sy+3.8)<.00001, f'{j}: rail-side geometry')
    slots.append({'slot':n,'jumper':j,'jumper_anchor_mm':mm(fps[j].GetPosition()),'jumper_envelope_mm':bounds,'module_shadow_mm':shadow,'rail_y_mm':sy,'gnd_y_mm':gy,'existing_socket_misalignment_mm':[round(sx-gx,4),round(sy-(gy-45.72),4)]})
for ref,pin,net in [('F1','2','VBUS_IN'),('F1','1','VBUS_PROT'),('F2','1','VBUS_PROT'),('F2','2','5V_SYS'),('D2','1','VBUS_PROT'),('D3','1','5V_SYS'),('D2','2','GND'),('D3','2','GND'),('FB1','1','VBUS_PROT'),('FB1','2','LDO_VIN'),('U5','1','LDO_VIN')]:
    check((ref,pin) in actual[net], f'Protection topology: {ref}.{pin}')
check(actual['Net-(INPUT1-Pin_3)'] == {('INPUT1',str(k)) for k in [3,4,5]} | {('R57','1')} and ('R57','2') in actual['GND'], 'R57 input return')
check(fps['R57'].GetValue() == '100' and fps['R57'].GetFieldText('LCSC') == 'C25076', 'R57 part')
for ref,side in [('R58','L'),('R59','R')]:
    check(fps[ref].GetValue() == '10k' and fps[ref].GetFieldText('LCSC') == 'C25744' and expected[ref,'1'] == f'IN_{side}' and expected[ref,'2'] == f'IN_{side}_PROT', f'{ref}: injection limiting')
check(actual['MONO_SEL'] == {('U18','1'),('U18','5'),('R55','1'),('J23','2')}, 'Mono control')
check(fps['J23'].IsDNP() and fps['R55'].GetValue() == '100k' and ('R55','2') in actual['GND'], 'Fail-safe stereo pulldown / DNP')
check(expected['U18','2'] == 'BUFF_IN_L' and expected['U18','9'] == 'IN_R_PROT' and expected['U18','10'] == 'RIN_SEL', 'Mono audio map')
check(expected['J23','1'] == '+3.3V' and expected['C48','1'] == '+3.3V' and expected['C48','2'] == 'GND', 'Mono supply')
for ref in ['U2','U3','U4']:
    check({d.GetNumber() for d in fps[ref].Pads()} == set('12345678') and len(list(fps[ref].Pads())) == 8, f'{ref}: fictitious EP/paste pad')
for ref in ['C50','C51','C52']:
    check(expected[ref,'1']=='GND' and expected[ref,'2']=='+3.3V' and fps[ref].GetFieldText('LCSC')=='C1525', f'{ref}: dedicated supply bypass')
for ref in ['C14','C15','C20']:
    check(expected[ref,'1']=='GND' and expected[ref,'2']=='+2.5V', f'{ref}: preserved bias bypass')
from assembly_datum import expected_position
check(all(abs(a-z)<1e-9 for a,z in zip(expected_position(fps['J5'],b.GetDesignSettings().GetAuxOrigin()),(4.035,130.81))), 'Independent J5 body datum')
check(fps['U3'].GetValue() == 'TS922IDT' and fps['U3'].GetFieldText('LCSC') == 'C93687', 'Headphone driver')
stale = stale_stack_inputs(stack,BASE)
check(not stale, f'Stale stack evidence: {stale}')
check(stack.get('clearance_ok') is True, 'Insufficient calculated stack clearance')
report = {'assertions_passed':checks,'stack_report_inputs_fresh':True,'pcb_sha256':digest(board_path),'routed_pcb_sha256_pinned':baseline['routed_pcb_sha256'],'schematic_sha256':digest(sch_path),'slot_schematic_sha256':digest(BASE/'slot.kicad_sch'),'footprints':len(fps),'pad_net_assignments':len(expected),'copper_layers':2,'unchanged_mounting_holes':len(holes),'preserved_input_footprints':len(mechanical['footprints']),'slots':slots,'stack_height_verified':bool(stack['clearance_ok']),'stack_clearance_nominal_mm':stack['clearance_nominal_mm'],'stack_clearance_worst_case_mm':stack['clearance_worst_case_mm'],'release_status':'software-checked candidate; NOT order authorization','pcb_pending_schematic_ahead':None,'physical_validation_pending':stack['assumptions']+stack['exceptions']}
if args.report: args.report.write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: {checks} assertions; {len(fps)} footprints; {len(expected)} pad nets; full parity with NO PCB_PENDING; geometry preserved.')
print('STACK: 5.0 mm nominal / 3.8 mm calculated worst case; not a measured mating trial.')
