# C-tight — ONE additional clearance gauge, not a case or lock

The user reports all original C channels slide comfortably on their standard
Bambu P2S / 0.4 mm nozzle. This tighter **female-only experiment is unprinted**;
filament remains unknown. Existing A/B/C files are unchanged.

Print only [`stl/C_female_G0.40_G0.20_G0.00.stl`](stl/C_female_G0.40_G0.20_G0.00.stl)
(**34.2 × 29 × 5 mm**). Reuse the **already printed**
[`../stl/C_male_8.00.stl`](../stl/C_male_8.00.stl) as-is; no new male print needed.

Viewed labels-up, with entries at the front, left → right:

| Requested clearance PER SIDE | Engraved TOTAL-gap label | Female width on full-size lands | Same male |
| --- | --- | --- | --- |
| 0.20 mm | G0.40 | 8.40 mm | 8.00 mm |
| 0.10 mm | G0.20 | 8.20 mm | 8.00 mm |
| 0.00 mm | G0.00 | 8.00 mm | 8.00 mm |

G = female − male; centred per-side clearance = G/2. Open roof-free channels,
20 mm engagement, 5 mm height, 2.4 mm walls, 0.4 mm bottom-edge relief and the
unchanged male's tip lead-in are retained. Labels are recessed away from contact
lands. Dimensions apply **above bed relief**, not at the first-layer flare.

## Print and record, without forcing

- Flat, labels **up**, **100% scale**, assumed **0.20 mm layers**. Supports are
  not planned; inspect every layer/support preview locally in Bambu Studio.
- Keep the **same material/profile** as the successful original C. Record actual
  filament, settings, measured widths, first-layer flare and seams. Do not assume
  XY hole compensation changes these open channels, or alter it for this test.
- Try G0.40 first, then G0.20, then G0.00, gently by hand to ~20 mm engagement.
  **Stop if 0.10 mm per side or zero binds; zero nominal clearance may not slide
  in print. Never force, hammer or sand contact lands.** Record slide/bind,
  entry-only resistance and rocking as printed; do not turn a bind into a fit.
- CAD zero distances are **expected contact**, not a physical sliding guarantee.
  No slicing, print-time estimate, remote printing or material qualification.

## Live CAD, strict isolated rerun and evidence

`cad/C-tight.FCStd` contains Parameters + one live FeaturePython female. Open
`Open.FCMacro` from FreeCAD's Macro menu so its proxy is importable; edit
`Parameters.GaugeGaps` (TOTAL gaps, left to right) to see geometry and labels
recompute. The delivery recipe remains fixed in `tight_gauge.DEFAULTS`; the
strict validator requires exactly [0.40, 0.20, 0.00]. GUI edits do not update STL.

From repository root, use an **existing** extracted runtime (no download):

```bash
FREECAD_APPDIR=/path/to/squashfs-root bash opt/travel-case/lock-studies/c-tight/run.sh build
```

Also accepts `FREECAD_PYTHON` or an existing local/parent/slide-clips runtime.
`run.sh validate` checks existing hashes first, revalidates and refreshes its own
report/hashes; `run.sh open` is a headless reopen check, not a desktop launcher.
The build exports just this one female; cleanup touches only this extension's
`cad/`, `stl/`, `reports/` and manifest. Parent `run.sh` cannot erase these files.
No baseline build/validation script is imported or executed.

`reports/validation.json` records reopened live edit/restoration, a single closed
CAD solid, actual exported mesh topology/orientation/self-intersections and a
mesh-to-CAD geometric comparison (1e-6 mm boolean tolerance for STL float32,
plus bidirectional surface samples within 1e-5 mm; no mesh repair). It measures
all channels and the original
rail on full-size CAD/STL lands, checks 41 insertion poses per channel **plus a
conservative continuous swept enclosure**, allows zero contact without
positive-volume collision, and screens roof/support geometry at 0.20 layers.
No claim of arbitrary manipulation, print fit, strength or slicer qualification.

`baseline.SHA256SUMS` pins the original 22 parent entries; checks enforce all
20 non-doc artifacts unchanged and allow only README/PRINT_TEST_GUIDE checksum
updates. `SHA256SUMS` covers this extension's sources, docs, CAD, one STL and
report (not itself or ignored caches). Strict build exits nonzero on any failure.
