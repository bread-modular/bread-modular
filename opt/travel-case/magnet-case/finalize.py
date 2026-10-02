#!/usr/bin/env python3
"""Audit pristine sources/cleanup and write measured review handoff + hashes.
A remaining failed mesh check is a blocker, not an all-mesh-pass.
"""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parent

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    v=json.loads((ROOT/'reports/validation.json').read_text())
    b=json.loads((ROOT/'reports/build.json').read_text())
    r=json.loads((ROOT/'reports/reopen.json').read_text())
    c=json.loads((ROOT/'reports/cleanup.json').read_text())
    p=json.loads((ROOT/'provenance.json').read_text())
    assert b['clean_geometry_rebuilt_from_release_only'] and b['exports_from_edited_CAD'] and r['passed']
    assert v['saved_document_sha256']==digest(ROOT/'cad/original-magnet-case.FCStd')
    preview_metadata=json.loads((ROOT/'.cache/preview-cad.json').read_text())
    assert preview_metadata['native_document_sha256']==v['saved_document_sha256']
    current_preview_hash=digest(ROOT/'previews/filled-surfaces.png')
    if p['preview']['sha256']!=current_preview_hash:
        p['preview']['uploaded_url']='Not uploaded in this rebuild; see previews/filled-surfaces.png'
    p['preview']['input_native_document_sha256']=v['saved_document_sha256']
    p['preview']['sha256']=current_preview_hash
    p['authorized_surface_regions']={k:v['parts'][k]['authorized_fill_region_bounds_mm'] for k in ('base','lid')}
    p['source_to_final_material_mm3']={k:{'added':v['parts'][k]['added_material_vs_original_mm3'],
        'removed':v['parts'][k]['removed_material_vs_original_mm3'],
        'added_outside_authorized_region':v['parts'][k]['added_outside_authorized_region_mm3']} for k in ('base','lid')}
    (ROOT/'provenance.json').write_text(json.dumps(p,indent=2)+'\n')
    assert sorted(x.name for x in ROOT.parent.iterdir())==['README.md','magnet-case','original']
    assert all(not (ROOT.parent/name).exists() for name in c['authorized_removed_design_directories'])
    for name,expected in c['immutable_preserved_source_metadata_license_sha256'].items():
        assert digest(ROOT.parent/'original/case_1.0.0'/name)==expected
    for kind,filename in [('base','case_bottom_underside_down.stl'),('lid','case_lid_roof_down.stl')]:
        assert digest(ROOT/'stl'/filename)==v['parts'][kind]['written_STL_sha256']==b['print_exports'][kind]['sha256']
        assert v['parts'][kind]['removed_material_vs_original_mm3'] < 1e-5
        assert v['parts'][kind]['added_outside_authorized_region_mm3'] < 1e-5
    base,lid=v['parts']['base'],v['parts']['lid']
    assert lid['written_STL_mesh']['self_intersection_check_passed']
    assert not base['written_STL_mesh']['self_intersection_check_passed']
    fmt=lambda xs:' × '.join(f'{x:.8f}' for x in xs)
    rows=[]
    for name,part in [('Base',base),('Lid',lid)]:
        rows.append(f"| {name} | {fmt(part['dimensions_mm'])} | {part['bounds_mm'][2]:.2f}..{part['bounds_mm'][5]:.2f} | {part['added_material_vs_original_mm3']:.9f} | {part['removed_material_vs_original_mm3']:.1f} |")
    text=f"""# Validation — original magnets / requested flush surfaces

**CAD, authorized-material, protected-feature, native reopen/depth-edit and STL surface-fidelity checks pass. Overall all-mesh status is NOT PASS:** the base's preserved internal engraving still fails self-intersection checking. The lid export is clean after the single explicitly authorized measured-logo-region fill. No physical print or slicer qualification is claimed.

## Measured edits / dimensions

Assembly: **{fmt(v['assembly_dimensions_mm'])} mm**; nominal **243.12 × 179.62 × 77.5 mm**, original exterior bounds retained.

| Part | Measured XYZ size (mm) | Assembly Z (mm) | Added material (mm³) | Removed (mm³) |
|---|---|---|---|---|
{chr(10).join(rows)}

- **Base exterior only:** two capsule-shaped source floor faces at Z1, filled 1.0 mm to adjacent underside Z0. X20.046623..223.073380; Y20..60.000004 and Y119.619995..159.620010. Their boundaries exactly match the two holes in the source Z0 underside face. Final underside is one Z0 face with one outer wire. **Inner engraving Z7.5..8, floor and mounts remain untouched.**
- **Lid backside only:** explicitly authorized measured logo bounding region X61.975433..177.036880, Y81.886337..97.430740, **Z75..75.5 only**. Fills the 0.5 mm recess to inner roof Z75; overlap into adjacent already-solid roof adds no material there. Exterior roof remains Z77.5. This single bounded fallback removed residual crossed-wall fragments left by the 34-floor-fragment method; the source releases were not repaired or altered.
- Source-to-final removed material / added outside the authorized regions / missing authorized fills: **0.0 mm³ for both parts**. Projected fill caps not covered by final target planes: **0.0 mm²**. Original intersecting engraving topology makes summed source area identities imperfect; the report records that discrepancy rather than substituting it for exact cap/material tests.

## Original functional geometry / native document

Both final parts are closed, basic-OCC-valid **single solids**. Independent final-CAD pocket discovery finds **6+6** original 24-sided Ø5.2 mm pockets, full depth about 1.65 mm, straight depth 1.15 mm, original 0.5 mm mouth chamfers / fitted Ø6.2 mm mouths. Nominal centres:

`(5,89.81), (81.04,5), (81.04,174.62), (162.08,5), (162.08,174.62), (238.12,89.81)` mm.

Maximum measured pocket deltas: **{base['pocket_geometry_max_delta_mm']:.3g} / {lid['pocket_geometry_max_delta_mm']:.3g} mm**. All **{base['unchanged_out_of_region_face_count']} / {lid['unchanged_out_of_region_face_count']}** source faceted surfaces outside authorized fill bounds match final face centroid/area signatures, including inner base floor, PCB mounts, connectors, skirt/seam/lip, pockets and chamfers. Maximum matched centroid errors: {base['unchanged_face_centroid_max_error_mm']:.3g} / {lid['unchanged_face_centroid_max_error_mm']:.3g} mm. This is not a smooth-surface or Hausdorff claim.

Fresh-process saved FCStd reopen, forced recompute, native depth edits +0.2 mm base / -0.2 mm lid, and restoration of defaults **passed**. No Python proxies or project-module imports are needed to reopen. **Frozen faceted source shells and script-rebuilt, validated direct-OCC surface-filled `Part::Feature` shells**, with labelled measured fill profiles/extrusions as evidence; downstream Sketcher/extrusion/fuse/cut pocket features and print-placement links remain live. Surface fill-depth parameters are **not** live shell drivers. No recovered Fusion history / smooth fully-parametric shell claim.

## Written STL fidelity / honest remaining warning

Both print files export **edited CAD**, not transformed original triangles. Base underside-down; lid exterior-roof-down; lowest print Z0. Canonical CAD tessellation, exact orthogonal double-precision placement, and one STL float32 rounding. Linear deflection 0.03 mm / angular deflection 10°.

- Bounds / vertex correspondence: <=0.00002 mm float32 allowance; observed maximum {base['print_triangle_coordinate_error_max_mm']:.3g} / {lid['print_triangle_coordinate_error_max_mm']:.3g} mm.
- OCC can choose different diagonals in coplanar polygons. The validator proves changed planar patches retain the same boundary-edge multiset and area, rather than requiring triangle-index equality. {base['different_coplanar_triangle_records']} / {lid['different_coplanar_triangle_records']} triangle records differed in this independent re-tessellation.
- Independently accumulated float64 STL volume deltas vs CAD: **{base['written_STL_volume_delta_vs_CAD_mm3']:.9f} / {lid['written_STL_volume_delta_vs_CAD_mm3']:.9f} mm³**; bounded by surface area × 0.00002 mm. Mesh library float32 accumulated volumes are not used as the precision fidelity test.

| Written mesh check | Base | Lid |
|---|---|---|
| Closed / manifold | Pass | Pass |
| Boundary / non-two-incident edges | 0 / 0 | 0 / 0 |
| Winding conflicts / zero-area facets | 0 / 0 | 0 / 0 |
| Self-intersection pairs, source → final | **12 → 13: FAIL** | **19 → 0: PASS** |

Base failures localize to original **internal engraving Z7.5..8** (approximately X48.11..150.94, Y89.30..98.06). Source engraving geometry was not changed; re-tessellation changes the pair count, so **not “unchanged 12 warnings”**. The historical fragmented-logo lid had 28 final / 30 canonical flags localized to old logo crossed-wall slivers, not merely float32/coplanar T-junctions. Exact-transform diagnostic did not resolve them. **One authorized whole measured-logo-region fill resolved the lid to 0 flags** (`reports/lid-region-probe.json`). No further alternatives or source-base engraving repairs were attempted.

## Artifacts / cleanup / preview

- `cad/original-magnet-case.FCStd`; two final edited-CAD STLs in `stl/`; one `previews/filled-surfaces.png`.
- Preview is a measured before/after orthographic projection of **saved native source/final BRep tessellations**, not a conceptual drawing or a GUI screenshot. Uploaded image: `{p['preview']['uploaded_url']}`. Green outlines are annotations, not raised pads.
- Removed **{c['deleted_tracked_file_count']} tracked rejected-design files** under flush-latch, slide-clips, lock-studies (including c-tight), quarter-turn-case; no screw-lock files were present. Exact deletion/source-hash audit remains in `reports/cleanup.json`. No Git history/worktree/branch removal or outside-project edits.
- Pristine release STLs/F3Z, metadata, inventory, MIT license and original checksums remain byte-identical. Only the explanatory original README navigation changes.
- All deliverable hashes: `SHA256SUMS`. Changes staged/uncommitted for review; **no physical, sliced, fit, adhesive, retention, durability or print-safety qualification**.
"""
    (ROOT/'VALIDATION.md').write_text(text)
    paths=sorted(path for path in ROOT.rglob('*') if path.is_file() and '.cache' not in path.parts
                 and '.runtime' not in path.parts and '__pycache__' not in path.parts
                 and path.name!='SHA256SUMS' and not path.name.endswith(('.FCStd1','.FCBak')))
    (ROOT/'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.relative_to(ROOT)}\n' for path in paths))
    print('FINAL HANDOFF/HASH AUDIT:',len(paths),'files; native/protected geometry PASS, lid mesh PASS; base engraving self-intersection FAIL retained.')

if __name__=='__main__': main()
