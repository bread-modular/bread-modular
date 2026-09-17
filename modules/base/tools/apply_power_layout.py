#!/usr/bin/python3
"""Reproducible base power layout from an explicitly supplied pre-upgrade PCB."""
import pcbnew as p
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse, hashlib, json
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-board', type=Path, required=True)
parser.add_argument('--netlist', type=Path, required=True, help='Fresh kicadxml export of the merged schematic')
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
src=args.source_board
baseline=json.loads((Path(__file__).resolve().parents[1]/'verification/fixed-geometry.json').read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==baseline['pcb_sha256'], 'Expected the untouched pre-upgrade PCB; refusing to overwrite/re-apply to a routed board'
b=p.LoadBoard(str(src))
project_path=Path(__file__).resolve().parents[1]/'base.kicad_pro'
settings=p.GetSettingsManager()
assert settings.LoadProject(str(project_path))
b.SetProject(settings.GetProject(str(project_path)))
assert b.GetDesignSettings().m_MinClearance==p.FromMM(.2), 'Project rules were not loaded'
xml=ET.parse(str(args.netlist)).getroot()
M=p.FromMM
V=lambda xy:p.VECTOR2I(M(xy[0]),M(xy[1]))
xy=lambda q:(round(p.ToMM(q.x),6),round(p.ToMM(q.y),6))
fps={f.GetReference():f for f in b.GetFootprints()}
nets={str(n):v for n,v in b.GetNetsByName().items()}
for n in xml.find('nets'):
 name=n.attrib['name']
 if name not in nets:
  ni=p.NETINFO_ITEM(b,name);b.Add(ni);nets[name]=ni
pn={(a.attrib['ref'],a.attrib['pin']):n.attrib['name'] for n in xml.find('nets') for a in n}
# HRO's A1/A4 are the second GND/VBUS contact on the 16-contact receptacle;
# map them to the power-only symbol's B12/B9 without changing pad geometry.
for pad in fps['J5'].Pads():
 if pad.GetNumber() in ['A1','A4']:pad.SetNumber({'A1':'B12','A4':'B9'}[pad.GetNumber()])
# Identify old-net renames from original pad identity, excluding split rails.
rename={}
for f in fps.values():
 for pad in f.Pads():
  old=pad.GetNetname();new=pn.get((f.GetReference(),pad.GetNumber()))
  if old and new and old not in ['+3.3V','Net-(D1-A)']:
   if old in rename:assert rename[old]==new,(old,rename[old],new)
   rename[old]=new
rename['Net-(D1-A)']='VBUS_PROT'
# Keep original 3.3V regulator, audio and utility socket distribution. Remove
# only shared horizontal slot conductors and their three approach diagonals.
for t in list(b.GetTracks()):
 a,c=xy(t.GetStart()),xy(t.GetEnd());name=t.GetNetname()
 remove=name=='+3.3V' and t.GetClass()=='PCB_TRACK' and (
  (a[1]==c[1] and a[1] in [38.1,106.68] and max(a[0],c[0])>60) or
  (max(a[0],c[0])==60.96 and min(a[0],c[0])==55.88))
 # Reroute input copper explicitly through F1; retain only FB1/C17/C21 link.
 if name=='Net-(D1-A)' and min(a[1],c[1])<55:remove=True
 if remove:b.Remove(t)
 elif name in rename:t.SetNet(nets[rename[name]])
for f in fps.values():
 for pad in f.Pads():
  name=pn.get((f.GetReference(),pad.GetNumber()),'')
  pad.SetNet(nets[name])
# Copy schematic metadata and add library footprints, never moving old hardware.
newrefs=[]
for comp in xml.find('components'):
 ref=comp.attrib['ref'];ident=comp.findtext('footprint')
 if not ident or comp.find("property[@name='exclude_from_board']") is not None:continue
 if ref not in fps:
  lib,item=ident.split(':',1);f=p.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty',item)
  assert f,ident
  b.Add(f);f.SetReference(ref);f.SetFPID(p.LIB_ID(lib,item));fps[ref]=f;newrefs.append(ref)
 f=fps[ref];f.SetValue(comp.findtext('value'));f.SetPath(p.KIID_PATH('/'+comp.findtext('tstamps')))
 for name in ['LCSC','MPN','Manufacturer']:
  val=comp.findtext(f"fields/field[@name='{name}']")
  if val:
   field=f.GetFieldByName(name)
   if not field:
    field=p.PCB_FIELD(f,f.GetNextFieldId(),name);field=f.AddField(field)
   field.SetText(val);field.SetVisible(False)
 for pad in f.Pads():
  pad.SetNet(nets[pn.get((ref,pad.GetNumber()),'')])
 # Sch simulation sources/on-board no are absent from the exported board BOM.

def place(ref,x,y,angle=0):
 f=fps[ref];f.SetPosition(V((x,y)));f.SetOrientationDegrees(angle)
 f.Value().SetVisible(False)
 f.Reference().SetTextSize(V((.8,.8)));f.Reference().SetTextThickness(M(.12));f.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
 f.Reference().SetPosition(V((x,y-2.1)))
 return f

def pt(ref,pin):return xy(next(d for d in fps[ref].Pads() if d.GetNumber()==str(pin)).GetPosition())
def wire(net,points,width=.25,layer=p.F_Cu):
 for a,c in zip(points,points[1:]):
  if a==c:continue
  t=p.PCB_TRACK(b);t.SetStart(V(a));t.SetEnd(V(c));t.SetWidth(M(width));t.SetLayer(layer);t.SetNet(nets[net]);b.Add(t)
def via(net,pos,diam=.8,drill=.4):
 v=p.PCB_VIA(b);v.SetPosition(V(pos));v.SetWidth(M(diam));v.SetDrill(M(drill));v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(nets[net]);b.Add(v)
def ground(ref,pin,pos,width=.25):
 wire('GND',[pt(ref,pin),pos],width);via('GND',pos)
# Twelve identical clusters; preserve the 5mm copper mounting-hole annuli.
for n in range(1,13):
 f=fps[f'VSUPPLY_{n}'];x,y=pt(f.GetReference(),5)
 U=f'U{n+5}';J=f'J{n+6}';RI=f'R{26+2*n}';RS=f'R{27+2*n}';CA=f'C{20+2*n}';CB=f'C{21+2*n}';OUT=f'VSLOT_{n}';SEL=f'SEL_{n}'
 place(U,x+14,y-6.5,180);place(J,x,y-3.8,90)
 place(RI,x+18,y-8.6);place(RS,x+19,y-3)
 place(CA,x+13.5,y-1.8,-90);place(CB,x+16,y-1.8,-90)
 fps[J].Reference().SetPosition(V((x+1,y-6.1)))
 fps[RI].Reference().SetPosition(V((x+18,y-11)))
 fps[RS].Reference().SetPosition(V((x+19,y-1.5)))
 fps[CA].Reference().SetPosition(V((x+13.5,y+1.5)))
 fps[CB].Reference().SetPosition(V((x+16,y+1.5)))
 wire(OUT,[pt(f.GetReference(),5),pt(f.GetReference(),1)],1.0)
 o=(x+9.8,y-6.175);wire(OUT,[pt(U,7),o],.25);via(OUT,o)
 wire(OUT,[o,(x+9.8,y-.36),pt(f.GetReference(),1)],1.0,p.B_Cu)
 for cap in [CA,CB]:
  a=pt(cap,1);v=(a[0],y-2.9);wire(OUT,[a,v],.4);via(OUT,v)
  wire(OUT,[v,(x+9.8,y-2.9)],.8,p.B_Cu)
  ground(cap,2,(a[0],y+.3),.4)
 # Power-pad escapes are the only fine-pitch sections.
 v=(x+12,y-4.7);wire('5V_SYS',[pt(U,8),v],.25);via('5V_SYS',v)
 wire('5V_SYS',[v,(x+12,y-16.8)],.8,p.B_Cu);via('5V_SYS',(x+12,y-16.8))
 a=pt(U,6);v=(x+9.8,y-7.425)
 wire('+3.3V',[a,(x+10.4,a[1]),v],.25);via('+3.3V',v)
 wire('+3.3V',[v,(x+9.8,y-10.16)],.8,p.B_Cu);via('+3.3V',(x+9.8,y-10.16))
 wire('+3.3V',[pt(J,1),(x,y-10.16)],.25,p.B_Cu);via('+3.3V',(x,y-10.16))
 # Separate logic leaf from header to D1 / 100k. Never carries slot current.
 wire(SEL,[pt(U,2),(x+18.49,y-6.175),pt(RS,1)],.25)
 wire(SEL,[pt(J,2),(x+18.49,y-3.8)],.25)
 ground(RS,2,(x+20.3,y-3),.25)
 wire(f'Net-({U}-ILIM)',[pt(U,4),(x+17.49,y-8.1025),pt(RI,1)],.25)
 ground(RI,2,(x+19.5,y-8.6),.25)
 ground(U,5,(x+10.9,y-9),.25)
 a=pt(U,3);wire('GND',[a,(x+17.9,a[1]),(x+18.3,y-7.225)],.25);via('GND',(x+18.3,y-7.225))
 ground(U,1,(x+16.8625,y-4.65),.25)
# 0.8mm 3.3V row buses pass between the fixed mounting-hole annuli.
for y in [38.1,106.68]:
 wire('+3.3V',[(55.88,y-10.16),(228 if y<50 else 223.16,y-10.16)],.8)
 wire('5V_SYS',[(58.5,y-16.8),(226,y-16.8)],1.2)
x,y=pt('VSUPPLY_1',5)
wire('5V_SYS',[(x+12,y-16.8),(x+12,21.3)],.8)
wire('+3.3V',[(x+9.8,y-10.16),(x+9.8,27.94)],.8)
wire('+3.3V',[(x,y-10.16),(x,27.94)],.25)
wire('+3.3V',[(55.88,27.94),(55.88,43.18)],1.0)
wire('+3.3V',[(55.88,101.6),(55.88,111.76)],.5)
# Disconnect old slot-6 tap from the audio feed without losing the audio rail.
for t in list(b.GetTracks()):
 if t.GetNetname()=='+3.3V' and t.GetClass()=='PCB_TRACK' and xy(t.GetStart())==(223.52,38.1):
  b.Remove(t)
wire('+3.3V',[(223.52,43.815),(234,43.815),(236,41.815),(236,27.94),(228,27.94)],.5,p.B_Cu);via('+3.3V',(228,27.94))
for t in list(b.GetTracks()):
 if t.GetNetname()=='+3.3V' and t.GetClass()=='PCB_TRACK' and xy(t.GetEnd())==(223.52,38.1):b.Remove(t)
wire('+3.3V',[(244.729,38.1),(236,38.1)],.5,p.B_Cu)
# Keep audio components fixed; detour the two original F.Cu output runs
# around the right side of channel 12's new placement (no layer changes).
for t in list(b.GetTracks()):
 if t.GetClass()=='PCB_TRACK' and t.GetNetname() in ['Net-(C10-Pad1)','Net-(C11-Pad1)']:
  a,c=xy(t.GetStart()),xy(t.GetEnd())
  if (min(a[1],c[1])<102 and max(a[1],c[1])>100):b.Remove(t)
wire('Net-(C10-Pad1)',[(237.49,95.615),(235.5,97.605),(235.5,108.5),(232.0125,111.9875),(232.0125,116.84)],.3)
wire('Net-(C11-Pad1)',[(238.76,92.71),(234.7,96.77),(234.7,107.5),(231.0875,111.1125),(231.0875,137.5175)],.3)
# Input protection cluster in the free area beside J5.
place('F1',44.5,47,180);place('F2',51.2,43.8);place('D2',51.2,49.8)
place('D3',51.2,29);place('C46',51.2,35.8,180);place('C47',52.0,39.8,180)
# USB VBUS contact pair -> fuse; contact fanout stays outside adjacent GND pads.
wire('VBUS_IN',[pt('J5','A9'),(39.8,49.44),(41.2,48.04),(41.2,47),pt('F1',2)],.5)
wire('VBUS_IN',[pt('J5','B9'),(39.8,44.54),(41.2,45.94),(41.2,47)],.5)
wire('VBUS_IN',[(41.2,47),pt('F1',2)],1.2)
# Other USB ground contact is connected, not left floating as on the old PCB.
ground('J5','B12',(39.9,43.3),.3)
wire('VBUS_PROT',[pt('F1',1),(47.6,47),(47.6,43.8),pt('F2',1)],1.2)
wire('VBUS_PROT',[(47.6,47),(47.6,49.8),pt('D2',1)],1.2)
wire('VBUS_PROT',[(47.6,49.8),(47.6,53.718),pt('C17',1)],1.0)
wire('VBUS_PROT',[(47.6,43.8),(47.6,40),(46,38.4),(42.175,38.4),pt('D1',2)],.3)
# TVS cathodes on rails, anodes with parallel ground vias.
for ref in ['D2','D3']:
 a=pt(ref,2)
 for dy in [-.7,.7]:ground(ref,2,(a[0]+1.5,a[1]+dy),.8)
# Branch 5V: 1.2 mm trunk, paired 0.4 mm drilled vias at layer changes.
a=pt('F2',2)
for dx in [.3,1.3]:
 v=(a[0]+dx,a[1]);wire('5V_SYS',[a,v],1.0);via('5V_SYS',v,1,.5)
wire('5V_SYS',[(a[0]+1.3,a[1]),(58.5,43.8),(58.5,21.3)],1.2,p.B_Cu)
wire('5V_SYS',[(58.5,43.8),(58.5,89.88)],1.2,p.B_Cu)
for y in [21.3,89.88]:
 for dx in [0,1.2]:
  via('5V_SYS',(58.5+dx,y),1,.5);wire('5V_SYS',[(58.5,y),(58.5+dx,y)],1.2,p.B_Cu)
wire('5V_SYS',[pt('D3',1),(47.9,29),(47.9,21.3),(58.5,21.3)],1.2)
for ref,pos in [('C46',(53.8,35.8)),('C47',(53.5,39.8))]:
 wire('5V_SYS',[pt(ref,1),pos],.8 if ref=='C46' else .4);via('5V_SYS',pos)
 wire('5V_SYS',[pos,(58.5,pos[1])],1.2,p.B_Cu)
ground('C46',2,(49.725,33.6),.8);ground('C47',2,(50.5,39.8),.4)
# GND long rails are retained except the vertical right-edge links now
# superseded by the continuous back plane; fixed sockets are untouched.
for t in list(b.GetTracks()):
 if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='GND':
  a,c=xy(t.GetStart()),xy(t.GetEnd())
  if a[0]==c[0] and 226<a[0]<231 and abs(a[1]-c[1])>30:b.Remove(t)
# Add a coherent board-wide bottom GND plane; retain the existing two local pours.
z=p.ZONE(b);z.SetAssignedPriority(2);z.SetLayer(p.B_Cu);z.SetNet(nets['GND']);z.SetLocalClearance(M(.25));z.SetMinThickness(M(.2));z.SetThermalReliefGap(M(.25));z.SetThermalReliefSpokeWidth(M(.4));z.SetPadConnection(p.ZONE_CONNECTION_THERMAL)
z.Outline().NewOutline()
for a in [(31.1,18.4),(253.4,18.4),(253.4,177.2),(31.1,177.2)]:z.Outline().Append(int(M(a[0])),int(M(a[1])))
b.Add(z)
# Remove obsolete stubs and a legacy via with no layer transition.
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in ['61c1c235-bd5a-46b9-83d0-c98ae758f681','311756cb-8423-415b-a62c-224b7d4ed5be','bc86eb12-990b-4d6d-a8ac-a5e59a985d4a']:b.Remove(t);continue
 if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='GND':
  a,c=xy(t.GetStart()),xy(t.GetEnd())
  if a in [(226.4,83.82),(227.5,150.325),(225.425,152.4)]:b.Remove(t)
  elif a==(220.98,83.82):t.SetEnd(V((223.52,83.82)))
# Silkscreen cleanup: keep all hardware geometry fixed. The old filled INPUT
# banner obscured its own text; use ordinary readable lettering instead.
for z0 in list(b.Zones()):
 if z0.GetLayerSet().Contains(p.F_SilkS):b.Remove(z0)
for d in b.GetDrawings():
 if d.GetClass()=='PCB_TEXT':
  if d.GetText()=='BASE\n1.2.0':d.SetText('BASE\n1.3.0')
  if d.IsKnockout():d.SetIsKnockout(False)
  if d.GetText()=='-MULT-':d.SetPosition(V((246.5,80.8)))
# Tiny inherited reference labels now meet the 0.8 mm text rule.
for f in fps.values():
 if f.Reference().IsVisible() and p.ToMM(f.Reference().GetTextHeight())<.8:
  f.Reference().SetTextSize(V((.8,.8)))
# Nonessential inside-body artwork over jack/switch pads is retained on Fab.
for ref in ['J1','J2','J4','J6','SW1']:
 f=fps[ref]
 for g in f.GraphicalItems():
  if g.GetLayer()==p.F_SilkS and ((ref!='SW1' and g.GetShape()==p.SHAPE_T_ARC) or ref=='SW1'):
   g.SetLayer(p.F_Fab)
for ref,pos in {'F1':(44.5,44.3),'F2':(51.2,41.1),'D2':(51.2,47.3),'D3':(51.2,26.5),'C47':(49.0,39.8)}.items():fps[ref].Reference().SetPosition(V(pos))
label=p.PCB_TEXT(b);label.SetText('OPEN = 3V3   |   SHUNT = 5V');label.SetPosition(V((136,23.8)));label.SetLayer(p.F_SilkS);label.SetTextSize(V((1.1,1.1)));label.SetTextThickness(M(.17));b.Add(label)
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());b.BuildListOfNets()
used={n.attrib['name'] for n in xml.find('nets')}|{''}
for name,ni in list(nets.items()):
 if name not in used:b.Remove(ni)
p.SaveBoard(str(args.output),b,True)
print('Added',len(newrefs),'footprints; total',len(fps),'tracks',len(b.GetTracks()))
