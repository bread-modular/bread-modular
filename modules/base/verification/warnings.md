# Retained DRC warnings

All 59 findings are `lib_footprint_mismatch`; none is suppressed.

| References | Count | Reason retained |
|---|---:|---|
| 5V14, C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, D1, FB1, FB2, INPUT1, R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R12, R14, R15, R16, R17, R18, R19, R20, R21, R24, R25, R26, R27, U2, U3, U4, U5 | 53 | Existing library-revision/customized footprint copies. Their physical lands, holes and positions are preserved, rather than silently refreshed. This is not a new manufacturer qualification. |
| J5 | 1 | Physical second GND/VBUS pads renamed B12/B9 to match the merged schematic; all geometry unchanged. |
| J1, J2, J4, J6, SW1 | 5 | Internal pad-overlapping silkscreen artwork moved to F.Fab; all physical geometry unchanged. |

See `drc-after.json` for each reference, UUID and location. There are no remaining
silk collisions, undersized text, dangling tracks/vias, or schematic-parity warnings.
