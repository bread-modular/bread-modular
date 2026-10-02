#!/usr/bin/env python3
"""Build FINAL original-sized shells from raw release (never latch-cut shells).
STLs are exported only AFTER reopen/recompute. run.sh then enforces validate.py.
Any failed build exits nonzero; no stale exports or success manifest can survive.
"""
from pathlib import Path
import hashlib,json,time
import FreeCAD as App
import Part,Mesh,MeshPart
import final_features as F
import clip_features as C
R=Path(__file__).resolve().parent
for n in ('cad','stl','reports','.cache','previews'):(R/n).mkdir(exist_ok=True)
# Never present an old success report as evidence for a failed new build.
for n in ('validation.json','build.json','delivery.json'):(R/'reports'/n).unlink(missing_ok=True)
for path in (R/'stl').glob('*.stl'):path.unlink()
(R/'cad/slide-clips.FCStd').unlink(missing_ok=True)
p=json.loads((R/'parameters.json').read_text());F.check(p)
m=json.loads((R/'reports/pristine-measurements.json').read_text());profile=F.profile_from_measurements(m)
start=time.monotonic();source={};provenance={}
transform=App.Matrix(1,0,0,-20.68,0,0,-1,-7.98,0,1,0,15,0,0,0,1)
for name in ('Bottom','Top'):
    raw=R.parent/'original/case_1.0.0'/f'bm_case_{name.lower()}_1.0.0.stl'
    digest=hashlib.sha256(raw.read_bytes()).hexdigest()
    assert digest==m['parts'][name.lower()]['source_sha256'],'Modified original '+name
    # Raw conversion is just seconds and eliminates any ambiguity about cached cuts.
    mesh=Mesh.Mesh(str(raw));mesh.transform(transform)
    s=Part.Shape();s.makeShapeFromMesh(mesh.Topology,.00001);s=Part.makeSolid(s).removeSplitter()
    assert s.isValid() and len(s.Solids)==1 and s.isClosed()
    assert abs(s.Volume-m['parts'][name.lower()]['volume_mm3'])<1e-5
    source[name]=s
    s.exportBrep(str(R/'.cache'/f'release-{name.lower()}.brep'));mesh.write(str(R/'.cache'/f'release-{name.lower()}.stl'))
    provenance[name]={'raw_stl':str(raw.relative_to(R.parent)),'source_sha256':digest,'volume_mm3':s.Volume,
                      'reference':'fresh raw mesh to faceted BRep; no native Fusion history imported',
                      'cache_sha256':hashlib.sha256((R/'.cache'/f'release-{name.lower()}.brep').read_bytes()).hexdigest()}
    print('RAW',name,s.Volume,flush=True)
d=App.newDocument('BreadModularSlideClips')
pa=d.addObject('App::FeaturePython','Parameters');pa.Label='EDIT fit / jaws / grooves; original envelope fixed'
for k,v in p.items():
    typ='App::PropertyFloat' if 'Slope' in k or 'Deflection' in k else ('App::PropertyDistance' if k=='InterferencePerJaw' else 'App::PropertyLength')
    pa.addProperty(typ,k,'Fit' if k in ('InterferencePerJaw','FitStepPerJaw') else 'Dimensions');setattr(pa,k,v)
    if k in ('CaseWidth','CaseDepth','CaseHeight','SeamZ','StationX','ReleaseRearY','CouponWidth','CouponDepth','CouponHeight'):pa.setEditorMode(k,1)
pa.addProperty('App::PropertyString','PhysicalStatus','Evidence').PhysicalStatus='UNTESTED: friction, force, fit, creep, load, withdrawal, rocking. NOT safety rated.'
pa.addProperty('App::PropertyString','History','Evidence').History='Frozen raw faceted shells + analytical repair/groove/clip/coupon features. Native Fusion history NOT recovered.'
refs={}
for name,s in source.items():
    o=d.addObject('PartDesign::Feature','Release'+name);o.Shape=s;o.Label='UNTOUCHED raw-release faceted '+name;refs[name]=o

def feature(name,kind,ref=None,idx=0,variant=0):
    o=d.addObject('PartDesign::FeaturePython',name)
    F.SlideFeature(o,kind,pa,ref,profile if kind in ('Bottom','Top','BottomTools','TopTools') else None,idx,variant)
    d.recompute();assert not o.Shape.isNull() and o.Shape.isValid() and not any(x in ('Invalid','Error') for x in o.State),name
    print('FEATURE',name,o.Shape.Volume,len(o.Shape.Solids),flush=True);return o
rb=feature('RepairedBottom','RepairBottom',refs['Bottom']);rt=feature('RepairedTop','RepairTop',refs['Top'])
feature('BottomGrooveTools','BottomTools');feature('TopGrooveTools','TopTools')
b=feature('Bottom','Bottom',rb);t=feature('Top','Top',rt)
nom=feature('UniversalClip','Clip');feature('ClipLooser','Clip',variant=-1);feature('ClipTighter','Clip',variant=1)
for i in range(4):
    o=feature('Clip'+'ABCD'[i],'SiteClip',nom,i);o.Label='Site '+'ABCD'[i]+(' / diagonal minimum' if i in (0,3) else ' / optional second pair')
feature('CouponBottom','CouponBottom',b);feature('CouponTop','CouponTop',t)
visible={'Bottom','Top','ClipA','ClipD'}
for o in d.Objects:
    if getattr(o,'ViewObject',None):
        o.ViewObject.Visibility=o.Name in visible
        if hasattr(o.ViewObject,'ShapeColor'):
            o.ViewObject.ShapeColor=(.21,.43,.61) if o.Name=='Bottom' else ((.68,.76,.83) if o.Name=='Top' else (.99,.48,.08))
            o.ViewObject.LineColor=(.18,.22,.26)
d.recompute();d.saveAs(str(R/'cad/slide-clips.FCStd'));App.closeDocument(d.Name)
d=App.openDocument(str(R/'cad/slide-clips.FCStd'))
for o in d.Objects:
    if isinstance(getattr(o,'Proxy',None),F.SlideFeature):o.touch()
d.recompute()
for o in d.Objects:
    if hasattr(o,'Shape'):
        assert o.Shape.isValid() and o.Shape.isClosed() and not any(x in ('Error','Invalid') for x in o.State),o.Name
        if not getattr(o,'Kind','').endswith('Tools'):assert len(o.Shape.Solids)==1,o.Name


def export(shape,path):
    assert shape.isValid() and len(shape.Solids)==1
    MeshPart.meshFromShape(Shape=shape,LinearDeflection=p['MeshLinearDeflection'],AngularDeflection=p['MeshAngularDeflection'],Relative=False).write(str(path))

exports={
 'case_bottom':('Bottom','Bottom'),'case_lid':('Top','Top'),
 'clip_nominal':('UniversalClip','Clip'),'clip_looser_throat_plus0.24':('ClipLooser','Clip'),
 'clip_tighter_throat_minus0.24':('ClipTighter','Clip'),
 'coupon_bottom':('CouponBottom','CouponBottom'),'coupon_lid':('CouponTop','CouponTop')}
for filename,(obj,kind) in exports.items():
    export(F.bed_shape(d.getObject(obj).Shape,kind),R/'stl'/f'{filename}.stl')
# Rendering intermediates only, always from the reopened FINAL geometry.
for name in ('Bottom','Top','UniversalClip','CouponBottom','CouponTop'):
    export(d.getObject(name).Shape,R/'.cache'/f'final-{name}.stl')
for name in ('Bottom','Top'):
    local=F.to_local(d.getObject('Coupon'+name).Shape,p)
    export(local.common(C.box(-13,0,0,20,-1,40)).removeSplitter(),R/'.cache'/f'local-section-{name.lower()}.stl')
export(d.UniversalClip.Shape.common(C.box(-13,0,-8,10,-4,40)).removeSplitter(),R/'.cache/local-section-clip.stl')
r={'status':'Built/reopened/recomputed; independent validate.py REQUIRED','build_seconds':time.monotonic()-start,
   'exports':exports,'source_provenance':provenance,'transform':list(transform.A),
   'toolchain':{'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION},'cad_sha256':hashlib.sha256((R/'cad/slide-clips.FCStd').read_bytes()).hexdigest()}
(R/'reports/build.json').write_text(json.dumps(r,indent=2)+'\n');App.closeDocument(d.Name)
print('BUILD EXIT 0',r['build_seconds'],flush=True)
