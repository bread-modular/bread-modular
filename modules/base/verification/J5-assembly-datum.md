# J5 nominal body datum — BASE 1.3.13 (portal signoff still pending)

## Evidence, not an average of pads

Native source identifies **HRO TYPE-C-31-M-12, LCSC C165948**. The manufacturer's
one-page drawing supplied by LCSC is archived as `J5-C165948-datasheet.pdf` with
its SHA-256 in `J5-assembly-datum.json`. The part identity is independently
confirmed by the distributor. [source](https://www.lcsc.com/product-detail/C165948.html)
The HRO drawing shows nominal **8.94 mm width and 7.35 mm shell length**, with the
mouth at the front of that rectangular shell, the front shell legs 2.60 mm
behind it and the rear shell legs 6.77 mm behind it. The 0.40 mm contact-tail
protrusion is NOT part of the body datum. This is a nominal bounding-shell centre,
not a measured centre of mass, pad-centre average, nozzle/pickup point or portal
library origin. [source](https://www.lcsc.com/datasheet/C165948.pdf)

The project's `BreadModular_TypeC:HRO-TYPE-C-31-M-12` installed instance has a
mouth-centred anchor at **board (30.840,46.990) mm**, rotation 270°. Its local axes
are +X across the connector and -Y into the board; local -Y maps to board +X at
this rotation. Front shell-slot centres are 2.60 mm behind the anchor; rear
centres are 6.78 mm behind it (0.01 mm different from this drawing, inside its
±0.05 mm PCB-layout tolerance). Width is symmetric about the anchor. NPTH pin
spacing 5.78 mm and shell-leg spacing 8.64 mm agree with the drawing. None of
these pads, drills, the board outline or the anchor are moved.

The embedded footprint originally had **no body rectangle on F.Fab**. Historical
repository Type-C library body graphics on Dwgs.User use 8.94 × **7.30** mm; this
is 0.05 mm shorter than the retrieved HRO drawing and is not the dimensional
source for the correction. Silk extents are clearance art, not body dimensions.
A non-fabrication **F.Fab-only 8.94 × 7.35 mm rectangle** now documents the HRO
nominal shell: board X **30.840..38.190**, Y **42.520..51.460** mm. Physical
pad/hole geometry and mating/stack hardware are unchanged; no library footprint
or other module was edited.

## Exact nominal correction and axis convention

- Local body centre: **(0,-3.675) mm** from the mouth (`7.35 / 2`).
- Board body centre: **(34.515,46.990) mm** (KiCad board Y grows down).
- Drill/place origin: **(30.480,177.800) mm**.
- Expected exported Cartesian centre: **(4.035,130.810) mm**, rotation **270°**, top.
- Previous off-centred CPL: `(0.360,130.810)`; that was the mouth, not body centre.

Assembly-only native fields in BOTH schematic and PCB are:

```
JLCPCB Position Offset X = 3.675
JLCPCB Position Offset Y = 0
```

The exporter adds these signed **millimetre deltas in the exported board frame**:
X right, Y up; both sides use the common top-view frame. They are **not** rotated
with the footprint or rotation correction and **not** mirrored on the bottom.
Missing/blank values mean zero; numeric 0 is valid. Normalized field aliases and
schematic/PCB values merge numerically; conflicting, malformed, NaN/infinite or
overflowing values stop export. If a part is rotated/flipped its board-frame
assembly offset requires deliberate re-evaluation. J5's rotation is unchanged;
there is **no guessed part-specific library rotation/XY correction**.

The release validator independently derives the expected J5 centre from the
pinned manufacturer's shell dimensions, fixed mouth datum and F.Fab rectangle,
then checks the emitted CPL against that expected centre. It does not accept the
raw anchor or an arbitrary native field value as proof of centring.
JLCPCB defines Mid X/Y as the component centroid. [source](https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly)

## Review / release hold

Astra's prior **1.3.12** review passed copper/connectivity/fabrication and held
assembly for J5's mouth-based placement (historical HOLD). **Targeted Astra Max
1.3.13 software/layout/export confirmation is complete: PASS**, including the
nominal shell datum and corrected CPL, in chat
`fa1ba1b6-d28a-4178-bb09-cf6a42d01a68`. `astra-confirmation.json` records
the user-supplied completed review and exact reviewed source/export identities.
No advisor or other model was invoked during this integration.
The **JLCPCB library/portal placement preview has genuinely NOT been performed**.
That remains a separate hold: validate shell/contact registration, orientation,
pin mapping and any portal-specific correction before authorizing assembly.
No order, live price/stock qualification, physical measurement or bench proof is
implied by this nominal correction.
