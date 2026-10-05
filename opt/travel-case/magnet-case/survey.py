#!/usr/bin/env python3
"""Bounded, source-only two-face survey in canonical assembly coordinates.
No surface edit is inferred from a generic rectangle or from mounting features.
"""
from collections import defaultdict
import FreeCAD as App
import numpy as np
import geometry as G


def plane_faces(shape, z, sign=None):
    result = []
    for face in shape.Faces:
        b = face.BoundBox
        if abs(b.ZMin-z) < 1e-7 and abs(b.ZMax-z) < 1e-7:
            n = face.normalAt(0, 0)
            if sign is None or n.z*sign > 0.99:
                result.append(face)
    return result


def rings_from_faces(faces):
    rings = []
    for face in faces:
        for wire in face.Wires:
            points = [v.Point for v in wire.OrderedVertexes]
            if (points[0]-points[-1]).Length < 1e-8:
                points.pop()
            assert len(points) >= 3
            rings.append([[p.x, p.y] for p in points])
    return rings


def vertical_envelope(mesh):
    points, triangles = mesh.Topology
    xyz = np.array([[p.x, p.y, p.z] for p in points])
    # Interior grid plus the known central engraving region, excluding the border.
    xs = np.linspace(2.75, 240.37, 96)
    ys = np.linspace(2.75, 176.87, 72)
    x, y = np.meshgrid(xs, ys)
    x, y = x.ravel(), y.ravel()
    low, high = np.full(len(x), np.inf), np.full(len(x), -np.inf)
    for indices in triangles:
        a, b, c = xyz[list(indices)]
        den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den) < 1e-12:
            continue
        u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
        v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
        mask = (u >= -1e-9) & (v >= -1e-9) & (u+v <= 1+1e-9)
        z = u*a[2]+v*b[2]+(1-u-v)*c[2]
        low[mask] = np.minimum(low[mask], z[mask])
        high[mask] = np.maximum(high[mask], z[mask])
    hit = np.isfinite(low) & np.isfinite(high)
    assert np.count_nonzero(hit) > 6800
    # Rounded outer corners legitimately have no surface at some rectangular-grid points.
    return {'attempted_ray_count':len(x), 'surface_hit_count':int(hit.sum()),
            'outside_rounded_footprint_count':int((~hit).sum()),
            'first_from_below_z_range_mm':[float(low[hit].min()),float(low[hit].max())],
            'first_from_above_z_range_mm':[float(high[hit].min()),float(high[hit].max())]}


def survey_shape(shape, mesh, kind):
    groups = defaultdict(lambda: {'area_mm2':0., 'face_count':0})
    for face in shape.Faces:
        b = face.BoundBox
        if b.ZLength < 1e-7:
            key = (round(b.ZMin, 6), 1 if face.normalAt(0,0).z > 0 else -1)
            groups[key]['area_mm2'] += face.Area
            groups[key]['face_count'] += 1
    z = 7.5 if kind == 'base' else 75.5
    sign = 1 if kind == 'base' else -1
    recess = plane_faces(shape, z, sign)
    assert recess
    rings = rings_from_faces(recess)
    combined = App.BoundBox()
    for f in recess: combined.add(f.BoundBox)
    outer_z = 0.0 if kind == 'base' else 77.5
    exterior = plane_faces(shape, outer_z, -sign)
    assert exterior
    underside_recess = None
    if kind == 'base':
        inset = plane_faces(shape, 1.0, -1)
        assert len(inset) == 2 and all(len(f.Wires) == 1 for f in inset)
        inset_rings = rings_from_faces(inset)
        # The two Z1 floor contours must exactly coincide in XY with the two
        # inner wires of the surrounding Z0 outer underside, proving inset bays
        # rather than feet, mounts, an inner-floor recess or the Z15 seam.
        outer_holes = [w for f in exterior for w in f.Wires if not w.isSame(f.OuterWire)]
        assert len(outer_holes) == 2
        hole_xy = {tuple(round(c, 7) for c in (v.Point.x,v.Point.y)) for w in outer_holes for v in w.Vertexes}
        inset_xy = {tuple(round(c, 7) for c in p) for r in inset_rings for p in r}
        assert hole_xy == inset_xy
        underside_recess = {'floor_z_mm':1.0, 'adjacent_outer_plane_z_mm':0.0,
                            'depth_mm':1.0, 'floor_face_count':2,
                            'area_mm2':sum(f.Area for f in inset),
                            'individual_bounds_mm':[G.bounds(f) for f in inset],
                            'boundary_rings_xy_mm':inset_rings,
                            'floor_boundary_matches_surrounding_Z0_holes':True}
    return {
        'source_sha256':G.sha256(G.source_path(kind)), 'bounds_mm':G.bounds(shape),
        'horizontal_planes':[{'z_mm':z,'normal_z_sign':s,**row} for (z,s),row in sorted(groups.items())],
        'exterior_face':{'plane_z_mm':outer_z, 'face_count':len(exterior),
                         'wire_counts':[len(f.Wires) for f in exterior],
                         'area_mm2':sum(f.Area for f in exterior),
                         'boundary_rings_xy_mm':rings_from_faces(exterior)},
        'interior_engraving':{'floor_z_mm':z, 'adjacent_plane_z_mm':8. if kind=='base' else 75.,
                             'depth_mm':0.5, 'floor_face_count':len(recess),
                             'boundary_ring_count':len(rings),
                             'area_mm2':sum(f.Area for f in recess),
                             'bounds_mm':[combined.XMin,combined.YMin,combined.ZMin,combined.XMax,combined.YMax,combined.ZMax],
                             'boundary_rings_xy_mm':rings},
        'exterior_underside_recess':underside_recess,
        'vertical_envelope_grid':vertical_envelope(mesh),
        'interpretation':('Exterior underside has TWO identifiable capsule-shaped inset bays at Z1, surrounded by the original outer bottom Z0. Fill only those exact source contours down to Z0. Internal engraving at Z7.5..8 and mounts are separate and untouched.' if kind=='base' else 'Backside/internal roof logo recess Z75..75.5 is identifiable; fill only its measured contours to Z75. Exterior roof remains Z77.5.')
    }


def main():
    G.verify_original()
    report={'method':'Source meshes converted to valid faceted BReps; horizontal-face/wire inventory and 6912 vertical source-mesh rays per part. Both faces inspected.', 'parts':{}}
    for kind in ('base','lid'):
        mesh=G.release_mesh(kind)
        shape=G.solid_from_mesh(mesh)
        row=survey_shape(shape,mesh,kind)
        report['parts'][kind]=row
        print(kind, row['bounds_mm'], 'exterior', {k:v for k,v in row['exterior_face'].items() if k!='boundary_rings_xy_mm'}, 'engraving', {k:v for k,v in row['interior_engraving'].items() if k!='boundary_rings_xy_mm'}, 'rays',row['vertical_envelope_grid'],flush=True)
        print('PLANES',kind,row['horizontal_planes'],flush=True)
    report['base_decision']='Unambiguous recessed EXTERIOR bottom: two Z1 capsule bays whose exact boundaries match the surrounding Z0 underside. Authorized fill is only Z0..1 in those two measured contours; no interior-floor or mounting edits.'
    (G.ROOT/'reports').mkdir(exist_ok=True)
    G.write_json(G.ROOT/'reports/surface-survey.json',report)

if __name__=='__main__': main()
