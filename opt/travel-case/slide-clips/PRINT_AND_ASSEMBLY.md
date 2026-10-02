# Print-first / close / push / pull

## Smallest useful first print

1 × `coupon_bottom.stl` + 1 × `coupon_lid.stl` + 1 × `clip_nominal.stl`.
These are exact final shell crops, not a generic calibration cube. No jig or
other part is needed. Their matching rim/skirt should seat normally by hand;
use aligned cropped side edges to identify the same X position.

Start **PETG / 0.4 nozzle / 0.2 layer / 100% scale**, using your PETG profile.
Use sufficient walls and solid/near-solid clips as a starting choice; this is not
a certified mechanical slicer recipe. STLs have bed Z0 and the intended orientation:

| Part | On the bed | Size XYZ (mm) |
| --- | --- | --- |
| Full base | Original underside | 243.12 × 179.62 × 15 |
| Full lid | Original roof exterior | 243.12 × 179.62 × 63.5 |
| Coupon base | Original underside | 24 × 20 × 15 |
| Coupon lid | Z40 cropped straight-wall edge, inverted | 24 × 14 × 26 |
| Nominal clip | Complete C cross-section in XY | 14.10 × 21.791895 × 12 |
| Looser clip | Same orientation | 14.10 × 22.031895 × 12 |
| Tighter clip | Same orientation | 14.10 × 21.551895 × 12 |

Clip layers are the whole constant C profile; no clip support expected. Case and
coupon shallow grooves may involve bridges/overhangs: **inspect layer preview and
supports**. Check first-layer/elephant-foot interference especially at groove mouths,
upper bearing and clip contact faces. Do not flood contact grooves with difficult
support or make tiny supported snap features; there are none in this design.
Any cleanup should remove printing artifacts, not sand away functional preload
or reshape the skirt. Reprint the calibration clip instead of forcing a bad fit.

## Three-step operation

1. **CLOSE**: seat original skirt/rim. Hold both halves together; no hidden
   mechanism to align, no gate to install.
2. **PUSH**: align upper jaw on the lid shoulder and lower jaw below the base,
   perpendicular to long face. Push ~9 mm from a wholly clear approach to
   hand-snug. The nominal final ~1 mm elastically spreads the jaws. No positive
   click, barb or detent. If binding, stop—never hammer or pry.
3. **PULL**: grip the integral pad, withdraw straight backwards. Remove every
   clip before lifting the lid. A spring/friction wedge should loosen on withdrawal.

## Fit choices on the SAME coupon/shell grooves

Print nominal first. Too tight -> `clip_looser_throat_plus0.24.stl`; too loose ->
`clip_tighter_throat_minus0.24.stl`. Nominal .16 total interference; looser .08
geometric gap; tighter .40 total interference. These are useful .24 mm throat
steps, not arbitrary global scaling. Width 12, jaws 2.4, web 3.2, R1.4 roots and
lead-ins stay unchanged. Looser may fit but offer insufficient friction. Tighter
starts contacting sooner (~2.7 mm from seat) and can be too hard to install;
more preload is **not** automatically more useful or safer retention.

Measure and record printing material/profile, seating and removal behavior,
obvious wall/clip flex, whitening/cracking, short repeat cycles, and retention
while the base remains supported. Check after dwell for relaxation/creep before
moving to full shells. The local coupon does not certify global twist/peel stiffness.

## Full case / manual stability and transport tests

Print one full base + one full lid + two identical chosen-fit clips. Use A + D:
A front X32; D rear X211.12. Front Y0, rear Y179.62. Rotate rear clip 180° about Z.
Optional B front X211.12 and C rear X32 use the same part. No short-edge clips;
original connector openings remain uncut. Verify your actual cables/plugs and
finger access, which were not supplied for certification.

**Two clips project 2.158 mm below the base.** On a flat surface, check all contact
points and gentle rocking with the real installed contents; do not assume two
contacts provide a stable tabletop platform. Four clips also require a check.
Only with independent support/containment, gradually inspect separation, peeling,
twisting, friction loss and creep under the intended load. Never lift loaded case
by the lid or clips as an initial test. Carrying strength, drop resistance and
safe load remain unknown, regardless of computational geometry check count.

Not a safety-rated lock; do not entrust valuables or safety-critical transport
to this closure without physical validation. Continue using independent containment
and supporting the base while evaluating it.
