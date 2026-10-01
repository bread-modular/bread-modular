#!/usr/bin/python3
"""Reproduce BASE 1.3.12 local PCB migration from the base-improvements input.

Requires KiCad system Python. Never changes the schematic/project or the input.
Supply the original b8df0829... board (git show ab9fd44:modules/base/base.kicad_pcb)
and a fresh kicadxml hierarchical netlist. Output is NOT verified by this script:
run the independent release checks including saved-board CLI DRC/parity.
"""
import argparse
import hashlib
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET
import pcbnew as p
import sys
sys.excepthook = sys.__excepthook__

BASE = Path(__file__).resolve().parents[1]
SOURCE_SHA = 'b8df082974c533e45a36d78a7b12d548ffbb5ad383fc22f28c40d850fb490db6'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-board', type=Path, required=True)
parser.add_argument('--netlist', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
a = parser.parse_args()
assert hashlib.sha256(a.source_board.read_bytes()).hexdigest() == SOURCE_SHA, 'Wrong migration input'
assert a.source_board.resolve() != a.output.resolve(), 'Never overwrite the migration input'
# KiCad 10 owns project settings with the loaded board: rebinding SetProject
# after LoadBoard can invalidate its net settings. Load a private same-stem
# project/board copy instead, leaving all source project settings untouched.
import tempfile
import shutil
context = tempfile.TemporaryDirectory(prefix='base-finalize-')
context_path = Path(context.name)
shutil.copyfile(a.source_board, context_path/'base.kicad_pcb')
for name in ['base.kicad_pro', 'base.kicad_dru']:
    shutil.copyfile(BASE/name, context_path/name)
b = p.LoadBoard(str(context_path/'base.kicad_pcb'))
assert b.GetDesignSettings().m_MinClearance == p.FromMM(.2)
M = p.FromMM
V = lambda q: p.VECTOR2I(M(q[0]), M(q[1]))
xy = lambda v: (round(p.ToMM(v.x), 6), round(p.ToMM(v.y), 6))
serial = 0
# Keep detached wrappers alive during the edit. Python 3.14 + this SWIG build
# loses type registrations when an owning removed FOOTPRINT wrapper is collected.
# RemoveNative does not flip ownership; these bounded migration objects are
# retained until process exit rather than letting that wrapper destructor run.
detached = []
def remove(item):
    b.RemoveNative(item)
    detached.append(item)

def identify(item, name):
    item.SetUuid(p.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL, 'bread-modular/base/1.3.12/'+name))))

r = ET.parse(a.netlist).getroot()
cs = {c.attrib['ref']: c for c in r.find('components')
      if c.findtext('footprint') and c.find("property[@name='exclude_from_board']") is None}
pn = {(v.attrib['ref'], v.attrib['pin']): n.attrib['name'] for n in r.find('nets') for v in n
      if v.attrib['ref'] in cs}
fps = {f.GetReference(): f for f in b.GetFootprints()}
nets = {str(k): v for k, v in b.GetNetsByName().items()}
for name in set(pn.values()) - set(nets):
    ni = p.NETINFO_ITEM(b, name); b.Add(ni); nets[name] = ni
# Remove all obsolete parts, never historical gain parts from the authoritative circuit.
for ref in set(fps) - set(cs):
    remove(fps.pop(ref))
# Replace only intentional package changes. SOIC external pad coordinates match
# the old footprint exactly; its fictitious pad 9 and unnumbered paste pads vanish.
for ref, c in cs.items():
    ident = c.findtext('footprint'); lib, item = ident.split(':', 1)
    old = fps.get(ref)
    if old is None or str(old.GetFPID().GetLibNickname())+':'+str(old.GetFPID().GetLibItemName()) != ident:
        f = p.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty', item)
        assert f, ident
        f.SetFPID(p.LIB_ID(lib, item))
        if old:
            f.SetUuid(old.m_Uuid)
            f.SetPosition(old.GetPosition()); f.SetOrientationDegrees(old.GetOrientationDegrees())
            f.Reference().SetPosition(old.Reference().GetPosition())
            for d in f.Pads():
                match = next((q for q in old.Pads() if q.GetNumber() == d.GetNumber()), None)
                if match: d.SetUuid(match.m_Uuid)
            remove(old)
        else:
            identify(f, ref)
            for i, d in enumerate(f.Pads()): identify(d, ref+'/pad/'+d.GetNumber()+'/'+str(i))
        b.Add(f); fps[ref] = f
    f = fps[ref]
    f.SetReference(ref); f.SetValue(c.findtext('value'))
    stamp = c.findtext('tstamps').split()[0]
    f.SetPath(p.KIID_PATH(c.find('sheetpath').attrib['tstamps'].rstrip('/')+'/'+stamp))
    props = {q.attrib['name']: q.attrib.get('value', '') for q in c.findall('property')}
    f.SetDNP('dnp' in props); f.SetExcludedFromBOM('exclude_from_bom' in props)
    f.SetExcludedFromPosFiles(False)
    f.SetSheetname(props.get('Sheetname', '')); f.SetSheetfile(props.get('Sheetfile', ''))
    fields = {q.attrib['name']: q.text or '' for q in c.findall('fields/field')}
    # These are actual symbol instance fields, including ~ placeholders. KiCad 10
    # parity distinguishes '~' from blank, so do not normalize the source metadata.
    fields.update({'Datasheet': c.findtext('datasheet') or fields.get('Datasheet', ''),
                   'Description': fields.get('Description', '')})
    for name, value in fields.items():
        if name in ['Reference', 'Value', 'Footprint']: continue
        f.SetField(name, value)
        f.GetField(name).SetVisible(False)
    for d in f.Pads():
        d.SetNet(nets[pn.get((ref, d.GetNumber()), '')])
    f.Value().SetVisible(False)

def pt(ref, pin):
    return xy(next(q for q in fps[ref].Pads() if q.GetNumber() == str(pin)).GetPosition())

def wire(net, points, width=.25, layer=p.F_Cu):
    global serial
    for start, end in zip(points, points[1:]):
        if V(start) == V(end): continue
        t = p.PCB_TRACK(b); t.SetStart(V(start)); t.SetEnd(V(end))
        t.SetWidth(M(width)); t.SetLayer(layer); t.SetNet(nets[net]); serial += 1
        identify(t, 'track/'+str(serial)); b.Add(t)

def via(net, q, diameter=.8, drill=.4):
    global serial
    t = p.PCB_VIA(b); t.SetPosition(V(q)); t.SetWidth(M(diameter)); t.SetDrill(M(drill))
    t.SetViaType(p.VIATYPE_THROUGH); t.SetLayerPair(p.F_Cu, p.B_Cu); t.SetNet(nets[net]); serial += 1
    identify(t, 'via/'+str(serial)); b.Add(t)

def place(ref, q, angle=0, label=None):
    f = fps[ref]; f.SetOrientationDegrees(angle); f.SetPosition(V(q))
    f.Reference().SetTextSize(V((.8, .8))); f.Reference().SetTextThickness(M(.12))
    f.Reference().SetTextAngle(p.EDA_ANGLE(0, p.DEGREES_T))
    f.Reference().SetPosition(V(label or (q[0], q[1]-2)))
    f.Reference().SetVisible(True)

def ground(ref, pin, q, width=.4):
    wire('GND', [pt(ref, pin), q], width); via('GND', q)

# Rip up only repeated local mux clusters, preserving row buses and mechanical holes.
anchors = {n: pt(f'VSUPPLY_{n}', 5) for n in range(1, 13)}
for t in list(b.GetTracks()):
    start, end = xy(t.GetStart()), xy(t.GetEnd()); net = t.GetNetname()
    if t.GetClass() == 'PCB_VIA' and t.GetDrillValue() > M(1): continue
    local = any(x-.05 <= min(start[0],end[0]) and max(start[0],end[0]) <= x+20.7
                and y-11 <= min(start[1],end[1]) and max(start[1],end[1]) <= y+.8
                for x,y in anchors.values())
    five_drop = net == '5V_SYS' and t.GetClass() == 'PCB_TRACK' and any(
        start[0] == end[0] == round(x+12,6) and min(start[1],end[1]) >= y-17
        and max(start[1],end[1]) <= y-4 for x,y in anchors.values())
    if local or five_drop or (net == '5V_SYS' and t.GetClass() == 'PCB_VIA' and any(abs(start[0]-x-12)<.001 and abs(start[1]-y+16.8)<.001 for x,y in anchors.values())) or net.startswith('SEL_') or net.startswith('VSLOT_') or '-ILIM)' in net:
        remove(t)
# Old feedback gain extensions/jumpers and obsolete normalling copper.
for t in list(b.GetTracks()):
    net = t.GetNetname(); start, end = xy(t.GetStart()), xy(t.GetEnd())
    if net in ['LFB_A','LFB_B','RFB_A','RFB_B','RIN_SEL']:
        remove(t)
    elif net == 'BUFF_IN_L' and min(start[1],end[1]) < 67:
        remove(t)
    elif net in ['IN_L','IN_R']:
        ripup = False
        if net == 'IN_L':
            ripup = (start == (238.76,76.2) or end == (238.76,76.2))
        else:
            ripup = min(start[1],end[1]) < 78 or (start == (241.3,76.2) or end == (241.3,76.2))
        if ripup: remove(t)
        else: t.SetNet(nets[net+'_PROT'])
for t in list(b.GetTracks()):
    if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == 'GND' and t.GetLayer() == p.B_Cu and min(xy(t.GetStart())[0],xy(t.GetEnd())[0])>251 and abs(xy(t.GetStart())[1]-xy(t.GetEnd())[1])>50:
        remove(t)  # superseded by continuous filled B.Cu GND, not a signal trace
# TPS2116 pin map and rail selection: two broad VOUT pins, short escapes,
# 0.8 mm input drops and 1.0 mm socket feed. MODE/header are logic only.
for n, (x,y) in anchors.items():
    u,j,rs,ca,cb = f'U{n+5}',f'J{n+6}',f'R{27+2*n}',f'C{20+2*n}',f'C{21+2*n}'
    out,sel = f'VSLOT_{n}',f'SEL_{n}'
    place(u,(x+14,y-6.5),180,(x+14,y-9.7))
    place(ca,(x+14,y-3.0),0,(x+14,y+.2))
    place(cb,(x+14,y-4.4),0,(x+16.5,y-2.7))
    wire(out,[pt(f'VSUPPLY_{n}',5),pt(f'VSUPPLY_{n}',1)],1.0)
    wire(out,[pt(u,2),pt(u,7)],.25)
    wire(out,[pt(u,7),(x+10,y-6.25),(x+10,y-5.2)],.25); via(out,(x+10,y-5.2))
    wire(out,[(x+10,y-5.2),(x+10,y-.16),pt(f'VSUPPLY_{n}',1)],1.0,p.B_Cu)
    wire(out,[(x+11.5,y-6.25),(x+11.5,y-5.5)],.25)
    wire(out,[(x+11.5,y-5.5),(x+11.5,y-3.0),pt(ca,1)],.5)
    wire(out,[(x+11.5,y-4.4),pt(cb,1)],.5)
    ground(ca,2,(x+15.5,y-3.0)); ground(cb,2,(x+15.5,y-4.4))
    wire('5V_SYS',[pt(u,3),(x+17,y-6.75),(x+17,y-5.85)],.25); via('5V_SYS',(x+17,y-5.85))
    if n in [6,12]:
        bridge_y = 29 if n == 6 else 96.0
        bridge_x = x+17 if n == 6 else 230.0
        bus_y = 21.3 if n == 6 else 89.88
        bridge = [(x+17,y-5.85),(bridge_x,bridge_y)] if n == 6 else [(x+17,y-5.85),(x+17,100.4),(229.0,100.4),(229.0,bridge_y),(bridge_x,bridge_y)]
        wire('5V_SYS',bridge,.8,p.B_Cu); via('5V_SYS',(bridge_x,bridge_y))
        wire('5V_SYS',[(bridge_x,bridge_y),(bridge_x,bus_y),(226,bus_y)],.8)
    else:
        wire('5V_SYS',[(x+17,y-5.85),(x+17,y-16.8)],.8,p.B_Cu); via('5V_SYS',(x+17,y-16.8))
    wire('+3.3V',[pt(u,6),(x+10.5,y-6.75),(x+10,y-7.25)],.25)
    wire('+3.3V',[(x+10,y-7.25),(x+10,y-8.2)],.6); via('+3.3V',(x+10,y-8.2))
    wire('+3.3V',[(x+10,y-8.2),(x+10,y-10.16)],.8,p.B_Cu); via('+3.3V',(x+10,y-10.16))
    wire('VBUS_PROT',[pt(u,5),(x+12.15,y-7.25),(x+12.15,y-8.6)],.25); via('VBUS_PROT',(x+12.15,y-8.6))
    vbus_y = 25.1 if n <= 6 else 87.5
    wire('VBUS_PROT',[(x+12.15,y-8.6),(x+12.15,vbus_y)],.25,p.B_Cu); via('VBUS_PROT',(x+12.15,vbus_y))
    wire('VBUS_PROT',[pt(j,1),(x,vbus_y)],.25,p.B_Cu); via('VBUS_PROT',(x,vbus_y))
    wire(sel,[pt(j,2),(x+4,y-1.8),(x+18.49,y-1.8),pt(rs,1)],.25)
    wire(sel,[pt(u,4),(x+18.49,y-7.25),pt(rs,1)],.25)
    ground(rs,2,(x+20.3,y-3),.25)
    ground(u,1,(x+16.3,y-5.0),.25)
    # Slot 1's legacy supply anchor is 0.10 mm below the common bus registration.
    if n == 1:
        wire('+3.3V',[(x+10,y-10.16),(x+10,27.94)],.8)
        wire('5V_SYS',[(x+17,y-16.8),(x+17,21.3)],.8)
for y in [25.1,87.5]:
    wire('VBUS_PROT',[(57.3,y),(226,y)],.4); via('VBUS_PROT',(57.3,y))
wire('VBUS_PROT',[(57.3,25.1),(57.3,33.5)],.4,p.B_Cu)
via('VBUS_PROT',(57.3,33.5))
wire('VBUS_PROT',[(57.3,33.5),(57.3,45.8)],.4)
via('VBUS_PROT',(57.3,45.8))
wire('VBUS_PROT',[(57.3,45.8),(57.3,87.5)],.4,p.B_Cu)
wire('VBUS_PROT',[(47.6,47),(57.3,47)],.4,p.B_Cu); via('VBUS_PROT',(47.6,47))
via('+3.3V',(228,27.94))
wire('+3.3V',[(223.16,96.52),(223.36,96.52)],.8)
via('+3.3V',(243.459,63.754))
# Move only the reference-voltage distribution trace, not R24/R5 or hardware,
# to make room for the protected left-input path on F.Cu over the GND plane.
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in ['3ac3bb7c-397c-4f7f-b111-4eae72e4670e','5edd4190-47d9-4ee2-a5ce-b49588c8357b','da8a27f2-3efe-4e3d-bd0c-607a40d0d648']:
        remove(t)
wire('+2.5V',[(240.411,64.643),(235.4,64.643),(235.4,75.0),(235.0,75.0)],.3)

# Restore ONLY the approved fixed line-out feedback network.
wire('LFB_A',[pt('U4',2),(240.738,54.09),(238.44,56.388),(238.44,61.153),pt('R17',1)])
wire('RFB_A',[pt('U4',6),(248.081,55.36),(248.982,56.261),(248.982,61.153),pt('R16',1)])
place('U18',(249.0,68.2),180,(249.0,63.5))
place('C48',(248.7,65.0),0,(250.8,64.8))
place('J23',(248.0,72.4),90,(252.8,72.3))
place('R55',(240.5,69.0),180,(240.0,67.5))
place('R57',(246.38,79.4),0,(247.6,81.0))
place('R58',(238.76,72.2),90,(236.7,72.2))
place('R59',(241.3,72.2),90,(242.8,74.0))
wire('IN_L',[pt('INPUT1',1),pt('R58',1)])
wire('IN_L_PROT',[pt('R58',2),(238.76,68.832)])
wire('IN_L_PROT',[pt('R58',2),(236.22,71.69),(236.22,78.74)])
wire('IN_R',[pt('INPUT1',2),pt('R59',1)])
wire('IN_R_PROT',[pt('R59',2),(239.95,73.04),(239.95,81.2),(241.3,82.55)])
wire('IN_R_PROT',[pt('R59',2),(245.5,71.69),(245.5,68.7),pt('U18',9)])
wire('Net-(INPUT1-Pin_3)',[pt('INPUT1',4),(245.87,76.71),pt('R57',1)],.4)
ground('R57',2,(248.4,79.4))
wire('BUFF_IN_L',[pt('U18',2),(252.9,68.7),(252.9,84.0)])
wire('RIN_SEL',[pt('U18',10),(247.8,69.2),(247.8,70.3)])
via('RIN_SEL',(247.8,70.3))
wire('RIN_SEL',[(247.8,70.3),(249.2,70.3),(249.2,62.5),(250.317,62.5)],.25,p.B_Cu)
via('RIN_SEL',(250.317,62.5)); wire('RIN_SEL',[(250.317,62.5),pt('R16',2)])
wire('MONO_SEL',[pt('U18',1),(250,69.2),(250,70.2)])
via('MONO_SEL',(250,70.2))
wire('MONO_SEL',[pt('U18',5),(252.3,67.2),(252.3,66.0)])
via('MONO_SEL',(252.3,66.0))
wire('MONO_SEL',[(252.3,66.0),(252.3,70.2),(250,70.2)],.25,p.B_Cu)
wire('MONO_SEL',[pt('R55',1),(241.01,69.0),(244.7,69.0)])
via('MONO_SEL',(244.7,69.0))
wire('MONO_SEL',[(244.7,69.0),(246,69.0),(246,74.7),(251.4,74.7),(251.4,73.0),pt('J23',2),(250,70.2)],.25,p.B_Cu)
wire('GND',[pt('R55',2),(239.99,70.49),(240.5,71.0)])
via('GND',(240.5,71.0))
wire('GND',[pt('U18',3),(250,68.2),(250,68.0)])
wire('GND',[pt('U18',4),(250,67.7),(250,68.0)])
via('GND',(250,68.0))
wire('GND',[pt('U18',6),(245.6,67.2),(245.6,66.8)])
wire('GND',[pt('U18',7),(245.6,67.7),(245.6,67.2)])
via('GND',(245.6,66.8))
wire('+3.3V',[pt('U18',8),(248.2,68.2),(248.2,68.35)])
via('+3.3V',(248.2,68.35))
wire('+3.3V',[pt('C48',1),(248.3,65.9)],.4); via('+3.3V',(248.3,65.9))
wire('+3.3V',[(248.3,65.9),(248.2,68.35)],.4,p.B_Cu)
wire('+3.3V',[(243.459,63.754),(244.5,62.8),(248.22,62.8),pt('C48',1)],.4)
wire('+3.3V',[pt('J23',1),(247,72),(247,68.35),(248.2,68.35)],.25,p.B_Cu)
ground('C48',2,(250.1,65.0))
wire('GND',[(250.1,65),(250,65.1),(250,68)])
wire('GND',[(250,67.7),(248.8,67.7),(248.8,67.2),pt('U18',6)])
# Manufacturing datum: lower left, Cartesian CPL coordinates upward into board.
b.GetDesignSettings().SetAuxOrigin(V((30.48,177.8)))
for d in b.GetDrawings():
    if d.GetClass() != 'PCB_TEXT': continue
    if d.GetText().startswith('BASE\n'): d.SetText('BASE\n1.3.12')
    elif d.GetText().strip() == 'INPUT':
        d.SetText('INPUT'); d.SetPosition(V((239.8,81.2))); d.SetTextSize(V((.8,.8))); d.SetTextThickness(M(.12))
    elif d.GetText() == '-MULT-':
        d.SetText('RETURN 100R'); d.SetPosition(V((244,83.0))); d.SetTextSize(V((.8,.8))); d.SetTextThickness(M(.12))
# Remove truly unused net records only after every pad/track/zone was remapped.
used = set(pn.values()) | {''}
for t in b.GetTracks(): assert t.GetNetname() in used, ('stale copper net',t.GetNetname())
for name, ni in list(nets.items()):
    if name not in used: remove(ni)
b.BuildConnectivity(); p.ZONE_FILLER(b).Fill(b.Zones()); b.BuildListOfNets()
p.SaveBoard(str(a.output),b,True)
print(f'Wrote {a.output}: {len(fps)} physical footprints, {len(list(b.GetTracks()))} tracks/vias. DRC REQUIRED.')
