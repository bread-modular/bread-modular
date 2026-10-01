#!/usr/bin/python3
"""One-shot 1.3.12 -> 1.3.13 local edit. Only three supply caps + J5 XY metadata.

Requires exact imported PCB/schematic hashes; never operates on 261. Preserves
all existing pads, anchors and routing. Refill/save and real DRC/parity are
mandatory afterwards; this editing script is not validation or bench proof.
"""
import hashlib
from pathlib import Path
import re
import uuid
import pcbnew as p
from build_slot_template import split_top

BASE = Path(__file__).resolve().parents[1]
PCB = BASE/'base.kicad_pcb'; SCH = BASE/'base.kicad_sch'
assert hashlib.sha256(PCB.read_bytes()).hexdigest() == '56d67e8c1b57de40f1e740f89ac97465bc2076fa609e08c6769f41e82780999b'
assert hashlib.sha256(SCH.read_bytes()).hexdigest() == 'ee92e702490409808f284c5113125f6b25afa314cb45e66cdcaa12a46c232e68'

def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'bread-modular/base/1.3.13/'+name))

def field(name, value):
    return f'\t\t(property "{name}" "{value}" (at 226.06 66.04 0)\n\t\t\t(hide yes) (effects (font (size 1.27 1.27))))\n'

text = SCH.read_text()
blocks = [text[a:z] for a,z in split_top(text)]
cap = next(q for q in blocks if q.startswith('(symbol') and '(property "Reference" "C15"' in q)
j5 = next(q for q in blocks if q.startswith('(symbol') and '(property "Reference" "J5"' in q)
fields = {'JLCPCB Position Offset X': '3.675', 'JLCPCB Position Offset Y': '0'}
new_j5 = j5.replace('\t\t(instances', ''.join(field(k,v) for k,v in fields.items())+'\t\t(instances')
text = text.replace(j5, new_j5, 1)
# Separate labeled branches beside each existing audio power unit. Global labels
# at capacitor pins use the already-global supply names; no power symbol/flag
# or existing wire, unit, label or pin is changed.
new = []
for ref,x,y,target in [('C50',553.72,144.78,'U2'),('C51',553.72,194.31,'U3'),('C52',553.72,246.38,'U4')]:
    assert f'"{ref}"' not in text
    c = cap.replace('"C15"',f'"{ref}"')
    c = re.sub(r'\(uuid "([^"]+)"\)',lambda m:f'(uuid "{uid(ref+"/"+m[1])}")',c)
    c = re.sub(r'\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)',
               lambda m:f'(at {float(m[1])+x-549.91:.4f} {float(m[2])+y-306.07:.4f} {m[3]})',c)
    new.append('\t'+c)
    # Device:C at 90 degrees: pin 1 left, pin 2 right, +/-3.81 mm.
    for pin,net,px,angle in [('1','GND',x-3.81,0),('2','+3.3V',x+3.81,180)]:
        new.append(f'\t(global_label "{net}" (shape input) (at {px:.4f} {y:.4f} {angle})\n\t\t(effects (font (size 1.27 1.27)) (justify left bottom))\n\t\t(uuid "{uid(ref+"/label/"+pin)}"))')
    new.append(f'\t(text "{ref}: {target} pin 8 supply bypass, 100 nF" (at {x+1:.4f} {y+7.62:.4f} 0)\n\t\t(effects (font (size 1.27 1.27)) (justify left))\n\t\t(uuid "{uid(ref+"/note")}"))')
text = text.rstrip()[:-1]+'\n'+'\n'.join(new)+'\n)\n'
SCH.write_text(text)

b = p.LoadBoard(str(PCB)); fps = {f.GetReference():f for f in b.GetFootprints()}
M = p.FromMM; V = lambda q: p.VECTOR2I(M(q[0]),M(q[1]))
nets = {str(k):v for k,v in b.GetNetsByName().items()}
def identify(q,name): q.SetUuid(p.KIID(uid(name)))
def pad(ref,num): return next(q for q in fps[ref].Pads() if q.GetNumber()==str(num))
def xy(q): return (p.ToMM(q.x),p.ToMM(q.y))
def wire(net,points,name):
    for i,(a,z) in enumerate(zip(points,points[1:])):
        t=p.PCB_TRACK(b); t.SetStart(V(a)); t.SetEnd(V(z)); t.SetWidth(M(.3)); t.SetLayer(p.F_Cu); t.SetNet(nets[net]); identify(t,name+'/'+str(i)); b.Add(t)
def via(net,pos,name):
    t=p.PCB_VIA(b);t.SetPosition(V(pos));t.SetWidth(M(.7));t.SetDrill(M(.4));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(nets[net]);identify(t,name);b.Add(t)
for ref,pos,angle,target,gnd in [
    ('C50',(244.65,83.7),180,'U2',(245.13,83.3)),
    ('C51',(245.60,93.65),0,'U3',(244.4,93.65)),
    ('C52',(247.65,51.4),180,'U4',(248.13,50.6)),
]:
    f=p.FOOTPRINT(fps['C15']); f.SetReference(ref); identify(f,ref)
    for i,q in enumerate(f.Pads()): identify(q,ref+'/pad/'+str(i))
    for i,q in enumerate(f.GraphicalItems()): identify(q,ref+'/graphic/'+str(i))
    for i,q in enumerate(f.GetFields()): identify(q,ref+'/field/'+str(i))
    # Match the new symbol instance UUID, not the footprint UUID.
    symbol_uuid=re.search(r'\(uuid "([^"]+)"\)', next(q for q in new if q.startswith('\t(symbol') and f'"{ref}"' in q))[1]
    f.SetPath(p.KIID_PATH('/'+symbol_uuid))
    f.SetOrientationDegrees(angle);f.SetPosition(V(pos))
    for q in f.Pads(): q.SetNet(nets['GND' if q.GetNumber()=='1' else '+3.3V'])
    f.Reference().SetTextSize(V((.8,.8))); f.Reference().SetTextThickness(M(.1)); f.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
    f.Reference().SetPosition(V((250.3,83.0) if ref=='C50' else (pos[0],pos[1]-1.1)));f.Reference().SetVisible(True)
    b.Add(f);fps[ref]=f
    wire('+3.3V',[xy(pad(target,8).GetPosition()),xy(pad(ref,2).GetPosition())],ref+'/supply')
    wire('GND',[xy(pad(ref,1).GetPosition()),gnd],ref+'/return');via('GND',gnd,ref+'/GND-via')
# Label-only shift to keep existing U2 silk off the new C50 mask opening.
fps['U2'].Reference().SetPosition(V((242.45,84.345)))
for key,value in fields.items():
    fps['J5'].SetField(key,value);fps['J5'].GetField(key).SetVisible(False)
# Board-frame nominal shell rectangle, from HRO C165948 drawing, no pads changed.
for i,(a,z) in enumerate(zip([(30.84,42.52),(38.19,42.52),(38.19,51.46),(30.84,51.46)],[(38.19,42.52),(38.19,51.46),(30.84,51.46),(30.84,42.52)])):
    q=p.PCB_SHAPE(fps['J5']);q.SetShape(p.SHAPE_T_SEGMENT);q.SetStart(V(a));q.SetEnd(V(z));q.SetLayer(p.F_Fab);q.SetWidth(M(.1));identify(q,'J5/body/'+str(i));fps['J5'].Add(q)
for name,pos,size in [('J23 LINE MONO',(231,70.0),.8),('OPEN=STEREO',(231,71.4),.8)]:
    t=p.PCB_TEXT(b);t.SetText(name);t.SetPosition(V(pos));t.SetLayer(p.F_SilkS);t.SetTextSize(V((size,size)));t.SetTextThickness(M(.10));identify(t,'J23/'+name);b.Add(t)
for q in b.GetDrawings():
    if q.GetClass()=='PCB_TEXT' and '1.3.12' in q.GetText(): q.SetText(q.GetText().replace('1.3.12','1.3.13'))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(PCB),b,True)
print('Applied bounded sources; must run saved-board DRC/parity/ERC and delta proof.')
