# Print, coupon calibration and assembly

**Starting assumptions only — no slicer run or physical print has been performed.** The closure is not load/drop/fatigue certified and does not seal the seam. Use the coupon before spending filament on either full half.

## BOM and bed orientations

- 1 × `case_bottom.stl`: original outer underside on the bed, opening up. 243.12 × 179.62 × 15 mm nominal.
- 1 × `case_lid.stl`: original exterior roof down, opening/skirt up. 243.12 × 179.62 × 63.5 mm nominal; assembled height is 77.5 mm, not the sum of half heights, because the original skirt overlaps 1 mm.
- 2 × `slider_A.stl`, 2 × `slider_B.stl`: head's flat inward face toward bed; 28 × 11.6 × 10.7 mm bed bounds. No auto-orient/scale. Beam length X and longitudinal strain lie **in the layer plane**, not along the interlayer stacking direction.
- 2 × `gate_A.stl`, 2 × `gate_B.stl`: inward tongue faces toward bed; 38.6 × 8.2 × 3.3 mm bed bounds. Gate finger length (assembly Z) lies in the layer plane. Root-to-tip extrusion paths should be continuous; inspect the thin fingers in layer preview.
- Initial test: `coupon_bottom.stl` (53 × 14 × 7 mm), `coupon_lid.stl` (53 × 14 × 12 mm), one A slider and A gate. Coupon orientations match the final halves' local layer direction. They are actual cropped walls/keyways/guides, not a generic cube.

A is front-left/rear-right; B is front-right/rear-left. Front = assembly Y0. Rotate the rear parts in plane as indicated by the assembly; do not mirror the STL in the slicer accidentally.

The P2S specified build volume is 256 × 256 × 256 mm and its included nozzle is 0.4 mm, rechecked against the primary specification. [source](https://bambulab.com/en-us/p2s/specs) A 5 mm brim gives approximately 253.12 mm overall width; confirm usable plate/prime-line clearance in your slicer. Do not enlarge the case or scale its mating interfaces to get more room.

## PETG starting settings — tune on the coupon

| Setting | Starting proposal, not certification |
|---|---|
| Material | Dry, unfilled PETG; use the filament maker's profile/range |
| Nozzle / layer | Included 0.4 mm nozzle; 0.20 mm layers (0.16 mm coupon if needed) |
| Temperature | Maker's PETG preset; 245 °C nozzle / 80 °C bed only if within that filament's permitted range |
| Perimeters | 4–5 walls; 5–6 top/bottom layers; solid small slider/gate parts |
| Infill | 20–30% case body; local solid fill at keyways/rails; small latch pieces 100% |
| Thin features | Inspect variable-width paths: 1.2 mm skin, 1.3 mm skin, 1.2 mm leaf and 0.8 mm gate fingers must actually print continuously |
| Speed | Start critical outer walls/beam paths at 30–40 mm/s; avoid maximum machine-speed presets for the first coupon |
| Supports | As-needed painted supports for lid keyway/guide overhangs and slider underside; tune interface separation on the coupon, not by forcing components |
| Adhesion | Small-part brim if needed; retain the exported bed orientation |

The print orientation keeps longitudinal beam fibers within layers, but does not eliminate anisotropy. Gate/floor bridge undersides and thin slider beam/paddle areas may need supports. Avoid support welding to flexures or square detent faces. Remove support residue without thinning catch lands, barbs or the 1.2 mm bottom skin. Do not assume the coupon will work straight from an uncalibrated printer.

## Coupon acceptance procedure

1. Calibrate extrusion flow, pressure advance and first-layer/elephant-foot behavior for the selected PETG. Use the same settings/support strategy for coupon and full case.
2. Print the four coupon pieces at **100% scale**. Deburr stringing/support contact gently; no drilling, glue or magnets. Inspect the two gate fingers and leaf root for layer separation or missing extrusion paths.
3. Assemble the slider/gate using the seam-side sequence below. Each gate tongue must seat under its matching lid land; the square gate detents must release into their pockets. Reject a fit that needs forceful bending, trimming off a barb, or a gate that can backslide freely.
4. With OPEN retained, bring the actual lower/upper coupon surfaces together using their original skirt. The toe must enter vertically without scraping. Press the paddle inward, travel 8 mm to LOCKED and release; repeat to OPEN. Both endpoints must retain positively when unpressed.
5. In LOCKED, try a **gentle** separation by hand: limited seam play is normal, but the toe must catch. In OPEN the lid coupon must lift freely at least 4.6 mm. Check that the slider cannot fall out axially or vertically with its gate installed.
6. Cycle the coupon repeatedly by hand while watching for whitening/cracks and increasing looseness. This is a screening test, **not fatigue/load certification**. Do not increase test load near your electronics.

Nominal per-face running allowance is 0.3 mm. Correct extrusion, elephant foot and support residue first. A clearance edit affects toe overlap, skin and detent engagement; it must be made in the CAD recipe and pass the full checks again. Never globally scale one half or remove positive stop teeth to fix fit.

## Lid-off assembly — screws/magnets/glue not required

The long head cannot be inserted through the historic tiny end-cap alone. The final bayonet gate removes the floor and stops of the loading bay during assembly.

1. Leave the corresponding gate out. At that station, start the slider **11 mm outboard of OPEN** (away from centre). Press the paddle inward 0.8 mm so its face clears the **untouched original skirt**. Feed the complete slider upward from the open seam side into its loading bay, then press/slide it tangentially 11 mm toward centre into retained OPEN. Release the paddle.
2. Start the gate **3 mm outboard of its final position**. From the lid-off seam side, press its two snap fingers inward approximately 0.5 mm and feed the rigid tongues up through their keyways. A blunt plastic tool can reach the fingers from the seam-side opening; protect the thin roots. Hold them released and slide the gate 3 mm toward centre to seat the bayonet tongues. Release so both square detents retain its axial position.
3. Confirm all four rigid tongues are under their integral lands and the gate floor is seated, not perched on support residue. Its nominal tongue/land lower faces are bearing contact surfaces, not friction wedges. Gate withdrawal must be blocked when its fingers are unpressed; slider axial withdrawal must be blocked even when its own pawl is pressed.
4. Repeat with the correct handed parts at all four stations. The added parts are captive in use and stay within the original occupied-wall envelope.

Service removal is deliberate and **lid-off only**: unload the gate, reach/press both fingers, slide the gate 3 mm outboard and lower it from the seam. Press/slide the slider 11 mm outboard into its loading bay, keeping its paddle pressed while lowering past the original skirt. Do not pry against a loaded gate or floor.

The assembly calculations translate flexible regions only as an **elastic clearance surrogate**. They do not prove that a rigid printed snap can travel through a wall; real flexure/force/support cleanup must pass the physical coupon.

## Normal operation

- **Close:** all four sliders retained OPEN; lower the lid vertically using the original alignment skirt. Press each paddle inward 0.8 mm, slide 8 mm toward centre, release into LOCKED. Never use a latch to force a misaligned lid shut.
- **Open:** set the case down and fully seat/unload the seam. Press each paddle inward and slide 8 mm outward into OPEN; release. Lift the lid vertically at least 4.6 mm to clear the toes.
- Up to **0.6 mm nominal free seam lift** precedes rigid bearing contact. This is a retention closure, not a compressive/weatherproof seal.
- The rigid load path includes the gate floor/tongues and lower catch, not either release spring. Gate bearing overlap, print anisotropy, long-term creep, strength, fatigue, drop performance and actual fit remain **untested**. Until tested, support the bottom when moving the case; do not rely on the lid to carry valuable electronics.
