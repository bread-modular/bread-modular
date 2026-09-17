# BASE v1.3.1 slot-template refactor - netlist identity evidence

* before: `verification/netlist-before.kicadsexpr`
* after : `verification/netlist-after.kicadsexpr`

**result: IDENTICAL (netlist)**

## Nets
* nets compared: 78; identical name/node sets: yes
* nodes compared: 513 (before), 513 (after)

## Components
* components compared: 163
* value/footprint/sourcing differences: 0
* Sheetname/Sheetfile (expected to change): 192 components
* free-text Description differences (expected, template-generic): 48
  - C22, C23, C24, C25, C26, C27, C28, C29 ...

## Sheet instances (ref mapping)

| instance | sheet | parts |
|---|---|---|
| Slot1 | slot.kicad_sch | C22, C23, GND1, J7, R28, R29, U6, VSUPPLY_1 |
| Slot2 | slot.kicad_sch | C24, C25, GND2, J8, R30, R31, U7, VSUPPLY_2 |
| Slot3 | slot.kicad_sch | C26, C27, GND3, J9, R32, R33, U8, VSUPPLY_3 |
| Slot4 | slot.kicad_sch | C28, C29, GND4, J10, R34, R35, U9, VSUPPLY_4 |
| Slot5 | slot.kicad_sch | C30, C31, GND5, J11, R36, R37, U10, VSUPPLY_5 |
| Slot6 | slot.kicad_sch | C32, C33, GND6, J12, R38, R39, U11, VSUPPLY_6 |
| Slot7 | slot.kicad_sch | C34, C35, GND7, J13, R40, R41, U12, VSUPPLY_7 |
| Slot8 | slot.kicad_sch | C36, C37, GND8, J14, R42, R43, U13, VSUPPLY_8 |
| Slot9 | slot.kicad_sch | C38, C39, GND9, J15, R44, R45, U14, VSUPPLY_9 |
| Slot10 | slot.kicad_sch | C40, C41, GND10, J16, R46, R47, U15, VSUPPLY_10 |
| Slot11 | slot.kicad_sch | C42, C43, GND11, J17, R48, R49, U16, VSUPPLY_11 |
| Slot12 | slot.kicad_sch | C44, C45, GND12, J18, R50, R51, U17, VSUPPLY_12 |

## ERC
* `erc-before.json`: error pin_not_connected x4, error power_pin_not_driven x3, warning lib_symbol_mismatch x1
* `erc-after.json`: error pin_not_connected x4, error power_pin_not_driven x3, warning lib_symbol_mismatch x1
* identical finding counts per type: yes
* representative item changes (same finding, different reporting symbol):
  - error power_pin_not_driven: 1 -> 0
  - error power_pin_not_driven: 0 -> 1
