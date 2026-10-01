#!/usr/bin/env python3
"""Build editable full assembly/coupon and bed-oriented STL exports. Run validate.py.
No GUI is required; FreeCAD AppRun python + usr/lib is the established runtime.
"""
import hashlib
import json
from pathlib import Path
import time
import FreeCAD as App
import Part
import Mesh
import MeshPart
import latch_features as F
R=Path(__file__).resolve().parent
for folder in ('.cache','cad','stl','reports','previews'):(R/folder).mkdir(exist_ok=True)
p=json.loads((R/'parameters.json').read_text());F.check(p)
source={}
for name in ('Bottom','Top'):
    cache=R/'.cache'/('release-'+name.lower()+'.brep')
    if not cache.exists():
        m=Mesh.Mesh(str(R.parent/'original/case_1.0.0'/f'bm_case_{name.lower()}_1.0.0.stl'))
        m.transform(App.Matrix(1,0,0,-20.68,0,0,-1,-7.98,0,1,0,15,0,0,0,1))
        s=Part.Shape();s.makeShapeFromMesh(m.Topology,.00001)
        s=Part.makeSolid(s).removeSplitter();s.exportBrep(str(cache))
    s=Part.Shape();s.read(str(cache));source[name]=s

d=App.newDocument('BreadModularFlushLatch')
pa=d.addObject('App::FeaturePython','Parameters')
pa.Label='EDITABLE closure / original envelope fixed'
for k,v in p.items():
    pa.addProperty('App::PropertyDistance' if v<0 else 'App::PropertyLength',k,'Dimensions')
    setattr(pa,k,v)
    if k not in ('HookThickness','BeamThickness','BeamHeight','PaddleRecess','HookRootRadius','BeamRootRadius','MeshLinearDeflection','MeshAngularDeflection'):pa.setEditorMode(k,1)
pa.addProperty('App::PropertyString','PhysicalStatus','Evidence').PhysicalStatus='Physical fit/strength/fatigue untested; coupon REQUIRED'
refs={}
for name,s in source.items():
    o=d.addObject('PartDesign::Feature','Release'+name);o.Shape=s
    o.Label='UNTOUCHED faceted release '+name;refs[name]=o


def feature(name,kind,ref=None,index=0,prototype=None):
    o=d.addObject('PartDesign::FeaturePython',name)
    F.LatchFeature(o,kind,pa,ref,index,prototype)
    d.recompute()
    assert not o.Shape.isNull() and o.Shape.isValid(), 'Failed feature '+name
    if kind not in ('BottomTools','TopTools'):assert len(o.Shape.Solids)==1,(name,len(o.Shape.Solids))
    print(name,round(o.Shape.Volume,4),len(o.Shape.Solids),flush=True)
    return o

start=time.monotonic()
rb=feature('RepairedBottom','RepairBottom',refs['Bottom'])
rt=feature('RepairedTop','RepairTop',refs['Top'])
bt=feature('BottomMachining','BottomTools');tt=feature('TopMachining','TopTools')
b=feature('Bottom','Bottom',rb);t=feature('Top','Top',rt)
sp=feature('SliderPrototype','SliderPrototype',refs['Top'])
gp=feature('GatePrototype','GatePrototype')
sliders=[];gates=[]
for i in range(4):
    sliders.append(feature('Slider'+str(i+1),'Slider',index=i,prototype=sp))
    gates.append(feature('Gate'+str(i+1),'Gate',index=i,prototype=gp))
for o in sliders:o.Travel=p['Stroke']
d.recompute()
cb=feature('CouponBottom','CouponBottom',b);ct=feature('CouponTop','CouponTop',t)
visible={'Bottom','Top'}|{o.Name for o in sliders+gates}
colors={'Bottom':(.19,.42,.61),'Top':(.67,.73,.79)}
for o in d.Objects:
    if getattr(o,'ViewObject',None):
        o.ViewObject.Visibility=o.Name in visible
        if hasattr(o.ViewObject,'ShapeColor'):
            o.ViewObject.ShapeColor=colors.get(o.Name,(.98,.48,.07) if o.Name.startswith('Slider') else (.28,.65,.38))
            o.ViewObject.LineColor=(.16,.20,.24)

d.recompute();d.saveAs(str(R/'cad/flush-latch.FCStd'))
report={'build_seconds':time.monotonic()-start,'CAD':'cad/flush-latch.FCStd','exports':{},'status':'Built; final validation REQUIRED'}


def export(name,shape,kind,assembled=False):
    s=shape if assembled else F.bed_shape(shape,kind)
    assert s.isValid() and len(s.Solids)==1, name
    m=MeshPart.meshFromShape(Shape=s,LinearDeflection=p['MeshLinearDeflection'],AngularDeflection=p['MeshAngularDeflection'],Relative=False)
    path=(R/'.cache' if assembled else R/'stl')/(name+'.stl')
    m.write(str(path))
    # Inspect the ACTUAL binary file, not just pre-export CAD or tessellation.
    w=Mesh.Mesh(str(path))
    row={'facets':w.CountFacets,'points':w.CountPoints,'closed':w.isSolid(),
         'nonmanifold':w.hasNonManifolds(),'inconsistent_normals':w.hasNonUniformOrientedFacets(),
         'self_intersections':w.hasSelfIntersections(),'components':w.countComponents(),
         'dimensions_mm':[w.BoundBox.XLength,w.BoundBox.YLength,w.BoundBox.ZLength],
         'minimum_z_mm':w.BoundBox.ZMin,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if not assembled:report['exports'][name]=row
    print('MESH',name,row,flush=True)
    (R/'reports/mesh-export.json').write_text(json.dumps(report,indent=2)+'\n')
    assert row['closed'] and not row['nonmanifold'] and not row['inconsistent_normals'] and not row['self_intersections'] and row['components']==1,'Bad export '+name

for name,o,kind in [('case_bottom',b,'Bottom'),('case_lid',t,'Top'),
                     ('slider_A',sp,'Slider'),('gate_A',gp,'Gate'),
                     ('coupon_bottom',cb,'CouponBottom'),('coupon_lid',ct,'CouponTop')]:
    export(name,o.Shape,kind)
# Hand B is a true mirror; front-left and rear-right use A (rotated in assembly).
mirror=App.Matrix(-1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
for name,o,kind in [('slider_B',sp,'Slider'),('gate_B',gp,'Gate')]:
    export(name,o.Shape.transformGeometry(mirror),kind)
for o in [b,t]+sliders+gates+[cb,ct]:export(o.Name,o.Shape,o.Kind,True)
export('local_slider_locked',F.moved(sp.Shape,x=8),'Slider',True)
export('local_gate',gp.Shape,'Gate',True)
report['status']='All written STL checks PASS; run validate.py for preservation/motion/reopen evidence'
report['build_seconds']=time.monotonic()-start
(R/'reports/mesh-export.json').write_text(json.dumps(report,indent=2)+'\n')
print('BUILD DONE',report['build_seconds'],flush=True)
App.closeDocument(d.Name)
