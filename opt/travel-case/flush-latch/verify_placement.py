#!/usr/bin/env python3
"""Check four proposed slider sites against the ACTUAL pristine material envelope.
No full-case latch geometry, repair, or printable export is produced.
"""
import json
from pathlib import Path
import FreeCAD as A
import Part
import concept_features as F
R=Path(__file__).resolve().parent
p=json.loads((R/'concept-parameters.json').read_text());raw={}
for n in ('bottom','top'):
 s=Part.Shape();s.read(str(R/'.cache'/f'release-{n}.brep'));raw[n]=s
# Pristine local reference windows; far from defective central engraving.
base=raw['top'].common(F.box(33,77,0,14,8,25));base.translate(A.Vector(-47,0,0))
slide=F.slide(p,base);rows=[]
for sx in (1,-1):
 for sy in (1,-1):
  tx=47 if sx==1 else p['CaseWidth']-47;ty=0 if sy==1 else p['CaseDepth']
  M=A.Matrix(sx,0,0,tx, 0,sy,0,ty, 0,0,1,0, 0,0,0,1)
  corners=[(sx*u+tx,sy*y+ty) for u in (-14,30) for y in (0,14)]
  xs=[a for a,b in corners];ys=[b for a,b in corners]
  region=F.box(min(xs),max(xs),min(ys),max(ys),8,25)
  ref=raw['top'].common(region).fuse(raw['bottom'].common(region)).removeSplitter()
  outside=[]
  for travel in (0,4,8):
   q=slide.copy();q.translate(A.Vector(travel,0,0));q=q.transformGeometry(M)
   outside.append({'stroke_mm':travel,'outside_pristine_closed_material_mm3':q.cut(ref).Volume,'valid':q.isValid()})
  rows.append({'side':'front' if sy==1 else 'rear','station_center_X_mm':50 if sx==1 else 193.12,
               'closed_wall_coordinates':'inward Y measured from this side',
               'full_region_bounds_mm':[min(xs),min(ys),8,max(xs),max(ys),25], 'samples':outside})
r={'status':'placement concept; not a full-case preserved-interface validation',
   'original_envelope_mm':[243.12,179.62,77.5],
   'independently_measured_envelope_mm':[raw['bottom'].BoundBox.XLength,raw['bottom'].BoundBox.YLength,raw['top'].BoundBox.ZMax],
   'placement_samples':rows,'all_inside_original_closed_material':all(x['outside_pristine_closed_material_mm3']<1e-5 and x['valid'] for row in rows for x in row['samples']),
   'protected_interface_reason':'All edits are local to two long-wall bands; no PCB mounting/cutout edits are proposed. Complete difference tests deferred until implementation.',
   'upstream_source':'pristine checkpoint 252bc256b1b926c6568de9b1831dce3bb5817c1f only'}
(R/'reports'/'placement-checks.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
if not r['all_inside_original_closed_material']:raise SystemExit(2)
