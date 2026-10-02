# B quarter-turn / actual complete case + small test coupons

**TEST COUPONS ONLY — UNSLICED / UNPRINTED.** Complete live editable CAD and seven
small STLs; no full-case STL/STEP, print request, installed-electronics clearance
certification or safe-travel claim. All delivery files stay inside this directory;
only a small parent README link changes. Historical sources/STLs are unchanged.

- [PRINT_AND_ASSEMBLY.md](PRINT_AND_ASSEMBLY.md): seven-part BOM, actual print
  orientations, support/access constraints, operation and record-test procedure.
- [Open.FCMacro](Open.FCMacro): open/recompute/color
  [cad/quarter-turn-case.FCStd](cad/quarter-turn-case.FCStd).
- [One actual-geometry guide + cross-sections](previews/actual-case-guide.png).
- [Strict reopened CAD and written-STL report](reports/validation.json),
  [feasibility](reports/feasibility.json), [electronics survey](reports/electronics.json)
  and [export diagnosis](reports/export-diagnosis.json).

## Resolved PCB obstruction — strict check retained

The old floor posts Y14.4..17.6/Z8..49.2 cross the real registered base PCB:
**122.88 mm3 at X40 and 122.88 mm3 at X203.12**. They remain mandatory negative
regression fixtures. No PCB cuts, board relocation, holes or connector changes.

The final load path instead attaches to **existing solid base rim**:
local Y6.4..9.6/Z12.8..15, thickness3.2, original-solid root overlap168.96 mm3/site.
It rises inward .9 mm per mm of height, Y13.6..16.8 at Z23, then forms the keeper
above the board to **Z49.2**. It does not descend through the board. Keeper stock
and full integrated base have zero intersection with the original registered
board slab, and stock also clears an extra conservative top reserve to Z15.

Following the wall-contained candidate, the keeper is **.4 mm recessed into the
original 4 mm lid wall**. A local inward-open channel adds .4 mm inter-half air,
leaving a continuous **3.2 mm outer lid wall** outside the explicit keyhole.
The curved lower inner rim is locally relieved for brace seating/lift. Its
remaining wall is checked; the original alignment skirt is unchanged. This is
an explicit local lock mask, not permission to erase the mating rim generally.

Head axial thickness is reduced from the rejected 3 mm to **2 mm** so the
pushed/turning back face stops at local Y19.2. Keeper remains **3.2 mm**, pocket
web2.4, root3.2, parking-end ligament2.8, head retaining ear5.094 mm; top entry-tip
ligament3.4/3.6/3.8 mm. Printed strength remains unproven.

## Both ORIGINAL exterior profiles, not just bounding boxes

Pristine upstream STL SHA-256s and the native archive/metadata are checked. Raw
STLs register as X=rawX−20.68, Y=−rawZ−7.98, Z=rawY+15. Frozen faceted BReps are
source references, **not recovered Fusion feature history**. Only the proven
magnet-pocket fills and defective inner-logo repair helpers are reused from
`../slide-clips/final_features.py`; no historical latch/groove shell is imported.

Whole-shell Boolean differences outside exact repair/root/channel/keyhole masks
are zero for every fit. New keepers are contained in the actual original curved
complete-shell envelope with only the actual inner cavity filled. The rear STL
inner datum is **165.62001037597656**, not rounded165.62: correcting that empty
cavity fill eliminates a .00067513 mm3 false envelope-screen sliver without
moving, enlarging or trimming any case/keeper. Initial diagnosis is retained in
`reports/feasibility-initial.json`.

Original assembled body **243.12×179.62×77.50 mm**; floor/roof, mounting holes,
connector cuts, original skirt and mating geometry outside those exact masks
remain unchanged. **Base external shell is still Z0..15, but the complete base
part with internal keepers reaches Z49.2** — never call its total height15.
Removable grip projects12 mm from the local Y10 straight wall, 2 mm past the
global long-side edge; both fitted keys increase nominal assembly depth183.62.
No exterior wing/lug is added to either shell.

## Actual electronics screening and limits

`modules/base/base.kicad_pcb`: continuous223.52×160.02 mm board; all FOUR mounting
holes register at (-20.68,-7.98) to the existing case holes. PCB thickness1.60 mm
comes from KiCad; **Z13..14.6 remains the explicit unchanged installed-stack
screen, not a physical measurement**. The extra Z15 top screen is additive.

Read-only pcbnew survey includes **163 actual base footprints/courtyards**, all
12 bus slots, 28 repo module PCB outlines/body/courtyard bounds and available
3D model references. Unknown base component heights reserve the entire cavity;
D3's actual available D_SMA STEP bounds give2.22 mm height, enlarged by1 mm.
Unknown installed module heights reserve the entire populated band
**Y19.339..157.395/Z14.6..75**, across the board width, with .25 mm XY allowance.
Supply-to-supply and ground-to-ground bus registration fixes module Y direction;
reversing Y would interchange power and ground, not be a legitimate placement.

Keeper and full insertion/rotation/parking/withdrawal sweeps clear those reserves
at both sites/all fits. **Closest pushed-head gap to that conservative band is
.139 mm**: no physical installed-stack or arbitrary knob/wiring protrusion is
proven. A taller PCB stack or occupied lock corridor stops any later full-case
manufacture. Missing 3D models are not treated as free space. The PCB snapshot
may precede schematic revisions (see `modules/base/POWER.md`).

## Live geometry / operation / real crops

`Parameters` → pristine references → permitted repairs → three full Base/Lid
features → exact front-site crops → only non-bearing identification engravings.
Fit edits recompute the entire shells and both coupon labels; a live .20→.10 edit
is validated. The other properly rotated handed site is cropped/checked too.
One COMMON genuinely one-piece key is used by both sites and all fits.

c=.20/.10/.00 mm **PER SIDE** changes only specified entry/parking flat lands:
2c=.40/.20/.00. .80 pocket,1.20 push,.40 turn air,.60 total neck rotation gap,
.40 inter-half air stay fixed. No scaled solids. .00 may contact ideal CAD;
positive volume interference is forbidden. Print relief apexes are not fit lands.

Continuous translation sweeps and full-circle rotational bounds are tested
against BOTH halves and electronics; head/base and collar/lid axial capture,
parked-turn blocking, locked vertical/diagonal lid retention, unpark/withdraw,
full lid seating/lift, actual channels and open cleanup are checked. Unlocked
inward diagonal lifting hits a channel; **lift straight35.6 mm before sliding**.
Substantial tilting is only for a fully removed lid. No spring holds parking;
inward bump + turn may release. CAD geometry is not a safe-travel rating.

Exact32×24 mm coupons retain full actual floor/roof and curved seam. Height49.2
base /63.5 lid. Exported bed frames preserve underside-down base and **roof-down
lid**. Key broad face down. Geometry screening identifies stock lid-flare
outside support risk; it is **not slicing**. No support allowed on functional
fit/mating surfaces or inside a trapped chamber; cleanup access is open with
halves apart before electronics installation. Filament unknown; P2S .4 nozzle,
.20 layer assumed. C .10/.00 sliding tests are not B closed-hole evidence.

## Strict portable reproduction — existing tools only

```sh
# Existing extracted FreeCAD; no installation or source-workspace dependency:
FREECAD_APPDIR=/path/to/squashfs-root opt/travel-case/quarter-turn-case/run.sh build
# Or FREECAD_PYTHON=/path/to/freecad-capable/python
# KICAD_PYTHON optionally chooses an EXISTING pcbnew-capable interpreter.
opt/travel-case/quarter-turn-case/run.sh validate
opt/travel-case/quarter-turn-case/run.sh hashes
```

Build prepares SHA-verified pristine caches (fresh STL conversion if missing),
surveys actual KiCad electronics, screens feasibility, builds/reopens live CAD,
strictly validates CAD, exports seven small test STLs, checks written topology/
volume/extents/bed frame, makes one guide and hashes the delivery. Failed gates
stop exports; build failures delete stale STLs. No commit/merge/push/base
checkout, advisor/model call, installation or historical source edit is used.

The first export correctly failed on four non-manifold valence4 edges in the B
**engraved label**, not keyhole/case geometry or STL quantization. The bitmap
label's diagonal vertex contacts were replaced by a continuous outline with two
separated counters. No mesh welding, facet dropping, tolerance relaxation or
success patch was used. Written meshes must independently pass the same strict
checks. `reports/export-diagnosis.json` retains the measured failing edges.
