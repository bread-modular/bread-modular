# Original magnet travel case

Only the original **case_1.0.0 magnet closure** is retained, with the two explicitly requested surface edits:

- [`original/case_1.0.0/`](original/case_1.0.0/): pristine release STL/F3Z, metadata, inventory, checksums and MIT license; bytes unchanged.
- [`magnet-case/`](magnet-case/): one final FreeCAD design with the lid backside logo filled flush and the base EXTERIOR underside bays filled flat. Original profile, dimensions, magnets, seam, connector openings and PCB mounting retained.

Start with [`magnet-case/README.md`](magnet-case/README.md) and [`VALIDATION.md`](magnet-case/VALIDATION.md). Surface shells are script-rebuilt frozen faceted BReps; native pocket-depth features remain editable. Final lid mesh checks pass. **Preserved inner base engraving still has 13 final vs 12 original self-intersection flags; no all-mesh-pass or print qualification is claimed.**

Rejected alternative closures/studies were removed from this working tree, not from Git history. Full deletion and pristine-source hash audit: [`magnet-case/reports/cleanup.json`](magnet-case/reports/cleanup.json).
