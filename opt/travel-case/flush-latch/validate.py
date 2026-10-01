#!/usr/bin/env python3
"""Enforced checks of reopened FINAL full CAD, written meshes, and real coupon.
No FEA, rigid snap-flex pretense, self-intersection deletion, or disabled checks.
Failures are recorded and cause nonzero exit. Collision tolerance 1e-5 mm^3.
"""
import hashlib
import json
from pathlib import Path
import time
import FreeCAD as App
import Part
import Mesh
import latch_features as F
R=Path(__file__).resolve().parent
r={'status':'RUNNING','checks':[],'failures':[],'limitations':[
    'Snap regions use explicit elastic clearance surrogates, not real deformed-beam/FEA verification.',
    'Physical print, slicer fit, force, load, drop, creep and fatigue are untested; coupon is REQUIRED.',
    'Frozen faceted release references are faithful meshes, not recovered Fusion parametric history.',
    'Latch retains but does NOT compressively seal; nominal seam lift before bearing contact 0.6 mm.'
]}
start=time.monotonic()


def write():
    r['seconds']=time.monotonic()-start
    (R/'reports/validation.json').write_text(json.dumps(r,indent=2)+'\n')


def require(ok,label,**data):
    row={'test':label,'pass':bool(ok),**data};r['checks'].append(row)
    if not ok:r['failures'].append(row);print('FAIL',label,data,flush=True)
    write()


def clear(volume,label,**data):
    require(abs(volume)<1e-5,label,intersection_mm3=volume,**data)


def hit(volume,label,**data):
    require(volume>1e-5,label,blocking_intersection_mm3=volume,**data)


def bbox(s):
    # OCC BoundBox may overbound the untrimmed underlying tool surfaces. Use
    # optimal (trim-aware) bounds AND independent written-mesh measurements.
    b=s.optimalBoundingBox();return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]


def contact_area(s,t,z):
    def faces(q):
        return [a for a in q.Faces if abs(a.BoundBox.ZMin-z)<1e-5 and abs(a.BoundBox.ZMax-z)<1e-5]
    return sum(a.common(b).Area for a in faces(s) for b in faces(t))


r['cad_sha256']=hashlib.sha256((R/'cad/flush-latch.FCStd').read_bytes()).hexdigest()
r['recipe_sha256']={name:hashlib.sha256((R/name).read_bytes()).hexdigest() for name in ('latch_features.py','parameters.json','build.py','validate.py')}
r['FreeCAD']=App.Version();r['OCC']=Part.OCC_VERSION
d=App.openDocument(str(R/'cad/flush-latch.FCStd'))
for o in d.Objects:
    if isinstance(getattr(o,'Proxy',None),F.LatchFeature):o.touch()
d.recompute();p=F.values(d.Parameters);F.check(p)
final=[d.Bottom,d.Top]+[d.getObject(n+str(i)) for n in ('Slider','Gate') for i in range(1,5)]
for o in final+[d.CouponBottom,d.CouponTop]:
    require(o.Shape.isValid() and len(o.Shape.Solids)==1 and o.Shape.isClosed(),
            'Reopened/recomputed single valid closed solid '+o.Name,solids=len(o.Shape.Solids),bounds_mm=bbox(o.Shape))
a=d.SliderPrototype.Shape.Volume
d.Parameters.HookThickness=2.01;d.recompute();b=d.SliderPrototype.Shape.Volume
d.Parameters.HookThickness=2.;d.recompute();c=d.SliderPrototype.Shape.Volume
require(b-a>.01 and abs(c-a)<1e-7,'Editable proxy thickness change/restoration',edit_delta_mm3=b-a,restored_error_mm3=c-a)
raw={'Bottom':d.ReleaseBottom.Shape,'Top':d.ReleaseTop.Shape}
sh={'Bottom':d.Bottom.Shape,'Top':d.Top.Shape}
original=Part.makeCompound([raw['Bottom'],raw['Top']])
actual=Part.makeCompound([o.Shape for o in final])
ob=bbox(original);nb=bbox(actual)
r['envelope']={'nominal_mm':[243.12,179.62,77.5],'original_bounds_mm':ob,'final_bounds_mm':nb,
               'original_dimensions_mm':[ob[i+3]-ob[i] for i in range(3)],
               'final_dimensions_mm':[nb[i+3]-nb[i] for i in range(3)]}
require(max(abs(x-y) for x,y in zip(ob,nb))<.0001,'Exact original assembly envelope',**r['envelope'])
clear(sh['Top'].common(sh['Bottom']).Volume,'Zero bottom/lid seam material overlap')

# Explicit ALL-change masks, and smaller independent interface neighborhoods.
for name in ('Bottom','Top'):
    mask=F.fuse([F.repair_mask(name=='Top')]+[F.at(F.bottom_tools(p) if name=='Bottom' else F.top_tools(p),s) for s in F.stations(p)])
    outside0=raw[name].cut(mask);outside1=sh[name].cut(mask)
    removed=outside0.cut(outside1).Volume;added=outside1.cut(outside0).Volume
    require(abs(removed)<1e-4 and abs(added)<1e-4,'Whole-shell unchanged outside explicit repair/latch masks '+name,
            removed_mm3=removed,added_mm3=added)
    # No ADDED shell material except specifically authorized filled recesses.
    added_elsewhere=sh[name].cut(raw[name]).cut(F.repair_mask(name=='Top')).Volume
    clear(added_elsewhere,'No external box/substitution/addition '+name)

regions=[]
for x in (17.42,225.7):
    for y in (17.42,162.2):regions.append(('Bottom','PCB mounting hole/recess '+str((x,y)),F.box(x-4.5,x+4.5,y-4.5,y+4.5,0,15.01)))
for y in (20,119.62):regions.append(('Bottom','Underside mounting relief '+str(y),F.box(19.56,223.56,y,y+40,0,7.4)))
for x in (-.1,230.92):
    for y in (53.9,123.52):regions.append(('Bottom','Connector notch '+str((x,y)),F.box(x,x+12.3,y,y+2.2,7.9,15.1)))
for x,y in ((8.5,23),(8.5,107.62),(229.62,107.62)):
    regions.append(('Top','Connector/mounting slot '+str((x,y)),F.box(x,x+5,y,y+49,17.5,28.5)))
# Intact alignment skirt: no magnet patch touches its occupied Y<1.5 band.
regions.append(('Top','Complete alignment skirt Z14..14.999',F.box(-1,245,-1,181,14,14.999)))
for name,label,region in regions:
    s=raw[name].common(region);q=sh[name].common(region)
    a=s.cut(q).Volume;b=q.cut(s).Volume
    require(s.Volume>0 and abs(a)<1e-4 and abs(b)<1e-4,label,original_volume_mm3=s.Volume,removed_mm3=a,added_mm3=b)

r['magnet_fills']=[]
for name,z,mouthz in [('Bottom',13.4,14.8),('Top',15.05,15.01)]:
    for x,y in F.magnet_centres():
        core=Part.makeCylinder(2.5,1.5,F.V(x,y,z));mouth=Part.makeCylinder(3.09,.19,F.V(x,y,mouthz))
        missing=core.Volume-sh[name].common(core).Volume
        mm=mouth.Volume-sh[name].common(mouth).Volume
        row={'half':name,'center_mm':[x,y],'core_missing_mm3':missing,'mouth_missing_mm3':mm}
        r['magnet_fills'].append(row)
        require(abs(missing)<1e-5 and abs(mm)<1e-5,'Magnet cavity and mouth filled '+name+str((x,y)),**row)
for name,probe in [('Bottom',F.box(43,193,79,104,7.98,8)),('Top',F.box(60,180,80,100,75,75.02))]:
    clear(probe.Volume-sh[name].common(probe).Volume,'Only defective engraving filled flush '+name)

# Exterior/profile verification beyond bounding-box equality. Outside the explicitly
# recessed actuator relief mouth, the extreme original profile along each original
# long wall MUST agree at all 4 stations, for bottom/flared skirt/straight lid.
r['outside_profile_samples']=[]
for site in F.stations(p):
    sx,sy,tx,ty=site
    for u in (-16,-11,-5,3,10,20,28):
        x=tx+sx*u
        for z in (1,7.9,9,12,13.3,14.5,14.9,15.1,16,17,18,19,19.7,20,21,22,23.5,26,40,74.9,77.49):
            name='Bottom' if z<15 else 'Top'
            line=Part.makeLine(F.V(x,ty+sy*(-.5),z),F.V(x,ty+sy*14,z))
            def outer(q):
                es=q.common(line).Edges
                pts=[sy*(v.Point.y-ty) for e in es for v in e.Vertexes]
                return min(pts) if pts else None
            a=outer(raw[name]);b=outer(sh[name])
            # Explicit access relief only: paddle well and the surrounding spring
            # relief where it meets the actual flare, not a larger case envelope.
            access=(name=='Top' and -3.30001<=u<=26.30001 and 15<=z<=19.90001)
            ok=a is not None and b is not None and (abs(a-b)<1e-4 or access)
            r['outside_profile_samples'].append({'x_mm':x,'side':sy,'z_mm':z,'original_outward_y_mm':a,'final_outward_y_mm':b,'explicit_access_well':access,'pass':ok})
    # Check normal gate still occupies ORIGINAL wall, not the larger profile mask.
    gate=d.getObject('Gate'+str(F.stations(p).index(site)+1)).Shape
    clear(gate.cut(original).Volume,'Gate inside actual original occupied wall '+str(site))
require(all(a['pass'] for a in r['outside_profile_samples']),'Sampled original outside flared/straight profiles preserved except explicit actuator wells',samples=len(r['outside_profile_samples']))

sl=d.SliderPrototype.Shape;ga=d.GatePrototype.Shape
paddle=sl.common(F.box(8,18,-1,8.1,15.5,19.7));rigid=sl.cut(F.tooth(p));assembly_rigid=rigid.cut(paddle)
head=F.box(-10,18,p['RailOuterY'],p['RailInnerY'],18,22)
r['stations']=[]
require(9.6-(p['StemInnerY']+p['RunningClearance'])>=1.19999,'Bottom continuous inner skin >=1.2 mm',skin_mm=9.6-(p['StemInnerY']+p['RunningClearance']))
require(14-12.7>=1.29999,'Lid continuous inner skin >=1.3 mm including gate seats',skin_mm=14-12.7)
require(p['StemInnerY']-p['StemOuterY']>=1.69999,'Rigid stem retained at 1.7 mm',thickness_mm=p['StemInnerY']-p['StemOuterY'])
for i,site in enumerate(F.stations(p)):
    top=sh['Top'];bottom=sh['Bottom'];g=F.at(ga,site)
    row={'site':site,'travel':[],'unlocked_lift':[],'assembly':[]}
    clear(g.common(top).Volume,'Gate seated/lid clearance '+str(i))
    clear(g.common(bottom).Volume,'Gate/bottom seam clearance '+str(i))
    for travel in (0,.25,.5,1,2,3,4,5,6,7,7.5,7.75,8):
        q=F.at(F.moved(sl,x=travel),site)
        rr=F.at(F.moved(rigid,x=travel),site)
        tt=F.at(F.moved(F.tooth(p),x=travel,y=p['ReleasePress']),site)
        pp=F.at(F.moved(paddle,x=travel,y=p['ReleasePress']),site)
        data={'travel_mm':travel,'rigid_lid_mm3':rr.common(top).Volume,'bottom_mm3':q.common(bottom).Volume,
              'gate_mm3':q.common(g).Volume,'released_tooth_lid_mm3':tt.common(top).Volume,
              'pressed_paddle_lid_mm3':pp.common(top).Volume,'outside_original_mm3':q.cut(original).Volume,
              'pressed_tooth_outside_original_mm3':tt.cut(original).Volume,'pressed_paddle_outside_original_mm3':pp.cut(original).Volume}
        row['travel'].append(data)
        require(all(abs(v)<1e-5 for k,v in data.items() if k!='travel_mm'),'Pressed travel/actual-original-material station '+str(i)+' travel '+str(travel),**data)
        if travel in (0,8):clear(q.common(top).Volume,'Unpressed endpoint clearance '+str((i,travel)))
    for travel,departure in ((0,.4),(8,-.4)):
        hit(F.at(F.moved(sl,x=travel+departure),site).common(top).Volume,'Unpressed positive square position stop '+str((i,travel)))
    for z in (0,.2,.3,.6,1,2,3,4.6,6,15):
        # Entire lid-carried set separates without sliding, from retained OPEN.
        q=F.at(F.moved(sl,z=z),site)
        v=q.common(bottom).Volume;row['unlocked_lift'].append({'z_mm':z,'collision_mm3':v})
        clear(v,'OPEN insertion/lift keyway station '+str(i)+' z '+str(z))
    hit(F.at(F.moved(sl,x=8,z=.31),site).common(bottom).Volume,'LOCKED toe/shelf separation block '+str(i))
    # Static head/rail and rigid gate load contacts: no release spring in this path.
    hit(F.at(F.moved(head,z=-.31),site).common(g).Volume,'Head against 1.7 mm gate/rail floor '+str(i))
    hit(F.at(F.moved(ga,z=-.01),site).common(top).Volume,'Rigid gate tongues against integral lid lands '+str(i))
    hit(F.at(F.moved(head,z=.31),site).common(top).Volume,'Captive head upward escape blocked '+str(i))
    hit(F.at(F.moved(head,y=-.31),site).common(top).Volume,'Captive head radial escape blocked '+str(i))
    hit(F.at(F.moved(rigid,x=-.31),site).common(g).Volume,'Released slider outward axial escape blocked by gate '+str(i))
    hit(F.at(F.moved(rigid,x=8.31),site).common(top).Volume,'Released slider inward axial escape blocked by far wall '+str(i))

    # Seam-side service assembly: head up through the removable rail floor,
    # then gate up at -3 mm, +3 mm bayonet seat and paired detents release.
    # Gate fingers are explicitly translated elastic SURROGATES, not rigid snaps.
    for z in (-14,-10,-7,-5,-3,-2,-1,-.5,0):
        v=F.at(F.moved(assembly_rigid,x=-11,z=z),site).common(top).Volume+F.at(F.moved(paddle,x=-11,y=p['ReleasePress'],z=z),site).common(top).Volume+F.at(F.moved(F.tooth(p),x=-11,y=p['ReleasePress'],z=z),site).common(top).Volume
        row['assembly'].append({'slider_z_mm':z,'collision_mm3':v})
        clear(v,'Slider pressed seam-side assembly gate removed (elastic surrogate) '+str((i,z)))
    for travel in (-11,-10,-8,-6,-4,-2,-1,0):
        rr=F.at(F.moved(rigid,x=travel),site);tt=F.at(F.moved(F.tooth(p),x=travel,y=p['ReleasePress']),site)
        clear(rr.common(top).Volume+tt.common(top).Volume,'Slider tangential assembly after seam insert '+str((i,travel)))
    gr,ge=F.gate(p,True)
    for z in (-12,-8,-6,-4,-2,-1,-.5,0):
        q=F.at(F.moved(gr,x=-3,z=z),site);e=F.at(F.moved(ge,x=-3,z=z),site)
        v=q.common(top).Volume+e.common(top).Volume
        row['assembly'].append({'gate_z_mm':z,'gate_x_mm':-3,'pressed_surrogate_collision_mm3':v})
        clear(v,'Gate seam insertion (elastic surrogate) '+str((i,z)))
    for x in (-3,-2.75,-2.5,-2,-1.5,-1,-.5,-.25,0):
        q=F.at(F.moved(gr,x=x),site);e=F.at(F.moved(ge,x=x),site)
        v=q.common(top).Volume+e.common(top).Volume
        vs=q.common(F.at(sl,site)).Volume+e.common(F.at(sl,site)).Volume
        row['assembly'].append({'gate_x_mm':x,'pressed_surrogate_lid_collision_mm3':v,'slider_collision_mm3':vs})
        clear(v,'Gate pressed bayonet seating '+str((i,x)))
        clear(vs,'Gate install with slider present '+str((i,x)))
    hit(F.at(F.moved(ga,x=-.4),site).common(top).Volume,'Released gate square detents prevent bayonet reversal '+str(i))
    # Actual measured areas at planar contacts, not just nominal rectangle claims.
    toe_area=contact_area(F.at(F.moved(sl,x=8,z=.3),site),bottom,12.7)
    head_area=contact_area(F.at(F.moved(head,z=-.3),site),g,17.7)
    gate_area=contact_area(g,top,16.5)
    row['load_contacts_mm2']={'toe_shelf':toe_area,'head_floor':head_area,'gate_tongues_lid':gate_area}
    require(toe_area>=14.9999 and head_area>=67.1999 and gate_area>=6.,'Measured rigid load contact areas '+str(i),**row['load_contacts_mm2'])
    r['stations'].append(row);write()

for name in ('Bottom','Top'):
    # Exact same-geometry fit coupon: no generic substituted box.
    q=d.getObject('Coupon'+name).Shape
    crop=F.moved(sh[name].common(F.box(24,77,0,14,8,26)),-47)
    clear(q.cut(crop).Volume+crop.cut(q).Volume,'Coupon identical to final actual shell crop '+name)

# Nominal cantilever small-deflection estimates, ASSUMED isotropic modulus,
# NOT measured PETG properties/print certification or fatigue/load prediction.
r['elastic_assumptions']={}
for name,L,t,h,deflection,count in [('slider',16.6,1.2,1.2,.8,1),('gate_fingers',6.2,.8,.9,.5,2)]:
    I=h*t**3/12;strain=3*t*deflection/(2*L**2)
    forces=[count*3*E*I*deflection/L**3 for E in (1200,2200)]
    r['elastic_assumptions'][name]={'effective_length_mm':L,'bending_thickness_mm':t,'beam_width_mm':h,'deflection_mm':deflection,
        'peak_nominal_strain_fraction':strain,'assumed_E_MPa':[1200,2200],'estimated_force_N_range':forces,
        'model':'linear cantilever; stress concentration/print anisotropy/friction/creep/fatigue NOT validated'}
    require(strain<.02,'Nominal bending strain below assumed 2% design screen '+name,nominal_strain_fraction=strain)

# Sensitivity: loading at the lower barb rather than the finger tip shortens
# the assumed bending length. This is NOT covered by the nominal 2% screen.
r['elastic_assumptions']['gate_fingers']['shorter_load_point_sensitivity']={'effective_length_mm':5.2,'deflection_mm':.5,'nominal_strain_fraction':3*.8*.5/(2*5.2**2),'warning':'Approx. 2.22%; real distributed loading/root stress could exceed nominal screen. Physical snap test REQUIRED.'}

r['written_STLs']={}
for path in sorted((R/'stl').glob('*.stl')):
    m=Mesh.Mesh(str(path));bb=m.BoundBox
    data={'closed':m.isSolid(),'nonmanifold':m.hasNonManifolds(),'inconsistent_normals':m.hasNonUniformOrientedFacets(),
          'self_intersections':m.hasSelfIntersections(),'components':m.countComponents(),'facets':m.CountFacets,
          'dimensions_mm':[bb.XLength,bb.YLength,bb.ZLength],'min_z_mm':bb.ZMin,
          'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    r['written_STLs'][path.name]=data
    require(data['closed'] and not data['nonmanifold'] and not data['inconsistent_normals'] and not data['self_intersections'] and data['components']==1,'Written STL strict mesh '+path.name,**data)
    require(abs(bb.ZMin)<1e-5 and max(bb.XLength,bb.YLength,bb.ZLength)<256,'Bed orientation/build volume '+path.name)

r['strength_fatigue_load_tested']=False;r['physical_fit_tested']=False;r['slicer_tested']=False
r['checks_passed']=sum(q['pass'] for q in r['checks']);r['checks_total']=len(r['checks'])
r['status']='PASS - computational geometry only; coupon/physical tests REQUIRED' if not r['failures'] else 'BLOCKED - see failures; do NOT claim a ready closure'
write();App.closeDocument(d.Name)
print(json.dumps({k:r[k] for k in ('status','checks_passed','checks_total','failures','envelope','elastic_assumptions')},indent=2),flush=True)
assert not r['failures'],'Enforced validation failures; see reports/validation.json'
