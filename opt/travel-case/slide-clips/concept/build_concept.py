#!/usr/bin/env python3
"""Phase one only: local measured subtractive grooves and one universal clip.
No full grooved shell, coupon or production fit variants are manufactured here.
"""
from pathlib import Path
import json, hashlib, time, copy
import FreeCAD as App
import Part, Mesh, MeshPart
import clip_features as F
R=Path(__file__).resolve().parent
for folder in ('.cache','reports','cad','prototype','previews'):(R/folder).mkdir(exist_ok=True)
p=json.loads((R/'concept-parameters.json').read_text())
m=json.loads((R/'reports/pristine-measurements.json').read_text())
V=App.Vector
start=time.monotonic()
source={}
for name in ('bottom','top'):
 raw=R.parent/'original/case_1.0.0'/f'bm_case_{name}_1.0.0.stl'
 assert hashlib.sha256(raw.read_bytes()).hexdigest()==m['parts'][name]['source_sha256']
 s=Part.Shape();s.read(str(R/'.cache'/f'release-{name}.brep'));source[name]=s
profile=[]
for edge in m['parts']['top']['candidate_section_edges']:
 if len(edge)!=2:continue
 a,b=edge
 if min(a[2],b[2])>=17.4 and max(a[1],b[1])<=10.0001 and abs(a[1]-b[1])>1e-8:
  profile.append(((a[1],a[2]),(b[1],b[2])))
assert abs(F.outer_profile(profile,4)-18.349444)<.001
report={'phase':'1 / approval concept; not a print-ready complete case',
        'source':'raw case_1.0.0 only, fresh conversion; no flush-latch machined parts used',
        'source_hashes':{n:m['parts'][n]['source_sha256'] for n in source},
        'toolchain':{'FreeCAD':App.Version(),'OCC':Part.OCC_VERSION},
        'profile_segments_yz_mm':profile,'parameters':p,'sites':[],
        'repair_scope':'In phase 2 fill ONLY cosmetic engraving/fill all 12 magnet pockets with established patches. No full-body repairs or grooves performed in phase 1.'}

def bounds(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def contours(s):
 plane=Part.makePlane(25,37,V(0,-8,-4),V(1,0,0),V(0,1,0))
 section=s.section(plane)
 out=[]
 for e in section.Edges:
  pts=e.discretize(Deflection=.035) if not isinstance(e.Curve,Part.Line) else [v.Point for v in e.Vertexes]
  for a,b in zip(pts,pts[1:]):out.append([[a.y,a.z],[b.y,b.z]])
 return out

def mesh_export(s,path,check=False):
 mesh=MeshPart.meshFromShape(Shape=s,LinearDeflection=.04,AngularDeflection=.12,Relative=False)
 mesh.write(str(path))
 if check:
  q=Mesh.Mesh(str(path));r={'closed':q.isSolid(),'nonmanifold':q.hasNonManifolds(),
   'inconsistent_normals':q.hasNonUniformOrientedFacets(),'self_intersections':q.hasSelfIntersections(),
   'components':q.countComponents(),'facets':q.CountFacets,'bounds_mm':bounds(q),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  assert r['closed'] and not r['nonmanifold'] and not r['inconsistent_normals'] and not r['self_intersections'] and r['components']==1,r
  return r

doc=App.newDocument('SimpleSlideClipConcept')
params=doc.addObject('App::FeaturePython','Parameters')
for k,v in p.items():
 params.addProperty('App::PropertyFloat' if 'Slope' in k else 'App::PropertyLength',k,'Concept dimensions');setattr(params,k,v)
 if k in ('CaseWidth','CaseDepth','CaseHeight','SeamZ','StationX'):params.setEditorMode(k,1)
params.addProperty('App::PropertyString','Status','Evidence').Status='PHASE ONE ONLY; physical friction, creep, fit and load capacity untested'
params.addProperty('App::PropertyString','Original','Evidence').Original='case_1.0.0; no internal latch slots; only measured LOCAL pristine crops'
locals_first={}
clip=F.clip(p)
# Generous roots must stay outside the case wall.
assert p['WebClearance']-p['RootRadius']>.25
# Pocket fills cannot be re-opened by any groove, including at all four sites.
centres=[(81.04,5),(162.08,5),(5,89.81),(238.12,89.81),(81.04,174.62),(162.08,174.62)]
patches={name:Part.makeCompound([F.box(x-3.16,x+3.16,y-3.16,y+3.16,15 if name=='top' else 12.95,17.15 if name=='top' else 15) for x,y in centres]) for name in source}

def vertical(s,y):
 sec=s.common(Part.makeLine(V(0,y,-1),V(0,y,35)))
 return sorted([[e.BoundBox.ZMin,e.BoundBox.ZMax] for e in sec.Edges])

for index,(x,rear) in enumerate([(32,False),(211.12,False),(32,True),(211.12,True)]):
 local={};grooved={}
 for name,s in source.items():
  # Sample the REAL corner shell, not a made-up enclosure block.
  region=F.at_site(F.box(-12,12,0,15,-1,31),x,rear,p)
  q=s.common(region).removeSplitter();q.translate(V(-x,-p['CaseDepth'] if rear else 0,0))
  if rear:q.rotate(V(),V(0,0,1),180)
  local[name]=q
  tool=F.tools(p,profile,name=='top')
  assert F.at_site(tool,x,rear,p).common(patches[name]).Volume<1e-6
  g=q.cut(tool).removeSplitter();assert g.isValid() and len(g.Solids)==1,(index,name)
  grooved[name]=g
 row={'id':'ABCD'[index],'centre_x_mm':x,'edge_y_mm':p['CaseDepth'] if rear else 0,'insertion_vector':[0,-1 if rear else 1,0],
      'groove_pocket_patch_overlap_mm3':0,'rigid_approach_samples':[]}
 for withdrawal in (9,4,1.5,1.2,.5,0):
  q=F.moved(clip,y=-withdrawal)
  volumes={n:q.common(s).Volume for n,s in grooved.items()}
  row['rigid_approach_samples'].append({'outward_offset_mm':withdrawal,'intersection_mm3':volumes,
   'interpretation':'expected elastic preload (not a collision-free rigid assembly)' if withdrawal<=.5 else 'clear approach'})
  if withdrawal>=1.2:assert max(volumes.values())<1e-5,(index,withdrawal,volumes)
 # Eliminate designed interference for a separate rigid geometric capture check.
 clearance=copy.deepcopy(p);clearance['InterferencePerJaw']=-.02
 test=F.clip(clearance)
 neutral={n:test.common(s).Volume for n,s in grooved.items()}
 lid_lift=test.common(F.moved(grooved['top'],z=.30)).Volume
 base_drop=test.common(F.moved(grooved['bottom'],z=-.30)).Volume
 assert max(neutral.values())<1e-5,(index,'unexpected geometry',neutral)
 assert lid_lift>1 and base_drop>1
 row['geometric_capture']={'clearance_surrogate_mm_per_jaw':.02,'initial_intersection_mm3':neutral,
    'lid_lift_0_30mm_blocked_volume_mm3':lid_lift,'base_drop_0_30mm_blocked_volume_mm3':base_drop,
    'meaning':'opposed upper/lower jaws block vertical separation; does NOT establish physical load or torsional capacity'}
 row['minimum_remaining_lid_vertical_material_mm']=min(iv[1]-iv[0] for y in (1.51,2,3,4,5,6,7) for iv in vertical(grooved['top'],y))
 row['local_groove_removed_mm3']={n:local[n].Volume-grooved[n].Volume for n in source}
 report['sites'].append(row)
 print('SITE',row['id'],'local removed',row['local_groove_removed_mm3'],'remaining lid',row['minimum_remaining_lid_vertical_material_mm'],'capture',lid_lift,base_drop,flush=True)
 if index==0:
  locals_first={'original':local,'grooved':grooved}
  for name in source:
   o=doc.addObject('PartDesign::Feature','PristineLocal'+name.title());o.Shape=local[name];o.Label='UNTOUCHED measured release crop / '+name
   f=doc.addObject('PartDesign::FeaturePython','Local'+name.title());F.ConceptFeature(f,'Local'+name.title(),params,o,profile)
   doc.recompute();assert f.Shape.isValid() and len(f.Shape.Solids)==1
  obj=doc.addObject('PartDesign::FeaturePython','UniversalClip');F.ConceptFeature(obj,'Clip',params);doc.recompute()
  assert obj.Shape.isValid() and len(obj.Shape.Solids)==1

# One economic short-edge scan measures port interruptions, not generic assumptions.
connector=[]
for x in (.1,p['CaseWidth']-.1):
 q=source['bottom'].common(Part.makeLine(V(x,-1,12),V(x,p['CaseDepth']+1,12)))
 runs=sorted([[e.BoundBox.YMin,e.BoundBox.YMax] for e in q.Edges])
 gaps=[[runs[i][1],runs[i+1][0]] for i in range(len(runs)-1) if runs[i+1][0]-runs[i][1]>.1]
 connector.append({'edge':'left' if x<1 else 'right','sample_x_mm':x,'sample_z_mm':12,'material_y_intervals_mm':runs,'opening_y_intervals_mm':gaps})
report['short_edge_connector_scan']=connector
report['placement_choice']='Four corner-near sites, TWO ON EACH LONG FACE; straight radial insertion. Avoids both short-edge connector interruptions and allows one universal clip, rotated 180 degrees at rear.'
report['diagonal_pair']={'site_ids':['A','D'],'each_site_blocks_both_halves':True,'load_capacity':'not established','tilt_torsion_drop_tests':'pending physical tests'}
report['grooves']={'bottom_max_depth_mm':p['BottomDepth'],'bottom_zero_depth_at_y_mm':p['BottomRunout'],
 'top_max_vertical_depth_mm':max(F.outer_profile(profile,y)-(p['TopBearingZ']+p['TopBearingSlope']*y) for y in [i/100 for i in range(401)]),
 'top_zero_depth_by_y_mm':p['TopRunout'],'remaining_bottom_to_inner_floor_conservative_mm':8-p['BottomDepth'],
 'remaining_lid_vertical_min_sample_mm':min(q['minimum_remaining_lid_vertical_material_mm'] for q in report['sites']),
 'lid_skirt_original_thickness_mm':1.5,'skirt_seam_original_and_untouched':True,'groove_side_clearance_min_per_face_mm':(p['GrooveRunningWidth']-p['ClipWidth'])/2}
report['section_edges_yz_mm']={n:contours(s) for n,s in locals_first['grooved'].items()}
report['section_edges_yz_mm']['clip']=contours(clip)
report['original_section_edges_yz_mm']={n:contours(s) for n,s in locals_first['original'].items()}
# Rendering assets only; no new full case meshes.
for name,s in locals_first['grooved'].items():
 mesh_export(s.common(F.box(-13,0,0,15,-1,31)),R/'.cache'/f'local-section-{name}.stl')
 mesh_export(s,R/'.cache'/f'local-{name}.stl')
mesh_export(clip.common(F.box(-13,0,-8,10,-4,25)),R/'.cache/local-section-clip.stl')
mesh_export(clip,R/'.cache/clip-assembled.stl')
report['prototype_stl']=mesh_export(F.bed_shape(clip),R/'prototype/clip_concept_NOT_FIT_TESTED.stl',True)
# Upper/lower face ramps are very shallow in the loaded segment, unlike the steep uncut shoulder.
report['binding']={'bottom_ramp_degrees':__import__('math').degrees(__import__('math').atan(p['BottomDepth']/p['BottomRunout'])),
 'top_bearing_ramp_degrees':__import__('math').degrees(__import__('math').atan(p['TopBearingSlope'])),
 'paired_throat_increase_per_inward_mm':p['BottomDepth']/p['BottomRunout']+p['TopBearingSlope'],
 'intentional_total_throat_interference_mm':2*p['InterferencePerJaw'],
 'rigid_path_clear_to_outward_offset_mm':1.2,'final_push_requires_elastic_opening_mm_approx':.16,
 'friction_warning':'No positive lock or snap; hand seating and retention require friction + elastic preload. Fit, withdrawal, creep and force require a printed coupon.'}
# Exact measured unchanged case bounds vs the placed prototype clip envelope.
rawbounds=[min(source[n].BoundBox.XMin for n in source),min(source[n].BoundBox.YMin for n in source),min(source[n].BoundBox.ZMin for n in source),
 max(source[n].BoundBox.XMax for n in source),max(source[n].BoundBox.YMax for n in source),max(source[n].BoundBox.ZMax for n in source)]
cs=[F.at_site(clip,q['centre_x_mm'],q['edge_y_mm']>0,p).BoundBox for q in report['sites']]
combined=[min(rawbounds[0],*(b.XMin for b in cs)),min(rawbounds[1],*(b.YMin for b in cs)),min(rawbounds[2],*(b.ZMin for b in cs)),
 max(rawbounds[3],*(b.XMax for b in cs)),max(rawbounds[4],*(b.YMax for b in cs)),max(rawbounds[5],*(b.ZMax for b in cs))]
report['envelope']={'pristine_body_bounds_mm':rawbounds,'pristine_body_dimensions_mm':[rawbounds[j+3]-rawbounds[j] for j in range(3)],
 'with_four_clips_bounds_mm':combined,'with_four_clips_dimensions_mm':[combined[j+3]-combined[j] for j in range(3)],
 'with_diagonal_pair_dimensions_mm':[combined[j+3]-combined[j] for j in range(3)],
 'projection_each_long_face_mm':-clip.BoundBox.YMin,'projection_below_base_mm':-clip.BoundBox.ZMin,
 'case_body_permanent_projection_mm':0,'short_edge_clearance_to_clip_x_span_mm':p['StationX']-p['ClipWidth']/2}
report['printing']={'orientation':'C cross-section flat in XY; 12 mm edge width is layer height direction. Single one-piece clip.',
 'bed_dimensions_mm':[F.bed_shape(clip).BoundBox.XLength,F.bed_shape(clip).BoundBox.YLength,F.bed_shape(clip).BoundBox.ZLength],
 'minimum_jaw_thickness_mm':p['JawThickness'],'web_mm':p['WebThickness'],'root_radius_mm':p['RootRadius'],
 'tip_leadin_mm':p['TipLeadLength'],'clip_supports_expected':'none: constant 12 mm extrusion, each layer is the complete C profile',
 'case_supports':'not sliced in phase 1; lid roof-down and base underside-down retain normal original orientation. Shallow open exterior grooves need inspection in phase 2.'}
for o in doc.Objects:
 if getattr(o,'ViewObject',None):
  o.ViewObject.Visibility=o.Name in ('LocalBottom','LocalTop','UniversalClip')
  if hasattr(o.ViewObject,'ShapeColor'):o.ViewObject.ShapeColor={'LocalBottom':(.21,.43,.61),'LocalTop':(.64,.72,.80),'UniversalClip':(.98,.49,.07)}.get(o.Name,(.6,.6,.6))
doc.recompute();doc.saveAs(str(R/'cad/slide-clip-concept.FCStd'))
App.closeDocument(doc.Name)
# Reopen/recompute only these three analytical features; stop on any failed state.
reopened=App.openDocument(str(R/'cad/slide-clip-concept.FCStd'))
for name in ('LocalBottom','LocalTop','UniversalClip'):reopened.getObject(name).touch()
reopened.recompute()
for name in ('LocalBottom','LocalTop','UniversalClip'):
 o=reopened.getObject(name);assert o.Shape.isValid() and len(o.Shape.Solids)==1 and not any(s in ('Invalid','Error') for s in o.State),(name,o.State)
report['local_cad_reopen_recompute']='PASS (three local FeaturePython features)'
App.closeDocument(reopened.Name)
report['build_seconds']=time.monotonic()-start
(R/'reports/concept-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('DONE',report['build_seconds'],'envelopes',report['envelope'],'grooves',report['grooves'],'ports',connector,flush=True)
