#!/usr/bin/python3
"""Bounded native verification against the committed routed 16bit-5v baseline.

Rebound for the focused Basic/Economy metadata-only review in workspace 291. Historical
39f70c6/281 evidence is retained but is NOT replayed. This is not supplier,
manufacturing, physical-fit, thermal or bench approval. Sources/HEAD/workspace,
evidence hashes and the common tools remain guarded; no geometry changes are
permitted by this review.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import pcbnew as p

MOD = Path(__file__).resolve().parents[1]
ROOT = MOD.parents[1]
REF = '1e50e798d68e3d8d3167fb5fb47bdcb7ee436b83'
NAME = '16bit-5v'
EVIDENCE = MOD/'verification/basic-economy'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, default=EVIDENCE/'connectivity-final.json')
args = parser.parse_args()

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def original(name): return subprocess.check_output(['git','show',f'{REF}:modules/{NAME}/{name}'])
review = json.loads((EVIDENCE/'reviewed-source.json').read_text())
assert Path.cwd().resolve() == ROOT.resolve()
assert str(ROOT) == review['workspace']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() == REF == review['authority_ref']
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip() == review['branch']
assert review['release_status'] == 'HOLD'
assert {name:sha(MOD/name) for name in review['final_source_sha256']} == review['final_source_sha256'], 'Reviewed source changed'
assert all(hashlib.sha256(original(name)).hexdigest() == digest for name,digest in review['baseline_source_sha256'].items()), 'Wrong committed baseline'
assert all(sha(MOD/name) == digest for name,digest in review['evidence_sha256'].items()), 'Review evidence changed'
assert all(sha(ROOT/name) == digest for name,digest in review['common_tool_sha256'].items()), 'Common tool changed after review'
sys.path.insert(0,str(ROOT/'opt/kicad-jlcpcb'))
import export as e
plan = json.loads((EVIDENCE/'native-sourcing-plan.json').read_text())
assert plan['baseline_head'] == REF and plan['no_topology_or_geometry_changes'] is True
assert review['authorized_copper_delta'] == {'removed_original_ids':[], 'modified_original_ids':[], 'modified_geometry':{}, 'added_ids':[], 'added_geometry':{}}
assert review['placements'] == {}
checks = 0

def check(ok, msg):
    global checks
    checks += 1
    if not ok: raise AssertionError(msg)
def pos(q): return [q.x,q.y]
def fp_id(f): return f.GetFPID().GetUniStringLibId()
def padgeom(d):
    return [d.GetNumber(),pos(d.GetPosition()),pos(d.GetSize()),pos(d.GetDrillSize()),int(d.GetShape()),d.GetOrientationDegrees(),tuple(d.GetLayerSet().Seq()),int(d.GetAttribute())]
def copper(t):
    return [t.GetClass(),pos(t.GetStart()),pos(t.GetEnd()),t.GetLayer(),t.GetWidth(p.F_Cu) if t.GetClass()=='PCB_VIA' else t.GetWidth(),t.GetDrillValue() if t.GetClass()=='PCB_VIA' else 0,t.GetNetname()]
def edges(board):
    return {d.m_Uuid.AsString():[pos(d.GetStart()),pos(d.GetEnd()),int(d.GetShape())] for d in board.GetDrawings() if d.GetLayer()==p.Edge_Cuts}
def members(root):
    return {(v.attrib['ref'],v.attrib['pin']):n.attrib['name'] for n in root.find('nets') for v in n}
def xml_fields(comp):
    result = {f.attrib['name']:f.text or '' for f in comp.findall('fields/field')}
    result.update({f.attrib['name']:f.attrib.get('value','') for f in comp.findall('property')})
    result['Value'] = comp.findtext('value')
    result['Datasheet'] = comp.findtext('datasheet') or ''
    return result

with tempfile.TemporaryDirectory(prefix='16bit-routed-baseline-') as temp:
    oldpath=Path(temp)/'baseline.kicad_pcb'; oldpath.write_bytes(original(NAME+'.kicad_pcb'))
    before=p.LoadBoard(str(oldpath)); b=p.LoadBoard(str(MOD/(NAME+'.kicad_pcb')))
    oldroot=e.parse_sexpr(oldpath.read_text()); newroot=e.parse_sexpr((MOD/(NAME+'.kicad_pcb')).read_text())
    check(e.child(e.child(oldroot,'setup'),'stackup')==e.child(e.child(newroot,'setup'),'stackup'),'Changed stackup')
    check(e.child(oldroot,'layers')==e.child(newroot,'layers'),'Changed layer declarations')
    check(before.GetCopperLayerCount()==b.GetCopperLayerCount()==2,'Original has two copper layers')
    check(pos(before.GetDesignSettings().GetAuxOrigin())==pos(b.GetDesignSettings().GetAuxOrigin()),'Changed assembly/drill datum')
    fps={f.GetReference():f for f in b.GetFootprints()}; oldfps={f.GetReference():f for f in before.GetFootprints()}
    check(len(fps)==len(list(b.GetFootprints()))==62,'References must be complete/unique')
    check(set(fps)==set(oldfps),'Added/lost physical component')
    raw_old={e.atom(f,'uuid'):f for f in e.children(oldroot,'footprint')}
    raw_new={e.atom(f,'uuid'):f for f in e.children(newroot,'footprint')}
    def non_properties(form):
        return [n for n in form if not(isinstance(n,list) and n and n[0]=='property')]
    check(set(raw_old)==set(raw_new),'Footprint UUIDs changed')
    check(all(non_properties(raw_old[u])==non_properties(raw_new[u]) for u in raw_old),'Changed serialized lands/paste/silk/models/flags')
    for ref,f in fps.items():
        old=oldfps[ref]
        check(f.GetLayer()==old.GetLayer(),ref+': changed assembly/body side')
        check(f.GetOrientationDegrees()==old.GetOrientationDegrees(),ref+': changed rotation')
        check(pos(f.GetPosition())==pos(old.GetPosition()),ref+': changed placement')
        check(f.m_Uuid.AsString()==old.m_Uuid.AsString(),ref+': changed UUID')
        check(fp_id(f)==fp_id(old),ref+': changed package')
        pads={d.m_Uuid.AsString():d for d in f.Pads()}; opads={d.m_Uuid.AsString():d for d in old.Pads()}
        check(set(pads)==set(opads),ref+': added/lost terminal/thermal hole')
        check(all(padgeom(d)==padgeom(opads[u]) for u,d in pads.items()),ref+': land/drill geometry changed')
        fields={v.GetName():v.GetText() for v in f.GetFields()}
        oldfields={v.GetName():v.GetText() for v in old.GetFields()}
        intended=plan['allocations'].get(ref,{}).get('native_fields',{})
        check(all(fields.get(k)==v for k,v in intended.items()),ref+': stale sourcing/rating metadata')
        check({k:v for k,v in fields.items() if k not in intended}=={k:v for k,v in oldfields.items() if k not in intended},ref+': undocumented field change')
    check(edges(b)==edges(before),'Changed outline')
    mounts=lambda board:{t.m_Uuid.AsString():copper(t) for t in board.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetDrillValue()>p.FromMM(1)}
    check(mounts(b)==mounts(before) and len(mounts(b))==2,'Changed/lost either mount')
    def contours(root):
        return {e.atom(z,'uuid'):[e.child(z,'net'),e.child(z,'layer'),e.child(z,'layers'),e.children(z,'polygon'),e.child(z,'keepout')] for z in e.children(root,'zone')}
    check(contours(oldroot)==contours(newroot),'Changed net/pour/keepout contours')
    check(all(z.IsFilled() for z in b.Zones() if z.GetNetname()),'Saved zones not filled')
    oldtracks={t.m_Uuid.AsString():copper(t) for t in before.GetTracks()}; tracks={t.m_Uuid.AsString():copper(t) for t in b.GetTracks()}
    check(oldtracks==tracks,'Changed routed copper')
    forms=lambda root:{e.atom(n,'uuid'):n for kind in ['segment','via'] for n in e.children(root,kind)}
    check(forms(oldroot)==forms(newroot),'Changed serialized routing/nets')
    check(all(d.GetProperty()==p.PAD_PROP_HEATSINK for d in fps['U1'].Pads() if d.GetNumber()=='61'),'Changed thermal pad roles')
    check(sum(d.GetDrillSize().x>0 for d in fps['U1'].Pads() if d.GetNumber()=='61')==9,'Lost thermal holes')
    check(all(d.GetProperty()==p.PAD_PROP_MECHANICAL for d in fps['J5'].Pads() if d.GetNumber()=='S1'),'Changed shield-leg role')
    check((MOD/(NAME+'.kicad_pro')).read_bytes()==original(NAME+'.kicad_pro'),'Changed project/rules/severities/exclusions')
    pr=json.loads((MOD/(NAME+'.kicad_pro')).read_text()); check(pr['board']['design_settings']['drc_exclusions']==[],'DRC exclusions must remain empty')
    xml=Path(temp)/'live.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(MOD/(NAME+'.kicad_sch'))],check=True,capture_output=True)
    root=ET.parse(xml).getroot(); components={c.attrib['ref']:c for c in root.find('components') if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
    check(set(components)==set(fps),'Schematic/PCB physical refs differ')
    expected={pair:net for pair,net in members(root).items() if pair[0] in fps}; actual={}
    for ref,f in fps.items():
        check(f.GetValue()==components[ref].findtext('value'),ref+': stale value')
        check(fp_id(f)==components[ref].findtext('footprint'),ref+': stale footprint assignment')
        sf=xml_fields(components[ref])
        for key,val in plan['allocations'].get(ref,{}).get('native_fields',{}).items():
            check(sf.get(key)==val and f.GetFieldText(key)==val,ref+': schematic/PCB '+key+' mismatch')
        for d in f.Pads():
            pair=(ref,d.GetNumber()); check(d.GetNetname()==expected.get(pair,''),str(pair)+': wrong net'); actual[pair]=d.GetNetname()
    check(set(expected)<=set(actual),'Missing schematic terminal')
    baseline=ET.parse(EVIDENCE/'netlist-baseline.xml').getroot()
    oldmembers={pair:net for pair,net in members(baseline).items() if pair[0] in fps}
    check(expected==oldmembers,'Changed committed functional pin membership')
    j=fps['J5']; check(j.GetFieldText('JLCPCB Position Offset X')=='0' and j.GetFieldText('JLCPCB Position Offset Y')=='-3.675','Changed verified J5 body datum')
    lx=sum(math.hypot(t.GetEnd().x-t.GetStart().x,t.GetEnd().y-t.GetStart().y)/1e6 for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='/VREG_LX')
    report={'assertions_passed':checks,'baseline_ref':REF,'reviewed_source':'verification/basic-economy/reviewed-source.json','source_sha256':review['final_source_sha256'],'copper_layers':2,'component_count':62,'component_body_sides':dict(collections.Counter(b.GetLayerName(f.GetLayer()) for f in fps.values())),'back_body_refs':sorted(r for r,f in fps.items() if f.GetLayer()==p.B_Cu),'mounts_preserved':2,'thermal_holes_preserved':9,'unchanged_baseline_copper_items':len(tracks),'functional_pin_memberships_preserved':len(oldmembers),'physical_pad_count':sum(len(list(f.Pads())) for f in fps.values()),'filled_net_zones':sum(bool(z.GetNetname()) and z.IsFilled() for z in b.Zones()),'supplier_rating_metadata_refs':len(plan['allocations']),'VREG_LX_length_mm':round(lx,6),'release_status':'HOLD','scope':'Native refs/pins/metadata/unchanged geometry only; no human supplier/impedance/manufacturing/bench approval','remaining_blocked_refs':review['hold_refs']}
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS {checks} assertions; 62 refs; {len(tracks)} routed copper items exact; {len(oldmembers)} functional pin memberships exact; {len(plan["allocations"])} sourcing/rating refs synchronized; HOLD.')
