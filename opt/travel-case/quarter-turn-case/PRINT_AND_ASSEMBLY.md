# B quarter-turn — small actual-case coupon test

**Print the seven small parts below only. No full-case print requested or approved.**
CAD/electronics and written-mesh checks are geometric evidence, not slicing,
printed strength, installed-electronics verification or safe-travel approval.

[One actual-geometry guide](previews/actual-case-guide.png) · [Live complete CAD](cad/quarter-turn-case.FCStd)

## BOM — 7 STLs, one COMMON one-piece key

| Fit c PER SIDE | Total opposed land gap 2c | Base coupon | Lid coupon |
|---|---:|---|---|
| .20 mm | .40 mm | [B_base_c020.stl](stl/B_base_c020.stl) | [B_lid_c020.stl](stl/B_lid_c020.stl) |
| .10 mm | .20 mm | [B_base_c010.stl](stl/B_base_c010.stl) | [B_lid_c010.stl](stl/B_lid_c010.stl) |
| .00 mm | .00 mm | [B_base_c000.stl](stl/B_base_c000.stl) | [B_lid_c000.stl](stl/B_lid_c000.stl) |

Print **one [B_key_common.stl](stl/B_key_common.stl)**, reused across all three
matched pairs. Do not mix base/lid fits. Read B/L and .20/.10/.00 engravings on
non-bearing inside floor/roof; B on the key grip. No pins, screws, magnets, spring,
separate gate, glue or hidden assembly. Parts are not scaled.

The 32 × 24 mm XY crops retain actual floor, roof, curved seam, alignment skirt,
root, receiver and recessed lid channel. Base coupon height **49.2 mm** includes
its internal keeper; lid crop spans original Z14..77.5 (**63.5 mm** tall).
The tall lid coupon is intentional: chopping off its roof would falsify the
requested roof-down print and support situation.

## Orientations / access — already encoded in STL

- **Base: original underside DOWN.** Never lay the receiver on its side. The
  3.2 mm root attaches to the original rim, rises above the unchanged PCB screen,
  and grows inward .9 mm per mm of print height (less than a 45° overhang).
- **Lid: original exterior roof DOWN.** Never print seam-down. The original
  flared lower exterior contains steep overhangs: accessible **outside-only**
  support may be necessary. Use the slicer's actual preview to decide; support
  must not touch keyhole lands, neck bore, parking, inner channel, mating skirt
  or rim. If these cannot be printed cleanly without functional-face support,
  stop and record it rather than changing orientation to hide the problem.
- **Key: broad X/Y face DOWN**, 4 mm extrusion builds upward; B engraving UP.
- P2S / standard **0.4 mm nozzle**, **0.20 mm layer assumed**, filament unknown.
  No slicing/toolpaths or printing were done. Check stability and bed adhesion;
  a removable brim on non-fit bed edges is acceptable. **No scaling or fit
  compensation changes** between pairs; record any slicer XY/hole compensation.
- Double-ended 45° aperture reliefs suit both opposite print directions; the
  closing bridge cap is 1.2 mm. Parking has 45° roof relief. The lid's inner
  channel and base parking pocket are exposed with halves apart. There is no
  trapped backing chamber. Remove outside supports and debris **before** fitting
  or installing electronics; do not sand/drill bearing lands to force a pass.

## Assemble / operate — support the halves, do not carry by the lock

1. Start with **.20**, then .10, then .00. Seat the original curved seam/skirt
   with no key; verify no rocking, positive gap, forced bending or skirt drag.
2. Put the key's **18 mm head vertical**. Insert straight through BOTH closed
   apertures. Push to the external collar stop, then quarter-turn to horizontal.
3. Pull outward **1.2 mm** to park the head in the base pocket. The pocket walls
   resist turning only when fully parked. Check both halves are retained with a
   gentle supported vertical and diagonal tug; stop on cracks or obvious flex.
4. Unlock: push inward 1.2 mm → reverse quarter-turn → withdraw the entire
   one-piece key. Hold the lid and key so gravity does not make them drop.
5. Lift the lid **straight upward at least 35.6 mm before sliding sideways**.
   The internal keepers reach Z49.2; the skirt starts at Z14. Closed-height
   diagonal lifting collides with the real channels. Do not force or lever it.
   Keep lifting straight until fully free before substantial tilting; lower it
   straight to reseat. Full-case CAD checks cover both handed diagonal lock sites.

**No spring holds axial parking.** An inward bump can unpark the head and permit
rotation; gravity/vibration may release or lose the key. Friction is not proven
as a parking hold. This is not a safety-rated travel/carrying closure.

## What changes with fit, and what does NOT

c changes head-entry and parking **flat end/bottom lands** only:
entry W×H = 4.40×18.40 / 4.20×18.20 / 4.00×18.00 mm;
parking L×W = 18.40×4.40 / 18.20×4.20 / 18.00×4.00 mm.

Roof relief apexes are print relief, not opposed flat fit lands. Fixed at all
fits: 7.81110255 mm neck-turn bore, .60 mm total rotational space, .80 mm pocket
depth, 1.20 mm push, .40 mm turn air, .40 mm inter-half channel gap. At c=.00
ideal CAD contact is allowed; positive material interference is not.

The head is 18×4 mm with **2 mm axial thickness**, neck 6×4 mm and 7.2 mm axial
length. Keeper thickness 3.2, rear pocket web 2.4, root thickness 3.2, minimum
parking-end ligament 2.8 mm; top entry-tip ligament 3.4/3.6/3.8 mm. These are
nominal geometric dimensions, **not a printed-strength test**.

## Record the actual test

For each pair record filament/brand, drying, printer/profile, layer/nozzle,
orientation, supports, compensation, cleanup and photographs; then record:

- Seam/skirt seating without key; entry drag and whether the head fully passes
  both **closed** apertures without flexing or scraping.
- Push travel, quarter-turn resistance, seating into parking, free play and
  gentle supported vertical/diagonal retention; collar/head/neck deformation.
- Push/unpark, reverse turn, withdrawal; straight lift and reseat, repeated cycles.
- Whether gravity changes parking when turned on its side; accidental axial push
  response. Do not shake or carry installed electronics to make a travel claim.

The user's **C .10 slides well; C .00 works with wall drag**. Those open-slide
results do not prove B's closed keyholes, turn space or parking mechanism.

## Before any later full-case print

Original body remains **243.12 × 179.62 × 77.50 mm**, including original exterior
curvature; removable grips add 12 mm beyond the local straight wall, 2 mm beyond
each global long-side edge. With both keys: nominal depth 183.62 mm.

Original board screen X9.8..233.32/Y9.8..169.82/Z13..14.6 is unchanged; thickness
1.60 comes from KiCad, installed Z is not physically measured. The extra top
reserve reaches Z15. Unknown module heights are reserved to the original roof.
Closest pushed-head/module-screen gap is only **.139 mm AFTER a .25 mm XY reserve**;
actual installed modules, knobs, wiring and PCB seating must therefore be checked.
A raised board stack or any occupied lock corridor is a STOP condition, not
permission to move the passing screen. No full-case STL/STEP is supplied.
