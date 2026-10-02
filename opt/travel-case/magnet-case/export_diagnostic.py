#!/usr/bin/env python3
"""One bounded export diagnostic: canonical CAD triangulation, exact orthogonal
print transform in double precision, one STL float32 rounding. No mesh healing,
source engraving repair, moved CAD geometry or suppressed failed checks.
"""
import struct
import math
import numpy as np
import FreeCAD as App
import Mesh
import geometry as G


def double_volume(mesh):
    points,tris=mesh.Topology
    p=np.array([[v.x,v.y,v.z] for v in points],dtype=np.float64)
    p-=p.mean(axis=0)
    a,b,c=p[np.array(tris)].transpose(1,0,2)
    return float(np.einsum('ij,ij->i',a,np.cross(b,c)).sum()/6)


def exact_cad_stl(kind,destination,shape):
    mesh=G.cad_mesh(shape)
    points,tris=mesh.Topology
    b=G.bounds(shape)
    def transform(p):
        return (p.x-b[0],p.y-b[1],p.z-b[2]) if kind=='base' else (p.x-b[0],b[4]-p.y,b[5]-p.z)
    xyz=[transform(p) for p in points]
    output=bytearray(('Edited native CAD '+kind+'; exact orthogonal print axes; float32 once').encode().ljust(80,b' ')[:80]+struct.pack('<I',len(tris)))
    for tri in tris:
        p=[xyz[i] for i in tri]
        a,b,c=[App.Vector(*v) for v in p]
        n=(b-a).cross(c-a); n.normalize()
        output.extend(G.STL_RECORD.pack(n.x,n.y,n.z,*(v for point in p for v in point),0))
    destination.write_bytes(output)
    return mesh


def localized(mesh,kind,placement):
    points,tris=mesh.Topology
    inverse=placement.inverse()
    records=[]
    for pair in mesh.getSelfIntersections():
        i,j=int(pair[0]),int(pair[1])
        a,b=[points[k] for k in tris[i]],[points[k] for k in tris[j]]
        na=(a[1]-a[0]).cross(a[2]-a[0]); nb=(b[1]-b[0]).cross(b[2]-b[0])
        na.normalize(); nb.normalize()
        segments=[inverse.multVec(p) for p in pair[2:]]
        vertices=[inverse.multVec(v) for v in a+b]
        bb=App.BoundBox()
        for v in vertices: bb.add(v)
        records.append({'facets':[i,j], 'shared_vertex_count':len(set(tris[i])&set(tris[j])),
            'abs_normal_dot':abs(na.dot(nb)),
            'plane_vertex_distance_max_mm':max(abs((p-a[0]).dot(na)) for p in b),
            'canonical_triangle_bounds_mm':[bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax],
            'canonical_segment_mm':[[v.x,v.y,v.z] for v in segments],
            'segment_length_mm':(segments[-1]-segments[0]).Length if len(segments)>1 else 0.})
    return records


def main():
    doc=App.openDocument(str(G.ROOT/'cad/original-magnet-case.FCStd'))
    report={'method':'Single canonical-CAD export candidate per part; exact signed-permutation print transform and one float32 rounding. Original source/CAD geometry untouched; no mesh repair or check suppression.',
            'native_document_sha256':G.sha256(G.ROOT/'cad/original-magnet-case.FCStd'), 'parts':{}}
    for kind,name,filename in [('base','Base','case_bottom_underside_down.stl'),('lid','Lid','case_lid_roof_down.stl')]:
        shape=doc.getObject(name).Shape
        placement=G.print_placement(G.bounds(shape),kind)
        destination=G.ROOT/'stl'/filename
        current=Mesh.Mesh(str(destination))
        current_checks=G.mesh_checks(current)
        current_locations=localized(current,kind,placement)
        candidate_path=G.ROOT/'.cache'/('diagnostic_'+filename)
        canonical=exact_cad_stl(kind,candidate_path,shape)
        candidate=Mesh.Mesh(str(candidate_path))
        checks=G.mesh_checks(candidate)
        # Candidate may only replace an export if strict topology is clean and
        # it adds no self-intersection failures. Failed checks remain failures.
        clean=checks['is_solid'] and not checks['non_manifold'] and all(checks[k]==0 for k in ('boundary_edges','non_two_incident_edges','inconsistent_edge_winding','zero_area_facets'))
        volume_error=abs(double_volume(candidate)-shape.Volume)
        assert volume_error <= shape.Area*0.00002
        improved=clean and checks['self_intersection_pair_count']<=current_checks['self_intersection_pair_count']
        if improved: destination.write_bytes(candidate_path.read_bytes())
        row={'before':current_checks,'before_localization':current_locations,
             'canonical_CAD_mesh':G.mesh_checks(canonical), 'candidate':checks,
             'candidate_localization':localized(candidate,kind,placement),
             'candidate_double_precision_volume_mm3':double_volume(candidate),
             'candidate_volume_delta_vs_CAD_mm3':double_volume(candidate)-shape.Volume,
             'candidate_selected':improved, 'selected_STL_sha256':G.sha256(destination)}
        report['parts'][kind]=row
        print('EXPORT DIAGNOSTIC',kind,'self intersections before/canonical/candidate',current_checks['self_intersection_pair_count'],row['canonical_CAD_mesh']['self_intersection_pair_count'],checks['self_intersection_pair_count'],'selected',improved,'double volume delta',row['candidate_volume_delta_vs_CAD_mm3'],flush=True)
        for label,records in [('before',current_locations),('candidate',row['candidate_localization'])]:
            print('LOCALIZATION',kind,label,[{'bounds':r['canonical_triangle_bounds_mm'],'segment_mm':r['segment_length_mm'],'shared_vertices':r['shared_vertex_count'],'plane_error_mm':r['plane_vertex_distance_max_mm']} for r in records],flush=True)
    G.write_json(G.ROOT/'reports/export-diagnostic.json',report)
    App.closeDocument(doc.Name)

if __name__=='__main__': main()
