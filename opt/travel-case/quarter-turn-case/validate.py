#!/usr/bin/env python3
"""Strict reopened CAD + real electronics + rigid operation + exact-crop checks.
STLs are forbidden until CAD phase passes. --stl-only checks written assets against
reopened live CAD and appends to the same compact report. No force/travel claims.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,math,sys,time
import numpy as np
import FreeCAD as App
import Part,Mesh
import features as F
import screen as S
R=Path(__file__).resolve().parent;V=App.Vector;TOL=1e-5;start=time.monotonic()
stl_only='--stl-only' in sys.argv
r=json.loads((R/'reports/validation.json').read_text()) if stl_only else {
 'status':'RUNNING','checks':[],'failures':[], 'limitations':[
 'Ideal rigid CAD geometry, not strength, carrying, vibration, wear or print-force verification.',
 'PCB original Z13..14.6 mandatory; thickness1.60 from KiCad; installed stack not measured. Extra top reserve toZ15.',
 'All module heights unknown and reserved to original roof with actual module body/courtyard XY; wiring/knob protrusions beyond footprint are unmeasured.',
 'P2S .4 nozzle / .20 layers assumed, filament unknown; geometry support screen is NOT slicing.',
 'No spring holds parking. Inadvertent push + turn can release key; not safe-travel approval.',
 'Faceted pristine shell references, not recovered Fusion feature history.'
 ]}
def req(ok,label,**data):
 row={'test':label,'pass':bool(ok),**data};r['checks'].append(row)
 if not ok:r['failures'].append(row);print('FAIL',label,json.dumps(data),flush=True)
def clear(vol,label,**data):req(abs(vol)<TOL,label,overlap_mm3=vol,**data)
def bounds(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def diff(a,b):return a.cut(b).Volume+b.cut(a).Volume
def possible(a,b):
 x=a.BoundBox;y=b.BoundBox
 return x.XMin<y.XMax and x.XMax>y.XMin and x.YMin<y.YMax and x.YMax>y.YMin and x.ZMin<y.ZMax and x.ZMax>y.ZMin
def section_segments(shape,axis,value):
 if axis=='x':pts=[V(value,-3,-.1),V(value,24.1,-.1),V(value,24.1,77.6),V(value,-3,77.6)]
 else:pts=[V(-16.1,value,-.1),V(16.1,value,-.1),V(16.1,value,77.6),V(-16.1,value,77.6)]
 plane=Part.Face(Part.makePolygon(pts+[pts[0]]));out=[];seen=set()
 for e in shape.section(plane).Edges:
  vs=[v.Point for v in e.Vertexes] if isinstance(e.Curve,Part.Line) else e.discretize(Deflection=.04)
  for a,b in zip(vs,vs[1:]):
   coords=((a.y,a.z),(b.y,b.z)) if axis=='x' else ((a.x,a.z),(b.x,b.z))
   row=[[round(t,4) for t in xy] for xy in coords];key=tuple(sorted(tuple(xy) for xy in row))
   if key not in seen and key[0]!=key[1]:out.append(row);seen.add(key)
 return out

build=json.loads((R/'reports/build.json').read_text());path=R/'cad/quarter-turn-case.FCStd'
req(hashlib.sha256(path.read_bytes()).hexdigest()==build['cad_sha256'],'Saved CAD SHA256 equals build')
req(hashlib.sha256((R/'features.py').read_bytes()).hexdigest()==build['feature_source_sha256'],'Feature source SHA256 equals build')
d=App.openDocument(str(path))
for o in d.Objects:
 if isinstance(getattr(o,'Proxy',None),F.Feature):o.touch()
d.recompute();p=F.values(d.Parameters)
for o in d.Objects:
 if hasattr(o,'Shape') and o.TypeId!='App::DocumentObjectGroup':
  req(o.Shape.isValid() and o.Shape.isClosed() and len(o.Shape.Solids)==(2 if o.Name=='LidTools020' else 1) and not any(x in ('Error','Invalid') for x in o.State),
    'Reopen/re-execute '+o.Name,solids=len(o.Shape.Solids),state=list(o.State))
if not stl_only:
 raw={'base':d.RawBottom.Shape,'lid':d.RawTop.Shape};refs={'base':d.RepairedBase.Shape,'lid':d.RepairedLid.Shape}
 original=bounds(Part.makeCompound(list(raw.values())))
 r['parameters']=p;r['fit_dimensions']=[F.dimensions(p,c) for c in p['FitVariantsPerSide']]
 r['cad_sha256']=build['cad_sha256']
 for n,k in [('bottom','base'),('top','lid')]:
  pr=build['provenance'][n];q=Part.Shape();q.read(str(R/'.cache'/('raw-'+n+'.brep')))
  req(hashlib.sha256((R.parent/pr['source']).read_bytes()).hexdigest()==pr['sha256'],'Pristine original STL SHA '+n)
  req(hashlib.sha256((R/'.cache'/('raw-'+n+'.brep')).read_bytes()).hexdigest()==pr['cache_brep_sha256'],'Pristine BRep SHA '+n)
  clear(diff(q,raw[k]),'Saved pristine reference equals source-derived BRep '+n)
 stock=Part.makeCompound([F.at_site(F.keeper_stock(p),p,i) for i in range(2)])
 channel=Part.makeCompound([F.at_site(F.lid_relief(p),p,i) for i in range(2)])
 envelope=F.fuse([*refs.values(),F.box(14,229.12,14,p['ReleaseRearY']-14,8,75)])
 clear(stock.cut(envelope).Volume,'Keeper entirely inside original curved complete-shell exterior, ACTUAL rear datum')
 pcb=F.pcb_screen();legacy=F.box(-12,12,14.4,17.6,8,49.2)
 for i,(sid,x,rear) in enumerate(F.sites(p)):
  v=F.at_site(legacy,p,i).common(pcb).Volume
  req(abs(v-122.88)<TOL,'NEGATIVE REGRESSION old floor-post PCB clash '+sid,overlap_mm3=v)
 module,reserves=S.electronics_reservations();req(not S.r['blockers'],'Electronics source/model hashes match survey')
 r['electronics']=S.r['electronics']
 r['operation']={'sites':[], 'straight_lift_before_sideways_mm':35.6,
  'diagonal_note':'Closed-height diagonal extraction is not a supported operation: the tall keepers require an initial straight lift. Locked diagonal samples must obstruct; after 35.6mm straight lift sideways motion must be clear.'}
 insert=S.sweep(F.key(p,90,p['PushTravel']),[0,-36,0]);park=S.sweep(F.key(p),[0,p['PushTravel'],0]);rotation=S.rotation(p)
 # Frozen original regions unaffected by the intentional local rim/channel masks.
 regions=[]
 for x in (17.42,225.7):
  for y in (17.42,162.2):regions.append(('base','PCB mounting hole '+str((x,y)),F.box(x-4.5,x+4.5,y-4.5,y+4.5,0,15.01)))
 for y in (20,119.62):regions.append(('base','underside mounting relief '+str(y),F.box(19.56,223.56,y,y+40,0,7.4)))
 for x in (-.1,230.92):
  for y in (53.9,123.52):regions.append(('base','short-side connector notch '+str((x,y)),F.box(x,x+12.3,y,y+2.2,7.9,15.1)))
 for x,y in ((8.5,23),(8.5,107.62),(229.62,107.62)):
  regions.append(('lid','connector/mount slot '+str((x,y)),F.box(x,x+5,y,y+49,17.5,28.5)))
 regions += [('lid','COMPLETE original alignment skirt Z14..14.999',F.box(-1,245,-1,181,14,14.999)),
  ('base','original base rim Z13..15 outside integral root mask',F.box(-1,245,-1,181,13,15.00001).cut(stock)),
  ('lid','original inner roof (outside allowed logo repair)',F.box(14,229,14,165,74.99,75.01).cut(F.repair_mask(True))),
  ('base','original inner floor (outside allowed logo repair)',F.box(14,229,14,165,7.99,8.01).cut(F.repair_mask(False)))]
 for tag,c in [('020',.2),('010',.1),('000',0)]:
  base=d.getObject('Base'+tag).Shape;lid=d.getObject('Lid'+tag).Shape;sh={'base':base,'lid':lid}
  fullbounds=bounds(Part.makeCompound([base,lid]));req(max(abs(a-b) for a,b in zip(original,fullbounds))<.0001,'Original full W/D/H, c='+str(c),bounds_mm=fullbounds)
  clear(base.common(lid).Volume,'Zero positive inter-half seating interference c='+str(c))
  clear(base.common(pcb).Volume,'STRICT full base vs ORIGINAL registered PCB c='+str(c))
  clear(stock.common(F.box(9.8,233.32,9.8,169.82,13,15)).Volume,'Additional board top uncertainty reserve toZ15 c='+str(c))
  for half in ('base','lid'):
   tools=stock if half=='base' else F.fuse([channel,F.receiver_tools(p,c)])
   mask=F.fuse([tools,F.repair_mask(half=='lid')])
   clear(diff(raw[half].cut(mask),sh[half].cut(mask)),'ENTIRE '+half+' identical outside explicit root/channel/window/repair masks c='+str(c))
   clear(sh[half].cut(raw[half]).cut(F.fuse([stock,F.repair_mask(False)]) if half=='base' else F.repair_mask(True)).Volume,'No unauthorized additions '+half+' c='+str(c))
   clear(raw[half].cut(sh[half]).cut(tools).Volume,'No unauthorized cuts '+half+' c='+str(c))
  for half,label,region in regions:clear(diff(refs[half].common(region),sh[half].common(region)),'Frozen '+label+' c='+str(c))
  for i,(sid,x,rear) in enumerate(F.sites(p)):
   keeper=F.at_site(F.keeper(p,c),p,i);key=F.at_site(d.CommonKey.Shape,p,i)
   row={'fit_per_side_mm':c,'site':sid,'axis_XZ_mm':[x,p['AxisZ']]}
   for state,s in [('insert_withdraw_CONTINUOUS',insert),('turn_FULL_CIRCLE_BOUND',rotation),('park_unpark_CONTINUOUS',park),('parked_key',d.CommonKey.Shape)]:
    w=F.at_site(s,p,i)
    clear(w.common(base).Volume,sid+' '+state+' base c='+str(c));clear(w.common(lid).Volume,sid+' '+state+' lid c='+str(c))
    clear(w.common(module).Volume,sid+' '+state+' populated full-height module reserve c='+str(c))
    collisions=[{'reference':name,'mm3':w.common(z).Volume} for name,z in reserves if possible(w,z) and w.common(z).Volume>TOL]
    req(not collisions,sid+' '+state+' actual base courtyard/model reserves c='+str(c),collisions=collisions)
   clear(keeper.common(module).Volume,sid+' keeper vs populated full-height module reserve c='+str(c))
   collisions=[name for name,z in reserves if possible(keeper,z) and keeper.common(z).Volume>TOL]
   req(not collisions,sid+' keeper vs actual base courtyard/model reserves c='+str(c),collisions=collisions)
   v=F.at_site(F.key(p,10,0),p,i).common(base).Volume
   req(v>1,sid+' parked pocket blocks 10deg turn c='+str(c),obstruction_mm3=v);row['parked_10deg_obstruction_mm3']=v
   v=F.at_site(F.key(p,0,-3),p,i).common(base).Volume
   req(v>1,sid+' HEAD catches BASE on axial withdrawal c='+str(c),obstruction_mm3=v)
   v=F.at_site(F.key(p,0,3),p,i).common(lid).Volume
   req(v>1,sid+' COLLAR catches LID on inward push beyond release c='+str(c),obstruction_mm3=v)
   for delta in [(0,0,1),(1,1,1),(-1,1,1),(1,-1,1),(-1,-1,1)]:
    v=key.common(F.moved(lid,*delta)).Volume
    req(v>.1,sid+' locked neck retains LID, diagonal/vertical '+str(delta)+' c='+str(c),obstruction_mm3=v)
   clear(S.sweep(keeper,[0,0,-80]).common(lid).Volume,sid+' EXACT continuous keeper/real-channel upright lid lift c='+str(c))
   # Not a fictitious straight-wall slot: measure the real failed diagonal path.
   if c==.2:
    delta=[2,2,-80] if rear else [-2,-2,-80]
    v=S.sweep(keeper,delta).common(lid).Volume
    row['unlocked_inward_diagonal_relative_keeper_delta_mm']=delta
    row['unlocked_diagonal_2_2_80_obstruction_mm3']=v
    req(v>0,sid+' DISCLOSE diagonal lift obstruction: lift straight first',obstruction_mm3=v)
    access=F.at_site(F.box(-12.1,12.1,16.81,26.8,8.01,p['KeeperTopZ']+.01),p,i)
    clear(access.common(base).Volume,sid+' OPEN cleanup corridor with halves apart, before electronics installation')
    finger=F.at_site(Part.makeCylinder(10,7,V(0,-9,p['AxisZ']),V(0,1,0)),p,i)
    clear(finger.common(lid).Volume,sid+' External20mm finger/tool approach')
   region=F.coupon_region(p,i)
   for half in ('Base','Lid'):
    crop=sh[half.lower()].common(region).removeSplitter()
    req(crop.isValid() and crop.isClosed() and len(crop.Solids)==1,'EXACT crop solid '+sid+' '+half+' c='+str(c))
    if i==0:
     originalcrop=d.getObject('ExactCrop'+half+tag).Shape
     labelled=d.getObject('Coupon'+half+tag).Shape
     clear(diff(crop,originalcrop),'EXACT derived full-case crop '+half+' c='+str(c))
     label=F.coupon_label_tool(p,c,half,0)
     clear(diff(crop.cut(label).removeSplitter(),labelled),'Only non-bearing identification cut in coupon '+half+' c='+str(c))
     clear(label.common(F.at_site(F.keeper_stock(p),p,0)).Volume,'Label off lock bearing/root '+half+' c='+str(c))
     req(crop.Volume-labelled.Volume>1,'Label is physically engraved, not annotation '+half+' c='+str(c))
   r['operation']['sites'].append(row)
  for h in (0,.25,1,5,15,35.6,65,80):clear(base.common(F.moved(lid,z=h)).Volume,'Full lid seating/lift sample '+str(h)+' c='+str(c))
  for dx,dy in ((4,4),(-4,4),(4,-4),(-4,-4)):
   clear(base.common(F.moved(lid,dx,dy,35.6)).Volume,'Unlocked lateral/diagonal move AFTER35.6mm straight lift '+str((dx,dy))+' c='+str(c))
 # Live full case dependency editing: coupons recompute from edited full geometry.
 old=d.Base020.Shape.Volume;d.Base020.FitPerSide=.1;d.Lid020.FitPerSide=.1;d.recompute()
 clear(diff(d.Base020.Shape,d.Base010.Shape),'LIVE edit full base fit .20 -> .10')
 clear(diff(d.Lid020.Shape,d.Lid010.Shape),'LIVE edit full lid fit .20 -> .10')
 clear(diff(d.CouponBase020.Shape,d.CouponBase010.Shape),'LIVE edited labelled base coupon follows fit')
 clear(diff(d.CouponLid020.Shape,d.CouponLid010.Shape),'LIVE edited labelled lid coupon follows fit')
 req(abs(d.Base020.Shape.Volume-old)>1,'Live edit actually changes receiver geometry')
 d.Base020.FitPerSide=.2;d.Lid020.FitPerSide=.2;d.recompute()
 label=F.label_tool('B',-.9,.5,p['AxisZ']+p['HeadWidth']/2-.4,p['AxisZ']+p['HeadWidth']/2+.01,.6)
 clear(diff(F.key(p).cut(label).removeSplitter(),d.CommonKey.Shape),'ONE common key: only grip-face label removed')
 req(len(d.CommonKey.Shape.Solids)==1,'Common key genuinely one solid, no pins/glue/gate')
 r['envelope']={'original_and_integrated_body_bounds_mm':original,'body_dimensions_mm':[original[i+3]-original[i] for i in range(3)],
  'base_shell_external_height_mm':15,'base_with_internal_keeper_bounds_mm':bounds(d.Base020.Shape),
  'internal_keeper_height_mm':49.2,'local_grip_projection_beyond_straight_side_wall_mm':12,
  'grip_projection_beyond_global_side_edge_mm':2,'body_with_both_keys_dimensions_mm':[p['CaseWidth'],p['ReleaseRearY']+4,p['CaseHeight']],
  'keeper_original_wall_recess_mm':.4,'local_lid_channel_recess_mm':.8,'remaining_straight_lid_outer_wall_mm':3.2,
  'receiver_top_ligament_mm':[F.dimensions(p,c)['base_top_ligament_at_entry_tip_mm'] for c in p['FitVariantsPerSide']],
  'keeper_parking_end_ligament_min_mm':(p['ReceiverWidth']-(p['HeadLength']+.4))/2,
  'root_thickness_mm':p['RootBackY']-p['RootFrontY'],'keeper_thickness_mm':3.2,'keeper_axial_web_after_pocket_mm':2.4}
 # Compact local cross-sections only, no full-facet/edge-array survey dump.
 local={n:F.from_site(d.getObject(o).Shape,p,0) for n,o in [('base','CouponBase020'),('lid','CouponLid020'),('key','Key0')]}
 local['raw_base']=F.from_site(raw['base'].common(F.coupon_region(p,0)),p,0)
 local['raw_lid']=F.from_site(raw['lid'].common(F.coupon_region(p,0)),p,0)
 local['PCB']=F.from_site(pcb.common(F.coupon_region(p,0)),p,0)
 r['sections']={'YZ_centre':{n:section_segments(s,'x',0) for n,s in local.items()},
  'YZ_head_ear_X7':{n:section_segments(s,'x',7) for n,s in local.items() if n in ('base','lid','key')}}
 # Identify stock external lid flare overhangs in true roof-down direction.
 e=r['sections']['YZ_centre']['raw_lid'];steep=[]
 for a,b in e:
  if 15<=min(a[1],b[1]) and max(a[1],b[1])<=27.501 and max(a[0],b[0])<=10.001 and min(a[0],b[0])>=-.001 and abs(b[1]-a[1])>1e-6:
   ratio=abs((b[0]-a[0])/(b[1]-a[1]))
   if ratio>1:steep.append({'Z_range_mm':sorted([a[1],b[1]]),'outward_per_up_print_Z':ratio})
 r['print_screen']={'base':'true underside down; rising brace .9mm outward/mm print height <=45deg; no functional-contact support planned',
  'lid':'true exterior roof down; original flared lower exterior may need accessible OUTSIDE-only supports; do not support aperture/parking/channel/mating lands',
  'stock_roof_down_flare_segments_exceeding_45deg':steep,
  'maximum_designed_aperture_bridge_cap_mm':p['ApertureBridgeCap'],
  'label_stroke_mm':{'coupon':.8,'key':.6},'label_recess_depth_mm':.4,
  'slicing_done':False,'support_contact_on_fit_faces_permitted':False,
  'cleanup':'No trapped chamber: lid inner channel and base rear parking pocket exposed with halves apart before electronics installation.'}
 r['status']='FAILED' if r['failures'] else 'PASS_CAD_GEOMETRY_CONDITIONAL_INSTALLED_STACK'
else:
 req(r['status']=='PASS_CAD_GEOMETRY_CONDITIONAL_INSTALLED_STACK','CAD gate passed before written-STL check')
 manifest=json.loads((R/'reports/exports.json').read_text());expected={'B_key_common.stl'}|{'B_'+half+'_c'+tag+'.stl' for tag in ('020','010','000') for half in ('base','lid')}
 actual={f.name for f in (R/'stl').glob('*.stl')}
 req(actual==expected,'Exactly7STLs, no full-case/STEP variants',files=sorted(actual))
 written=[]
 for row in manifest['files']:
  path=R/'stl'/row['filename'];mesh=Mesh.Mesh(str(path));shape=F.bed_shape(d.getObject(row['object']).Shape,row['kind'])
  topology=mesh.Topology;pts=np.array([[v.x,v.y,v.z] for v in topology[0]]);tris=np.array(topology[1],dtype=int)
  # Weld STL duplicate vertex records in-memory for analysis only; never repair export.
  q=np.round(pts,6);_,ids=np.unique(q,axis=0,return_inverse=True);faces=ids[tris]
  edges=Counter();orient=Counter()
  for tri in faces:
   for a,b in zip(tri,np.roll(tri,-1)):
    edges[tuple(sorted((int(a),int(b))))]+=1;orient[(int(a),int(b))]+=1
  bad=sum(n!=2 for n in edges.values());orient_bad=sum(orient[(a,b)]!=orient[(b,a)] for a,b in edges)
  areas=np.linalg.norm(np.cross(pts[tris[:,1]]-pts[tris[:,0]],pts[tris[:,2]]-pts[tris[:,0]]),axis=1)/2
  mb=[*pts.min(axis=0),*pts.max(axis=0)];bb=bounds(shape)
  req(mesh.isSolid() and mesh.countComponents()==1 and not mesh.hasNonManifolds() and bad==0 and orient_bad==0 and np.all(areas>1e-9),row['filename']+' WATERTIGHT, one component, no nonmanifold/degenerate/inverted edges',facets=len(tris),edge_errors=bad,orientation_errors=orient_bad)
  req(max(abs(a-b) for a,b in zip(mb,bb))<1e-4,row['filename']+' actual bed bounds match reopened CAD',bounds_mm=mb)
  req(abs(mesh.Volume-shape.Volume)<max(.15,shape.Volume*.0002),row['filename']+' written STL volume matches CAD',CAD_mm3=shape.Volume,STL_mm3=mesh.Volume)
  req(abs(mb[2])<1e-5,row['filename']+' true required face on Z0 bed')
  digest=hashlib.sha256(path.read_bytes()).hexdigest();req(digest==row['sha256'],row['filename']+' SHA equals exported bytes')
  written.append({'filename':row['filename'],'sha256':digest,'bounds_mm':mb,'volume_mm3':mesh.Volume,'facets':len(tris)})
 r['STLs']=written;r['status']='FAILED' if r['failures'] else 'PASS_CAD_AND_7_WRITTEN_STLS_TEST_ONLY'
r['validation_seconds']=time.monotonic()-start
(R/'reports/validation.json').write_text(json.dumps(r,indent=2)+'\n');App.closeDocument(d.Name)
print(r['status'],len(r['checks']),'checks;',len(r['failures']),'failures;',round(r['validation_seconds'],2),'s')
sys.exit(1 if r['failures'] else 0)
