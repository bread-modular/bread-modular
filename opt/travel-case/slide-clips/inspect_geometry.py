#!/usr/bin/env python3
"""Focused fresh measurements from raw case_1.0.0 meshes. No failed slots.
Run with FreeCAD AppRun python and usr/lib on PYTHONPATH.
"""
from pathlib import Path
import json, hashlib, time
import FreeCAD as App
import Part, Mesh
R=Path(__file__).resolve().parent
for folder in ('.cache','reports'):(R/folder).mkdir(exist_ok=True)
V=App.Vector
M=App.Matrix(1,0,0,-20.68,0,0,-1,-7.98,0,1,0,15,0,0,0,1)

def bounds(s):
 b=s.BoundBox
 return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def intervals(s,a,b,axis):
 q=s.common(Part.makeLine(V(*a),V(*b)))
 return sorted([[round(getattr(e.BoundBox,axis+'Min'),6),round(getattr(e.BoundBox,axis+'Max'),6)] for e in q.Edges])

r={'scope':'phase 1, pristine release only; focused corner/wall/connector approach survey',
   'transform':list(M.A),'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION,'parts':{}}
for name in ('bottom','top'):
 path=R.parent/'original/case_1.0.0'/f'bm_case_{name}_1.0.0.stl'
 m=Mesh.Mesh(str(path));m.transform(M)
 t=time.monotonic();s=Part.Shape();s.makeShapeFromMesh(m.Topology,0.00001)
 s=Part.makeSolid(s).removeSplitter()
 assert s.isValid() and len(s.Solids)==1
 s.exportBrep(str(R/'.cache'/f'release-{name}.brep'))
 m.write(str(R/'.cache'/f'release-{name}.stl'))
 row={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bounds_mm':bounds(s),'volume_mm3':s.Volume,
      'solid':s.isValid(),'solids':len(s.Solids),'conversion_seconds':time.monotonic()-t,'front_vertical':{},'rear_vertical':{},'short_edge_horizontal':{}}
 for x in (22,28,32,38,44,199.12,205.12,211.12,217.12,223.12):
  row['front_vertical'][str(x)]={str(y):intervals(s,(x,y,-1),(x,y,32),'Z') for y in (0.1,0.5,1,2,3,4,5,6,7,8,9,10,12,14.1)}
  row['rear_vertical'][str(x)]={str(y):intervals(s,(x,179.62-y,-1),(x,179.62-y,32),'Z') for y in (0.5,2,5,8,12)}
 for y in (10,20,30,40,50,65,80,89.81,100,115,130,145,159.62,169.62):
  row['short_edge_horizontal'][str(y)]={str(z):intervals(s,(-1,y,z),(244.2,y,z),'X') for z in (2,8.1,12,14.5,15.5,17,18,20)}
 # Actual shoulder contour and base outer/bottom profile through a candidate site.
 plane=Part.makePlane(25,35,V(32,-5,-3),V(1,0,0),V(0,1,0))
 row['candidate_section_edges']=[[[v.Point.x,v.Point.y,v.Point.z] for v in e.Vertexes] for e in s.section(plane).Edges]
 r['parts'][name]=row
 print(name,'bounds',row['bounds_mm'],'vertical x32',row['front_vertical']['32'],flush=True)
 print(name,'right edge Z12',[(y,zs['12']) for y,zs in row['short_edge_horizontal'].items()],flush=True)
(R/'reports/pristine-measurements.json').write_text(json.dumps(r,indent=2)+'\n')
