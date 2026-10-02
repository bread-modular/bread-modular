#!/usr/bin/python3
"""Read-only bounded 16bit-5v source/net/geometry verification (not bench signoff).

Adapted from BASE's native pcbnew/netlist verification pattern, without any
BASE-specific stack, pin geometry, hash pin or circuit assumptions. The original
39f70c6 board is read via Git only; no worktree/branch is switched or modified.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import importlib.util
import json
import math
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pcbnew as p

MOD = Path(__file__).resolve().parents[1]
REF = '39f70c646d854e1e43779866c62bead5ab3f003d'
NAME = '16bit-5v'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, default=MOD/'verification/connectivity.json')
args = parser.parse_args()
review=json.loads((MOD/'verification/review-response.json').read_text())
assert Path.cwd().resolve()==MOD.parents[1].resolve()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==REF
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()==review['branch']
assert str(MOD.parents[1])==review['workspace']
checks = 0
def check(ok, msg):
    global checks
    checks += 1
    if not ok: raise AssertionError(msg)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def pos(q): return [q.x, q.y]
def fp_id(f): return str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName())
def original(name): return subprocess.check_output(['git','show',f'{REF}:modules/{NAME}/{name}'])
def padgeom(d):
    return [d.GetNumber(), pos(d.GetPosition()), pos(d.GetSize()), pos(d.GetDrillSize()),
            int(d.GetShape()), d.GetOrientationDegrees(), tuple(d.GetLayerSet().Seq()), int(d.GetAttribute())]
def copper(t):
    return [t.GetClass(), pos(t.GetStart()), pos(t.GetEnd()), t.GetLayer(),
            t.GetWidth(p.F_Cu) if t.GetClass()=='PCB_VIA' else t.GetWidth(),
            t.GetDrillValue() if t.GetClass()=='PCB_VIA' else 0, t.GetNetname()]
spec = importlib.util.spec_from_file_location('exporter', MOD/'tools/jlcpcb_export.py')
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
with tempfile.TemporaryDirectory(prefix='16bit-original-') as temp:
    oldpath=Path(temp)/'original.kicad_pcb';oldpath.write_bytes(original(NAME+'.kicad_pcb'))
    before=p.LoadBoard(str(oldpath));b=p.LoadBoard(str(MOD/(NAME+'.kicad_pcb')))
    oldroot=e.parse_sexpr(oldpath.read_text());newroot=e.parse_sexpr((MOD/(NAME+'.kicad_pcb')).read_text())
    check(e.child(e.child(oldroot,'setup'),'stackup') == e.child(e.child(newroot,'setup'),'stackup'), 'Changed original stackup')
    check(before.GetCopperLayerCount()==b.GetCopperLayerCount()==2, 'Original is two-layer; do not invent a four-layer stack')
    fps={f.GetReference():f for f in b.GetFootprints()};oldfps={f.GetReference():f for f in before.GetFootprints()}
    check(len(fps)==len(list(b.GetFootprints()))==62, 'References must be complete and unique')
    check(set(fps)==set(oldfps), 'Lost/added physical component')
    for ref,f in fps.items():
        old=oldfps[ref]
        check(f.GetLayer()==old.GetLayer(), f'{ref}: changed body/assembly side')
        target=review['placements'].get(ref)
        want_angle=target['angle'] if target else old.GetOrientationDegrees()
        check(f.GetOrientationDegrees()==want_angle,f'{ref}: undocumented rotation')
        want=target['anchor_iu'] if target else pos(old.GetPosition())
        if ref=='C26':want[1]+=p.FromMM(.375)
        check(pos(f.GetPosition())==want,f'{ref}: undocumented placement')
        check(f.m_Uuid.AsString()==old.m_Uuid.AsString(),f'{ref}: lost native footprint UUID')
        check(fp_id(f)==('Package_SO:SOIC-8_3.9x4.9mm_P1.27mm' if ref in ['U3','U4'] else fp_id(old)),f'{ref}: unsupported package change')
        pads={d.m_Uuid.AsString():d for d in f.Pads()};opads={d.m_Uuid.AsString():d for d in old.Pads()}
        if ref in ['U3','U4']:
            opads={u:d for u,d in opads.items() if d.GetNumber() in list('12345678')}
            check(len(pads)==8 and {d.GetNumber() for d in pads.values()}==set('12345678'),ref+': unsupported EP or paste retained')
            check(all(p.F_Paste in list(d.GetLayerSet().Seq()) for d in pads.values()),ref+': missing standard lead paste')
        check(set(pads)==set(opads),f'{ref}: lost/added external terminal or thermal hole')
        delta=math.radians(want_angle-old.GetOrientationDegrees())
        for uid,d in pads.items():
            g=padgeom(opads[uid])
            if target:
                dx,dy=g[1][0]-old.GetPosition().x,g[1][1]-old.GetPosition().y
                g[1]=[round(want[0]+math.cos(delta)*dx+math.sin(delta)*dy),round(want[1]-math.sin(delta)*dx+math.cos(delta)*dy)]
                g[5]=(g[5]+want_angle-old.GetOrientationDegrees())%360
                now=padgeom(d);now[5]%=360
            else:
                if ref=='C26':g[1][1]+=p.FromMM(.375)
                now=padgeom(d)
            check(now==g,f'{ref}.{d.GetNumber()}: changed land/drill geometry')
    def edges(board):
        return {d.m_Uuid.AsString():[pos(d.GetStart()),pos(d.GetEnd()),int(d.GetShape())]
                for d in board.GetDrawings() if d.GetLayer()==p.Edge_Cuts}
    check(edges(b)==edges(before),'Changed board outline')
    def mounts(board):
        return {t.m_Uuid.AsString():copper(t) for t in board.GetTracks()
                if t.GetClass()=='PCB_VIA' and t.GetDrillValue()>p.FromMM(1)}
    check(mounts(b)==mounts(before) and len(mounts(b))==2,'Changed/lost either 3.2 mm mount')
    def contours(root):
        return {e.atom(z,'uuid'):[e.child(z,'net'),e.child(z,'net_name'),e.child(z,'layer'),e.child(z,'layers'),e.children(z,'polygon'),e.child(z,'keepout')]
                for z in e.children(root,'zone')}
    # Net serialization changed in KiCad 10; compare contour/layer/keepout geometry.
    ca,cz=contours(oldroot),contours(newroot)
    check(set(ca)==set(cz),'Changed original zone identities')
    check(all(a[2:]==cz[k][2:] for k,a in ca.items()),'Changed original pour/keepout contours')
    check(all(z.IsFilled() for z in b.Zones() if z.GetNetname()),'Saved copper zones are not filled')
    oldtracks={t.m_Uuid.AsString():copper(t) for t in before.GetTracks()};tracks={t.m_Uuid.AsString():copper(t) for t in b.GetTracks()}
    removed=set(review['authorized_copper_delta']['removed_original_ids'])
    changed=set(review['authorized_copper_delta']['modified_original_ids'])
    check(set(oldtracks)-set(tracks)==removed,'Undocumented discarded original routing')
    exact=0
    for uid,data in oldtracks.items():
        if uid not in removed|changed:check(tracks[uid]==data,'Changed preserved original copper '+uid);exact+=1
        elif uid in changed:check(tracks[uid]==review['authorized_copper_delta']['modified_geometry'][uid],'Stale documented local modification '+uid)
    added=set(tracks)-set(oldtracks)
    check(added==set(review['authorized_copper_delta']['added_ids']),'Undocumented routing additions')
    check(all(tracks[u]==review['authorized_copper_delta']['added_geometry'][u] for u in added),'Stale local route evidence')
    # Verify native serialized nets, independent of pcbnew loading/repair.
    def forms(root):return {e.atom(n,'uuid'):n for kind in ['segment','via'] for n in e.children(root,kind)}
    serial_old,serial_new=forms(oldroot),forms(newroot)
    check(all(e.atom(serial_new[u],'net')==e.atom(n,'net') for u,n in serial_old.items() if u in serial_new),'Existing ground/other conductor repurposed')
    for prefix in ['bf495bba','c8443bbc','83672839','d63ffa4d']:
        uid=next(u for u in serial_old if u.startswith(prefix))
        check(e.atom(serial_old[uid],'net')==e.atom(serial_new[uid],'net')=='+3V3','Candidate endpoint was not genuine original +3V3')
    check(all(d.GetProperty()==p.PAD_PROP_HEATSINK for d in fps['U1'].Pads() if d.GetNumber()=='61'),'Unclassified thermal pads')
    check(sum(d.GetDrillSize().x>0 for d in fps['U1'].Pads() if d.GetNumber()=='61')==9,'Lost MCU thermal holes')
    check(all(d.GetProperty()==p.PAD_PROP_MECHANICAL for d in fps['J5'].Pads() if d.GetNumber()=='S1'),'Unclassified shield legs')
    pr=json.loads((MOD/(NAME+'.kicad_pro')).read_text());oldpr=json.loads(original(NAME+'.kicad_pro'))
    check(pr['board']['design_settings']['drc_exclusions']==[],'DRC exclusions must be empty')
    for key in ['rules','rule_severities']:
        check(pr['board']['design_settings'][key]==oldpr['board']['design_settings'][key],'Relaxed global DRC '+key)
    check(pr['erc']==oldpr['erc'],'Changed/suppressed ERC settings')
    xml=Path(temp)/'live.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(MOD/(NAME+'.kicad_sch'))],check=True,capture_output=True)
    r=ET.parse(xml).getroot();components={c.attrib['ref']:c for c in r.find('components') if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
    check(set(components)==set(fps),'Schematic/PCB physical component set differs')
    expected={(v.attrib['ref'],v.attrib['pin']):n.attrib['name'] for n in r.find('nets') for v in n if v.attrib['ref'] in fps}
    actual={}
    for ref,f in fps.items():
        check(f.GetValue()==components[ref].findtext('value'),ref+': stale value')
        check(fp_id(f)==components[ref].findtext('footprint'),ref+': stale footprint')
        for d in f.Pads():
            pair=(ref,d.GetNumber());check(d.GetNetname()==expected.get(pair,''),str(pair)+': wrong net');actual[pair]=d.GetNetname()
    check(set(expected)<=set(actual),'Missing schematic terminal')
    oldxml=ET.parse(MOD/'verification/netlist.xml').getroot()
    aliases={('J5',n) for n in ['B1','B12','B4','B9']}
    oldmembers={(v.attrib['ref'],v.attrib['pin']):('/USB_VBUS_UNUSED' if n.attrib['name']=='Net-(J5-VBUS-PadA4)' else n.attrib['name'])
                for n in oldxml.find('nets') for v in n if v.attrib['ref'] in fps and (v.attrib['ref'],v.attrib['pin']) not in aliases}
    check(all(expected.get(pair)==net for pair,net in oldmembers.items()),'Changed original functional pin membership')
    check(set(expected)-set(oldmembers)=={('J5','A8'),('J5','B8')},'Unexpected new circuit pins')
    for ref in ['U6','L1']:
        check(fps[ref].GetValue()==oldfps[ref].GetValue() and fp_id(fps[ref])==fp_id(oldfps[ref]),ref+': blindly replaced power part')
    j=fps['J5'];check(j.GetFieldText('JLCPCB Position Offset X')=='0' and j.GetFieldText('JLCPCB Position Offset Y')=='-3.675','J5 body datum differs')
    sidecounts=collections.Counter(b.GetLayerName(f.GetLayer()) for f in fps.values())
    lx=sum(math.hypot(t.GetEnd().x-t.GetStart().x,t.GetEnd().y-t.GetStart().y)/1e6 for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='/VREG_LX')
    report={'assertions_passed':checks,'original_ref':REF,'pcb_sha256':sha(MOD/(NAME+'.kicad_pcb')),'schematic_sha256':sha(MOD/(NAME+'.kicad_sch')),
      'copper_layers':2,'component_count':62,'component_body_sides':dict(sidecounts),'back_body_refs':sorted(f.GetReference() for f in fps.values() if f.GetLayer()==p.B_Cu),
      'mounts_preserved':2,'thermal_holes_preserved':9,'unchanged_original_copper_items':exact,'removed_documented_local_segments':len(removed),'modified_original_copper_items':len(changed),'added_tracks_vias':len(added),
      'functional_pin_memberships_preserved':len(oldmembers),'physical_pad_count':sum(len(list(f.Pads())) for f in fps.values()),'filled_net_zones':sum(bool(z.GetNetname()) and z.IsFilled() for z in b.Zones()),
      'VREG_LX_length_mm':round(lx,6),'VREG_LX_before_length_mm':review['LX']['before_length_mm'],'VREG_LX_widths_mm':review['LX']['widths_mm'],'power_note':'Targeted short front LX + local input/output/PGND return; original inductor retained. Bench/ripple/inductor winding validation remains a release gate.',
      'assembly_note':'All 56 SMD bodies top; 2 top pots + 4 downward underside connector bodies retained and placement approved by user. Existing 2Cu preserved; routing/export data integration-ready. Physical header lead/pot-case clearance, sourcing/assembler and final production review still needed before ordering; no order authorized. Prior Astra corrections are historical evidence.',
      'j5_nominal_body_center_board_mm':[72.136,44.294],'release_status':'INTEGRATION-READY — user-approved THT/underside placement; existing 2Cu preserved; ORDERING HOLD, no order authorized'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS {checks} assertions; 62 unique physical refs; 2 mounts + 9 thermal holes; {exact} old copper items exact; 0 changed functional memberships.')
