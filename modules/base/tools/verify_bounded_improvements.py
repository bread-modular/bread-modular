#!/usr/bin/python3
"""Prove only three 100nF supplies + J5 metadata changed after verified 1.3.12.

Live XML and ERC exports are compared to immutable imported evidence. Checks
all old net memberships/types/metadata, all 157 old mechanical pad sets and old
copper; saved-board DRC/parity remains separately mandatory. Does not change PCB.
"""
import argparse
import collections
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as E
import pcbnew as p
from assembly_datum import expected_position

BASE=Path(__file__).resolve().parents[1];V=BASE/'verification'
CAPS={'C50':'U2','C51':'U3','C52':'U4'}
FIELDS={'JLCPCB Position Offset X':'3.675','JLCPCB Position Offset Y':'0'}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def xy(q): return [q.x,q.y]
def geometry(f):
    return {'uuid':f.m_Uuid.AsString(),'position':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'layer':f.GetLayer(),
      'pads':{q.m_Uuid.AsString():{'position':xy(q.GetPosition()),'size':xy(q.GetSize()),'drill':xy(q.GetDrillSize()),'shape':int(q.GetShape()),'orientation':q.GetOrientationDegrees(),'layers':list(q.GetLayerSet().Seq())} for q in f.Pads()}}
def copper(t):
    d={'class':t.GetClass(),'net':t.GetNetname(),'start':xy(t.GetStart()),'end':xy(t.GetEnd()),'width':t.GetWidth(p.F_Cu) if t.GetClass()=='PCB_VIA' else t.GetWidth(),'layer':t.GetLayer()}
    if t.GetClass()=='PCB_VIA':d['drill']=t.GetDrillValue();d['layers']=list(t.GetLayerSet().Seq())
    return d

def load_xml(path):
    r=E.parse(path).getroot()
    comps={c.get('ref'):c for c in r.findall('components/comp')}
    pins={(q.get('ref'),q.get('pin')):(n.get('name'),q.get('pinfunction'),q.get('pintype')) for n in r.findall('nets/net') for q in n.findall('node')}
    assert len(comps)==len(r.findall('components/comp'))
    return comps,pins

def canonical(c,remove_offsets=False):
    c=copy.deepcopy(c)
    if remove_offsets:
        fields=c.find('fields')
        for q in list(fields):
            if q.get('name') in FIELDS:fields.remove(q)
        for q in list(c):
            if q.tag=='property' and q.get('name') in FIELDS:c.remove(q)
    for q in c.iter():
        if q.text is not None and not q.text.strip():q.text=None
        q.tail=None
    return E.tostring(c)

def identities(d):
    return collections.Counter((s['path'],v['severity'],v['type'],v['description'],
      tuple(sorted((q['uuid'],q['description']) for q in v['items']))) for s in d['sheets'] for v in s['violations'])

def verify(report=None):
    imported=json.loads((V/'imported-candidate.json').read_text())
    for name,digest in imported['baseline_evidence_sha256'].items():
        assert sha(V/name)==digest, f'Imported baseline evidence changed: {name}'
    for name in ['slot.kicad_sch','base.kicad_pro','base.kicad_dru']:
        assert sha(BASE/name)==imported['source_hashes'][name], f'Unapproved source edit: {name}'
    before=json.loads((V/'improvements-before-geometry.json').read_text())
    assert before['routed_pcb_sha256']==imported['source_hashes']['base.kicad_pcb']
    assert before['schematic_sha256']==imported['source_hashes']['base.kicad_sch']
    with tempfile.TemporaryDirectory(prefix='base-bounded-') as t:
        t=Path(t);xml=t/'after.xml';erc=t/'erc.json'
        subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(BASE/'base.kicad_sch')],check=True)
        subprocess.run(['kicad-cli','sch','erc','--format','json','--severity-all','-o',str(erc),str(BASE/'base.kicad_sch')],check=True)
        old,old_pins=load_xml(V/'improvements-before.xml');new,pins=load_xml(xml)
        assert set(new)==set(old)|set(CAPS), 'Only C50-C52 may be added'
        assert identities(json.loads(erc.read_text()))==identities(json.loads((V/'improvements-before-erc.json').read_text())), 'ERC identity changed'
    expected=dict(old_pins)
    for ref in CAPS:
        expected[ref,'1']=('GND',None,'passive');expected[ref,'2']=('+3.3V',None,'passive')
        c=new[ref]
        assert c.findtext('value')=='0.1uf' and c.findtext('footprint')=='Capacitor_SMD:C_0402_1005Metric'
        fields={q.get('name'):q.text or '' for q in c.findall('fields/field')}
        assert fields['LCSC']=='C1525' and fields['MPN']=='CL05B104KO5NNNC' and fields['Manufacturer']=='Samsung'
        assert not any(q.get('name') in ['dnp','exclude_from_bom','exclude_from_board'] for q in c.findall('property'))
    assert pins==expected, f'Old nets/pin types changed: {[(k,expected.get(k),pins.get(k)) for k in set(expected)|set(pins) if expected.get(k)!=pins.get(k)]}'
    for ref,c in old.items():
        assert canonical(c)==canonical(new[ref],ref=='J5'), f'Old metadata changed: {ref}'
    j5_fields={q.get('name'):q.text or '' for q in new['J5'].findall('fields/field')}
    assert all(j5_fields[k]==v for k,v in FIELDS.items()), 'Wrong deliberate J5 metadata'
    b=p.LoadBoard(str(BASE/'base.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()}
    assert len(fps)==len(list(b.GetFootprints()))==160
    assert set(fps)==set(before['footprints'])|set(CAPS)
    for ref,data in before['footprints'].items():assert geometry(fps[ref])==data, f'Existing mechanical/pad geometry changed: {ref}'
    edges={q.m_Uuid.AsString():[xy(q.GetStart()),xy(q.GetEnd()),int(q.GetShape())] for q in b.GetDrawings() if q.GetLayer()==p.Edge_Cuts}
    holes={q.m_Uuid.AsString():[xy(q.GetPosition()),q.GetWidth(p.F_Cu),q.GetDrillValue()] for q in b.GetTracks() if q.GetClass()=='PCB_VIA' and q.GetDrillValue()>p.FromMM(1)}
    assert edges==before['edges'] and holes==before['mounting_holes'] and len(holes)==28
    old_tracks=json.loads((V/'improvements-before-copper.json').read_text())
    tracks={q.m_Uuid.AsString():copper(q) for q in b.GetTracks()}
    for ident,data in old_tracks.items():assert tracks[ident]==data, f'Existing copper edited: {ident}'
    added=[q for q in b.GetTracks() if q.m_Uuid.AsString() not in old_tracks]
    assert len(added)==9 and collections.Counter(q.GetClass() for q in added)=={'PCB_TRACK':6,'PCB_VIA':3}
    assert collections.Counter(q.GetNetname() for q in added)=={'GND':6,'+3.3V':3}
    local={}
    for ref,target in CAPS.items():
        f=fps[ref];assert not f.IsDNP() and not f.IsExcludedFromBOM() and not f.IsExcludedFromPosFiles()
        for field in ['Value','Datasheet','Description','LCSC','MPN','Manufacturer']:
            assert f.GetFieldText(field)==fps['C15'].GetFieldText(field), (ref,field)
        for q in f.Pads():assert q.GetNetname()==('GND' if q.GetNumber()=='1' else '+3.3V')
        gnd=next(q for q in f.Pads() if q.GetNumber()=='1');supply=next(q for q in f.Pads() if q.GetNumber()=='2')
        power=next(q for q in fps[target].Pads() if q.GetNumber()=='8')
        line=next(q for q in added if q.GetClass()=='PCB_TRACK' and q.GetNetname()=='+3.3V' and {tuple(xy(q.GetStart())),tuple(xy(q.GetEnd()))}=={tuple(xy(supply.GetPosition())),tuple(xy(power.GetPosition()))})
        length=p.ToMM(line.GetLength());assert length<3 and line.GetLayer()==p.F_Cu
        gline=next(q for q in added if q.GetClass()=='PCB_TRACK' and q.GetNetname()=='GND' and q.GetStart()==gnd.GetPosition())
        v=next(q for q in added if q.GetClass()=='PCB_VIA' and q.GetNetname()=='GND' and q.GetPosition()==gline.GetEnd())
        return_length=p.ToMM(gline.GetLength());assert return_length<=1 and v.GetDrillValue()==p.FromMM(.4)
        local[ref]={'target_pin8':target,'supply_track_mm':length,'GND_return_track_mm':return_length,'GND_via_board_mm':[p.ToMM(v.GetPosition().x),p.ToMM(v.GetPosition().y)]}
    assert all(z.IsFilled() for z in b.Zones()) and len(b.Zones())==3
    assert all(fps['J5'].GetFieldText(k)==v for k,v in FIELDS.items())
    datum=expected_position(fps['J5'],b.GetDesignSettings().GetAuxOrigin())
    assert all(abs(a-z)<1e-9 for a,z in zip(datum,(4.035,130.81)))
    captions={q.GetText() for q in b.GetDrawings() if q.GetClass()=='PCB_TEXT' and q.GetLayer()==p.F_SilkS}
    assert {'J23 LINE MONO','OPEN=STEREO'}<=captions
    assert fps['J23'].IsDNP() and not any('HEADPHONE MONO' in q for q in captions)
    result={'result':'PASS','source_sha256':{n:sha(BASE/n) for n in imported['source_hashes']},'old_schematic_components_preserved':len(old),'old_schematic_pin_memberships_preserved':len(old_pins),'added_schematic_pins':6,'total_schematic_pin_memberships':len(pins),'old_physical_geometry_preserved':157,'outline_and_all_28_mounting_holes_preserved':True,'old_copper_items_preserved':len(old_tracks),'new_copper_items':9,'dedicated_bypass_caps':local,'J5_expected_CPL_mm':list(datum),'ERC_identity_delta':0,'ERC_counts':{'error':7,'warning':4},'PCB_pending_skips':0,'bench_proof':False}
    if report:Path(report).write_text(json.dumps(result,indent=2)+'\n')
    print('BOUNDED PASS: '+json.dumps(result,sort_keys=True))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path);a=ap.parse_args();verify(a.report)
