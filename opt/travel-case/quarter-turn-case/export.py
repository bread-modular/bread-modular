#!/usr/bin/env python3
"""Seven small test STLs ONLY; guard against stale/failed CAD gate."""
from pathlib import Path
import hashlib,json
import FreeCAD as App
import MeshPart
import features as F
R=Path(__file__).resolve().parent
v=json.loads((R/'reports/validation.json').read_text());b=json.loads((R/'reports/build.json').read_text())
assert v['status']=='PASS_CAD_GEOMETRY_CONDITIONAL_INSTALLED_STACK' and not v['failures']
assert hashlib.sha256((R/'cad/quarter-turn-case.FCStd').read_bytes()).hexdigest()==v['cad_sha256']==b['cad_sha256']
assert hashlib.sha256((R/'features.py').read_bytes()).hexdigest()==b['feature_source_sha256']
d=App.openDocument(str(R/'cad/quarter-turn-case.FCStd'))
for o in d.Objects:
 if isinstance(getattr(o,'Proxy',None),F.Feature):o.touch()
d.recompute()
items=[('B_key_common.stl','CommonKey','Key')]+[
 ('B_'+half.lower()+'_c'+tag+'.stl','Coupon'+half+tag,half)
 for tag in ('020','010','000') for half in ('Base','Lid')]
(R/'stl').mkdir(exist_ok=True)
for f in (R/'stl').glob('*.stl'):f.unlink()
rows=[]
for filename,obj,kind in items:
 shape=F.bed_shape(d.getObject(obj).Shape,kind)
 assert shape.isValid() and shape.isClosed() and len(shape.Solids)==1
 mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.03,AngularDeflection=.1,Relative=False)
 path=R/'stl'/filename;mesh.write(str(path))
 rows.append({'filename':filename,'object':obj,'kind':kind,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
  'CAD_volume_mm3':shape.Volume,'orientation':'EXTERIOR ROOF down' if kind=='Lid' else 'UNDERSIDE down' if kind=='Base' else 'BROAD X/Y face down;4mm extrusion up'})
App.closeDocument(d.Name)
(R/'reports/exports.json').write_text(json.dumps({'cad_sha256':v['cad_sha256'],'files':rows,'test_only':True,'no_full_case_STL_or_STEP':True},indent=2)+'\n')
print('Exported7 small TEST STLs: one common one-piece key, two exact-case coupon halves per fit')
