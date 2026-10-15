# LED placement — current snapshot and preservation proof

`summary.json` records the saved coordinates, rotations and LCSC codes for all
thirteen switch/MOSFET/LED/resistor groups, including the MONO group.

All 201 footprint/pad/part/silkscreen geometries were preserved from the saved PCB
at the start of this completion pass. The user's D16 orientation and R74 placement
were already present in that input and are reflected in the new CPL; they were not
changed by this repair. No LED or buffer was moved during this pass.

The earlier before/after evidence for the claimed Q1–Q12 nudge and D4–D15 placement
change was absent. This snapshot does not reconstruct that historical delta, prove
module underside clearance, or certify LED visibility with a module installed.

See `../selectors/README.md` and its source-bound native reports for current
connectivity, DRC, schematic/library repairs and export verification. JLCPCB's
component/polarity preview remains required before an order.
