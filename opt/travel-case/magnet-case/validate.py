#!/usr/bin/env python3
"""Independent edited-CAD/export checks; failed mesh checks remain explicit.
Base uses exact exterior source faces; lid uses the explicitly authorized measured logo bounding region. Never an interior-base repair.
"""
import math
from collections import Counter, defaultdict
import time
import json
import FreeCAD as App
import Part
import Mesh
import numpy as np
from scipy.spatial import cKDTree
import geometry as G
from survey import plane_faces, vertical_envelope

ROOT = G.ROOT
start = time.monotonic()
source_checks = G.verify_original()
reopen = json.loads((ROOT/'reports/reopen.json').read_text())
assert reopen['passed'] and reopen['no_project_module_imports']
D = App.openDocument(str(ROOT/'cad/original-magnet-case.FCStd'))
for obj in D.Objects: obj.touch()
D.recompute()
for obj in D.Objects:
    assert not any(s in ('Invalid','Error') for s in obj.State), (obj.Name,obj.State)
assert not any('Python' in o.TypeId or getattr(o,'Proxy',None) is not None for o in D.Objects)
report = {'status':'Native/material/functional/export validation in progress',
          'source_checksums_verified':source_checks, 'fidelity_tolerance_mm':0.00002,
          'basis':'No removed material; all additions inside independently measured base face extrusions / authorized lid-logo bounding region; unchanged bounds and all out-of-region faceted surfaces; independent final pocket measurements; written STL compared to edited CAD tessellation.',
          'assembly_transform':list(G.MATRIX), 'parts':{}, 'mesh_warnings':{},
          'authorized_regions':{'base':'Two EXTERIOR underside bays only, Z0..1',
                                'lid':'Entire explicitly authorized measured backside-logo bounding region, Z75..75.5 only'}}


def bbox_overlap(a,b):
    aa,bb=G.bounds(a),G.bounds(b)
    return all(aa[i] <= bb[i+3]+1e-7 and bb[i] <= aa[i+3]+1e-7 for i in range(3))


def xyz(points):
    return np.array([[p.x,p.y,p.z] for p in points])


for kind,name,filename in [('base','Base','case_bottom_underside_down.stl'),
                           ('lid','Lid','case_lid_roof_down.stl')]:
    mesh=G.release_mesh(kind)
    source=G.solid_from_mesh(mesh)
    final=D.getObject(name).Shape
    reference=D.getObject('Release'+name).Shape
    assert final.isValid() and final.isClosed() and len(final.Solids)==1
    assert source.cut(reference).Volume < 1e-5 and reference.cut(source).Volume < 1e-5
    z,depth,target=(1.,1.,0.) if kind=='base' else (75.5,.5,75.)
    floors=plane_faces(source,z,-1)
    assert len(floors)==(2 if kind=='base' else 34)
    if kind=='base':
        allowed=Part.makeCompound([f.extrude(App.Vector(0,0,-depth)) for f in floors])
    else:
        bb=App.BoundBox()
        for f in floors: bb.add(f.BoundBox)
        allowed=Part.makeBox(bb.XLength,bb.YLength,depth,App.Vector(bb.XMin,bb.YMin,target))
    removed=source.cut(final).Volume
    addition=final.cut(source)
    outside=addition.cut(allowed).Volume
    missing=allowed.cut(final).Volume
    assert removed < 1e-5 and outside < 1e-5 and missing < 1e-5, (kind,removed,outside,missing)
    bound_delta=max(abs(a-b) for a,b in zip(G.bounds(final),G.bounds(source)))
    assert bound_delta < 1e-7
    assert abs((final.Volume-source.Volume)-addition.Volume) < 1e-5
    # Compare every source faceted surface wholly outside the measured additions.
    # The entire original-vs-final shell is NOT required to have zero difference.
    unchanged=[f for f in source.Faces if not any(bbox_overlap(f,t) for t in allowed.Solids)]
    final_faces=list(final.Faces)
    centres=xyz([f.CenterOfMass for f in final_faces])
    distances,matches=cKDTree(centres).query(xyz([f.CenterOfMass for f in unchanged]))
    area_error=max(abs(f.Area-final_faces[int(i)].Area) for f,i in zip(unchanged,matches))
    face_centre_error=float(distances.max())
    assert face_centre_error < 2e-5 and area_error < 1e-5
    # These checks include the entire inner base floor, PCB mount faces, connector
    # openings, seam / lip and pocket/chamfer surfaces outside the two fill regions.
    canonical_final_mesh=G.cad_mesh(final)
    source_pockets=G.measure_pockets(mesh,kind)
    pockets=G.measure_pockets(canonical_final_mesh,kind)
    pocket_error=0.
    for a,b in zip(source_pockets,pockets):
        for key in ('diameter_fit_mm','floor_z_mm','neck_z_mm','mouth_z_mm',
                    'full_depth_mm','straight_depth_mm','chamfer_height_mm','mouth_diameter_fit_mm'):
            pocket_error=max(pocket_error,abs(a[key]-b[key]))
        pocket_error=max(pocket_error,math.dist(a['centre_mm'],b['centre_mm']))
        assert a['floor_polygon_vertex_count']==b['floor_polygon_vertex_count']==24
    assert pocket_error < 2e-5
    if kind=='base':
        original_inside=plane_faces(source,7.5,1)
        final_inside=plane_faces(final,7.5,1)
        assert len(original_inside)==len(final_inside)==34
        assert abs(sum(f.Area for f in original_inside)-sum(f.Area for f in final_inside)) < 1e-5
        assert len(plane_faces(final,1.,-1))==0
        bottom=plane_faces(final,0.,-1)
        assert len(bottom)==1 and len(bottom[0].Wires)==1
    else:
        assert len(plane_faces(final,75.5,-1))==0
    flat_faces=plane_faces(final,target,-1)
    before_flat=plane_faces(source,target,-1)
    area_gain=sum(f.Area for f in flat_faces)-sum(f.Area for f in before_flat)
    if kind=='base':
        projected_caps=Part.makeCompound(floors)
        projected_caps.translate(App.Vector(0,0,-depth))
    else:
        projected_caps=Part.makeCompound(plane_faces(allowed,target,-1))
    uncovered_cap_area=projected_caps.cut(Part.makeCompound(flat_faces)).Area
    assert uncovered_cap_area < 1e-5
    # Source intersecting engraving topology makes area-sum identities unreliable;
    # exact cap coverage and material-region tests are the strict geometric tests.
    rays=vertical_envelope(canonical_final_mesh)
    if kind=='base':
        assert max(abs(v) for v in rays['first_from_below_z_range_mm']) < 1e-7

    print_link=D.getObject(name+'Print')
    expected_placement=G.print_placement(G.bounds(source),kind)
    print_shape=final.copy(); print_shape.Placement=expected_placement
    assert max(abs(a-b) for a,b in zip(G.bounds(print_link.Shape),G.bounds(print_shape))) < 1e-6
    assert abs(G.bounds(print_link.Shape)[2]) < 1e-6
    expected=G.cad_mesh(print_shape)
    written=Mesh.Mesh(str(ROOT/'stl'/filename))
    assert written.CountFacets==expected.CountFacets
    expected_pts,expected_tris=expected.Topology
    written_pts,written_tris=written.Topology
    distances,_=cKDTree(xyz(expected_pts)).query(xyz(written_pts))
    reverse,_=cKDTree(xyz(written_pts)).query(xyz(expected_pts))
    print_error=max(float(distances.max()),float(reverse.max()))
    assert print_error < 2e-5
    assert max(abs(a-b) for a,b in zip(G.bounds(written),G.bounds(print_shape))) < 2e-5
    # Vertex correspondence alone is insufficient: compare unordered full triangles.
    point_ids=cKDTree(xyz(expected_pts)).query(xyz(written_pts))[1]
    expected_triangles=Counter(tuple(sorted(t)) for t in expected_tris)
    mapped_triangles=Counter(tuple(sorted(int(point_ids[i]) for i in t)) for t in written_tris)
    expected_changed=expected_triangles-mapped_triangles
    written_changed=mapped_triangles-expected_triangles
    # OCC re-meshing may choose other diagonals in the SAME planar polygon.
    # Do not mislabel that as identical records: strictly prove each changed
    # coplanar region has the same boundary edge multiset and projected area.
    expected_xyz=xyz(expected_pts)
    def planar_regions(changed):
        groups=defaultdict(list)
        for tri in changed.elements():
            a,b,c=expected_xyz[list(tri)]
            n=np.cross(b-a,c-a); magnitude=float(np.linalg.norm(n))
            assert magnitude > 1e-12
            n=n/magnitude
            significant=next(v for v in n if abs(v)>1e-7)
            if significant < 0: n=-n
            plane=tuple(round(float(v),5) for v in n)+(round(float(np.dot(n,a)),5),)
            groups[plane].append(tri)
        result={}
        for plane,triangles in groups.items():
            edges=Counter(tuple(sorted((t[i],t[j]))) for t in triangles for i,j in ((0,1),(1,2),(2,0)))
            boundary=Counter({edge:count for edge,count in edges.items() if count==1})
            assert all(count in (1,2) for count in edges.values())
            area=sum(float(np.linalg.norm(np.cross(expected_xyz[t[1]]-expected_xyz[t[0]],expected_xyz[t[2]]-expected_xyz[t[0]])))/2 for t in triangles)
            result[plane]=(boundary,area)
        return result
    expected_regions=planar_regions(expected_changed)
    written_regions=planar_regions(written_changed)
    assert expected_regions.keys()==written_regions.keys()
    for plane,(boundary,area) in expected_regions.items():
        other_boundary,other_area=written_regions[plane]
        assert boundary==other_boundary
        assert abs(area-other_area)<1e-5
    retriangulated_count=sum(written_changed.values())
    from export_diagnostic import double_volume
    written_double_volume=double_volume(written)
    volume_tolerance=final.Area*2e-5
    assert abs(written_double_volume-final.Volume) < volume_tolerance
    source_topology=G.mesh_checks(mesh)
    written_topology=G.mesh_checks(written)
    assert written_topology['is_solid'] and not written_topology['non_manifold']
    for key in ('boundary_edges','non_two_incident_edges','inconsistent_edge_winding','zero_area_facets'):
        assert written_topology[key]==0,(kind,key,written_topology[key])
    # Self intersections are recorded as failures, never reclassified as passes.
    if not written_topology['self_intersection_check_passed']:
        report['mesh_warnings'][kind]={'source_pairs':source_topology['self_intersection_pair_count'],
            'final_pairs':written_topology['self_intersection_pair_count'],
            'final_check_passed':False, 'evidence':written_topology['self_intersection_evidence'],
            'note':'Mesh check FAILED. Base flags localize to preserved internal engraving Z7.5..8 (original 12 pairs, final tessellation 13). Base engraving geometry is unchanged, but triangle pair counts are not claimed unchanged. The historical fragmented-logo lid had 28 export pairs; one authorized measured-region fallback resolved the lid issue. No physical or slicer qualification.'}
    report['parts'][kind]={
        'basic_OCC_solid_valid':final.isValid(),'closed':final.isClosed(),'solids':len(final.Solids),
        'bounds_mm':G.bounds(final), 'dimensions_mm':[G.bounds(final)[i+3]-G.bounds(final)[i] for i in range(3)],
        'volume_mm3':final.Volume,'area_mm2':final.Area,'volume_delta_mm3':final.Volume-source.Volume,
        'removed_material_vs_original_mm3':removed,'added_material_vs_original_mm3':addition.Volume,
        'added_outside_authorized_region_mm3':outside,'missing_authorized_fill_mm3':missing,
        'source_engraving_or_bay_floor_area_mm2':sum(f.Area for f in floors),
        'authorized_fill_region_bounds_mm':G.bounds(allowed),
        'authorized_profile_area_mm2':allowed.Volume/depth,
        'sum_profile_extrusions_mm3':allowed.Volume,
        'fill_tool_overlapping_existing_source_material_mm3':allowed.Volume-addition.Volume,
        'fill_target_plane_z_mm':target,'fill_depth_mm':depth,
        'max_bounds_delta_mm':bound_delta,
        'unchanged_out_of_region_face_count':len(unchanged),
        'unchanged_face_centroid_max_error_mm':face_centre_error,
        'unchanged_face_area_max_error_mm2':area_error,
        'mount_connector_seam_profile_preserved_by_boolean_and_face_checks':True,
        'base_interior_engraving_untouched':True if kind=='base' else None,
        'pocket_count':len(pockets),'pockets':pockets,'source_pockets':source_pockets,
        'pocket_geometry_max_delta_mm':pocket_error,
        'flat_plane_face_count':len(flat_faces), 'flat_plane_area_gain_mm2':area_gain,
        'uncovered_projected_authorized_fill_caps_mm2':uncovered_cap_area,
        'area_sum_vs_added_volume_over_depth_discrepancy_mm2':area_gain-addition.Volume/depth,
        'final_vertical_envelope_grid':rays,
        'print_bounds_mm':G.bounds(print_link.Shape),'print_triangle_coordinate_error_max_mm':print_error,
        'written_STL_matches_independent_edited_CAD_surface':True,
        'different_coplanar_triangle_records':retriangulated_count,
        'retriangulated_regions_same_plane_boundary_and_area':True,
        'source_mesh':source_topology,'written_STL_mesh':written_topology,
        'written_STL_sha256':G.sha256(ROOT/'stl'/filename),
        'written_STL_double_precision_volume_mm3':written_double_volume,
        'written_STL_volume_delta_vs_CAD_mm3':written_double_volume-final.Volume,
        'volume_tolerance_mm3_from_surface_area_times_0_00002mm':volume_tolerance}
    print('VALIDATE',kind,'added',addition.Volume,'removed',removed,'outside',outside,
          'pockets',len(pockets),'STL',written.CountFacets,'self-intersection pairs source/final',
          source_topology['self_intersection_pair_count'],written_topology['self_intersection_pair_count'],flush=True)

base,lid=G.bounds(D.Base.Shape),G.bounds(D.Lid.Shape)
combined=[min(base[i],lid[i]) for i in range(3)]+[max(base[i],lid[i]) for i in range(3,6)]
dimensions=[combined[i+3]-combined[i] for i in range(3)]
assert max(abs(a-b) for a,b in zip(dimensions,(243.12,179.62,77.5))) < 2e-5
report.update(status='PASS native/material/functional/export checks; '+('FINAL STL SELF-INTERSECTION FAILURES REMAIN' if report['mesh_warnings'] else 'final STL self-intersection checks passed'),
              assembly_bounds_mm=combined,assembly_dimensions_mm=dimensions,
              saved_document_sha256=G.sha256(ROOT/'cad/original-magnet-case.FCStd'),
              validation_seconds=time.monotonic()-start,
              overall_passed=not bool(report['mesh_warnings']),
              export_diagnostic_report='export-diagnostic.json',
              no_physical_or_slicer_qualification=True,
              physical_status='No physical print, fit test, slicing, adhesive/magnetic retention or qualification claimed.',
              limitations='Faceted frozen source shells, not recovered Fusion history or smooth fully-parametric shell. Native pocket-depth and source-face surface-fill features are retained; failed mesh tests stay failed.')
G.write_json(ROOT/'reports/validation.json',report)
App.closeDocument(D.Name)
print('VALIDATION COMPLETE',report['status'],report['validation_seconds'],flush=True)
