#!/usr/bin/python3
"""Freeze final release evidence ONLY after real saved-board DRC/parity and input geometry proof.

Not part of routine export. Needs the original ab9fd44 board, never a freshly
modified substitute. Current schematic/root/slot/project/rules must be unchanged
from the reviewed circuit authority, unless --bounded-improvements proves the
three authorized supply capacitors and J5 metadata against the imported candidate. Refuses PCB errors, parity or opens. The
mechanical invariant file preserves the input geometry independently of final
package/layout geometry. No severities/exclusions or circuit sources are changed.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pcbnew as p

BASE = Path(__file__).resolve().parents[1]
V = BASE/'verification'
INPUT_HASHES = {
    'base.kicad_pcb':'b8df082974c533e45a36d78a7b12d548ffbb5ad383fc22f28c40d850fb490db6',
    'base.kicad_sch':'ee92e702490409808f284c5113125f6b25afa314cb45e66cdcaa12a46c232e68',
    'slot.kicad_sch':'76d098af20c61ec651943f95069bd292694ae9cb9cbfdf1ed3593b1eee8740b1',
    'base.kicad_pro':'0d16b3f17e34bcda4b8d45860c69665f8b6db5a991470dc710e6dd95c1876101',
}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pos(q): return [q.x,q.y]
def pads(f, external_only=False):
    return {q.m_Uuid.AsString():{'position':pos(q.GetPosition()),'size':pos(q.GetSize()),
            'drill':pos(q.GetDrillSize()),'shape':int(q.GetShape()),
            'orientation':q.GetOrientationDegrees(),'layers':list(q.GetLayerSet().Seq())}
            for q in f.Pads() if not external_only or q.GetNumber() in list('12345678')}
def fp(f, external_only=False):
    return {'uuid':f.m_Uuid.AsString(),'position':pos(f.GetPosition()),'angle':f.GetOrientationDegrees(),
            'layer':f.GetLayer(),'pads':pads(f,external_only)}
def edges(b):
    return {q.m_Uuid.AsString():[pos(q.GetStart()),pos(q.GetEnd()),int(q.GetShape())]
            for q in b.GetDrawings() if q.GetLayer() == p.Edge_Cuts}
def holes(b):
    return {q.m_Uuid.AsString():[pos(q.GetPosition()),q.GetWidth(p.F_Cu),q.GetDrillValue()]
            for q in b.GetTracks() if q.GetClass() == 'PCB_VIA' and q.GetDrillValue() > p.FromMM(1)}
def run(*cmd): subprocess.run(list(map(str,cmd)),check=True)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-board',type=Path,required=True)
parser.add_argument('--bounded-improvements',action='store_true',help='Admit only the independently proven 1.3.13 three-cap/J5 delta')
a = parser.parse_args()
assert sha(a.source_board) == INPUT_HASHES['base.kicad_pcb'], 'Not the original branch board'
for name,digest in INPUT_HASHES.items():
    if name != 'base.kicad_pcb' and not (a.bounded_improvements and name=='base.kicad_sch'): assert sha(BASE/name) == digest, f'Circuit authority/project changed: {name}'
if a.bounded_improvements:
    from verify_bounded_improvements import verify
    verify(V/'bounded-improvements.json')
old = p.LoadBoard(str(a.source_board)); b = p.LoadBoard(str(BASE/'base.kicad_pcb'))
oldfps = {f.GetReference():f for f in old.GetFootprints()}; fps = {f.GetReference():f for f in b.GetFootprints()}
assert len(fps) == len(list(b.GetFootprints()))
assert edges(old) == edges(b) and holes(old) == holes(b)
assert b.GetCopperLayerCount() == old.GetCopperLayerCount() == 2
assert all(z.IsFilled() for z in b.Zones()) and len(b.Zones()) == 3
moved = {f'C{n}' for n in range(22,46)} # local output decouplers only
packages = {f'U{n}' for n in range(6,18)} | {'U2','U3','U4'}
removed = {f'R{n}' for n in range(28,51,2)} | {'R53','R54','J20','J21','J22'}
added = {'U18','J23','R55','C48','R57','R58','R59'}
assert set(oldfps)-set(fps) == removed and set(fps)-set(oldfps) == added | ({'C50','C51','C52'} if a.bounded_improvements else set())
preserved = {}
for ref in sorted(set(oldfps)&set(fps)):
    if ref in moved: continue
    before,after = fp(oldfps[ref]),fp(fps[ref])
    assert {k:before[k] for k in ['uuid','position','angle','layer']} == {k:after[k] for k in ['uuid','position','angle','layer']}, f'Anchor moved: {ref}'
    if ref not in packages:
        assert before == after, f'Unapproved pad/mechanical change: {ref}'
        preserved[ref] = before
    elif ref in ['U2','U3','U4']:
        assert fp(oldfps[ref],True) == fp(fps[ref],True), f'External SOIC pads moved: {ref}'
        preserved[ref] = fp(oldfps[ref],True)
# All refs/pins and suppliers independently checked before any hashes move.
with tempfile.TemporaryDirectory(prefix='base-freeze-') as temp:
    xml = Path(temp)/'final.xml'
    run('kicad-cli','sch','export','netlist','--format','kicadxml','-o',xml,BASE/'base.kicad_sch')
    r = ET.parse(xml).getroot()
    cs = {c.attrib['ref']:c for c in r.find('components') if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
    assert set(cs) == set(fps)
    pn = {(v.attrib['ref'],v.attrib['pin']):n.attrib['name'] for n in r.find('nets') for v in n if v.attrib['ref'] in cs}
    for ref,f in fps.items():
        c = cs[ref]
        assert f.GetValue() == c.findtext('value')
        assert str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()) == c.findtext('footprint')
        for d in f.Pads(): assert d.GetNetname() == pn.get((ref,d.GetNumber()),'')
        for q in c.findall('fields/field'):
            if q.attrib['name'] not in ['Reference','Value','Footprint']:
                assert f.GetFieldText(q.attrib['name']) == (q.text or ''), (ref,q.attrib['name'])
    assert set(map(str,b.GetNetsByName().keys()))-{''} == set(pn.values())
    run('kicad-cli','pcb','drc','--format','json','--schematic-parity','--severity-all','-o',V/'drc-after.json',BASE/'base.kicad_pcb')
    drc = json.loads((V/'drc-after.json').read_text())
    assert not drc['schematic_parity'] and not drc['unconnected_items']
    assert not any(q['severity']=='error' for q in drc['violations'])
    run('kicad-cli','sch','erc','--format','json','--severity-all','-o',V/'erc-after.json',BASE/'base.kicad_sch')
    run('kicad-cli','sch','export','netlist','--format','kicadsexpr','-o',V/'netlist-after.kicadsexpr',BASE/'base.kicad_sch')
prior = json.loads((V/'fixed-geometry.json').read_text())
project = json.loads((BASE/'base.kicad_pro').read_text())
assert prior['project_design_rules'] == project['board']['design_settings']['rules']
assert prior['project_rule_severities'] == project['board']['design_settings']['rule_severities']
assert project['board']['design_settings']['drc_exclusions'] == []
for key,value in prior['project_erc']['rule_severities'].items():
    assert project['erc']['rule_severities'][key] == value, f'ERC severity weakened: {key}'
mechanical = {'schema':'bread-modular/base/mechanical-invariants/2','input_pcb_sha256':INPUT_HASHES['base.kicad_pcb'],
              'note':'Input geometry, NOT a snapshot of the final changed footprints. SOIC external pads 1-8 retained; fictitious EP/paste removed.',
              'footprints':preserved,'edges':edges(old),'mounting_holes':holes(old),
              'intentional_local_decoupler_moves':sorted(moved),'intentional_package_changes':sorted(packages),
              'removed_obsolete_footprints':sorted(removed),'added_authoritative_footprints':sorted(added)}
mechanical_path = V/'mechanical-invariants.json'
if mechanical_path.exists():
    assert json.loads(mechanical_path.read_text()) == mechanical, 'Refusing mechanical baseline replacement'
else: mechanical_path.write_text(json.dumps(mechanical,indent=2)+'\n')
final = {'schema':'bread-modular/base/frozen-release/2','release_version':(BASE/'VERSION').read_text().strip(),
         'pcb_sha256':INPUT_HASHES['base.kicad_pcb'],'routed_pcb_sha256':sha(BASE/'base.kicad_pcb'),
         'schematic_sha256':sha(BASE/'base.kicad_sch'),'slot_schematic_sha256':sha(BASE/'slot.kicad_sch'),
         'project_sha256':sha(BASE/'base.kicad_pro'),'custom_rules_sha256':sha(BASE/'base.kicad_dru'),
         'mechanical_invariants_sha256':sha(mechanical_path),'copper_layers':2,
         'footprints':{ref:fp(f) for ref,f in sorted(fps.items())},'edges':edges(b),'mounting_holes':holes(b),
         'project_design_rules':project['board']['design_settings']['rules'],
         'project_rule_severities':project['board']['design_settings']['rule_severities'],
         'project_erc':project['erc'],'project_schematic':project['schematic']}
(V/'fixed-geometry.json').write_text(json.dumps(final,indent=2)+'\n')
erc = json.loads((V/'erc-after.json').read_text())
prior_evidence = json.loads((V/'improvements-before-geometry.json').read_text()) if a.bounded_improvements else prior
evidence = {'status':'software validation complete; order/bench/mating signoffs pending','input_hashes':INPUT_HASHES,
            'final_source_hashes':{n:sha(BASE/n) for n in ['base.kicad_pcb','base.kicad_sch','slot.kicad_sch','base.kicad_pro','base.kicad_dru']},
            'prior_pins':{k:prior_evidence.get(k) for k in ['pcb_sha256','routed_pcb_sha256','schematic_sha256','slot_schematic_sha256']},
            'drc':{'errors':0,'unconnected_items':0,'schematic_parity':0,'warnings':dict(collections.Counter(q['type'] for q in drc['violations']))},
            'erc':dict(collections.Counter(q['severity'] for sheet in erc['sheets'] for q in sheet['violations'])),
            'geometry':{'preserved_footprints':len(preserved),'preserved_mounting_holes':len(holes(b)),
                        'package_changes':sorted(packages),'local_decoupler_moves':sorted(moved),'added':sorted(added),'removed':sorted(removed),'bounded_supply_additions':['C50','C51','C52'] if a.bounded_improvements else []},
            'erc_pin_refresh_note':'Project/ERC severities unchanged. With --bounded-improvements, live ERC identities and old net memberships are proven identical except six supply/GND pins and two deliberate J5 fields; see bounded-improvements.json.'}
(V/'baseline-refresh.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'FROZEN after saved-board DRC: {len(fps)} refs, {len(pn)} pad nets; {len(preserved)} input anchors/pad sets and {len(holes(b))} mounting holes preserved.')
