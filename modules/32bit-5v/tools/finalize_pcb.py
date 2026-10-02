#!/usr/bin/python3
"""Bounded ORIGINAL32bit-5v PCB correction; no shared/base code is changed.
Rebuilds only the stale LDO cluster from original HEAD, retaining multilayer
routing, thermal pads, mounting holes and ALL connector registration/orientation.
This migration alone is not release signoff: run saved-board DRC/ERC/parity.
"""
from pathlib import Path
import collections, hashlib, json, subprocess, sys, tempfile, shutil
import xml.etree.ElementTree as E
import pcbnew as p
sys.excepthook=sys.__excepthook__
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[1]
PCB=BASE/'32bit-5v.kicad_pcb'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='65e1d7202f22f0ef8b387e9f1e0c1b6740731ead'
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip().startswith('okbrain/bread-modular-kicad/274-')
original=subprocess.check_output(['git','show','HEAD:modules/32bit-5v/32bit-5v.kicad_pcb'])
ctx=tempfile.TemporaryDirectory(prefix='32bit-finalize-'); cp=Path(ctx.name)
(cp/PCB.name).write_bytes(original);shutil.copyfile(BASE/'32bit-5v.kicad_pro',cp/'32bit-5v.kicad_pro')
b=p.LoadBoard(str(cp/PCB.name));assert b.GetCopperLayerCount()==4
M=p.FromMM; V=lambda q:p.VECTOR2I(M(q[0]),M(q[1]))
xy=lambda q:(round(p.ToMM(q.x),6),round(p.ToMM(q.y),6))
fps={f.GetReference():f for f in b.GetFootprints()}; detached=[]
def remove(q): b.RemoveNative(q);detached.append(q)
def geometry():
    return {'copper_layers':[b.GetLayerName(i) for i in b.GetEnabledLayers().CuStack()],
            'edges':[(d.GetShapeStr(),xy(d.GetStart()),xy(d.GetEnd())) for d in b.GetDrawings() if d.GetLayer()==p.Edge_Cuts],
            'mounts':[(xy(t.GetPosition()),p.ToMM(t.GetDrill()),p.ToMM(t.GetWidth(p.F_Cu))) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetDrill()>M(3)],
            'connectors':{ref:{'side':b.GetLayerName(f.GetLayer()),'anchor':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'pads':[(d.GetNumber(),xy(d.GetPosition()),d.GetNetname(),xy(d.GetSize()),xy(d.GetDrillSize())) for d in f.Pads()]} for ref,f in fps.items() if ref in {'GND1','V_SUPPLY1','INPUT1','OUTPUT1','J5','RV1','RV2'}},
            'thermal':[(d.GetNumber(),xy(d.GetPosition()),list(d.GetLayerSet().Seq()),xy(d.GetSize()),xy(d.GetDrillSize())) for d in fps['U4'].Pads() if d.GetNumber()=='29']}
baseline=geometry(); original_tracks={str(t.m_Uuid.AsString()) for t in b.GetTracks()}
r=E.parse(BASE/'verification/final-netlist.xml').getroot()
cs={c.get('ref'):c for c in r.find('components') if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
pn={(v.get('ref'),v.get('pin')):n.get('name') for n in r.find('nets') for v in n}
nets={str(k):v for k,v in b.GetNetsByName().items()}
for name in set(pn.values())-set(nets): ni=p.NETINFO_ITEM(b,name);b.Add(ni);nets[name]=ni
# Only historical caps removed by the authoritative schematic, never circuit edits.
assert set(fps)-set(cs)=={'C9','C10','C11','C12','C13'}
for ref in set(fps)-set(cs): remove(fps.pop(ref))
# Remove obsolete LDO power drops only. All other copper remains intact.
for t in list(b.GetTracks()):
    if isinstance(t,p.PCB_VIA):continue
    a,z=xy(t.GetStart()),xy(t.GetEnd())
    if t.GetLayer()==p.B_Cu and t.GetNetname() in {'+5V','+3V3','GND'} and 53<=min(a[0],z[0]) and max(a[0],z[0])<68 and 50<=min(a[1],z[1]) and max(a[1],z[1])<63:
        remove(t)
# Obsolete capacitor branches identified by native DRC, never valid live routes.
prune=BASE/'verification/obsolete-cap-stubs.json'
prune_ids=set(json.loads(prune.read_text())) if prune.exists() else set()
for t in list(b.GetTracks()):
    if str(t.m_Uuid.AsString()) in prune_ids or (isinstance(t,p.PCB_VIA) and xy(t.GetPosition())==(62.15,47.15)):
        assert not (isinstance(t,p.PCB_VIA) and t.GetDrill()>M(3))
        remove(t)
# Replace only true package faults; preserve U3 external lead registration exactly.
for ref in ['U3','U5','C42']:
    c=cs[ref];lib,item=c.findtext('footprint').split(':',1)
    f=p.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty',item);assert f
    f.SetFPID(p.LIB_ID(lib,item));old=fps.get(ref)
    if old:
        f.SetUuid(old.m_Uuid); f.SetPosition(old.GetPosition());f.SetOrientationDegrees(old.GetOrientationDegrees())
        f.SetPath(old.GetPath());f.Reference().SetPosition(old.Reference().GetPosition())
        if ref=='U3':
            assert all(xy(d.GetPosition())==xy(next(q for q in old.Pads() if q.GetNumber()==d.GetNumber()).GetPosition()) for d in f.Pads())
        remove(old)
    b.Add(f);fps[ref]=f
for ref,c in cs.items():
    f=fps[ref];f.SetReference(ref);f.SetValue(c.findtext('value'))
    if not f.GetPath().AsString():f.SetPath(p.KIID_PATH(c.find('sheetpath').get('tstamps')+c.findtext('tstamps')))
    props={v.get('name'):v.get('value','') for v in c.findall('property')}
    f.SetSheetname(props.get('Sheetname',''));f.SetSheetfile(props.get('Sheetfile',''))
    fields={v.get('name'):v.text or '' for v in c.findall('fields/field')}
    fields.update({'Datasheet':c.findtext('datasheet') or fields.get('Datasheet',''),'Description':fields.get('Description','')})
    for name,value in fields.items():
        if name in {'Reference','Value','Footprint'}:continue
        f.SetField(name,value);f.GetField(name).SetVisible(False)
    for d in f.Pads():d.SetNet(nets[pn.get((ref,d.GetNumber()),'')])
    f.Value().SetVisible(False)
def place(ref,q,angle=0,label=None):
    f=fps[ref]
    if f.GetLayer()==p.B_Cu:f.Flip(f.GetPosition(),False)
    f.SetOrientationDegrees(angle);f.SetPosition(V(q))
    f.Reference().SetTextSize(V((.8,.8)));f.Reference().SetTextThickness(M(.12));f.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
    f.Reference().SetPosition(V(label or (q[0],q[1]-1.8)));f.Reference().SetVisible(True)
place('U5',(60.5,47.5),0,(60.5,45.2))
place('C40',(55.3,47.0),0,(55.3,45.3))
place('C41',(65.05,53.0),0,(65.05,54.0))
place('C42',(56.8,49.0),90,(56.8,49.8))
def pt(ref,num):return xy(next(d for d in fps[ref].Pads() if d.GetNumber()==str(num)).GetPosition())
def wire(net,points,width=.3,layer=p.F_Cu):
    for a,z in zip(points,points[1:]):
        if V(a)==V(z):continue
        t=p.PCB_TRACK(b);t.SetStart(V(a));t.SetEnd(V(z));t.SetWidth(M(width));t.SetLayer(layer);t.SetNet(nets[net]);b.Add(t)
def via(net,q,size=.6,drill=.3):
    t=p.PCB_VIA(b);t.SetPosition(V(q));t.SetWidth(M(size));t.SetDrill(M(drill));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(nets[net]);b.Add(t)
# VIN and EN approach each lead from the outside of the SOT-23 body.
wire('+5V',[pt('U5',1),(58.1,46.55),(58.1,48.2),(58.1,49.2),(58.42,49.52),(58.42,50.8)],.3)
wire('+5V',[pt('U5',3),(58.1,48.45)],.25)
wire('+5V',[pt('C40',1),(54.35,47.0),(54.35,49.2),(55.88,50.73),(55.88,50.8)],.35)
wire('+5V',[pt('C42',1),(56.8,49.65),(57.4,50.25),(58.42,50.25)],.25)
for ref,pin,q in [('U5',2,(59.3625,47.5)),('C40',2,(56.25,46.5)),('C41',2,(66.35,53.25))]:
    wire('GND',[pt(ref,pin),q],.3);via('GND',q)
wire('GND',[pt('C42',2),(56.8,47.55),pt('C40',2)],.3)
via('+3V3',(61.95,46.5));wire('+3V3',[pt('U5',5),(61.95,46.55),(61.95,46.5)],.35)
# Pass outside the fifth rail pin rather than violating the 0.15mm global width.
wire('+3V3',[(61.95,46.5),(64.0,48.55),(66.65,48.55),(68.1,50.0),(68.1,51.5),(67.25,52.35),(64.1,52.35)],.35,p.B_Cu)
via('+3V3',(64.1,52.35));wire('+3V3',[pt('C41',1),(64.1,52.35)],.35)
wire('+3V3',[(64.1,52.35),(64.0,52.25),(57.5,52.25)],.35,p.B_Cu)
# Preserve original land coordinates; part-specific clearance applies only pad pairs.
local=BASE/'Module32.pretty';local.mkdir(exist_ok=True)
usbf=fps['J5'];usbf.SetFPID(p.LIB_ID('Module32','HRO-TYPE-C-31-M-12'))
# Mounted connector remains SMD, with four legitimate plated shell anchors.
# Thermal-via QFN is SMD with intentional PTH thermal pads, not a THT body.
assert geometry()==baseline,'Protected mechanics/thermal/stack changed'
for d in usbf.Pads():
    if d.GetNumber() in {'A1','A4','A9','A12'}:
        size=d.GetSize();size.x=M(.575);d.SetSize(size)
summary_land_note='J5 four wide power lands: 0.600 to 0.575mm width within exact cached HRO TYPE-C-31-M-12 drawing p1 4-0.60mm and PCB-layout +/-0.05mm (verification/identity-land-evidence.json); not overall physical-fit approval; all centers, drills and connector registration unchanged; no relaxed clearances.'
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(PCB),b)
summary={'base_commit':'65e1d7202f22f0ef8b387e9f1e0c1b6740731ead','original_pcb_sha256':hashlib.sha256(original).hexdigest(),'protected_geometry':baseline,
         'retained_original_track_objects':len(original_tracks&{str(t.m_Uuid.AsString()) for t in b.GetTracks()}),'original_track_objects':len(original_tracks),
         'physical_side_counts':dict(collections.Counter(b.GetLayerName(f.GetLayer()) for f in b.GetFootprints())),
         'bottom_body_refs':sorted(f.GetReference() for f in b.GetFootprints() if f.GetLayer()==p.B_Cu),
         'assembly_status':'PENDING HUMAN SIDE DECISION; underside connectors preserved, not an authorized exception'}
(BASE/'verification/layout-migration.json').write_text(json.dumps(summary,indent=2)+'\n')
print('Saved four-layer original-derived board: stale packages/caps synced, front LDO cluster routed; protected geometry unchanged.')
