#!/usr/bin/env python3
"""Read-only KiCad footprint/courtyard/model inventory; never modify PCBs.
Run with an existing pcbnew-capable system Python. Compact report, no facet dump.
Unknown installed module heights are conservatively reserved up to original roof.
"""
import glob, hashlib, json, os, re
from pathlib import Path
import pcbnew as K
R=Path(__file__).resolve().parent
ROOT=R.parents[2]
SHIFT=(-20.68,-7.98)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mm(v):return K.ToMM(v)
def bounds(bb,shift=(0,0)):
    return [mm(bb.GetX())+shift[0],mm(bb.GetY())+shift[1],mm(bb.GetRight())+shift[0],mm(bb.GetBottom())+shift[1]]
def edge_bounds(b):
    es=[d.GetBoundingBox() for d in b.GetDrawings() if d.GetLayer()==K.Edge_Cuts]
    return [min(mm(e.GetX()) for e in es),min(mm(e.GetY()) for e in es),max(mm(e.GetRight()) for e in es),max(mm(e.GetBottom()) for e in es)]
def models(f,path):
    rows=[]
    for m in f.Models():
        raw=m.m_Filename
        resolved=re.sub(r'\$\{KICAD\d+_3DMODEL_DIR\}', '/usr/share/kicad/3dmodels',raw)
        resolved=resolved.replace('${KIPRJMOD}',str(path.parent))
        if not Path(resolved).is_absolute():resolved=str(path.parent/resolved)
        q=Path(resolved)
        rows.append({'source':raw,'resolved':str(q),'available':q.is_file(),
            'sha256':sha(q) if q.is_file() else None,
            'offset':[m.m_Offset.x,m.m_Offset.y,m.m_Offset.z],
            'scale':[m.m_Scale.x,m.m_Scale.y,m.m_Scale.z],
            'rotation':[m.m_Rotation.x,m.m_Rotation.y,m.m_Rotation.z]})
    return rows
def footprint(f,path,shift=(0,0)):
    items=[g.GetBoundingBox() for g in f.GraphicalItems() if g.GetLayer() in (K.F_CrtYd,K.B_CrtYd)]
    if items:
        bs=[bounds(bb,shift) for bb in items]
        cb=[min(v[0] for v in bs),min(v[1] for v in bs),max(v[2] for v in bs),max(v[3] for v in bs)]
    else:cb=None
    bb=bounds(f.GetBoundingBox(False,False),shift)
    return {'reference':f.GetReference(),'value':f.GetValue(),'footprint':str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),
        'side':K.LayerName(f.GetLayer()),'orientation_degrees':f.GetOrientationDegrees(),
        'position':[mm(f.GetPosition().x)+shift[0],mm(f.GetPosition().y)+shift[1]],
        'body_fab_silk_pad_bounds_mm':bb,'courtyard_bounds_mm':cb,
        'models':models(f,path)}
path=ROOT/'modules/base/base.kicad_pcb';b=K.LoadBoard(str(path))
fps=[footprint(f,path,SHIFT) for f in b.GetFootprints()]
slots=[]
for f in b.GetFootprints():
    if f.GetReference().startswith('VSUPPLY_'):
        ground=b.FindFootprintByReference('GND'+f.GetReference().split('_')[-1])
        slots.append({'reference':f.GetReference(),'supply_pin1_mm':[mm(f.GetPosition().x)+SHIFT[0],mm(f.GetPosition().y)+SHIFT[1]],
            'ground_pin1_mm':[mm(ground.GetPosition().x)+SHIFT[0],mm(ground.GetPosition().y)+SHIFT[1]]})
module_rows=[]
for path in sorted((ROOT/'modules').glob('*/*.kicad_pcb')):
    if path.parent.name=='base':continue
    board=K.LoadBoard(str(path));ed=edge_bounds(board)
    fs=[footprint(f,path) for f in board.GetFootprints()]
    # Reserve board outline plus every non-text footprint body/courtyard;
    # registration uses the common 50.80/96.52 mm 45.72 mm spaced bus pair.
    union=[min([ed[0]]+[f['body_fab_silk_pad_bounds_mm'][0] for f in fs]),
        min([ed[1]]+[f['body_fab_silk_pad_bounds_mm'][1] for f in fs]),
        max([ed[2]]+[f['body_fab_silk_pad_bounds_mm'][2] for f in fs]),
        max([ed[3]]+[f['body_fab_silk_pad_bounds_mm'][3] for f in fs])]
    module_rows.append({'source':str(path.relative_to(ROOT)),'sha256':sha(path),'edge_bounds_with_edge_stroke_mm':ed,
        'populated_XY_bounds_mm':union,'footprints':len(fs),'models_available':sum(m['available'] for f in fs for m in f['models']),
        'bus_pair_Y_source_mm':[50.8,96.52], 'installed_Z':'UNKNOWN: reserved from base top 14.6 through roof 75'})
# All slots/all repo module types: full-width band is deliberately more
# conservative than individually placed module rectangles. Supply-to-supply and
# ground-to-ground establish Y direction; reversing Y would swap power/ground,
# not represent a valid installed module. Flipping the PCB face can reverse X.
front_overhang=max(50.8-m['populated_XY_bounds_mm'][1] for m in module_rows)
rear_overhang=max(m['populated_XY_bounds_mm'][3]-96.52 for m in module_rows)
ylo=min(s['supply_pin1_mm'][1] for s in slots)-front_overhang
yhi=max(s['ground_pin1_mm'][1] for s in slots)+rear_overhang
r={'source':'modules/base/base.kicad_pcb','source_sha256':sha(ROOT/'modules/base/base.kicad_pcb'),
    'thickness_mm_from_PCB':mm(b.GetDesignSettings().GetBoardThickness()),'XY_registration_mm':SHIFT,
    'registered_edge_bounds_with_edge_stroke_mm':[edge_bounds(b)[i]+SHIFT[i%2] for i in range(4)],
    'board_material_screen_mm':[9.8,9.8,13,233.32,169.82,14.6],
    'board_installed_Z':'13..14.6 assumed; actual stand-off stack not measured; do not move this screen',
    'base_footprints':fps,'slots':slots,'modules':module_rows,
    'conservative_module_reservation_mm':[9.8,ylo-.25,14.6,233.32,yhi+.25,75],
    'reservation_method':'All 12 slots, all repo module outline + body/fab/silk/pad/courtyard XY bounds, supply-to-supply and ground-to-ground Y registration; either PCB-face/X direction; full board width; unknown heights reserved to roof; 0.25 XY margin.',
    'limitations':['Actual selected modules, wiring/patch cables, knobs and PCB installed heights not measured.',
        'PCB file is a placed snapshot, not a verified installed assembly; POWER.md says schematic changes may precede PCB updates.',
        'No claim that stock enclosure fits every reserved module; screen tests NEW lock geometry only.',
        'Unmodeled body or wiring extending into lock corridor must stop full-case manufacture.']}
(R/'reports/electronics.json').write_text(json.dumps(r,indent=2)+'\n')
print('Survey:',len(fps),'base footprints,',len(module_rows),'module PCBs,',len(slots),'slots')
print('Full-height conservative populated module band:',r['conservative_module_reservation_mm'])
print('Base model files:',sum(m['available'] for f in fps for m in f['models']),'available /',sum(len(f['models']) for f in fps),'references')
