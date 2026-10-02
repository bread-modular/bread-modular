#!/usr/bin/env python3
"""Full live parametric case; exact crops then non-bearing labels. No export here.
Original faceted BReps are SHA verified, not reconstructed native Fusion history.
"""
from pathlib import Path
import hashlib,json,time
import FreeCAD as App
import Part
import features as F
import screen as S
R=Path(__file__).resolve().parent
start=time.monotonic();p=json.loads((R/'parameters.json').read_text());F.check(p,.2)
feas=json.loads((R/'reports/feasibility.json').read_text())
assert not feas['blockers'] and feas['parameters']==p,'Run passing feasibility first; no bypass'
for name in ('cad','reports','.cache','stl','previews'):(R/name).mkdir(exist_ok=True)
raw=S.cached_raw();assert not S.r['blockers']
provenance=json.loads((R/'cache-provenance.json').read_text())
for name in ('release.json','tag-ref.json','native-archive-inventory.json','SHA256SUMS'):
 provenance[name+'_sha256']=hashlib.sha256((R.parent/'original/case_1.0.0'/name).read_bytes()).hexdigest()
d=App.newDocument('QuarterTurnCase')
pa=d.addObject('App::FeaturePython','Parameters');pa.Label='LIVE quarter-turn / TEST COUPONS ONLY'
pa.addProperty('App::PropertyString','FixedRecipe','Recipe').FixedRecipe=json.dumps(p)
pa.addProperty('App::PropertyString','Evidence','Evidence').Evidence='CAD/electronics screen conditional on original board seating stack; unsliced/unprinted. Not safe-travel approval.'
for k,v in p.items():
 if k=='FitVariantsPerSide':continue
 pa.addProperty('App::PropertyLength',k,'Dimensions');setattr(pa,k,v)
 if k.startswith('Case') or k in ('ReleaseRearY','SeamZ','FloorZ','RoofInnerZ','NozzleDiameter','LayerAssumption'):pa.setEditorMode(k,1)
groups={n:d.addObject('App::DocumentObjectGroup',n) for n in ('PristineReferences','RepairFeatures','Fit020','Fit010','Fit000','LockInspection','ElectronicsScreens')}
refs={}
for name,s in raw.items():
 o=d.addObject('PartDesign::Feature','Raw'+name.title());o.Shape=s;o.Label='PRISTINE SHA-verified faceted '+name
 o.addProperty('App::PropertyString','SourceSHA256','Evidence').SourceSHA256=provenance[name]['sha256']
 refs[name]=o;groups['PristineReferences'].addObject(o)
def feature(name,kind,ref=None,c=.2,index=0,group=None):
 o=d.addObject('PartDesign::FeaturePython',name);F.Feature(o,kind,pa,ref,c,index)
 if group:groups[group].addObject(o)
 d.recompute()
 assert o.Shape.isValid() and o.Shape.isClosed() and not any(x in ('Error','Invalid') for x in o.State),name
 return o
rb=feature('RepairedBase','RepairBase',refs['bottom'],group='RepairFeatures')
rl=feature('RepairedLid','RepairLid',refs['top'],group='RepairFeatures')
common=feature('CommonKey','Key',group='LockInspection');common.Label='ONE common one-piece key / B on non-bearing grip face'
for tag,c in [('020',.2),('010',.1),('000',0)]:
 group='Fit'+tag
 base=feature('Base'+tag,'Base',rb,c,group=group);lid=feature('Lid'+tag,'Lid',rl,c,group=group)
 base.Label='FULL base / c='+format(c,'.2f')+' PER SIDE / internal height49.2'
 lid.Label='FULL lid / c='+format(c,'.2f')+' PER SIDE / original exterior'
 for half,ref in [('Base',base),('Lid',lid)]:
  crop=feature('ExactCrop'+half+tag,'Coupon',ref,c,index=0,group=group)
  crop.Label='EXACT full-height FRONT '+half+' crop / no label cuts'
  coupon=feature('Coupon'+half+tag,'Labelled'+half+'Coupon',crop,c,index=0,group=group)
  coupon.Label=half.upper()+' print coupon / '+format(c,'.2f')+' PER SIDE'
 for i in range(2):
  feature('Keeper'+tag+str(i),'Keeper',c=c,index=i,group='LockInspection')
for i in range(2):feature('Key'+str(i),'SiteKey',common,index=i,group='LockInspection')
# Other handed site is checked/cropped in strict validator, not an extra print set.
feature('OtherSiteExactBase','Coupon',d.Base020,index=1,group='LockInspection')
feature('OtherSiteExactLid','Coupon',d.Lid020,index=1,group='LockInspection')
feature('LidTools020','LidTools',group='LockInspection')
for name,shape,label in [
 ('PCBFootprintScreen',F.pcb_screen(),'Registered REAL base PCB / originalZ13..14.6 unchanged'),
 ('PCBTopUncertainty',F.box(9.8,233.32,9.8,169.82,14.6,15),'Extra TOP reserve toZ15; not shifted PCB'),
 ('PopulatedModuleBand',F.box(9.8,233.32,19.339,157.395,14.6,75),'ALL repo module body/courtyard XY: unknown heights reserved to original roof')]:
 o=d.addObject('PartDesign::Feature',name);o.Shape=shape;o.Label=label;groups['ElectronicsScreens'].addObject(o)
for o in d.Objects:
 if getattr(o,'ViewObject',None):o.ViewObject.Visibility=o.Name in ('Base020','Lid020','Key0','Key1')
path=R/'cad/quarter-turn-case.FCStd';d.recompute();d.saveAs(str(path));App.closeDocument(d.Name)
# Required reopen + code-backed re-execution, not a saved static-shape pass.
d=App.openDocument(str(path))
for o in d.Objects:
 if isinstance(getattr(o,'Proxy',None),F.Feature):o.touch()
d.recompute()
for o in d.Objects:
 if hasattr(o,'Shape') and o.TypeId!='App::DocumentObjectGroup':
  assert o.Shape.isValid() and o.Shape.isClosed() and not any(x in ('Error','Invalid') for x in o.State),o.Name
  assert len(o.Shape.Solids)==(2 if o.Name=='LidTools020' else 1),o.Name

def mesh(s):
 vs,fs=s.tessellate(.12)
 return {'vertices':[[v.x,v.y,v.z] for v in vs],'faces':fs}
preview_names=['Base020','Lid020','Key0','Key1','CouponBase020','CouponLid020','CommonKey','PCBFootprintScreen','PopulatedModuleBand']
geometry={n:mesh(d.getObject(n).Shape) for n in preview_names}
(R/'.cache/preview-meshes.json').write_text(json.dumps(geometry,separators=(',',':')))
App.closeDocument(d.Name)
r={'status':'BUILT_CAD_REOPENED_NOT_YET_EXPORT_VALIDATED','provenance':provenance,
 'parameters':p,'toolchain':{'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION},
 'cad_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'feature_source_sha256':hashlib.sha256((R/'features.py').read_bytes()).hexdigest(),
 'feasibility_sha256':hashlib.sha256((R/'reports/feasibility.json').read_bytes()).hexdigest(),
 'fit_dimensions':[F.dimensions(p,c) for c in p['FitVariantsPerSide']],
 'printable_exports':[],'build_seconds':time.monotonic()-start}
(R/'reports/build.json').write_text(json.dumps(r,indent=2)+'\n')
print('Built FULL live 3-fit CAD + exact front coupons, common key; reopened/recomputed;',round(r['build_seconds'],2),'s; no STL exported yet')
