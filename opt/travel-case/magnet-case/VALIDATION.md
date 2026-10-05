# Validation — original magnets / requested flush surfaces

**CAD, authorized-material, protected-feature, native reopen/depth-edit and STL surface-fidelity checks pass. Overall all-mesh status is NOT PASS:** the base's preserved internal engraving still fails self-intersection checking. The lid export is clean after the single explicitly authorized measured-logo-region fill. No physical print or slicer qualification is claimed.

## Measured edits / dimensions

Assembly: **243.11999481 × 179.62001036 × 77.50000000 mm**; nominal **243.12 × 179.62 × 77.5 mm**, original exterior bounds retained.

| Part | Measured XYZ size (mm) | Assembly Z (mm) | Added material (mm³) | Removed (mm³) |
|---|---|---|---|---|
| Base | 243.11999481 × 179.62001036 × 15.00000000 | 0.00..15.00 | 15555.070342294 | 0.0 |
| Lid | 243.11999481 × 179.62001036 × 63.50000000 | 14.00..77.50 | 197.005414206 | 0.0 |

- **Base exterior only:** two capsule-shaped source floor faces at Z1, filled 1.0 mm to adjacent underside Z0. X20.046623..223.073380; Y20..60.000004 and Y119.619995..159.620010. Their boundaries exactly match the two holes in the source Z0 underside face. Final underside is one Z0 face with one outer wire. **Inner engraving Z7.5..8, floor and mounts remain untouched.**
- **Lid backside only:** explicitly authorized measured logo bounding region X61.975433..177.036880, Y81.886337..97.430740, **Z75..75.5 only**. Fills the 0.5 mm recess to inner roof Z75; overlap into adjacent already-solid roof adds no material there. Exterior roof remains Z77.5. This single bounded fallback removed residual crossed-wall fragments left by the 34-floor-fragment method; the source releases were not repaired or altered.
- Source-to-final removed material / added outside the authorized regions / missing authorized fills: **0.0 mm³ for both parts**. Projected fill caps not covered by final target planes: **0.0 mm²**. Original intersecting engraving topology makes summed source area identities imperfect; the report records that discrepancy rather than substituting it for exact cap/material tests.

## Original functional geometry / native document

Both final parts are closed, basic-OCC-valid **single solids**. Independent final-CAD pocket discovery finds **6+6** original 24-sided Ø5.2 mm pockets, full depth about 1.65 mm, straight depth 1.15 mm, original 0.5 mm mouth chamfers / fitted Ø6.2 mm mouths. Nominal centres:

`(5,89.81), (81.04,5), (81.04,174.62), (162.08,5), (162.08,174.62), (238.12,89.81)` mm.

Maximum measured pocket deltas: **1.42e-14 / 2.66e-15 mm**. All **3870 / 2191** source faceted surfaces outside authorized fill bounds match final face centroid/area signatures, including inner base floor, PCB mounts, connectors, skirt/seam/lip, pockets and chamfers. Maximum matched centroid errors: 2.7e-13 / 9.95e-14 mm. This is not a smooth-surface or Hausdorff claim.

Fresh-process saved FCStd reopen, forced recompute, native depth edits +0.2 mm base / -0.2 mm lid, and restoration of defaults **passed**. No Python proxies or project-module imports are needed to reopen. **Frozen faceted source shells and script-rebuilt, validated direct-OCC surface-filled `Part::Feature` shells**, with labelled measured fill profiles/extrusions as evidence; downstream Sketcher/extrusion/fuse/cut pocket features and print-placement links remain live. Surface fill-depth parameters are **not** live shell drivers. No recovered Fusion history / smooth fully-parametric shell claim.

## Written STL fidelity / honest remaining warning

Both print files export **edited CAD**, not transformed original triangles. Base underside-down; lid exterior-roof-down; lowest print Z0. Canonical CAD tessellation, exact orthogonal double-precision placement, and one STL float32 rounding. Linear deflection 0.03 mm / angular deflection 10°.

- Bounds / vertex correspondence: <=0.00002 mm float32 allowance; observed maximum 4.29e-16 / 3.81e-06 mm.
- OCC can choose different diagonals in coplanar polygons. The validator proves changed planar patches retain the same boundary-edge multiset and area, rather than requiring triangle-index equality. 54 / 28 triangle records differed in this independent re-tessellation.
- Independently accumulated float64 STL volume deltas vs CAD: **0.000801174 / 0.006263417 mm³**; bounded by surface area × 0.00002 mm. Mesh library float32 accumulated volumes are not used as the precision fidelity test.

| Written mesh check | Base | Lid |
|---|---|---|
| Closed / manifold | Pass | Pass |
| Boundary / non-two-incident edges | 0 / 0 | 0 / 0 |
| Winding conflicts / zero-area facets | 0 / 0 | 0 / 0 |
| Self-intersection pairs, source → final | **12 → 13: FAIL** | **19 → 0: PASS** |

Base failures localize to original **internal engraving Z7.5..8** (approximately X48.11..150.94, Y89.30..98.06). Source engraving geometry was not changed; re-tessellation changes the pair count, so **not “unchanged 12 warnings”**. The historical fragmented-logo lid had 28 final / 30 canonical flags localized to old logo crossed-wall slivers, not merely float32/coplanar T-junctions. Exact-transform diagnostic did not resolve them. **One authorized whole measured-logo-region fill resolved the lid to 0 flags** (`reports/lid-region-probe.json`). No further alternatives or source-base engraving repairs were attempted.

## Artifacts / cleanup / preview

- `cad/original-magnet-case.FCStd`; two final edited-CAD STLs in `stl/`; one `previews/filled-surfaces.png`.
- Preview is a measured before/after orthographic projection of **saved native source/final BRep tessellations**, not a conceptual drawing or a GUI screenshot. Uploaded image: `/uploads/32c10017-a1df-48e2-bd0a-c5b7f5491e65.webp`. Green outlines are annotations, not raised pads.
- Removed **156 tracked rejected-design files** under flush-latch, slide-clips, lock-studies (including c-tight), quarter-turn-case; no screw-lock files were present. Exact deletion/source-hash audit remains in `reports/cleanup.json`. No Git history/worktree/branch removal or outside-project edits.
- Pristine release STLs/F3Z, metadata, inventory, MIT license and original checksums remain byte-identical. Only the explanatory original README navigation changes.
- All deliverable hashes: `SHA256SUMS`. Changes staged/uncommitted for review; **no physical, sliced, fit, adhesive, retention, durability or print-safety qualification**.
