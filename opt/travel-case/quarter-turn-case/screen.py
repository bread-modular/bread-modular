#!/usr/bin/env python3
"""ONE focused rim-rooted feasibility round; strict PCB/electronics and skin gate.
No CAD/STL printable exports. Exit 3 on any hard blocker, 0 to proceed to build.
"""
from pathlib import Path
import hashlib,json,math,time,sys
import FreeCAD as App
import Part
import features as F
R=Path(__file__).resolve().parent;V=App.Vector;TOL=1e-5
p=json.loads((R/'parameters.json').read_text());F.check(p,.2)
r={'status':'RUNNING','candidate':'Original-rim-rooted <=45deg brace, keeper .4mm recessed into original wall, 3.2mm continuous lid wall, 2mm axial head, no floor post','checks':[],'blockers':[]}
def bounds(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def req(ok,label,**v):
 row={'test':label,'pass':bool(ok),**v};r['checks'].append(row)
 if not ok:r['blockers'].append(row)
def clear(s,t,label):req(s.common(t).Volume<TOL,label,overlap_mm3=s.common(t).Volume)
def sweep(s,delta):
 vec=V(*delta);parts=[s,F.moved(s,*delta)]
 for face in s.Faces:
  a,b,c,d=face.ParameterRange;n=face.normalAt((a+b)/2,(c+d)/2)
  if abs(n.dot(vec))>1e-7:
   q=face.extrude(vec)
   if q.Volume>1e-8:parts.append(q)
 return F.fuse(parts)
def rotation(p):
 d=F.dimensions(p,0);z=p['AxisZ'];floor=d['pocket_floor_y_mm']+p['PushTravel']
 ct=d['collar_inner_face_parked_y_mm']+p['PushTravel'];cb=ct-p['CollarThickness']
 def cy(r,a,b):return Part.makeCylinder(r,b-a,V(0,a,z),V(0,1,0))
 return F.fuse([cy(d['head_turn_radius_mm'],floor,floor+p['HeadThickness']),
  cy(math.hypot(p['NeckLong'],p['NeckSize'])/2,ct,floor),
  cy(math.hypot(p['CollarLength'],p['CollarWidth'])/2,cb,ct),
  cy(math.hypot(p['GripWidth'],p['HeadWidth'])/2,cb-p['GripLength'],cb)])

def cached_raw():
 provenance=json.loads((R/'cache-provenance.json').read_text());raw={}
 for name in ('bottom','top'):
  entry=provenance[name];path=R/'.cache'/('raw-'+name+'.brep')
  req(hashlib.sha256((R.parent/entry['source']).read_bytes()).hexdigest()==entry['sha256'],'Pristine original STL SHA '+name)
  req(hashlib.sha256(path.read_bytes()).hexdigest()==entry['cache_brep_sha256'],'Pristine BRep SHA '+name)
  s=Part.Shape();s.read(str(path));raw[name]=s
  req(s.isValid() and s.isClosed() and len(s.Solids)==1 and abs(s.Volume-entry['volume_mm3'])<1e-5,'Pristine solid/volume '+name)
 return raw

def electronics_reservations():
 er=json.loads((R/'reports/electronics.json').read_text())
 source=R.parents[2]/er['source'];req(hashlib.sha256(source.read_bytes()).hexdigest()==er['source_sha256'],'PCB survey source unchanged')
 # Installed module heights are unknown: keep the entire band to the roof.
 module=F.box(*[er['conservative_module_reservation_mm'][i] for i in (0,3,1,4,2,5)])
 reserves=[];model_checks=[]
 for f in er['base_footprints']:
  if f['footprint'].split(':')[-1].startswith('MountingHole'):continue
  bb=f['courtyard_bounds_mm'] or f['body_fab_silk_pad_bounds_mm'];m=p['ComponentXYMargin']
  xy=[bb[0]-m,bb[1]-m,bb[2]+m,bb[3]+m]
  # Only geometry within either actual lock corridor needs model height;
  # other base components reserve full height, so missing models never mean clear.
  near=(xy[0]<54 and xy[2]>26 and xy[1]<19.3) or (xy[0]<217.12 and xy[2]>189.12 and xy[3]>160.3)
  h=None
  if near and f['models'] and all(x['available'] for x in f['models']):
   zs=[]
   for model in f['models']:
    q=Path(model['resolved']);req(hashlib.sha256(q.read_bytes()).hexdigest()==model['sha256'],'Available component model SHA '+f['reference'])
    shape=Part.read(str(q));rot=model['rotation']
    shape.rotate(V(),V(1,0,0),rot[0]);shape.rotate(V(),V(0,1,0),rot[1]);shape.rotate(V(),V(0,0,1),rot[2])
    zs.append(shape.BoundBox.ZMax*model['scale'][2]+model['offset'][2])
   h=max(zs)+1.0 # measured model height plus conservative 1mm height margin
  z0,z1=(8,75) if h is None else (14.6,14.6+h)
  reserves.append((f['reference'],F.box(xy[0],xy[2],xy[1],xy[3],z0,z1)))
  if near:model_checks.append({'reference':f['reference'],'XY_reserved_mm':xy,'height_above_board_reserved_mm':h,'reserved_Z_mm':[z0,z1], 'unknown_full_height':h is None})
 r['electronics']={'module_band_mm':bounds(module),'near_base_components':model_checks,
   'unknown_module_height_handling':'Full-height 14.6..75 reserved for ALL source body/courtyard/board bounds plus .25 XY margin',
   'installed_stack_condition':'PCB underside nominal Z13 seating datum, thickness1.6 verified in KiCad; physical installed stack not measured. Additional top uncertainty screen Z14.6..15 remains mandatory.',
   'wiring':'Unknown user patch cables/wiring not cleared: keep lock corridor empty; no travel claim.'}
 return module,reserves

if __name__=='__main__':
 start=time.monotonic();raw=cached_raw();base_ref=F.repaired(raw['bottom'],False);lid_ref=F.repaired(raw['top'],True)
 base=F.base_shape(base_ref,p,.2);lid=F.lid_shape(lid_ref,p,.2)
 pcb=F.pcb_screen();legacy=F.box(-12,12,14.4,17.6,8,49.2)
 for i,(sid,x,rear) in enumerate(F.sites(p)):
  req(abs(F.at_site(legacy,p,i).common(pcb).Volume-122.88)<TOL,'REGRESSION legacy floor post MUST fail '+sid,overlap_mm3=F.at_site(legacy,p,i).common(pcb).Volume)
 clear(base,pcb,'STRICT full new base / exact registered PCB slab')
 module,reserves=electronics_reservations()
 insert=sweep(F.key(p,90,p['PushTravel']),[0,-36,0]);park=sweep(F.key(p),[0,p['PushTravel'],0]);turn=rotation(p)
 all_stock=Part.makeCompound([F.at_site(F.keeper_stock(p),p,i) for i in range(2)])
 envelope=F.fuse([base_ref,lid_ref,F.box(14,229.12,14,p['ReleaseRearY']-14,8,75)])
 req(all_stock.cut(envelope).Volume<TOL,'Keeper stock within ORIGINAL curved exterior (not bbox)',outside_mm3=all_stock.cut(envelope).Volume)
 clear(base,lid,'Closed full halves seating')
 skirt=F.box(-1,245,-1,181,14,14.999)
 req(lid_ref.common(skirt).cut(lid).Volume<TOL,'Original alignment skirt unchanged')
 for i,(sid,x,rear) in enumerate(F.sites(p)):
  stock=F.at_site(F.keeper_stock(p),p,i);added=stock.cut(base_ref)
  root=F.at_site(F.box(-12,12,p['RootFrontY'],p['RootBackY'],12.8,15),p,i)
  req(root.common(base_ref).Volume>150,'RIM load root overlaps original solid '+sid,root_overlap_mm3=root.common(base_ref).Volume)
  clear(stock,F.box(9.8,233.32,9.8,169.82,13,15),'PCB top uncertainty reserve toZ15 '+sid)
  for state,s in [('brace_keeper',stock),('insertion_withdrawal',insert),('push_pull',park),('full_circle_rotation',turn)]:
   w=F.at_site(s,p,i) if state!='brace_keeper' else s
   clear(w,module,sid+' '+state+' POPULATED module full-height reserve')
   clashes=[{'reference':ref,'overlap_mm3':w.common(z).Volume} for ref,z in reserves if w.common(z).Volume>TOL]
   req(not clashes,sid+' '+state+' ACTUAL base courtyards + model/unknown-height reserves',clashes=clashes)
   if state!='brace_keeper':
    clear(w,base,sid+' '+state+' base motion');clear(w,lid,sid+' '+state+' lid motion')
  ks=F.at_site(F.keeper(p,.2),p,i)
  clear(sweep(ks,[0,0,-80]),lid,sid+' exact continuous upright lid lift / brace seating')
  # Relief opening doesn't remove the exterior surface; retain at least 3.2mm
  # of local Y skin measured from raw faceted front rays below entry aperture.
  skin=[]
  for z in (15.001,16,17,18,19,20,21,22,23,27.5,35,48):
   ray=raw['top'].common(Part.makeLine(V(x,-1,z),V(x,22,z)))
   y0=min(v.Y for v in ray.Vertexes)
   front=p['RootFrontY']-p['ReliefGap']+max(0,z-p['BraceStartZ'])*(p['KeeperFrontY']-p['RootFrontY'])/(p['BraceEndZ']-p['BraceStartZ'])
   front=min(front,p['KeeperFrontY']-p['ReliefGap'])
   skin.append([z,front-y0])
  req(min(v[1] for v in skin)>=3.2-1e-7,sid+' locally relieved lid minimum exterior wall >=3.2',samples_Z_Ythickness_mm=skin)
 r['parameters']=p;r['dimensions']=F.dimensions(p,.2)
 r['body_bounds_mm']=bounds(Part.makeCompound([base,lid]));r['base_with_internal_rise_bounds_mm']=bounds(base)
 r['seconds']=time.monotonic()-start;r['status']='BLOCKED' if r['blockers'] else 'FEASIBILITY_PASS_CONDITIONAL_INSTALLED_STACK'
 (R/'reports/feasibility.json').write_text(json.dumps(r,indent=2)+'\n')
 print(r['status'],len(r['checks']),'checks;',len(r['blockers']),'blockers;',round(r['seconds'],2),'seconds')
 for row in r['blockers']:print(json.dumps(row))
 sys.exit(3 if r['blockers'] else 0)
