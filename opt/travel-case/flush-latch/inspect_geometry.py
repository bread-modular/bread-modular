#!/usr/bin/env python3
"""Independent concept-phase measurements of the untouched case_1.0.0 release.
Run only with the installed FreeCAD AppRun Python + usr/lib. No rejected geometry.
Coordinates in mm: (X,Y,Z) = (release X-20.68, -release Z-7.98, release Y+15).
"""
import hashlib
import json
from pathlib import Path
import time
import FreeCAD as App
import Part
import Mesh

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'original' / 'case_1.0.0'
CACHE = ROOT / '.cache'
REPORT = ROOT / 'reports'
CACHE.mkdir(exist_ok=True)
REPORT.mkdir(exist_ok=True)
V = App.Vector
M = App.Matrix(1,0,0,-20.68, 0,0,-1,-7.98, 0,1,0,15, 0,0,0,1)

def bounds(b):
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def intervals(s, x, z, direction='y'):
    a,b=(V(x,-1,z),V(x,180.7,z)) if direction=='y' else (V(-1,x,z),V(244.2,x,z))
    q=s.common(Part.makeLine(a,b))
    axis='Y' if direction=='y' else 'X'
    return sorted([[round(getattr(e.BoundBox,axis+'Min'),5),round(getattr(e.BoundBox,axis+'Max'),5)] for e in q.Edges])

report={'scope':'concept measurements; pristine release meshes, not recovered Fusion history',
        'coordinate_transform':list(M.A), 'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION,'parts':{}}
for name in ('bottom','top'):
    path=SOURCE/f'bm_case_{name}_1.0.0.stl'
    m=Mesh.Mesh(str(path));m.transform(M)
    t=time.monotonic()
    sewn=Part.Shape();sewn.makeShapeFromMesh(m.Topology,0.00001)
    s=Part.makeSolid(sewn).removeSplitter()
    s.exportBrep(str(CACHE/f'release-{name}.brep'))
    m.write(str(CACHE/f'release-{name}.stl'))
    row={'source':str(path.relative_to(ROOT.parent)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'mesh_bounds_mm':bounds(m.BoundBox),'brep_bounds_mm':bounds(s.BoundBox),
         'mesh_facets':m.CountFacets,'mesh_closed':m.isSolid(),'brep_valid':s.isValid(),
         'solids':len(s.Solids),'volume_mm3':s.Volume,'conversion_seconds':time.monotonic()-t,
         'long_wall_y_intervals':{},'short_wall_x_intervals':{}}
    zs=[0.5,7.49,7.99,8.01,9,10,11,12,13,13.3,13.7,14.1,14.5,14.9] if name=='bottom' else [14.1,14.5,14.9,15.01,16,17,18,19,20,21,22,23,24,26,28,30,35,45,60,74.9,75.01,76,77.49]
    for x in [30,50,65,81.04,100,121.56,162.08,193.12,213.12]:
        row['long_wall_y_intervals'][str(x)]={str(z):intervals(s,x,z) for z in zs}
    for y in [40,60,89.81,120,139.62]:
        row['short_wall_x_intervals'][str(y)]={str(z):intervals(s,y,z,'x') for z in zs if z>=8}
    # Signed material sections for accurate cross-section drawings, including skirt.
    for x in [50,121.56,193.12]:
        plane=Part.makePlane(200,90,V(x,-10,-1),V(1,0,0))
        # A line-based material query is authoritative; section edges used only for drawings.
        plane=Part.makePlane(200,90,V(x,-10,-1),V(1,0,0),V(0,1,0))
        sec=s.section(plane)
        row.setdefault('cross_sections',{})[str(x)]=[[[v.Point.x,v.Point.y,v.Point.z] for v in e.Vertexes] for e in sec.Edges]
    report['parts'][name]=row
    print(name, 'bounds', row['mesh_bounds_mm'], 'solid',row['brep_valid'],'conversion',round(row['conversion_seconds'],2),flush=True)
    print('x=50 front material y: ',{z:v[:3] for z,v in row['long_wall_y_intervals']['50'].items()},flush=True)
(REPORT/'original-measurements.json').write_text(json.dumps(report,indent=2)+'\n')
