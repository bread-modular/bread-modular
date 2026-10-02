#!/usr/bin/env python3
"""ENFORCED validation of reopened/recomputed final CAD and ACTUAL written STLs.
Geometric clearance/capture only, not force/friction/load or print certification.
Every failed assertion causes exit 1. Never relax a check to obtain a release.
"""
from pathlib import Path
import hashlib,json,time,copy,math
import FreeCAD as App
import Part,Mesh,MeshPart
import final_features as F
import clip_features as C
R=Path(__file__).resolve().parent;start=time.monotonic();TOL=1e-5
r={'status':'RUNNING','checks':[],'failures':[],'sites':[],'written_STLs':{},'limitations':[
 'Actual free clip has terminal interference, NOT rigidly collision-free seated geometry.',
 '0.02 mm/jaw gap surrogate tests geometric capture only; no elastic force/friction certification.',
 'Physical fit, withdrawal, friction, creep, rocking, carrying/drop/torsional load and slicer supports untested.',
 'Not a safety-rated lock; computational check count does not establish strength.',
 'Raw STL to faceted BRep reference; native Fusion feature history not recovered.']}

def write():
    r['seconds']=time.monotonic()-start;(R/'reports/validation.json').write_text(json.dumps(r,indent=2)+'\n')
def require(ok,label,**data):
    row={'test':label,'pass':bool(ok),**data};r['checks'].append(row)
    if not ok:r['failures'].append(row);print('FAIL',label,data,flush=True)
    write()
def clear(v,label,**kw):require(abs(v)<TOL,label,intersection_mm3=v,**kw)
def bounds(s):
    b=s.optimalBoundingBox() if hasattr(s,'optimalBoundingBox') else s.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def difference(a,b):return a.cut(b).Volume+b.cut(a).Volume

def contours(s):
    plane=Part.makePlane(30,48,C.V(0,-8,-4),C.V(1,0,0),C.V(0,1,0));out=[]
    for e in s.section(plane).Edges:
        pts=[v.Point for v in e.Vertexes] if isinstance(e.Curve,Part.Line) else e.discretize(Deflection=.035)
        for a,b in zip(pts,pts[1:]):out.append([[a.y,a.z],[b.y,b.z]])
    return out

def vertical(s,x,y):
    sec=s.common(Part.makeLine(C.V(x,y,-1),C.V(x,y,41)))
    return sorted([[e.BoundBox.ZMin,e.BoundBox.ZMax] for e in sec.Edges])

build=json.loads((R/'reports/build.json').read_text())
r['cad_sha256']=hashlib.sha256((R/'cad/slide-clips.FCStd').read_bytes()).hexdigest()
require(r['cad_sha256']==build['cad_sha256'],'CAD file matches this completed build')
r['recipe_sha256']={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in ('build.py','validate.py','final_features.py','clip_features.py','parameters.json')}
r['toolchain']={'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION}
d=App.openDocument(str(R/'cad/slide-clips.FCStd'))
for o in d.Objects:
    if isinstance(getattr(o,'Proxy',None),F.SlideFeature):o.touch()
d.recompute();p=F.values(d.Parameters);F.check(p);r['parameters']=p
r['mandatory_refinement']={'rear_groove_tool_datum_y_mm':p['ReleaseRearY'],
 'shift_vs_nominal_mm':p['ReleaseRearY']-p['CaseDepth'],
 'reason':'Align tool mouths to raw float32 rear face, avoiding a 0.000010376 mm tessellation sliver. CAD-only datum registration; no STL hole patching or dropped intersections.',
 'nominal_clip_sites_unchanged':True}
profile=F.measured_profile(d.Top);r['profile_segments_yz_mm']=profile
for o in d.Objects:
    if hasattr(o,'Shape'):
        require(o.Shape.isValid() and o.Shape.isClosed() and not any(x in ('Error','Invalid') for x in o.State)
                and (getattr(o,'Kind','').endswith('Tools') or len(o.Shape.Solids)==1),
                'Reopened/recomputed valid closed feature '+o.Name,solids=len(o.Shape.Solids),state=list(o.State),bounds_mm=bounds(o.Shape))
raw={'Bottom':d.ReleaseBottom.Shape,'Top':d.ReleaseTop.Shape};sh={'Bottom':d.Bottom.Shape,'Top':d.Top.Shape}
for name in raw:
    src=R.parent/build['source_provenance'][name]['raw_stl']
    require(hashlib.sha256(src.read_bytes()).hexdigest()==build['source_provenance'][name]['source_sha256'],'Untouched source hash '+name)
    cache=R/'.cache'/f'release-{name.lower()}.brep';q=Part.Shape();q.read(str(cache))
    require(hashlib.sha256(cache.read_bytes()).hexdigest()==build['source_provenance'][name]['cache_sha256'],'Fresh raw conversion cache hash '+name)
    clear(difference(raw[name],q),'Reopened frozen reference identical to fresh raw conversion '+name)
ob=bounds(Part.makeCompound(list(raw.values())));nb=bounds(Part.makeCompound(list(sh.values())))
clips=[d.getObject('Clip'+s).Shape for s in 'ABCD'];allbounds=bounds(Part.makeCompound(list(sh.values())+clips))
pairbounds=bounds(Part.makeCompound(list(sh.values())+[clips[0],clips[3]]))
r['envelope']={'original_bounds_mm':ob,'body_bounds_mm':nb,'body_dimensions_mm':[nb[i+3]-nb[i] for i in range(3)],
               'four_clip_bounds_mm':allbounds,'four_clip_dimensions_mm':[allbounds[i+3]-allbounds[i] for i in range(3)],
               'diagonal_pair_dimensions_mm':[pairbounds[i+3]-pairbounds[i] for i in range(3)],
               'projection_each_long_face_mm':6.1,'projection_under_base_mm':-allbounds[2]}
require(max(abs(a-b) for a,b in zip(ob,nb))<.0001,'Original body envelope unchanged',**r['envelope'])
require(max(abs(a-b) for a,b in zip(r['envelope']['four_clip_dimensions_mm'],[243.12,191.82,79.657895]))<.0001,'Selected fitted nominal clip envelope')
clear(sh['Bottom'].common(sh['Top']).Volume,'Zero inter-half seam material overlap')

# ALL changes must be within explicit groove/repair masks; no resized substitute shell.
for name in raw:
    top=name=='Top';grooves=d.getObject(name+'GrooveTools').Shape;repair=F.repair_mask(top)
    mask=Part.makeCompound([grooves,repair])
    old=raw[name].cut(mask);new=sh[name].cut(mask)
    require(difference(old,new)<1e-4,'Whole shell unchanged outside explicit groove and repair masks '+name,
            removed_mm3=old.cut(new).Volume,added_mm3=new.cut(old).Volume)
    clear(sh[name].cut(raw[name]).cut(repair).Volume,'No added material outside authorized fills '+name)
    clear(raw[name].cut(sh[name]).cut(grooves).Volume,'No removed material outside four shallow grooves '+name)
    clear(grooves.common(repair).Volume,'Grooves cannot reopen filled magnet/engraving patches '+name)

# Independent important interfaces, not merely a bounding box check.
regions=[]
for x in (17.42,225.7):
    for y in (17.42,162.2):regions.append(('Bottom','PCB hole/recess '+str((x,y)),C.box(x-4.5,x+4.5,y-4.5,y+4.5,0,15.01)))
for y in (20,119.62):regions.append(('Bottom','Underside mounting relief '+str(y),C.box(19.56,223.56,y,y+40,0,7.4)))
for x in (-.1,230.92):
    for y in (53.9,123.52):regions.append(('Bottom','Connector notch '+str((x,y)),C.box(x,x+12.3,y,y+2.2,7.9,15.1)))
for x,y in ((8.5,23),(8.5,107.62),(229.62,107.62)):
    regions.append(('Top','Connector/mount slot '+str((x,y)),C.box(x,x+5,y,y+49,17.5,28.5)))
regions.append(('Top','Complete original alignment skirt Z14..14.999',C.box(-1,245,-1,181,14,14.999)))
regions.append(('Bottom','Unchanged cavity floor outside engraving',C.box(14,229,14,165,7.99,8.01).cut(F.repair_mask(False))))
regions.append(('Top','Unchanged cavity roof outside engraving',C.box(14,229,14,165,74.99,75.01).cut(F.repair_mask(True))))
for name,label,region in regions:
    a=raw[name].common(region);b=sh[name].common(region)
    require(a.Volume>0 and difference(a,b)<1e-4,'Original interface preserved: '+label,original_volume_mm3=a.Volume,difference_mm3=difference(a,b))
r['magnet_fills']=[]
for name,z,mz in [('Bottom',13.4,14.8),('Top',15.05,15.01)]:
    for x,y in F.magnet_centres():
        core=Part.makeCylinder(2.5,1.5,C.V(x,y,z));mouth=Part.makeCylinder(3.09,.19,C.V(x,y,mz))
        row={'half':name,'centre_mm':[x,y],'core_missing_mm3':core.Volume-sh[name].common(core).Volume,
             'mouth_missing_mm3':mouth.Volume-sh[name].common(mouth).Volume};r['magnet_fills'].append(row)
        require(abs(row['core_missing_mm3'])<TOL and abs(row['mouth_missing_mm3'])<TOL,'Filled final magnet pocket '+name+str((x,y)),**row)
for name,probe in [('Bottom',C.box(43,193,79,104,7.98,8)),('Top',C.box(60,180,80,100,75,75.02))]:
    clear(probe.Volume-sh[name].common(probe).Volume,'Cosmetic engraving flush to original floor/roof '+name)

# Real full-local-height coupons: no added mount, jig, weakened generic block.
for name in sh:
    crop=sh[name].common(F.coupon_region(p)).removeSplitter();coupon=d.getObject('Coupon'+name).Shape
    clear(difference(crop,coupon),'Coupon EXACT final shell crop '+name)
    require(coupon.isValid() and len(coupon.Solids)==1,'Coupon one separately printable solid '+name)
r['coupon']={'site':'A','crop_bounds_mm':bounds(F.coupon_region(p)),
             'local_wall_curve_finishes_z_mm':27.5,'straight_wall_retained_to_z_mm':40,
             'unaltered_straight_wall_above_curve_mm':12.5,'base_entire_height_mm':15,
             'lid_local_height_mm':26,'required_parts':['coupon_bottom','coupon_lid','clip_nominal'],
             'jig_required':False,'warning':'Exact local fit/bending-section coupon, NOT a global case torsion/load substitute.'}
# Verify existing 4 mm straight lid wall is retained above its complete flare.
straight=C.box(20,44,10.01,13.99,27.6,39.99)
clear(straight.Volume-d.CouponTop.Shape.common(straight).Volume,'Coupon retains full existing straight wall above curvature')

variants=[('nominal',d.UniversalClip.Shape,p['InterferencePerJaw'],1.2),
          ('looser',d.ClipLooser.Shape,p['InterferencePerJaw']-p['FitStepPerJaw'],1.2),
          ('tighter',d.ClipTighter.Shape,p['InterferencePerJaw']+p['FitStepPerJaw'],2.8)]
r['fit_variants']={name:{'interference_per_jaw_mm':i,'total_interference_mm':2*i,
                        'throat_delta_vs_nominal_mm':-2*(i-p['InterferencePerJaw']),
                        'lower_first_contact_outward_offset_mm':max(0,i/(p['BottomDepth']/p['BottomRunout'])),
                        'upper_first_contact_outward_offset_mm':max(0,i/p['TopBearingSlope'])} for name,s,i,c in variants}
# Exact translational swept volumes: endpoints + every transverse boundary face
# extruded along withdrawal. All clip side faces are planar or monotone root arcs;
# their sweeps cover the continuous path, not just the tabulated sample offsets.
def rigid_sweep(shape,clear_at):
    delta=9-clear_at;pieces=[shape,C.moved(shape,y=-delta)]
    for face in shape.Faces:
        u0,u1,v0,v1=face.ParameterRange
        normal=face.normalAt((u0+u1)/2,(v0+v1)/2)
        if abs(normal.y)>1e-7:
            q=face.extrude(C.V(0,-delta,0))
            if abs(q.Volume)>1e-9:
                assert q.isValid() and len(q.Solids)==1
                pieces.append(q)
    swept=pieces[0].multiFuse(pieces[1:]).removeSplitter()
    assert swept.isValid() and len(swept.Solids)==1
    return C.moved(swept,y=-clear_at)
sweeps={name:rigid_sweep(shape,0 if name=='looser' else clear_at) for name,shape,i,clear_at in variants}
# Explicit clearance surrogate, never substituted for the actual printable free shape.
sur=dict(p);sur['InterferencePerJaw']=-.02;test=C.clip(sur)
for idx,(x,rear) in enumerate(F.stations(p)):
    row={'id':'ABCD'[idx],'centre_x_mm':x,'edge_y_mm':p['CaseDepth'] if rear else 0,
         'insertion_vector':[0,-1 if rear else 1,0],'rigid_motion':{},'geometric_capture':{}}
    row['continuous_rigid_sweeps']={}
    for name,shape,interference,clear_at in variants:
        swept=C.at_site(sweeps[name],x,rear,p)
        sweep_volumes={n:swept.common(s).Volume for n,s in sh.items()}
        require(max(abs(v) for v in sweep_volumes.values())<TOL,'Continuous straight approach AND withdrawal '+row['id']+' '+name,
                outward_interval_mm=[0 if name=='looser' else clear_at,9],**sweep_volumes)
        row['continuous_rigid_sweeps'][name]={'outward_interval_mm':[0 if name=='looser' else clear_at,9],'intersection_mm3':sweep_volumes}
        samples=[]
        for withdrawal in (9,4,2.8,1.5,1.2,1,.5,0):
            q=C.at_site(C.moved(shape,y=-withdrawal),x,rear,p)
            vols={n:q.common(s).Volume for n,s in sh.items()}
            samples.append({'outward_offset_mm':withdrawal,'intersection_mm3':vols,
                            'meaning':'rigidly clear approach/withdrawal' if withdrawal>=clear_at else 'terminal region: elastic preload if positive'})
            if withdrawal>=clear_at or name=='looser':
                require(max(abs(v) for v in vols.values())<TOL,'Same-groove approach/withdrawal '+row['id']+' '+name+' @'+str(withdrawal),**vols)
            if withdrawal==0 and interference>0:
                require(min(vols.values())>TOL,'Quantified intentional terminal preload '+row['id']+' '+name,**vols)
        row['rigid_motion'][name]=samples
    q=C.at_site(test,x,rear,p)
    neutral={n:q.common(s).Volume for n,s in sh.items()}
    lift=q.common(C.moved(sh['Top'],z=.3)).Volume;drop=q.common(C.moved(sh['Bottom'],z=-.3)).Volume
    require(max(abs(v) for v in neutral.values())<TOL,'Explicit .02 gap surrogate clear '+row['id'],**neutral)
    require(lift>1 and drop>1,'Surrogate captures BOTH halves at .3 separation '+row['id'],lid_lift_mm3=lift,base_drop_mm3=drop)
    row['geometric_capture']={'gap_per_jaw_mm':.02,'initial_intersection_mm3':neutral,'lid_lift_0.30mm_blocked_volume_mm3':lift,
                              'base_drop_0.30mm_blocked_volume_mm3':drop,'strength_force_friction_proven':False}
    # Independent line probes on FINAL lid, at all four sites.
    thickness=[]
    for inward in (1.51,2,3,4,5,6,7):
        intervals=vertical(sh['Top'],x,p['CaseDepth']-inward if rear else inward)
        thickness.extend(b-a for a,b in intervals)
    row['minimum_remaining_lid_vertical_material_mm']=min(thickness)
    require(min(thickness)>=2.1707,'Actual remaining lip at least 2.1707 mm '+row['id'],minimum_mm=min(thickness))
    r['sites'].append(row);write();print('SITE PASS',row['id'],flush=True)
r['diagonal_pair']={'sites':['A','D'],'both_halves_geometrically_captured':True,'carrying_strength_certified':False,'tabletop_stability_tested':False}
r['grooves']={'bottom_max_depth_mm':p['BottomDepth'],'bottom_runout_mm':p['BottomRunout'],
 'top_max_vertical_depth_mm':max(C.outer_profile(profile,y)-(p['TopBearingZ']+p['TopBearingSlope']*y) for y in [i/100 for i in range(401)]),
 'top_runout_mm':p['TopRunout'],'bottom_floor_reserve_conservative_mm':8-p['BottomDepth'],
 'minimum_remaining_lid_vertical_material_mm':min(s['minimum_remaining_lid_vertical_material_mm'] for s in r['sites']),
 'original_skirt_thickness_mm':1.5,'mouth_width_mm':p['GrooveMouthWidth'],'running_width_mm':p['GrooveRunningWidth'],
 'minimum_side_clearance_mm':(p['GrooveRunningWidth']-p['ClipWidth'])/2}
r['binding']={'pure_friction_wedge':True,'positive_detent':False,'nominal_elastic_throat_spread_mm':2*p['InterferencePerJaw'],
 'bottom_ramp_degrees':math.degrees(math.atan(p['BottomDepth']/p['BottomRunout'])),
 'top_ramp_degrees':math.degrees(math.atan(p['TopBearingSlope'])),
 'force_or_friction_calculated':False}

# Live document edit/restoration of FIT and THICKNESS, plus a shell/coupon groove edit.
v0=d.UniversalClip.Shape.Volume;dims0=bounds(d.UniversalClip.Shape);shell0=d.Bottom.Shape.Volume
old=float(d.Parameters.InterferencePerJaw);d.Parameters.InterferencePerJaw=old+.01;d.recompute();v1=d.UniversalClip.Shape.Volume
require(abs(v1-v0)>.01 and abs(d.Bottom.Shape.Volume-shell0)<TOL,'Live editable throat recomputes clip without changing shells',volume_delta_mm3=v1-v0)
d.Parameters.InterferencePerJaw=old;d.recompute();clear(abs(d.UniversalClip.Shape.Volume-v0),'Live throat restoration')
old=float(d.Parameters.JawThickness);d.Parameters.JawThickness=old+.05;d.recompute();v1=d.UniversalClip.Shape.Volume
require(v1-v0>.1,'Live jaw thickness recompute',delta_mm3=v1-v0)
d.Parameters.JawThickness=old;d.recompute();clear(abs(d.UniversalClip.Shape.Volume-v0),'Live jaw restoration')
old=float(d.Parameters.BottomDepth);cb0=d.CouponBottom.Shape.Volume
d.Parameters.BottomDepth=old+.01;d.recompute();changed=d.Bottom.Shape.Volume;cb1=d.CouponBottom.Shape.Volume
require(changed<shell0 and cb1<cb0,'Live groove edit propagates to full final shell and exact coupon',shell_delta_mm3=changed-shell0,coupon_delta_mm3=cb1-cb0)
d.Parameters.BottomDepth=old;d.recompute();clear(abs(d.Bottom.Shape.Volume-shell0),'Live groove restoration')
clear(abs(d.CouponBottom.Shape.Volume-cb0),'Live coupon restoration')

# Read ACTUAL binary files, enforce all mandatory topology checks and bed Z=0.
# Independently remesh recomputed final shape to ensure exported geometry is current.
expected=set(build['exports'])
require({q.stem for q in (R/'stl').glob('*.stl')}==expected,'Exact seven final STL exports; no stale extra files')
for stem,(name,kind) in build['exports'].items():
    path=R/'stl'/f'{stem}.stl';mesh=Mesh.Mesh(str(path));b=mesh.BoundBox
    row={'closed':mesh.isSolid(),'nonmanifold':mesh.hasNonManifolds(),'inconsistent_normals':mesh.hasNonUniformOrientedFacets(),
         'self_intersections':mesh.hasSelfIntersections(),'components':mesh.countComponents(),'facets':mesh.CountFacets,
         'bounds_mm':bounds(mesh),'dimensions_mm':[b.XLength,b.YLength,b.ZLength],'bed_z_mm':b.ZMin,
         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    r['written_STLs'][path.name]=row
    require(row['closed'] and not row['nonmanifold'] and not row['inconsistent_normals'] and not row['self_intersections'] and row['components']==1,
            'Written STL closed/manifold/oriented/no-self-intersection/one-component '+path.name,**row)
    require(abs(b.ZMin)<TOL,'Written STL bed Z0 '+path.name,bed_z_mm=b.ZMin)
    shape=F.bed_shape(d.getObject(name).Shape,kind)
    out=R/'.cache'/('verify-'+stem+'.stl')
    MeshPart.meshFromShape(Shape=shape,LinearDeflection=p['MeshLinearDeflection'],AngularDeflection=p['MeshAngularDeflection'],Relative=False).write(str(out))
    require(path.read_bytes()==out.read_bytes(),'Written STL byte-identical to independently remeshed reopened final '+path.name)
    print('STL PASS',path.name,flush=True)
# Actual sections support the annotated preview, not stylized generic proxy profiles.
r['section_edges_yz_mm']={n.lower():contours(F.to_local(d.getObject('Coupon'+n).Shape,p)) for n in sh}
r['section_edges_yz_mm']['clip']=contours(d.UniversalClip.Shape)
r['original_section_edges_yz_mm']={n.lower():contours(F.to_local(s.common(F.coupon_region(p)),p)) for n,s in raw.items()}
r['short_edge_connector_scan']=[]
for x in (.1,p['CaseWidth']-.1):
    q=sh['Bottom'].common(Part.makeLine(C.V(x,-1,12),C.V(x,p['CaseDepth']+1,12)))
    runs=sorted([[e.BoundBox.YMin,e.BoundBox.YMax] for e in q.Edges]);gaps=[[runs[i][1],runs[i+1][0]] for i in range(len(runs)-1) if runs[i+1][0]-runs[i][1]>.1]
    r['short_edge_connector_scan'].append({'edge':'left' if x<1 else 'right','opening_y_intervals_mm':gaps})
r['checks_passed']=sum(x['pass'] for x in r['checks']);r['checks_total']=len(r['checks'])
r['status']='PASS - final computational geometry only; physical tests REQUIRED' if not r['failures'] else 'BLOCKED - mandatory check failed'
write();App.closeDocument(d.Name)
print(r['status'],r['checks_passed'],'/',r['checks_total'],'seconds',r['seconds'],flush=True)
assert not r['failures'],'Mandatory final checks failed; see reports/validation.json'
