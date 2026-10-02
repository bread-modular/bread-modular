#!/usr/bin/env python3
"""Strict small-kit build. Delete stale deliverables before work; never read shells."""
from pathlib import Path
import json, hashlib
import FreeCAD as App
import Part, MeshPart
import studies as S
R=Path(__file__).resolve().parent
for sub in ('cad','stl','reports','.cache'): (R/sub).mkdir(exist_ok=True)
for sub,pattern in (('stl','*.stl'),('cad','*.FCStd'),('reports','*.json')):
    for f in (R/sub).glob(pattern): f.unlink()
for name in ('SHA256SUMS','comparison.svg'): (R/name).unlink(missing_ok=True)
p=json.loads((R/'parameters.json').read_text()); S.check(p)
d=App.newDocument('StandaloneLockStudies')
pa=d.addObject('App::FeaturePython','Parameters'); pa.Label='EDIT HardwareTotalGap; all mating clearances (NOT hook engagement)'
for k,v in p.items():
    typ='App::PropertyFloatList' if isinstance(v,list) else 'App::PropertyFloat'
    pa.addProperty(typ,k,'Fits' if k in ('HardwareTotalGap','HookOverlap','GaugeGaps') else 'Dimensions'); setattr(pa,k,v)
pa.addProperty('App::PropertyString','Scope','Evidence').Scope='STANDALONE MECHANISM COUPONS. No full case imports / crop / native case history.'
pa.addProperty('App::PropertyString','PrintStatus','Evidence').PrintStatus='UNSLICED; material/profile unknown; physical fit, strength, cycles and creep NOT qualified.'
pa.addProperty('App::PropertyString','Axes','Evidence').Axes='A: +X press, +Y lid separation, Z width. B: +Z insert, X entry head / seam, Y separation.'
pa.addProperty('App::PropertyString','IntegrationNotes','Evidence').IntegrationNotes='Later real-section test: original 243.12 x 179.62 x 77.5; seam Z15; floor 8; curved lid shoulder. Avoid underfloor projections / fiddly captive integration.'
colours={'C':(.28,.65,.51),'A':(.31,.53,.76),'B':(.61,.46,.76)}
for k in S.KINDS:
    o=d.addObject('PartDesign::FeaturePython',k); S.Coupon(o,k,pa); o.Label=S.export_names(p)[k]+' / standalone'
    d.recompute()
    assert o.Shape.isValid() and o.Shape.isClosed() and len(o.Shape.Solids)==1 and o.Shape.Volume>0, k
    print('BUILT',k,'volume',round(o.Shape.Volume,2),flush=True)
    if o.ViewObject:
        o.ViewObject.ShapeColor=(.99,.53,.19) if k in ('A_CLASP','B_KEY') else colours[k[0]]
# Save actual study-coordinate assemblies. Gauge moved beside A; B offset clear of A.
for k in S.KINDS:
    o=d.getObject(k)
    if k.startswith('C_'): o.Placement.Base=S.V(40,0,0) if k=='C_FEMALE' else S.V(85,0,0)
    if k.startswith('B_'): o.Placement.Base=S.V(135,0,0)
d.recompute(); d.saveAs(str(R/'cad/lock-studies.FCStd')); App.closeDocument(d.Name)
d=App.openDocument(str(R/'cad/lock-studies.FCStd'))
for o in d.Objects:
    if isinstance(getattr(o,'Proxy',None),S.Coupon): o.touch()
d.recompute()
exports={}
for k in S.KINDS:
    o=d.getObject(k); assert o.Shape.isValid() and len(o.Shape.Solids)==1 and 'Error' not in o.State,k
    s=o.Shape.copy(); s.Placement=o.Placement.inverse().multiply(s.Placement)
    bed=S.bed_shape(s,k)
    path=R/'stl'/ (S.export_names(p)[k]+'.stl')
    MeshPart.meshFromShape(Shape=bed,LinearDeflection=p['MeshLinearDeflection'],AngularDeflection=p['MeshAngularDeflection'],Relative=False).write(str(path))
    exports[k]={'file':str(path.relative_to(R)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'volume_mm3':bed.Volume}
App.closeDocument(d.Name)
(R/'.cache/build.json').write_text(json.dumps({'status':'REOPENED_AND_EXPORTED; independent validation required',
 'cad_sha256':hashlib.sha256((R/'cad/lock-studies.FCStd').read_bytes()).hexdigest(), 'parameters':p,
 'toolchain':{'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION}, 'exports':exports},indent=2)+'\n')
