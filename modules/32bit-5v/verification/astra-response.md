# Bounded final EP correction — prior Astra delta applied

Owner: Sol Max only, no advisors. Workspace `/home/azero/.okbrain/workspaces/bread-modular-kicad/279`; branch `okbrain/bread-modular-kicad/279-57e03384`; original `32bit-5v` / HEAD `65e1d7202f22f0ef8b387e9f1e0c1b6740731ead`. Ported exactly 72 staged uncommitted regular module files from worker277, using its exact index inventory; initial PCB/SCH hashes match the requested identities (`port-report.json`). Worker277 and all other worktrees/refs are protected. No commit/merge/push/order.

Input: `/tmp/astra-final-delta-20261002/HANDOFF.md`. Its prior identity/routing/C40/BOOT/J5/artwork corrections remain applied. This is **not post-fix Astra approval**. Only the ES8388 EP qualification gap was corrected.

## Device pad vs PCB copper vs stencil

Cached intended ES8388 datasheet physical page35 is a package outline, **not a recommended PCB land pattern**. Device D1/E1=2.50–2.70mm; body D/E=3.924–4.076mm; pitch0.450mm. No explicit cached manufacturer support for the previous 2.40mm PCB land was found; its smaller size was not by itself proof of an electrical failure. No new web research/sourcing.

Module-local actual footprint `Module32:ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias` uses **2.60×2.60mm F.Cu**, the device-pad range midpoint, and **2.65×2.65mm F.Mask** (+0.025mm per edge). Existing B.Cu thermal copper remains2.40×2.40mm and is not backside component placement. All28 outer pad nodes/nets/UUIDs, nine real Ø0.20mm PTH drills with Ø0.50mm annular copper and their positions, footprint position/rotation/side, mounts, tracks, vias, keepouts, rules and saved filled planes are unchanged. Actual SCH, embedded/local symbol and PCB footprint IDs agree. Nominal inner lead-to-EP copper gap is0.25mm; native DRC supplies the actual manufacturing-clearance gate.

**Stencil is not a full EP paste blob.** Four retained1.04×1.04mm rounded apertures (corner radius0.2500004mm), centers(±0.60,±0.60)mm: total opening area4.11179748mm², **60.82541%** of the6.76mm² copper land. Web0.16mm; opening-to-copper edge0.18mm. This is a project-selected reduced segmented-paste pattern adapted from the existing native thermal-via footprint, not blanket manufacturer PCB/stencil approval. Four corner via mouths fully overlap paste apertures. Four axial mouth centers are outside the apertures, but their finite Ø0.20mm mouths slightly intersect rounded aperture edges (about0.01044mm); only the central mouth is fully clear. Eight mouths can wick paste. No encoded via fill/cap, drill omission or oversized paste change. Assembler must validate wicking/voiding, stencil thickness, via-fill/cap or appropriate validated process, reflow and thermal performance. Generic2.4mm-name 3D model is visualization only, not land qualification.

## Preserved release holds

61 physical refs (57front/4back),55 front SMD and6 manual THT; native4Cu stack preserved. Human stack/back-body approval is still absent. Back refs:GND1,V_SUPPLY1,INPUT1,OUTPUT1. GND1/RV1/RV2 header lead protrusion/trim/pot-case clearance is still unconfirmed. Correct ES8388 manufacturer/MPN/BOM, C40/BOOT and J5's proven0.575mm width within cached0.60±0.05mm tolerance are retained. Missing51 LCSC fields alone are not a fabrication blocker; no matching mission performed. **SCOPE/PHYSICAL/ORDERING HOLD — do not order.**

Fresh native gates, exact-output hashes and final changed-object measurements are recorded in `production/manifest.json`, `final-drc.json`, `final-erc.json` and `es8388-ep-delta.json`. Prior migration/preservation reports are explicitly historical, not evidence that the old EP remains unchanged. Production wrapper regenerates the13-member4CuZIP, IPC,61-ref full BOM/CPL,55-topSMD pair,6THT list and synchronized legacy archives; final current-source previews must be identified separately from historical native/3D previews.

## Exact final closeout

Fresh DRC errors/opens/parity **0/0/0**, **98 warnings**; ERC **0errors/16warnings**. Native independent comparison of all272 pad objects found only front EP size/mask changed; fresh whole-library footprint aligns exactly with all43 placed U4 pad objects. Outer28 leads and9 thermal drills are byte-identical. Native nominal copper gap0.250mm; actual outer mask margin0, EP margin0.025mm gives **0.225mm mask web**. Nominal mask2.65mm has rounded positive-expansion corners. All stored fills, other footprints, rules, routes, mounts, side/rotation/positions unchanged.

After timestamp-only normalization, **F_Cu/F_Mask and the single derived negative-polarity F_Silkscreen EP-mask knockout** differ among13 ZIP members. F_Paste, other3Cu, all positive silk ink, bottom silk, outline and PTH/NPTH drill files are unchanged. No native artwork edit; exact Gerber comparison proves only one clear region follows the new EP mask opening. Both package ZIPs match member-for-member; legacy ZIP and full CSVs synchronized. IPC has one changed numeric record, the front EP size. Full61 / topSMD55 / THT6 inventories and centroid coordinates match the port.51 SMD missing-LCSC entries are not a fabrication blocker.

PCB SHA256 `9474a84e034ae9df0aa8cb9f31aa39a5036cc3d9f4fcb5d5bc9974d640fe4fbe`
SCH SHA256 `bd774146e97fb1a453b6c3d8cc5af1db08e39f408329eda1f7f8d0b5c0a5741b`
ZIP SHA256 `65ec59b461c919cb4baa325d7d34966051679b4f189611abe3fc4e0b49bbc68f`

Final actual-ZIP EP/stencil closeup `/uploads/921e9150-1bce-45ac-9ffb-e4487719257a.webp`; actual-ZIP top `/uploads/f7be516c-29ed-4805-89fa-d12ce4df5559.webp`; cached package page35 `/uploads/975a8cbc-13bd-4963-8ec9-1d2e4867fefa.webp`. Images inspected; no further artwork edits. All20 protected worktrees' regular-file inventories, indexes, statuses and HEADs, plus all pre-existing named/main/checkpoint/remote refs, rechecked unchanged. External new ref additions were observed and left untouched; exact names/SHAs are recorded in es8388-ep-delta.json. Final changes staged but uncommitted. **Scope/physical/assembly-process/ordering HOLD remains; no post-fix Astra approval claimed.**
