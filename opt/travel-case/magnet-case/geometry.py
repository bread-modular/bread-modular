"""Self-contained release measurements/conversion. No closure-redesign dependencies.
Only FreeCAD's bundled Python/NumPy are needed; never repair source triangles.
"""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import math
import struct
import FreeCAD as App
import Mesh
import Part
import numpy as np

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT.parent / 'original' / 'case_1.0.0'
SOURCE_HASHES = {
    'bm_case_bottom_1.0.0.stl': '9b54e84fa84387984ac3beb4655cf139c6941f3c05d1e52d41358828d4c607b3',
    'bm_case_top_1.0.0.stl': '61a508e86d91a2fc7d8b43a006bd4d7f8b676c8fd83ab89cb2c56ee5cb6eb609',
    'breadmodular-case-1.0.0.f3z': 'f9c1daa038b2a73d891daa4cbb9b789b00389e58ce3e191e65417187f31e56fe',
}
MATRIX = (1, 0, 0, -20.68, 0, 0, -1, -7.98, 0, 1, 0, 15, 0, 0, 0, 1)
SEAM_Z = 15.0
SEW_TOLERANCE_MM = 0.00001
EXPECTED_CENTRES = [(5, 89.81), (81.04, 5), (81.04, 174.62),
                    (162.08, 5), (162.08, 174.62), (238.12, 89.81)]
STL_RECORD = struct.Struct('<12fH')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def verify_original():
    checks = {}
    for line in (ORIGINAL / 'SHA256SUMS').read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.strip().lstrip('*')
        actual = sha256(ORIGINAL / name)
        assert actual == digest, 'Upstream asset/metadata changed: ' + name
        checks[name] = actual
    for name, digest in SOURCE_HASHES.items():
        assert checks[name] == digest
    release = json.loads((ORIGINAL / 'release.json').read_text())
    for asset in release['assets']:
        assert asset['digest'] == 'sha256:' + checks[asset['name']]
        assert asset['size'] == (ORIGINAL / asset['name']).stat().st_size
    tag = json.loads((ORIGINAL / 'tag-ref.json').read_text())
    assert tag['object']['sha'] == '4bf18d99c3bf07a0d0a7c33ffb2b1b0f9e1d4337'
    return checks


def source_path(kind):
    return ORIGINAL / ('bm_case_bottom_1.0.0.stl' if kind == 'base'
                       else 'bm_case_top_1.0.0.stl')


def release_mesh(kind):
    mesh = Mesh.Mesh(str(source_path(kind)))
    mesh.transform(App.Matrix(*MATRIX))
    return mesh


def bounds(shape_or_mesh):
    b = shape_or_mesh.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def solid_from_mesh(mesh):
    shell = Part.Shape()
    shell.makeShapeFromMesh(mesh.Topology, SEW_TOLERANCE_MM)
    solid = Part.makeSolid(shell).removeSplitter()
    assert solid.isValid() and solid.isClosed() and len(solid.Solids) == 1
    return solid


def circle_fit(points):
    xy = np.array([[p.x, p.y] for p in points])
    mean = xy.mean(axis=0)
    local = xy - mean
    cx, cy, k = np.linalg.lstsq(np.c_[2 * local, np.ones(len(local))],
                               np.sum(local * local, axis=1), rcond=None)[0]
    centre = mean + [cx, cy]
    radius = math.sqrt(k + cx * cx + cy * cy)
    residual = max(abs(np.linalg.norm(xy - centre, axis=1) - radius))
    return centre.tolist(), float(radius), float(residual)


def measure_pockets(mesh, kind):
    """Discover circular floor caps from all horizontal triangles, not hole hints.

    Connected horizontal patches with a 5.2 mm fitted boundary identify the six
    floors. The original 24-sided outlines (not idealised circles) drive the CAD.
    Existing chamfers, including clipped base mouth facets, stay untouched.
    """
    points, triangles = mesh.Topology
    horizontal = []
    vertex_triangles = defaultdict(list)
    for i, tri in enumerate(triangles):
        z = [points[j].z for j in tri]
        if max(z) - min(z) < 1e-7:
            horizontal.append(i)
            for j in tri:
                vertex_triangles[j].append(i)
    unseen = set(horizontal)
    pockets = []
    while unseen:
        seed = unseen.pop()
        component = [seed]
        queue = [seed]
        while queue:
            for vertex in triangles[queue.pop()]:
                for neighbour in vertex_triangles[vertex]:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        component.append(neighbour)
                        queue.append(neighbour)
        edges = Counter(tuple(sorted((tri[a], tri[b])))
                        for i in component for tri in [triangles[i]]
                        for a, b in ((0, 1), (1, 2), (2, 0)))
        boundary = set(v for edge, count in edges.items() if count == 1 for v in edge)
        if not 12 <= len(boundary) <= 48:
            continue
        ring = [points[v] for v in boundary]
        centre, radius, residual = circle_fit(ring)
        if not 2.59 < radius < 2.61 or residual > 0.00002:
            continue
        floor_z = sum(p.z for p in ring) / len(ring)
        if not (12 < floor_z < 15 if kind == 'base' else 15 < floor_z < 18):
            continue
        x, y = centre
        ring.sort(key=lambda p: math.atan2(p.y - y, p.x - x))
        levels = defaultdict(list)
        for p in points:
            distance = math.hypot(p.x - x, p.y - y)
            if abs(p.z - SEAM_Z) < 3 and abs(distance - radius) < 0.00002:
                levels[round(p.z, 6)].append(p)
        neck_levels = [sum(p.z for p in group) / len(group)
                       for group in levels.values() if len(group) >= 20]
        neck_z = max(neck_levels) if kind == 'base' else min(neck_levels)
        mouth = [p for p in points if abs(p.z - SEAM_Z) < 1e-7
                 and 3.09 < math.hypot(p.x - x, p.y - y) < 3.11]
        _, mouth_radius, mouth_error = circle_fit(mouth)
        pockets.append({
            'centre_mm': centre, 'diameter_fit_mm': 2 * radius,
            'circle_fit_max_error_mm': residual,
            'floor_z_mm': floor_z, 'neck_z_mm': neck_z,
            'mouth_z_mm': SEAM_Z, 'full_depth_mm': abs(floor_z - SEAM_Z),
            'straight_depth_mm': abs(floor_z - neck_z),
            'chamfer_height_mm': abs(neck_z - SEAM_Z),
            'mouth_diameter_fit_mm': 2 * mouth_radius,
            'mouth_circle_fit_max_error_mm': mouth_error,
            'mouth_plane_vertex_count': len(mouth),
            'floor_polygon_vertex_count': len(ring),
            'floor_polygon_xy_mm': [[p.x, p.y] for p in ring],
        })
    pockets.sort(key=lambda p: (round(p['centre_mm'][0], 2), round(p['centre_mm'][1], 2)))
    assert len(pockets) == 6, 'Release must contain exactly six magnet floors per half'
    for pocket, expected in zip(pockets, EXPECTED_CENTRES):
        assert math.dist(pocket['centre_mm'], expected) < 0.00002
        assert pocket['floor_polygon_vertex_count'] == 24
        assert abs(pocket['full_depth_mm'] - 1.65) < 0.000001
        assert abs(pocket['chamfer_height_mm'] - 0.5) < 0.000001
    return pockets


def mesh_checks(mesh):
    """Keep failed source self-intersection checks visible; do not repair them."""
    points, triangles = mesh.Topology
    directed = Counter((tri[a], tri[b]) for tri in triangles
                       for a, b in ((0, 1), (1, 2), (2, 0)))
    undirected = Counter(tuple(sorted(edge)) for edge in directed.elements())
    pairs = mesh.getSelfIntersections()
    zero_area = sum((points[t[1]] - points[t[0]]).cross(points[t[2]] - points[t[0]]).Length
                    < 1e-12 for t in triangles)
    return {
        'facets': mesh.CountFacets, 'vertices': mesh.CountPoints,
        'bounds_mm': bounds(mesh), 'signed_volume_mm3': mesh.Volume,
        'is_solid': mesh.isSolid(), 'non_manifold': mesh.hasNonManifolds(),
        'boundary_edges': sum(c == 1 for c in undirected.values()),
        'non_two_incident_edges': sum(c != 2 for c in undirected.values()),
        'inconsistent_edge_winding': sum(directed[(a, b)] != directed[(b, a)]
                                         for a, b in undirected),
        'zero_area_facets': zero_area,
        'self_intersection_check_passed': not bool(pairs),
        'self_intersection_pair_count': len(pairs),
        'self_intersection_evidence': [
            {'facets': [int(p[0]), int(p[1])],
             'segment_mm': [[v.x, v.y, v.z] for v in p[2:]]} for p in pairs],
    }


def canonical_point(p):
    return (p[0] - 20.68, -p[2] - 7.98, p[1] + 15)


def print_placement(part_bounds, kind):
    if kind == 'base':
        position = App.Vector(-part_bounds[0], -part_bounds[1], -part_bounds[2])
        rotation = App.Rotation()
    else:
        position = App.Vector(-part_bounds[0], part_bounds[4], part_bounds[5])
        rotation = App.Rotation(App.Vector(1, 0, 0), 180)
    return App.Placement(position, rotation)


# Both final print files are tessellated from EDITED native CAD, never upstream triangles.
MESH_LINEAR_DEFLECTION_MM = 0.03
MESH_ANGULAR_DEFLECTION_RAD = math.radians(10)


def cad_mesh(print_shape):
    import MeshPart
    return MeshPart.meshFromShape(Shape=print_shape,
                                 LinearDeflection=MESH_LINEAR_DEFLECTION_MM,
                                 AngularDeflection=MESH_ANGULAR_DEFLECTION_RAD,
                                 Relative=False)


def write_print_stl(kind, destination, print_shape, canonical_shape):
    from export_diagnostic import exact_cad_stl
    mesh = exact_cad_stl(kind, Path(destination), canonical_shape)
    written = Mesh.Mesh(str(destination))
    assert written.CountFacets == mesh.CountFacets
    return {'sha256':sha256(destination), 'triangle_count':written.CountFacets,
            'orientation':'underside-down' if kind=='base' else 'exterior-roof-down',
            'geometry':'Final edited native CAD, canonical tessellation with exact orthogonal print transform; STL float32 rounded once; no source-triangle copy or mesh repair',
            'linear_deflection_mm':MESH_LINEAR_DEFLECTION_MM,
            'angular_deflection_rad':MESH_ANGULAR_DEFLECTION_RAD,
            'print_bounds_mm':bounds(written)}
