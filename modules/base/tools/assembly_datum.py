#!/usr/bin/python3
"""Independent BASE J5 shell-centre expectation; not exporter offset arithmetic.

The HRO dimensional evidence and fixed mouth registration are explicit here.
Native fields are checked against that evidence, not used to discover a centre.
Other refs must have zero XY fields until independently documented.
"""
import hashlib
import json
import math
from pathlib import Path
import pcbnew as p
BASE = Path(__file__).resolve().parents[1]

def require(ok, msg):
    if not ok: raise AssertionError('Assembly datum: '+msg)

def finite_field(f, name):
    value = f.GetFieldText(name) if f.HasField(name) else ''
    if not value.strip() or value.strip()=='~': return 0.0
    result=float(value)
    require(math.isfinite(result), f'{f.GetReference()}: non-finite {name}')
    return result

def expected_position(f, origin):
    dx=finite_field(f,'JLCPCB Position Offset X');dy=finite_field(f,'JLCPCB Position Offset Y')
    if f.GetReference()!='J5':
        require(dx==dy==0, f'{f.GetReference()}: undocumented nonzero XY correction')
        return p.ToMM(f.GetPosition().x-origin.x),p.ToMM(origin.y-f.GetPosition().y)
    d=json.loads((BASE/'verification/J5-assembly-datum.json').read_text())
    require(d['MPN']=='TYPE-C-31-M-12' and d['LCSC']=='C165948', 'wrong pinned part')
    require(f.GetFieldText('MPN')==d['MPN'] and f.GetFieldText('LCSC')==d['LCSC'], 'native J5 part changed')
    pdf=BASE/'verification/J5-C165948-datasheet.pdf'
    require(hashlib.sha256(pdf.read_bytes()).hexdigest()==d['datasheet_sha256'], 'changed HRO drawing')
    require(d['body_width_mm']==8.94 and d['body_depth_mm']==7.35, 'HRO nominal dimensions changed')
    require(d['mouth_board_mm']==[30.84,46.99] and d['board_rotation_deg']==270, 'registration changed')
    require([p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)]==d['mouth_board_mm'], 'mouth anchor moved')
    require(f.GetOrientationDegrees()%360==270 and f.GetLayer()==p.F_Cu, 'J5 rotated/flipped')
    half_depth=d['body_depth_mm']/2
    require(abs(dx-half_depth)<1e-12 and dy==0, 'native XY correction disagrees with HRO shell centre')
    require(finite_field(f,'JLCPCB Rotation Offset')==0, 'unproven rotation correction')
    # Check documented body art against dimensional evidence, not pad averages.
    segments=[q for q in f.GraphicalItems() if q.GetClass()=='PCB_SHAPE' and q.GetLayer()==p.F_Fab]
    have={tuple(sorted(((round(p.ToMM(q.GetStart().x),6),round(p.ToMM(q.GetStart().y),6)),
                       (round(p.ToMM(q.GetEnd().x),6),round(p.ToMM(q.GetEnd().y),6))))) for q in segments}
    vertices=[(30.84,42.52),(38.19,42.52),(38.19,51.46),(30.84,51.46)]
    want={tuple(sorted((a,z))) for a,z in zip(vertices,vertices[1:]+vertices[:1])}
    require(have==want, 'F.Fab does not represent documented nominal shell')
    # Independent body midpoint; neither native offsets nor raw anchor accepted.
    centre_x=(30.84+38.19)/2;centre_y=(42.52+51.46)/2
    return centre_x-p.ToMM(origin.x),p.ToMM(origin.y)-centre_y
