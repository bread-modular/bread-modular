#!/usr/bin/env python3
"""Strict independent saved-CAD/written-STL checks; no mesh repair or fit guarantee."""
import json
import time
import traceback
import numpy as np
from shapely.geometry import Polygon, GeometryCollection
import FreeCAD as App
import Part
import Mesh
import tight_gauge as T
S = T.S
TOL = 1e-5


def bounds(s):
    b = s.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def width(s, x, w, y=10, z=2.5):
    edges = s.common(Part.makeLine(S.V(x-1, y, z), S.V(x+w+1, y, z))).Edges
    edges = sorted(edges, key=lambda e: e.BoundBox.XMin)
    assert len(edges) == 2, 'Two intact channel side lands required'
    return edges[1].BoundBox.XMin - edges[0].BoundBox.XMax


def section(s, z):
    result = GeometryCollection()
    for wire in s.slice(S.V(0, 0, 1), z):
        poly = Polygon([(round(v.x, 8), round(v.y, 8)) for v in wire.discretize(Deflection=.015)])
        assert poly.is_valid
        result = result.symmetric_difference(poly)
    return result


def validate():
    start = time.monotonic()
    r = {'status': 'RUNNING', 'checks': [], 'channels': [], 'limitations': [
        'New female UNSLICED/UNPRINTED; filament unknown. No G-code, printer operation or physical fit guarantee.',
        'CAD continuous straight-path enclosure and samples do not simulate extrusion, seam bumps, warping or material.',
        'Zero nominal clearance has expected zero contact distances, NOT evidence of physical sliding. Never force or sand contact lands.',
        'Support screen uses assumed 0.20 mm layers and 45-degree growth; not slicer toolpaths. Preview locally with unchanged material/profile.']}

    def require(ok, test, **data):
        r['checks'].append(dict(test=test, passed=bool(ok), **data))
        if not ok:
            raise AssertionError(test + ': ' + str(data))

    def clear(a, b, test):
        v = abs(a.common(b).Volume)
        require(v < TOL, test, positive_volume_intersection_mm3=v)
        return v

    def mesh_check(path, cad, test):
        m = Mesh.Mesh(str(path))
        points, faces = m.Topology
        xyz = np.array([[p.x, p.y, p.z] for p in points])
        tri = xyz[np.array(faces)]
        signed = float(np.einsum('ij,ij->i', tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()/6)
        data = dict(file=str(path.relative_to(T.PARENT)), sha256=T.digest(path),
                    vertices=m.CountPoints, triangles=m.CountFacets, watertight=m.isSolid(),
                    components=m.countComponents(), nonmanifold=m.hasNonManifolds(),
                    nonuniform_orientation=m.hasNonUniformOrientedFacets(), self_intersections=m.hasSelfIntersections(),
                    signed_volume_mm3=signed, cad_volume_mm3=cad.Volume, bed_bounds_mm=bounds(m))
        require(data['watertight'] and data['components'] == 1 and not data['nonmanifold'] and
                not data['nonuniform_orientation'] and not data['self_intersections'] and signed > 0 and
                abs(m.BoundBox.ZMin) < TOL and abs(signed-cad.Volume) < .005,
                test + ' actual STL connected/watertight/manifold/outward/no self-intersections/bed Z0', **data)
        require(max(abs(a-b) for a, b in zip(bounds(m), bounds(cad))) < TOL, test + ' STL/CAD bounds match')
        # Reconstruct the ACTUAL exported triangles, unmodified, to compare full geometry.
        native = Part.Shape()
        native.makeShapeFromMesh(m.Topology, 1e-6)
        solid = Part.makeSolid(native).removeSplitter()
        require(solid.isValid() and solid.isClosed() and len(solid.Solids) == 1, test + ' actual mesh BRep valid')
        # Binary STL uses float32: bounded 1e-6 mm comparison tolerance avoids
        # coplanar OCC slivers. No mesh changes or collision-check tolerance change.
        a, b = cad.cut(solid, 1e-6), solid.cut(cad, 1e-6)
        delta = a.Volume + b.Volume
        samples = list(xyz) + list(tri.mean(axis=1))
        distances = [Part.Vertex(S.V(*q)).distToShape(cad.Shells[0])[0] for q in samples]
        distances += [v.distToShape(solid.Shells[0])[0] for v in cad.Vertexes]
        deviation = max(distances)
        data.update(comparison_boolean_tolerance_mm=1e-6, symmetric_difference_mm3=delta,
                    surface_sample_max_distance_mm=deviation, surface_samples=len(distances))
        require(a.isValid() and b.isValid() and delta < .005 and deviation < TOL,
                test + ' actual STL matches complete CAD (not just volume/bounds)',
                symmetric_difference_mm3=delta, comparison_boolean_tolerance_mm=1e-6,
                surface_sample_max_distance_mm=deviation, surface_samples=len(distances))
        return solid, data

    try:
        r['baseline_before'] = T.baseline_guard()
        require(len(list((T.ROOT/'stl').glob('*.stl'))) == 1 and T.STL.exists(), 'Exactly ONE additional female STL; no duplicate male')
        d = T.reopened()
        p = S.values(d.Parameters)
        require(p == T.DEFAULTS, 'Saved inputs preserve requested total-gap order and fixed dimensions', parameters=p)
        s = d.Female.Shape.copy()
        require(s.isValid() and s.isClosed() and len(s.Solids) == 1 and s.Volume > 0 and 'Error' not in d.Female.State,
                'Reopened/recomputed live female: single valid closed CAD solid', volume_mm3=s.Volume, bed_bounds_mm=bounds(s))
        require(abs(s.BoundBox.ZMin) < TOL and abs(s.BoundBox.XLength-34.2) < TOL and
                abs(s.BoundBox.YLength-29) < TOL and abs(s.BoundBox.ZLength-5) < TOL, 'Small female dimensions 34.2 x 29 x 5 mm at bed Z0')
        fresh = T.shape(p)
        require(s.cut(fresh).Volume + fresh.cut(s).Volume < TOL, 'Saved geometry matches fresh helper recipe including labels')
        # Actual edit AFTER reopen: verify changed widths, then restore without saving.
        d.Parameters.GaugeGaps = [.30, .20, .00]
        d.recompute()
        changed = d.Female.Shape
        require(changed.isValid() and len(changed.Solids) == 1 and abs(width(changed, 2.4, 8.3)-8.3) < TOL and
                abs(changed.Volume-s.Volume) > .01 and 'Error' not in d.Female.State, 'Reopened GaugeGaps edit changes live channel geometry')
        d.Parameters.GaugeGaps = p['GaugeGaps']
        d.recompute()
        require(s.cut(d.Female.Shape).Volume + d.Female.Shape.cut(s).Volume < TOL, 'Edit restoration exact; delivered CAD not overwritten')
        App.closeDocument(d.Name)

        # Read only the existing saved male; no other kit parts rebuilt or saved.
        baseline = App.openDocument(str(T.PARENT/'cad/lock-studies.FCStd'))
        bp = S.values(baseline.Parameters)
        S.check(bp)
        male = baseline.C_MALE.Shape.copy()
        male.Placement = baseline.C_MALE.Placement.inverse().multiply(male.Placement)
        App.closeDocument(baseline.Name)
        try:
            S.check(dict(bp, GaugeGaps=p['GaugeGaps']))
        except AssertionError:
            pass
        else:
            raise AssertionError('Baseline check must still reject non-baseline gaps')
        male_mesh, r['existing_male_stl'] = mesh_check(T.PARENT/'stl/C_male_8.00.stl', S.bed_shape(male, 'C_MALE'), 'Original male')
        female_mesh, r['female_stl'] = mesh_check(T.STL, s, 'New female')
        rail = male.common(S.box(-10, 20, 2, 18, 1, 4))
        mesh_rail = male_mesh.common(S.box(0, 12, 13, 29, 1, 4))
        require(abs(rail.BoundBox.XLength-8) < TOL and abs(mesh_rail.BoundBox.XLength-8) < TOL,
                'Existing rail measured 8.00 on CAD AND actual STL full-size lands', cad_width_mm=rail.BoundBox.XLength, stl_width_mm=mesh_rail.BoundBox.XLength)

        # These two boxes conservatively enclose every point of the original male.
        rail_box = S.box(0, 8, 0, 20, 0, 5)
        handle_box = S.box(-2, 10, -11, 0, 0, 5)
        require(male.cut(S.fuse([rail_box, handle_box])).Volume < TOL, 'Actual original male enclosed by rail/handle bounds')
        walls = s.common(Part.makeLine(S.V(-1, 10, 2.5), S.V(35.2, 10, 2.5))).Edges
        require(len(walls) == 4 and all(abs(e.Length-2.4) < TOL for e in walls), 'Four full-size walls remain 2.4 mm')
        x = 2.4
        for gap in p['GaugeGaps']:
            w = 8 + gap
            cad_widths = [width(s, x, w, y, z) for y in (1, 10, 19) for z in (.5, 2.5, 4.5)]
            stl_widths = [width(female_mesh, x, w, y, z) for y in (1, 10, 19) for z in (.5, 2.5, 4.5)]
            require(all(abs(v-w) < TOL for v in cad_widths+stl_widths), f'G{gap:.2f} measured widths on full-size CAD/STL lands', cad_widths_mm=cad_widths, stl_widths_mm=stl_widths)
            require(abs(width(s, x, w, z=.1)-(w+.6)) < TOL, f'G{gap:.2f} retained 0.4 mm / 45-degree bottom-edge relief')
            clear(S.box(x, x+w, 0, 20, 0, 6), s, f'G{gap:.2f} complete 20 mm channel open floor/roof-free')
            cx = x + gap/2
            # Continuous all-position proof: conservative swept rail+handle boxes,
            # not just finite samples. Covers every y translation in [-20, 0].
            sweep = S.fuse([S.box(cx, cx+8, -20, 20, 0, 5), S.box(cx-2, cx+10, -31, 0, 0, 5)])
            overlap = clear(sweep, s, f'G{gap:.2f} entire continuous straight insertion/withdrawal envelope clear')
            samples = []
            for offset in np.linspace(-20, 0, 41):
                pose = S.moved(male, x=cx, y=float(offset))
                volume = clear(pose, s, f'G{gap:.2f} straight path y={offset:.2f}')
                samples.append(dict(y_mm=float(offset), intersection_mm3=volume, distance_mm=pose.distToShape(s)[0]))
            land = S.moved(rail, x=cx)
            distance = land.distToShape(s)[0]
            require(abs(distance-gap/2) < TOL, f'G{gap:.2f} expected centred land distance (zero contact allowed)', distance_mm=distance)
            r['channels'].append(dict(label=f'G{gap:.2f}', total_gap_mm=gap, per_side_mm=gap/2,
                                      female_width_mm=w, male_width_mm=8, engagement_mm=20,
                                      continuous_sweep_intersection_mm3=overlap, samples=samples))
            x += w + 2.4

        # Only the recessed labels differ from the relieved, unlabelled comb.
        blank = S.box(0, 34.2, 0, 29, 0, 5)
        x = 2.4
        for gap in p['GaugeGaps']:
            blank = blank.cut(S.box(x, x+8+gap, -1, 20, -1, 6))
            x += 8 + gap + 2.4
        ink = S.relief(blank.removeSplitter(), p).cut(s)
        require(ink.Volume > 0 and ink.BoundBox.YMin > 22.9 and ink.BoundBox.ZMin >= 4.65-TOL,
                'G0.40 / G0.20 / G0.00 and C-F engraved off all contact lands', removed_mm3=ink.Volume, engraving_bounds_mm=bounds(ink))
        previous = None
        max_area = 0
        for z in np.arange(.1, 5, .2):
            poly = section(s, float(z))
            if previous is not None:
                area = poly.difference(previous.buffer(.2, resolution=12)).area
                max_area = max(max_area, area)
            previous = poly
        require(max_area < .1, 'Minimal 0.20 mm layer / 45-degree growth support screen', max_new_area_mm2=max_area)
        r['support'] = dict(status='UNSLICED_GEOMETRIC_SCREEN', layer_height_mm=.2,
                            roofs=False, supports_planned=False, max_new_area_mm2=max_area, local_slicer_preview_required=True)
        r['baseline_after'] = T.baseline_guard()
        require(r['baseline_before'] == r['baseline_after'], 'All 20 immutable parent artifacts and original male hash unchanged; 22 current parent checksums verified')
        r['cad_sha256'] = T.digest(T.CAD)
        r['toolchain'] = dict(FreeCAD=App.Version(), OCC=Part.OCC_VERSION)
        r['status'] = 'PASS_GEOMETRIC_ONLY_UNSLICED_UNPRINTED'
    except Exception as error:
        r['status'] = 'FAIL'
        r['error'] = str(error)
        traceback.print_exc()
        raise
    finally:
        r['seconds'] = round(time.monotonic()-start, 3)
        T.REPORT.parent.mkdir(exist_ok=True)
        T.REPORT.write_text(json.dumps(r, indent=2) + '\n')
    print('VALIDATION PASS:', len(r['checks']), 'checks;', r['seconds'], 'seconds', flush=True)
    return r


if __name__ == '__main__':
    try:
        validate()
    except Exception:
        raise SystemExit(1)
