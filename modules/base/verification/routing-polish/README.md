# Routing evidence scope — current completion, not recovered history

The historical routing-polish evidence referenced by the original 1.3.14 notes
was absent when this task resumed. In particular, the claimed 1,602-to-276 segment
reduction and TraceMaker/manual-routing comparison were not re-run or reconstructed.

`summary.json` records only this completion pass against the saved working PCB:

- Every one of the 201 footprint geometries, pad nets, placements and silkscreen
  objects was preserved, including the user's existing D16/R74 changes.
- Removed the still-present dead-end +3.3V supply branch: exactly 2 vias and
  4 segments. Exact UUIDs, geometry and the input PCB hash are in the report.
- All other track/via nodes, outline, settings and zone boundaries were preserved.
  Only zone fills were regenerated natively, and 48 footprint schematic-association
  fields were repaired. No rerouting, part moves or rule/severity changes occurred.
- Native final check: 0 DRC errors, 0 unconnected and 0 schematic-parity findings;
  61 pre-existing footprint-library-copy warnings remain.

The complete source-bound reports, pin-net comparison and JLCPCB export evidence
are in `../selectors/`. This is neither historical routing proof nor bench/order
approval.
