# Research decision — two small standalone mechanisms

Printer confirmed by user: **standard Bambu P2S, 0.4 mm nozzle**. Material,
filament/profile, plate, temperatures and support use remain unknown. The supplied
nozzle is 0.4 mm and build volume is 256 × 256 × 256 mm; neither establishes a fit
tolerance. [source](https://bambulab.com/en-us/p2s/specs)

## Compare the hypotheses, not certified products

| Study | Positive coupling / operation | Main uncertainty to print-test |
| --- | --- | --- |
| A — press-release bridge clasp | Rigid toe catches base keeper; relaxed cantilever hook above lid's square shoulder. Press pad, peel upper hook clear, unhook toe, remove. Broad self-contained travel stop stays with clasp. | Printed beam stiffness/strain, hook wear, finger access, cycling and creep; not a friction wedge. |
| B — quarter-turn bridge key | Each half has its OWN fully enclosed aligned keyhole. Insert head parallel to seam through both, rotate 90°, pull outward into rear pocket. Front collar catches lid, rear head catches base, neck couples closed holes. | Pocket parking under gravity/vibration; no spring or proven accidental push+turn resistance. |

Both use one removable printed moving part and two gently graspable receiver
halves. They are analytical local fixtures, **not faithful crops of the released
case**. No tiny gate fingers, metal pins, screws, magnets or glued assemblies.
A self-stop was chosen over a receiver-mounted stop because a fixed stop can
trap the intended peel/removal path. Motion checks exercise the actual toe and
upper-hook sequence, not an invented globally flexible rigid clip.

A baseline: L24 / W8, thickness 1.6→1.2, exact R1.4 root, E0.60 hook overlap,
~0.90 release displacement and ~1.20 positive self-stop. E is engagement, not
fit clearance. The deflected CAD is an explicit kinematic approximation, **not
FEA or a strain/force solution**; the locked beam has no imposed preload.

B baseline: 18 × 4 × 3 head, 4 × 4 neck, 22 × 4 broad front collar. Bore diameter
6.456854 = neck diagonal + G0.80; full head sweep diameter 19.239089 = head
diagonal + G0.80. Rear pocket 18.80 × 4.80 × 0.80, aligned 90° to entry slot;
1.20 axial push raises the head 0.40 above the rear face before rotation.
The head sweeps **open air**, not an undersized hidden chamber. Pocket walls block
seated rotation, but the key can unpark if pushed: accidental unlocking is unproven.

## What the live sources support — and what they do not

- **No universal FDM tolerance.** Orientation, interlocking geometry, calibration,
  settings and material all affect fit; supported surfaces differ from bed/side
  surfaces. Therefore gauge first, no intentional interference or global scaling,
  then test actual mechanisms. Prusa-specific accuracy/overhang examples are not
  P2S prescriptions. [source](https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135)
- **FDM snap fits are orientation-sensitive.** Formlabs distinguishes FDM/FFF
  anisotropy from SLA and SLS, recommends orienting FDM strength in XY, tapering
  the beam and iterating; it gives no universally correct snap dimensions. This
  kit prints A's bending profile in XY, width in Z. Its resin/nylon process claims,
  strain graphs and generic numeric clearances are NOT P2S PETG ratings.
  Injection-moulded snap formulas assume a different manufacturing/material
  model; no moulded or SLA design rule is claimed as FDM qualification here.
  [source](https://formlabs.com/blog/designing-3d-printed-snap-fit-enclosures/)
- **First-layer flare is a separate error.** Elephant-foot compensation shrinks
  the first-layer contour; measure the actual flare, and re-evaluate on plate
  changes. Nominal 0.40 bed-entry relief does not guarantee absence of flare.
  [source](https://wiki.bambulab.com/en/software/bambu-studio/parameter/elephant-foot)
- **XY hole compensation affects closed layer paths, not open grooves.** It is
  not universal assembly clearance and will not fix the open comb channels.
  Contour compensation also changes external sizes. Start without blindly added
  XY compensation; record any profile default and change one thing at a time.
  [source](https://wiki.bambulab.com/en/software/bambu-studio/xy-hole-contour-compensation)
- **Support XY gap and top-Z distance are different settings.** Bambu's roughly
  0.20 top-Z advice for same-material support is a starting point, not a universal
  spacing prescription; zero top-Z is discussed for appropriate support material.
  This kit avoids planned support contact on bearing faces. Support-free intent
  and solid/manifold tests do not replace slicer preview or material testing.
  [source](https://wiki.bambulab.com/en/software/bambu-studio/support)
- **Seams can protrude on interfaces.** Paint/locate seams away from rails,
  channels, bore, head, hook, toe and retaining shoulder; record the actual
  result. [source](https://wiki.bambulab.com/en/software/bambu-studio/Seam)

PETG is our suggested first material for the flexing clasp, **not an assertion
of the user's filament**. 0.20 layers, 100% scale and four walls/solid small load
parts are exploratory starting assumptions, not source-derived P2S certification.
The gauge isolates XY fit, not mechanism strength, closed-hole calibration,
all XYZ accuracy or whole-case stiffness. See the print guide for actual settings
and observations to record. The optional force/cycle targets in the brief are
screening proposals only, not publisher specifications or safe working loads.
