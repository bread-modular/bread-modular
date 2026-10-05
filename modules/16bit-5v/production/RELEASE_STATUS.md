# 📦 JLCPCB files — user-authorized existing design

The user explicitly accepts the inherited 16bit engineering and authorizes file generation: “Same goes for 16bit as well” extends “Just don't worry about it. It was already good. The only change here is to add a 5V to 3.3V regulator. Create the JLCPCB files.” LED/application, capacitor bias/ESR and resistor-stress reviews are **not file-generation HOLDs**. This acceptance is not a fabricated specification, supplier match, stock reservation, physical shipping certification or order authorization.

- **Existing regulator:** U6, AP2112K-3.3TRG1 / C51118 / SOT-23-5. VIN pin 1 and EN pin 3 are on +5V, GND pin 2 on GND, VOUT pin 5 on +3V3. It is already included in the schematic, PCB, assembly BOM and CPL; no duplicate or circuit change is needed.
- **Scope:** isolated workspace 292, base `17102ba4701cc24b2798b80a08f1f0180c1226aa`. All 116 missing checkpoint paths were restored before generation; 217 manifest hashes, seven resolved source inputs and 19 common files plus the skill were verified. Other workspaces/branches are untouched. Everything remains uncommitted and unstaged.
- **Passives:** preserve all existing native bindings: **41/43 required R/C have dated actual Basic + Economy evidence**. R7/R8 remain the original 27Ω/0402 parts with blank supplier codes. They are explicit **Basic sourcing exceptions**, not secretly Basic or dropped from assembly. The saved exact mixed-network calculation is not implemented; latest steering prioritizes exports and avoids unrelated USB redesign.
- **D1/U5:** preserve their existing BOM rows, footprints and blank codes. D1 remains generic LED; U5 remains generic PSRAM. Exact supplier matching is required during upload; no device is invented and neither row is omitted.
- **Matched outputs:** two copper layers; 56 top SMD references in assembly BOM/CPL; 62 physical references in complete BOM/CPL; six explicit manual parts (`GND1`, `V_SUPPLY1`, `J1`, `J2`, `RV1`, `RV2`). Outline, mounts, datum, existing filled zones, routing and all native sources are unchanged.
- **Actual tests:** the guarded generation checks native connectivity/metadata, ERC, DRC and schematic parity and rejects new concrete errors/warnings, exclusions or severity changes. Current results and artifact hashes are in `manifest.json`. Conservative common audits retain real unknowns; they do not veto user-authorized file generation or imply an authenticated order is ready.

## ⬆️ Upload inputs — Economy, top-side assembly

Use this matched set from `modules/16bit-5v/production/assembly/`:

1. PCB fabrication: `16bit-5v-gerbers.zip` (both copper layers, front/back mask/paste/silkscreen, outline, PTH and NPTH drills).
2. Assembly BOM: `bom.csv` — retain **all 56** references, including R7/R8, D1 and U5.
3. Assembly CPL: `positions.csv` — top side, mm, native drill/place datum; verified J5 body offset retained.
4. Provenance: `../manifest.json`; complete/manual references are documented in `../bom.csv`, `../positions.csv` and `../manual-assembly.csv` (do not substitute the complete THT-inclusive CPL for the top-SMD assembly CPL).

The byte-identical fabrication archive is also mirrored at `modules/16bit-5v/jlcpcb/production_files/GERBER-16bit-5v.zip`; loose matching Gerbers/drills are in `modules/16bit-5v/jlcpcb/gerber/`.

### Supplier/order matching still required (not inherited engineering HOLDs)

- Choose **Economy/Economic PCBA, top side** and verify current board/process options, every actual matched part and the portal's Economy eligibility. Dated Basic/Economy evidence is not authenticated order acceptance. A fully Basic-passive Economy BOM is **not yet proven** because R7/R8 are unassigned.
- Match R7/R8 to exact 27Ω/0402 parts with their intended tolerance/rating; do not claim Extended as Basic. Preserve D1's intended identity/polarity and U5's intended memory/firmware identity when matching their retained rows.
- Requested batch size is unknown; dated stock is only a one-board placement basis. Saved PT8211 C92004 stock was one, without attrition/minimum quantity or reservation. Recheck actual quantity, all stock, minima and attrition before an order.
- Install the six listed manual connector/pot parts separately. Review actual JLC placements, rotations/pin 1/polarity, all Gerber layers/drills/paste and current manufacturing options yourself. Physical shipping certification and authenticated upload/order were not performed.

**File generation authorized; supplier/order matching pending; `order_ready=false`.** No advisor, delegation, new supplier/manufacturer research, uploads, orders, commits, staging or pushing.
