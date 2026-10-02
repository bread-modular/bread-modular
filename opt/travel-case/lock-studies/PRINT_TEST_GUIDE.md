# Print small, measure first — UNSLICED / UNPRINTED

**Confirmed:** standard Bambu P2S, 0.4 mm nozzle. **Unknown:** filament,
profile, plate, temperatures, wall count, compensation and support use.
No remote printer operation, G-code or print-time estimate was performed.
[Actual-CAD one-page label/operation/orientation map](comparison.svg).

## Exact staged BOM — one of each, 8 pieces total

| Stage | Engraved ID | Exact bed-oriented STL | XYZ mm |
| --- | --- | --- | --- |
| 1 — gauge | C-F; G0.40/G0.60/G0.80 | `C_female_G0.40_G0.60_G0.80.stl` | 35.4 × 29 × 5 |
| 1 — gauge | C-M; 8.00 | `C_male_8.00.stl` | 12 × 31 × 5 |
| 2 — snap | A-B; G0.80 | `A_base_G0.80.stl` | 17.6 × 17 × 8.8 |
| 2 — snap | A-L; G0.80 | `A_lid_G0.80.stl` | 17.6 × 39 × 8.8 |
| 2 — snap | A-C | `A_clasp_E0.60_G0.80.stl` | 13.8 × 38.8 × 8 |
| 3 — key | B-B; G0.80 | `B_base_G0.80.stl` | 30 × 44 × 3.2 |
| 3 — key | B-L; G0.80 | `B_lid_G0.80.stl` | 30 × 44 × 3.2 |
| 3 — key | B-K | `B_key_G0.80.stl` | 22 × 21 × 4 |

Files are in `stl/`. No alternate clasp, hardware, glue, shaft assembly or full
shell. Do not mix A/B moving parts. Labels are recessed on non-bearing pads.

## Settings and support — assumptions are NOT a slicer result

Start at **100% scale, 0.20 mm layers**, using the correct material's existing
P2S profile. PETG is suggested for the flexing clasp, not presumed to be your
filament. Four walls and solid small load parts are an exploratory start;
thin 1.2/1.6 beam sections cannot contain four independent walls across their
thickness, so inspect actual continuous paths. No rated material or profile.
Record all defaults; do not blindly add XY hole/contour compensation. Avoid
raft; any optional external brim must stay off entry/bearing edges. Do not
accept functional sanding, drilling, hammering or tool-assisted operation as
“fit”. Removing a loose string/brim is different from changing mating lands.

| Parts | Keep supplied orientation | Planned support / interface notes |
| --- | --- | --- |
| C-F + C-M | Flat comb/rail XY, labelled faces up, Z5 | Open channels have no roofs. Relief on bottom entry edges; rail tip lead-in. Keep seams off rail/channel side lands. |
| A-B + A-L | Keeper/bending profiles XY, width builds Z8.8 | Flat extruded sections, no supported keeper roofs. Keep square shoulder and lower keeper lands clean. Centre A-C across width (~0.40 edge inset each side). |
| A-C | Beam bending profile XY, width builds Z8 | Continuous layers along beam/root; broad rigid self-stop beside it. Only rigid toe's external bed entry edges are chamfered: root/beam are not thinned by a blanket chamfer. Keep seams off flexure, hook/toe lands; place on pad/outer rigid spine. |
| B-B + B-L | Tabs flat XY, aperture axes Z; rear pocket UP | Closed holes go through. Rear parking recess is open upwards, not a supported roof. Bed-entry relief outside full-size lands. Keep seams out of hole and pocket. |
| B-K | H-like head/neck/collar side profile XY, thickness builds Z4 | One-piece neck length lies in print plane, NOT an upright narrow shaft with a floating head. Bed relief preserves lands above 0.40. Keep seams away from head/neck/retaining collar. |

**Geometric screen only:** no installed Bambu/Orca/Prusa slicer CLI was found.
At assumed 0.20 layers, native horizontal sections were compared with the
previous section expanded 0.20 (~45° growth). No new unsupported-growth region
>0.10 mm² was flagged; smaller corner/discretization residuals are recorded.
This checks geometry, NOT extrusion, bridge strategy, cooling, adhesion, material,
seam placement or support toolpaths. All bearing surfaces intentionally avoid
support contact, but **do not infer support-free printability from watertightness**.

Before each stage in **your Bambu Studio**:
1. Import only that stage; retain supplied orientation and 100% scale, check bed Z0.
2. Slice with actual filament/profile; scrub every layer, especially first 0.40,
   thin beam/root, key neck, enclosed bores and parking-pocket floor. Look for
   missing lines, floating islands, bridges/overhangs and seam bumps.
3. Inspect support preview separately. Intended support contact on mating faces
   is NONE. If generated there, stop and record a screenshot rather than printing
   scars into the fit. If external supports are required, record both XY and Z
   gaps; roughly 0.20 top-Z same-material advice is not a universal support recipe.
   See the exact sourced distinctions in [RESEARCH.md](RESEARCH.md).

## Stage 1 — gauge before mechanisms

Insert rail tip into each open channel up to ~20 mm; handle remains outside.
G = female − male: 8.40−8.00=0.40, 8.60−8.00=0.60, 8.80−8.00=0.80.
Centred per-side gaps are 0.20 / 0.30 / 0.40. No intentional interference.
Measure rail width and channel width on lands above the first 0.40, away from
lead-in, seams and labels; also note first-layer flare separately. Record which
slides by hand without scraping, whether it rocks and any entry-only bind.
This isolates XY fit, not strength, closed-hole calibration or all XYZ accuracy.
XY hole compensation does not fix these OPEN grooves. Change one setting or
`HardwareTotalGap` at a time, rebuild the complete matching set, and re-test.
Default mechanism hardware is G0.80 because the earlier clip barely fitted;
this is an exploratory fit allowance, not a universal printer tolerance.

## Additional C-only tight test — do not reprint the kit

Original C reportedly slides comfortably. Print only the new
[C-tight female](c-tight/README.md), **34.2 × 29 × 5 mm**, reusing your existing
8.00 mm male. Left → right: **0.20 / 0.10 / 0.00 per side** → engraved
**G0.40 / G0.20 / G0.00 total gaps** → **8.40 / 8.20 / 8.00 mm** channel widths.
Print flat, labels up, 100% scale, assumed 0.20 mm layers; keep the same material
and profile (filament unknown). Supports not planned; preview locally, without
hole-compensation assumptions. Stop if 0.10 per side or zero binds; **never force
or sand contact lands**. Record as-printed fit. CAD zero contact is expected,
not a promise of sliding. Original A/B/C artifacts remain unchanged.

## Stage 2 — press-release bridge clasp A

Assembly axes in diagram: **+X press/withdraw, +Y lid separation, Z width**.
Grip labelled base/lid pads; bring their seam ends together and centre widths.
- **Lock:** introduce clasp with upper pad held pressed and upper end peeled
  ~5° outwards. Engage rigid toe under base keeper. Pivot upper end upright while
  holding pad, placing hook behind lid's square shoulder, then relax. This is
  the reverse of the verified unlock path. Hook overlap **E0.60** is independent
  of fit **G0.80**; locked beam is geometrically relaxed, not wedge-preloaded.
- **Unlock:** press A-C pad gently inward about 0.90; its flexure peels hook clear.
  Peel the whole upper end ~5° about lower toe, lower clasp ~3 to free rigid toe,
  withdraw normally from keepers. Self-stop limits ideal tip travel ~1.20 and
  moves WITH clasp, so it does not block removal. Do not pry past the stop.
- **Check:** supported gentle +Y separation should take up ~0.40 slack before
  square hook/toe bearing holds the halves. Remove clasp before separating them.
  The printed flexure, force and fingers are not simulated. Approximate motion
  leaves Y unchanged and shears head by tip slope; it is NOT FEA.

A tests the intended separation direction when centred. **It is not a fully
laterally captive case latch:** open coupon sides/misalignment can allow escape.
Record side-slip/rocking, do not disguise them as retention strength. A future
real case would need its actual seam alignment/lateral constraints tested.

## Stage 3 — quarter-turn bridge key B

Overlap tabs with labelled grasps on opposite sides of seam; B-L is FRONT,
B-B with parking pocket is REAR. Align both closed holes. **+Z is inward**.
- **Lock:** align T-head along X, parallel to seam. Insert normally through BOTH
  holes until collar reaches front/push limit. Rotate 90° to Y in open rear air;
  pull outward ~1.20 to seat head in the rear pocket. Never turn while parked.
- **Unlock:** push inward ~1.20 (0.80 pocket depth + 0.40 rear gap), counter-turn
  90°, withdraw through both closed holes. No pin, gate or separate shaft pieces.
- **Check:** neck spans both holes and limits in-plane separation; front collar
  retains lid axially and rear head retains base. Some play is intentional:
  bore is neck diagonal + G, not a snug square socket. Pocket walls block a
  seated turn; **no spring holds it parked**, so gravity/vibration/accidental
  push+turn resistance is unproven. Check push, turn, parking and removal by hand
  in several orientations; never call positive head capture a safety rating.

## Record results / safe screening

For each stage record filament/brand/dryness, process/profile, plate, layer height,
nozzle/bed temperatures, walls/infill, compensation, seam position, support use
and XY/top-Z gaps if any; then measured dimensions, fit, forces if measurable,
side-slip, wear and photos. Blank/unknown means **unknown**, not a tested default.

Begin gentle supported hand operation, no tools or functional sanding. Stop on
binding, white stress marks, cracks, permanent bend or unreliable parking.
Optional later exploratory targets from the brief: actuation ≤15 N, separation
30 N for 10 s, withdrawal 10 N for 10 s, 50 cycles and 24 h locked dwell. These
are **screening proposals, NOT certified ratings or required destructive tests**.
Attempt loads only after gentle success, with supported grips, safe containment
of fragments and controlled measurement; do not load uncontained parts near
hands/face. If suitable measurement/containment is unavailable, skip load targets.
No electronics, loaded case, drops or travel. Kit results do not establish global
case stiffness or fit at the original curved lid shoulder; real-section testing
must precede any body change.
