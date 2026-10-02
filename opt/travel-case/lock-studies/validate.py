#!/usr/bin/env python3
"""Enforced reopen, editable fits, ACTUAL STL checks, motion states, layer geometry.
No mesh repair, suppressed intersections, FEA, physical or slicer qualification.
"""
from pathlib import Path
import json,math,hashlib,time,traceback
import numpy as np
from shapely.geometry import Polygon,GeometryCollection
import FreeCAD as App
import Part,Mesh
import studies as S
R=Path(__file__).resolve().parent; start=time.monotonic(); tol=1e-5
r={'status':'RUNNING','checks':[],'motion':{},'stl':{},'limitations':[
 'UNPRINTED / UNSLICED: no installed Bambu/Orca/Prusa CLI found; no G-code generated.',
 'Snap motion is an explicit small-deflection kinematic surrogate with unchanged y and tip-slope head shear, NOT FEA; no material/force/strain claims.',
 'Finite motion samples do not prove arbitrary 3D manipulation; key neck/head rotational envelopes additionally checked analytically.',
 'No certified strength, retention, accidental push+turn resistance, fatigue, creep or case integration.',
 'Standalone analytical tabs/keepers, NOT faithful shell crops. Later real-section test mandatory.']}

def write():
    r['seconds']=round(time.monotonic()-start,3)
    (R/'reports/validation.json').write_text(json.dumps(r,indent=2)+'\n')

def require(ok,label,**kw):
    r['checks'].append({'test':label,'pass':bool(ok),**kw}); write()
    if not ok: raise AssertionError(label+' '+str(kw))

def clear(s,obstacles,label):
    vols=[s.common(o).Volume for o in obstacles]
    require(max([0]+list(map(abs,vols)))<tol,label,intersection_mm3=vols)
    return vols

def bounds(s):
    b=s.BoundBox; return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def local(o):
    s=o.Shape.copy(); s.Placement=o.Placement.inverse().multiply(s.Placement); return s

def plane_poly(shape,z):
    poly=GeometryCollection()
    for w in shape.slice(S.V(0,0,1),z):
        pts=w.discretize(Deflection=.015)
        # Only normalize numerical closure noise (~1e-14 mm) in 2D section sampling.
        # Does not alter native solid, STL, holes, intersections or mesh checks.
        coords=[(round(a.x,8),round(a.y,8)) for a in pts]
        q=Polygon(coords)
        assert q.is_valid,'Invalid section polygon'
        poly=poly.symmetric_difference(q)
    return poly

try:
    build_path=R/'.cache/build.json'
    build=json.loads(build_path.read_text()) if build_path.exists() else json.loads((R/'reports/validation.json').read_text())['build']
    r['build']=build
    require(hashlib.sha256((R/'cad/lock-studies.FCStd').read_bytes()).hexdigest()==build['cad_sha256'],'FCStd belongs to completed build')
    d=App.openDocument(str(R/'cad/lock-studies.FCStd'))
    for o in d.Objects:
        if isinstance(getattr(o,'Proxy',None),S.Coupon): o.touch()
    d.recompute(); p=S.values(d.Parameters); S.check(p); r['parameters']=p
    # Filename-only regression: no alternate geometry or exported variants.
    for gap,engagement in ((.6,.4),(.8,.6)):
        names=S.export_names(dict(p,HardwareTotalGap=gap,HookOverlap=engagement))
        expected={'C_MALE':'C_male_8.00', 'C_FEMALE':'C_female_G0.40_G0.60_G0.80',
                  'A_BASE':f'A_base_G{gap:.2f}', 'A_LID':f'A_lid_G{gap:.2f}',
                  'A_CLASP':f'A_clasp_E{engagement:.2f}_G{gap:.2f}',
                  'B_BASE':f'B_base_G{gap:.2f}', 'B_LID':f'B_lid_G{gap:.2f}',
                  'B_KEY':f'B_key_G{gap:.2f}'}
        require(names==expected,f'export_names: invariant C names and updated A/B at G{gap:.2f}',
                hardware_total_gap_mm=gap,hook_overlap_mm=engagement,export_names=names)
    shapes={k:local(d.getObject(k)) for k in S.KINDS}
    require(set(build['exports'])==set(S.KINDS) and len(list((R/'stl').glob('*.stl')))==8,'Exactly eight baseline STL pieces')
    for k,s in shapes.items():
        require(s.isValid() and s.isClosed() and len(s.Solids)==1 and s.Volume>0 and 'Error' not in d.getObject(k).State,
                'Reopened/recomputed single valid closed solid '+k,bounds_mm=bounds(s),volume_mm3=s.Volume)
        fresh=S.shape(k,p)
        require(s.cut(fresh).Volume+fresh.cut(s).Volume<tol,'Reopened shape matches analytical recipe including orientation '+k)
        bed=S.bed_shape(s,k); b=bed.BoundBox
        require(abs(b.ZMin)<1e-6 and max(b.XLength,b.YLength,b.ZLength)<60,'Small coupon / CAD bed Z0 '+k,bed_dimensions_mm=[b.XLength,b.YLength,b.ZLength])
        path=R/build['exports'][k]['file']; digest=hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest==build['exports'][k]['sha256'],'Written STL belongs to this build '+k)
        m=Mesh.Mesh(str(path)); pts,faces=m.Topology; xyz=np.array([[v.x,v.y,v.z] for v in pts]); tri=xyz[np.array(faces)]
        signed=float(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6)
        data={'file':str(path.relative_to(R)),'sha256':digest,'vertices':m.CountPoints,'triangles':m.CountFacets,
              'closed_solid':m.isSolid(),'connected_components':m.countComponents(),'non_manifold':m.hasNonManifolds(),
              'nonuniform_orientation':m.hasNonUniformOrientedFacets(),'self_intersection':m.hasSelfIntersections(),
              'signed_volume_mm3':signed,'cad_volume_mm3':bed.Volume,'bed_bounds_mm':bounds(m)}
        r['stl'][k]=data
        require(data['closed_solid'] and data['connected_components']==1 and not data['non_manifold'] and
                not data['nonuniform_orientation'] and not data['self_intersection'] and signed>0 and
                abs(m.BoundBox.ZMin)<1e-5 and abs(signed-bed.Volume)/bed.Volume<.005,
                'ACTUAL STL watertight / manifold / connected / no self-intersections / outward / bed0 '+k,**data)
        require(max(abs(a-b) for a,b in zip(bounds(m),bounds(bed)))<1e-4,'Written STL matches CAD bed orientation '+k)
    print('CAD + eight written meshes PASS',flush=True)

    # Gauge functional widths, above relief and away from lead-in / labels.
    rail=shapes['C_MALE'].common(S.box(-10,20,2,18,1,4))
    require(abs(rail.BoundBox.XLength-8)<tol,'Gauge rail 8.00 mm measured on bearing lands',width_mm=rail.BoundBox.XLength)
    x=2.4; rows=[]
    for gap in p['GaugeGaps']:
        w=8+gap; probe=S.box(x,x+w,1,19,1,4)
        clear(probe,[shapes['C_FEMALE']],'Open channel empty at specified width '+str(w))
        line=Part.makeLine(S.V(x-1,10,2),S.V(x+w+1,10,2))
        edges=shapes['C_FEMALE'].common(line).Edges
        measured=sorted([e.BoundBox.XMin for e in edges])[1]-sorted([e.BoundBox.XMax for e in edges])[0]
        require(abs(measured-w)<tol,'Gauge channel measured '+str(w),female_width_mm=measured,total_gap_mm=gap,centred_per_side_mm=gap/2)
        for yoff in np.linspace(-20,0,9):
            clear(S.moved(shapes['C_MALE'],x=x,y=float(yoff)),[shapes['C_FEMALE']],'Gauge entry/withdrawal G'+str(gap)+' @'+str(yoff))
        rows.append({'label':'G'+format(gap,'.2f'),'male':8,'female':measured,'engagement':20,'per_side':gap/2}); x+=w+2.4
    r['gauge']=rows

    # Actual saved FeaturePython parameter update: changes holes, pocket, keepers and toe coherently.
    before={k:s.Volume for k,s in shapes.items()}; original_gap=p['HardwareTotalGap']
    d.Parameters.HardwareTotalGap=.6 if abs(original_gap-.6)>.01 else .8
    d.recompute(); changed={k:local(d.getObject(k)) for k in S.KINDS}
    for k in ('A_BASE','A_LID','A_CLASP','B_BASE','B_LID','B_KEY'):
        require(changed[k].isValid() and len(changed[k].Solids)==1 and abs(changed[k].Volume-before[k])>.01,
                'Live reopened parameter actually changes '+k,old_volume_mm3=before[k],new_volume_mm3=changed[k].Volume)
    q2=S.key_dims(S.values(d.Parameters))
    require(abs(q2['bore']-(math.sqrt(2)*4+float(d.Parameters.HardwareTotalGap)))<tol,'Changed parameter updates rotational bore')
    r['editable_update']={'tested_gap':float(d.Parameters.HardwareTotalGap),'old_gap':original_gap,'new_key_dimensions':q2,'saved_baseline_not_overwritten':True}
    d.Parameters.HardwareTotalGap=original_gap; d.recompute()
    for k,s in shapes.items():
        t=local(d.getObject(k)); require(abs(s.Volume-t.Volume)<tol,'Parameter restoration '+k)
    App.closeDocument(d.Name)

    # A: toe is rigid, beam bends +X. Saved relaxed solid is used for locked capture.
    base,lid,clasp=shapes['A_BASE'],shapes['A_LID'],shapes['A_CLASP']; obstacles=[base,lid]
    clear(base,[lid],'A halves close without material overlap')
    clear(clasp,obstacles,'A relaxed locked clasp has no preload interference')
    h=p['HardwareTotalGap']/2
    overlap=(-h)-(-h-p['HookOverlap'])
    require(abs(overlap-p['HookOverlap'])<tol,'A positive hook overlap distinct from G',hook_engagement_mm=overlap,total_gap_mm=p['HardwareTotalGap'])
    for s,axis,label in ((lid,1,'lid +Y'),(base,-1,'base -Y')):
        contact=S.moved(s,y=axis*(h+.2)).common(clasp).Volume
        require(contact>p['HookOverlap']*(p['BeamWidth']-.8)*.2*.9,'A load path blocks '+label,intersection_mm3=contact,
                meaning='positive geometric bearing overlap after taking up slack; NOT a force or strength metric')
    delta=p['HookOverlap']+.3; bent=S.snap_clasp(p,delta)
    require(delta<p['ReleaseStopTravel'],'A release travel below positive stop',release_mm=delta,stop_mm=p['ReleaseStopTravel'])
    require(bent.isValid() and len(bent.Solids)==1,'A release surrogate remains connected')
    rows=[]
    for dd in np.linspace(0,delta,10):
        sh=clasp if dd==0 else S.snap_clasp(p,float(dd))
        clear(sh,obstacles,'A press surrogate @'+format(dd,'.2f')); rows.append({'press_mm':float(dd),'tip_slope_radians':1.5*float(dd)/24})
    # At stop travel a planar pad edge touches fixed lid stop; overtravel collides it.
    stop=S.snap_stop(p)
    clear(S.snap_clasp(p,p['ReleaseStopTravel'],moving_only=True),[stop],'A self-contained release stop terminal position')
    over=S.snap_clasp(p,p['ReleaseStopTravel']+.1,moving_only=True).common(stop).Volume
    require(over>.01,'A physical stop blocks overtravel',overtravel_mm=.1,intersection_mm3=over)
    # Upper peel about rigid toe corner, toe disengagement downward, normal withdrawal.
    pivot=S.V(-4-h,-2.6-h,0)
    for a in np.linspace(0,5,11): clear(S.turned(bent,-float(a),pivot),obstacles,'A pressed upper peel @'+str(a))
    peeled=S.turned(bent,-5,pivot)
    for yy in np.linspace(0,-3,13): clear(S.moved(peeled,y=float(yy)),obstacles,'A rigid toe disengage @'+str(yy))
    free=S.moved(peeled,y=-3)
    for xx in np.linspace(0,12,25): clear(S.moved(free,x=float(xx)),obstacles,'A normal withdrawal @'+str(xx))
    # Reverse exactly these paths to insert toe, press/pivot upper hook behind shoulder, relax.
    clear(S.snap_clasp(p,delta),[S.moved(lid,y=4)],'A deflected upper hook permits lid separation')
    for yy in (0,1,4,12,30): clear(base,[S.moved(lid,y=yy)],'A released halves genuinely separate @'+str(yy))
    r['motion']['A']={'locked':{'unloaded_beam':True,'positive_overlap_mm':overlap,'axial_slack_each_end_mm':h},
        'approximation':'w(y)=delta*y^2*(3L-y)/(2L^3); y unchanged; head x shear from tip slope. Root/toe rigid. No FEA/material/force prediction.',
        'press_states':rows,'release_press_mm':delta,'stop_mm':p['ReleaseStopTravel'],
        'peel_degrees':5,'pivot_xy_mm':[pivot.x,pivot.y],'toe_disengage_y_mm':-3,'withdraw_x_mm':12,
        'insertion':'Reverse withdraw/down/peel sequence with upper pad pressed; seat rigid toe, pivot upper hook behind square shoulder, release pad.'}
    print('A snap release/toe paths PASS',flush=True)

    # B: exactly enclosed holes through BOTH tabs, not a seam-split entry slot.
    base,lid,key=shapes['B_BASE'],shapes['B_LID'],S.turned(shapes['B_KEY'],-90); q=S.key_dims(p); obstacles=[base,lid]
    r['key_dimensions']=q
    require(q['bore']+tol>=math.sqrt(2)*p['NeckSize']+p['HardwareTotalGap'] and
            q['sweep']+tol>=math.hypot(p['HeadLength'],p['HeadWidth'])+p['HardwareTotalGap'],
            'B rotational neck bore AND full head sweep include diagonal + G',**q)
    for name,sh,z in [('lid',lid,1.6),('base',base,q['base_front']+1.2)]:
        pp=plane_poly(sh,z)
        require(pp.geom_type=='Polygon' and len(pp.interiors)==1 and pp.is_valid,'B '+name+' keyhole fully enclosed in its own tab',closed_apertures=len(pp.interiors))
    clear(base,[lid],'B overlapping tabs have axial clearance')
    # Straight entry/withdrawal with head parallel to seam (X). Collar stops at front face.
    for zz in np.linspace(-18,q['push'],41): clear(S.moved(key,z=float(zz)),obstacles,'B straight entry/removal @'+format(zz,'.3f'))
    unpark=S.moved(key,z=q['push'])
    for aa in np.linspace(0,90,37): clear(S.turned(unpark,float(aa)),obstacles,'B unparked rotation @'+str(aa))
    # Head circular swept envelope lies entirely beyond rear face while unparked.
    envelope=Part.makeCylinder(q['sweep']/2,p['HeadThickness'],S.V(0,0,q['floor']+q['push']))
    clear(envelope,obstacles,'B full circular head sweep is clear, including unsampled angles')
    neck_envelope=Part.makeCylinder(math.sqrt(2)*p['NeckSize']/2,q['floor']+q['push'],S.V(0,0,0))
    clear(neck_envelope,obstacles,'B complete circumscribed neck rotation clear in both closed bores')
    locked=S.turned(key,90)
    for zz in np.linspace(q['push'],0,13): clear(S.moved(locked,z=float(zz)),obstacles,'B outward parking / inward unpark @'+str(zz))
    clear(locked,obstacles,'B locked key parked without interference')
    for aa in (-10,-5,5,10):
        contact=S.turned(locked,aa).common(base).Volume
        require(contact>.01,'B seated parking walls block rotation '+str(aa),intersection_mm3=contact)
    require(S.moved(locked,z=-.2).common(base).Volume>.01,'B locked rear head prevents withdrawal through base tab')
    for name,sh,delta_y in [('lid',lid,1),('base',base,-1)]:
        require(S.moved(sh,y=delta_y).common(locked).Volume>.01,'B neck blocks independent '+name+' separation along Y',translation_mm=delta_y)
    require(S.moved(lid,z=-q['push']-.2).common(locked).Volume>.01,'B front collar captures lid axially')
    require(S.moved(base,z=.2).common(locked).Volume>.01,'B rear T-head captures base axially')
    for yy in (0,2,10,25,45): clear(base,[S.moved(lid,y=yy)],'B released halves genuinely separate @'+str(yy))
    r['motion']['B']={'entry_head_axis':'X parallel to seam','locked_head_axis':'Y, 90 degrees',
          'push_to_rotate_mm':q['push'],'pocket_depth_mm':p['PocketDepth'], 'free_rotation_rear_gap_mm':q['push']-p['PocketDepth'],
          'collar_bar_mm':[22,4,2.8],'head_mm':[18,4,3], 'neck_mm':[4,4],
          'front_collar_captures_lid':True,'rear_head_captures_base':True,'closed_bores_couple_both_halves':True,
          'axial_no_spring':'Pull outward to park; no spring maintains parking. Gravity/vibration can unpark. Push+turn accidental resistance UNPROVEN.'}
    print('B entry / rotation / park / both-half capture PASS',flush=True)

    # Independent bounded layer-support geometry, not mesh validity or actual slicing.
    sr={'status':'UNSLICED_GEOMETRIC_SCREEN','slicer_cli_available':False,
        'searched':'PATH and bounded /usr/bin /usr/local/bin /opt /home/azero/Applications; no Bambu/Orca/Prusa CLI found',
        'assumed_layer_height_mm':.2,'allowed_lateral_growth_per_layer_mm':.2,'section_curve_deflection_mm':.015,
        'method':'Native bed-oriented CAD horizontal sections at layer centres. New area outside previous layer buffered 0.20 mm (~45-degree growth) is flagged. No toolpaths, cooling, bridge strategy or material simulation.',
        'parts':{},'manual_preview_required':True}
    for k,s in shapes.items():
        bed=S.bed_shape(s,k); prev=None; flags=[]; maxarea=0; footprint=0
        for z in np.arange(.1,bed.BoundBox.ZMax,.2):
            poly=plane_poly(bed,float(z))
            if prev is None: footprint=poly.area
            else:
                unsupported=poly.difference(prev.buffer(.2,resolution=12))
                a=unsupported.area; maxarea=max(a,maxarea)
                if a>.1: flags.append({'layer_centre_z_mm':round(float(z),3),'new_area_beyond_growth_mm2':a,'bounds_xy_mm':list(unsupported.bounds)})
            prev=poly
        sr['parts'][k]={'first_layer_section_area_mm2':footprint,'max_new_area_beyond_growth_mm2':maxarea,
                        'flagged_regions':flags,'geometric_result':'NO_FLAGGED_OVERHANGS' if not flags else 'PREVIEW_SUPPORT_REQUIRED'}
        require(not flags,'Bounded section support screen '+k,max_new_area_beyond_45degree_growth_mm2=maxarea)
    r['support']=sr
    r['support_status']=sr['status']; r['status']='PASS_GEOMETRIC_ONLY_UNSLICED_UNPRINTED'; write()
    print('VALIDATION PASS',len(r['checks']),'checks',r['seconds'],'seconds',flush=True)
except Exception as e:
    r['status']='FAIL'; r['error']=str(e); write(); traceback.print_exc(); raise SystemExit(1)
