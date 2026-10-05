# Original magnet case — requested flush surfaces

**One final design, original magnets only.** Lid backside logo removed flush; the two recessed EXTERIOR underside bays filled flat. Original body profile, dimensions, six + six magnet pockets/chamfers, seam, openings and PCB mounting retained. Pristine upstream release bytes are separate and untouched.

## Open / review

- [Native FreeCAD document](cad/original-magnet-case.FCStd) — separate Base/Lid single solids, pristine source references, labelled surface-fill evidence, native pocket-depth features and assembly/print links.
- [Portable opener](Open.FCMacro) — no project imports or custom Python proxies. Set `VIEW` to `assembly`, `print` or `exploded`.
- [Two-surface before/after preview](previews/filled-surfaces.png).
- [Measured validation / limitations](VALIDATION.md), [provenance](provenance.json), [deliverable hashes](SHA256SUMS).

## Exactly what changed

| Surface | Measured source recess | Final surface | Added material |
|---|---|---|---|
| Base EXTERIOR underside | Two capsule bays at Z1, surrounded by Z0 | Entire underside flat at Z0 | 15555.070342 mm³ |
| Lid backside / INNER roof logo | Z75..75.5, 0.5 mm deep | Flush to adjacent inner roof Z75 | 197.005414 mm³ |

**No removed material or additions outside authorized regions.** Nominal assembled size remains **243.12 × 179.62 × 77.5 mm**. Base inner engraving Z7.5..8, mounting geometry and lid exterior roof Z77.5 are not flattened/shaved.

The single lid fill uses the **explicitly authorized measured logo bounding region**: X61.975433..177.036880, Y81.886337..97.430740, Z75..75.5 only. Most of that shallow tool overlaps already-solid roof; only the recess gains material. This eliminates the source crossed-wall fragments that defeated a fragmented 34-floor fill. No second finished variant is retained.

## Native history and honest mesh status

**Faceted source BReps, not recovered Fusion history or a smooth fully-parametric shell.** Validated direct-OCC surface unions are labelled frozen `Part::Feature` shells and rebuild through `build.py`. Their measured profiles/native extrusions are construction evidence, **not live fill-depth shell drivers**. Downstream native Sketcher/extrusion/fuse/cut magnet-pocket features remain live: edit `Parameters.BasePocketDepth` / `LidPocketDepth` (shipped original defaults alone are validated). Fresh saved-file reopen, forced recompute, depth edits and restoration pass without Python proxies.

Both written STLs come from **edited CAD** and are closed/manifold, with zero boundary edges, winding conflicts or zero-area facets. **Lid self intersections: 0 (pass). Base self intersections: 13 vs 12 source (FAIL), localized to its preserved INTERNAL engraving Z7.5..8.** Geometry there is untouched; triangle pair counts are not claimed unchanged. This is **not an all-mesh-pass / printability qualification**. The historical 28-pair fragmented-logo lid was resolved by the one measured-region fallback; see `reports/lid-region-probe.json` and the explicitly historical export diagnostic.

## Print placement / rebuild

- [`stl/case_bottom_underside_down.stl`](stl/case_bottom_underside_down.stl): base exterior underside-down.
- [`stl/case_lid_roof_down.stl`](stl/case_lid_roof_down.stl): lid EXTERIOR roof-down. Both lowest print Z0.
- Intended ordinary **0.4 mm-nozzle** workflow; 0.2 mm layers are a starting point only, not a tested slicer profile. Inspect the base warning before manufacturing. No physical print, fit, slicing, adhesive, magnet retention, durability or safety guarantee.

Use an **existing** extracted FreeCAD runtime read-only; nothing is installed and no deleted closure-design modules are imported:

```sh
FREECAD_APPDIR=/path/to/existing/squashfs-root ./opt/travel-case/magnet-case/run.sh build
FREECAD_APPDIR=/path/to/existing/squashfs-root ./opt/travel-case/magnet-case/run.sh validate
FREECAD_APPDIR=/path/to/existing/squashfs-root ./opt/travel-case/magnet-case/run.sh open
```

`FREECAD_APPDIR` must contain `AppRun` and `usr/bin/python`. Its bundled NumPy/SciPy run build/validation; system Python with Pillow is used only for the one 2D annotated preview. `build` regenerates from pristine releases, reopens/tests, validates, produces the preview and updates hashes. It reports **exit 3 for the explicitly remaining base mesh blocker**, not a clean-mesh pass. `validate` does not rebuild geometry. Failed checks stay failed. No GUI/offscreen/install loops.

Rejected clips, latches, screw-locks/quarter-turn mechanisms and study outputs were removed from the working tree, not Git history. Exact deletion/source-hash audit: [`reports/cleanup.json`](reports/cleanup.json). Keep these changes staged and uncommitted for review.
