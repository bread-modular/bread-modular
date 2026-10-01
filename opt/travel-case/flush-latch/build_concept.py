#!/usr/bin/env python3
"""Build ONE editable local latch station and inexpensive concept checks.
Not a completed case or a printable latch release. Run inspect_geometry.py first.
"""
import json
from pathlib import Path
import FreeCAD as App
import Part
import MeshPart
import concept_features as F
ROOT=Path(__file__).resolve().parent
CACHE=ROOT/'.cache';OUT=ROOT/'reports';CAD=ROOT/'cad'
CAD.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
V=App.Vector
p=json.loads((ROOT/'concept-parameters.json').read_text())
origin=p['FrontStationX']-p['HookWidth']/2
source={}
for name in ('bottom','top'):
    s=Part.Shape();s.read(str(CACHE/f'release-{name}.brep'))
    s=s.common(F.box(origin-14,origin+30,0,14,8,25)).removeSplitter()
    s.translate(V(-origin,0,0));source[name]=s

d=App.newDocument('FlushLatchConcept')
pa=d.addObject('App::FeaturePython','Parameters')
for n,v in p.items():
    pa.addProperty('App::PropertyDistance' if v<0 else 'App::PropertyLength',n,'Concept dimensions')
    setattr(pa,n,v)
objects={}
for name in ('bottom','top'):
    o=d.addObject('PartDesign::Feature','Reference'+name.title());o.Shape=source[name]
    objects['reference_'+name]=o
for name in ('Bottom','Top','Slider'):
    ref=objects['reference_bottom' if name=='Bottom' else 'reference_top']
    o=d.addObject('PartDesign::FeaturePython',name+'Concept')
    F.LocalConcept(o,name,pa,ref);objects[name.lower()]=o
d.recompute()
for key,o in objects.items():
    if key.startswith('reference'):o.Label='UNTOUCHED release local '+key[10:]
    else:o.Label='CONCEPT ONLY / '+key
    if hasattr(o,'ViewObject') and o.ViewObject:
        o.ViewObject.Visibility=not key.startswith('reference')
        o.ViewObject.ShapeColor={'bottom':(.24,.48,.68),'top':(.67,.73,.79),'slider':(.98,.52,.12)}.get(key,(.5,.5,.5))
d.recompute();d.saveAs(str(CAD/'local-latch-concept.FCStd'))

sh={k:o.Shape for k,o in objects.items()}
original=source['top'].fuse(source['bottom'])
slider=sh['slider'];foot_top=p['HookBottomZ']+p['HookThickness']
report={'status':'CONCEPT ONLY - not print-ready; no full-case repairs or exports',
        'station_origin_X':origin, 'station_local_bounds':{}, 'part_validity':{},
        'collision_tolerance_mm3':1e-5,'endpoint_checks':[],'released_slide_samples':[],
        'printed_fit_assumptions':{'per_face_clearance_mm':.3,'pawl_clearance_press_mm':.8,
                                  'material':'PETG starting assumption; physical coupon required',
                                  'beam_flex_model':'NOT FEA; translated tooth/paddle clearance surrogate only'},
        'deferred':['Four-station full case booleans','12 magnet fills','cosmetic mesh repair',
                    'Final snap-gate hook details and pull-out checks','End-stop and final assembly tests',
                    'Full mesh manifold/self-intersection and functional-interface preservation tests',
                    'Slicer and physical tests']}
for name in ('bottom','top','slider'):
    s=sh[name];b=s.BoundBox
    report['part_validity'][name]={'valid':s.isValid(),'solids':len(s.Solids)}
    report['station_local_bounds'][name]=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
    m=MeshPart.meshFromShape(Shape=s,LinearDeflection=.05,AngularDeflection=.15,Relative=False)
    m.write(str(CACHE/f'local-{name}.stl'))
    # Local section actual CAD edges, suitable for a dimensioned drawing.
    section_shape=s.copy()
    if name=='slider':section_shape.translate(V(p['Stroke'],0,0))
    sec=section_shape.section(Part.makePlane(40,40,V(11,-5,0),V(1,0,0),V(0,1,0)))
    report.setdefault('locked_section_edges',{})[name]=[[[v.Point.y,v.Point.z] for v in e.Vertexes] for e in sec.Edges]

top=sh['top'];bottom=sh['bottom']
def moved(s,x=0,y=0,z=0):
    q=s.copy();q.translate(V(x,y,z));return q
# Detent release is deliberately analysed as an elastic-part clearance surrogate,
# not falsely labelled a simulated deformed, stress-tested printable cantilever.
tooth=F.box(8,10,3.6,4.5,16,17)
without_tooth=slider.cut(tooth)
paddle=slider.common(F.box(8,18,-1,8.1,15.5,19.7))
for travel in [0,.5,1,2,3,4,5,6,7,7.5,8]:
    q=moved(without_tooth,travel)
    row={'travel_mm':travel,'rigid_path_lid_intersection_mm3':q.common(top).Volume,
         'bottom_intersection_mm3':q.common(bottom).Volume,
         'released_tooth_lid_intersection_mm3':moved(tooth,travel,.8).common(top).Volume,
         'pressed_paddle_lid_intersection_mm3':moved(paddle,travel,.8).common(top).Volume,
         'outside_original_closed_material_mm3':moved(slider,travel).cut(original).Volume}
    report['released_slide_samples'].append(row)
for travel in (0,8):
    q=moved(slider,travel)
    row={'travel_mm':travel,'lid_intersection_mm3':q.common(top).Volume,
         'bottom_intersection_mm3':q.common(bottom).Volume,
         'outside_original_material_mm3':q.cut(original).Volume,
         'lift_0_31_bottom_intersection_mm3':moved(q,z=.31).common(bottom).Volume}
    report['endpoint_checks'].append(row)
# Positive stop: the tooth should block unpressed departure in BOTH positions.
report['positive_detents']={
    'unlocked_move_0_4mm_unpressed_lid_intersection_mm3':moved(slider,.4).common(top).Volume,
    'locked_move_minus_0_4mm_unpressed_lid_intersection_mm3':moved(slider,7.6).common(top).Volume,
    'tooth_radial_engagement_mm':.6,'pressed_radial_clearance_mm':.2}
head=F.box(-10,18,10,12.4,17,21)
report['captive_head_checks']={
    'down_0_31_lid_intersection_mm3':moved(head,z=-.31).common(top).Volume,
    'outward_0_31_lid_intersection_mm3':moved(head,y=-.31).common(top).Volume,
    'up_0_31_lid_intersection_mm3':moved(head,z=.31).common(top).Volume,
    'lid_floor_thickness_mm':1.7,'inner_skin_thickness_mm':1.3,
    'minimum_floor_head_bearing_area_mm2':28*2.4}
report['catch']={'foot_Z_top':foot_top,'underside_Z':12.7,'axial_slack_mm':.3,
                 'ledge_thickness_mm':15-12.7,'Y_overlap_mm':p['StemOuterY']-.3-p['HookOuterY'],
                 'X_overlap_locked_mm':6,'bearing_area_mm2_per_latch':6*(p['StemOuterY']-.3-p['HookOuterY']),
                 'open_entry_mm':[6.6,p['StemInnerY']+.3-(p['HookOuterY']-.3)], 'stem_slot_width_Y_mm':p['StemInnerY']-p['StemOuterY']+.6,
                 'nominal_two_clearances_lid_lift_before_load_mm':.6}
# Unlock/lift samples verify the actual keyway, without asserting a complete
# multi-station case motion simulation before approval.
report['unlocked_vertical_release']=[{'lift_mm':z,'receiver_intersection_mm3':moved(slider,z=z).common(bottom).Volume} for z in [0,.3,1,2,3,4.6,6]]
report['lower_receiver_inside_measured_rim']={'max_Y_mm':p['StemInnerY']+.3,'min_inner_rim_Y_mm':9.6,'remaining_inner_wall_mm':9.6-(p['StemInnerY']+.3),
                                          'catch_outer_root_mm':3.3-1.95698,
                                          'skirt_outer_Y_max_mm':1.5,'bottom_skirt_channel_start_Y_mm':1.75}
report['all_concept_checks_pass']=all(s.isValid() and len(s.Solids)==1 for s in [top,bottom,slider]) and all(
    row[k]<1e-5 for row in report['released_slide_samples'] for k in row if k!='travel_mm') and all(
    row[k]<1e-5 for row in report['endpoint_checks'] for k in ['lid_intersection_mm3','bottom_intersection_mm3','outside_original_material_mm3']) and report['endpoint_checks'][1]['lift_0_31_bottom_intersection_mm3']>1e-5 and all(
    report['positive_detents'][k]>1e-5 for k in ['unlocked_move_0_4mm_unpressed_lid_intersection_mm3','locked_move_minus_0_4mm_unpressed_lid_intersection_mm3']) and all(
    row['receiver_intersection_mm3']<1e-5 for row in report['unlocked_vertical_release'])
(OUT/'concept-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['locked_section_edges','released_slide_samples']},indent=2),flush=True)
print('released samples',report['released_slide_samples'],flush=True)
App.closeDocument(d.Name)
# Check actual editable recomputation after reopening, not just a saved snapshot.
d=App.openDocument(str(CAD/'local-latch-concept.FCStd'));d.recompute()
a=d.SliderConcept.Shape.Volume;d.Parameters.HookThickness=2.01;d.recompute();b=d.SliderConcept.Shape.Volume
d.Parameters.HookThickness=2.0;d.recompute();c=d.SliderConcept.Shape.Volume
report['editability']={'thickness_edit_delta_mm3':b-a,'restored_volume_error_mm3':c-a,'valid_after_restore':d.SliderConcept.Shape.isValid()}
(OUT/'concept-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('editability',report['editability'],flush=True)
App.closeDocument(d.Name)
if not report['all_concept_checks_pass']:raise SystemExit(2)
