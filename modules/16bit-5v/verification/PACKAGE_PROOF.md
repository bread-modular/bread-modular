# Targeted physical-package proof (2026-10-02)

- **U3 MCP6002-xSN:** Microchip DS20001733L physical PDF pp.31–33 explicitly identify 8-lead **SN narrow SOIC**, body E1=3.90mm, D=4.90mm, lead pitch=1.27mm. No exposed pad is present in this package drawing.
- **U4 PT8211-S:** Princeton Technology PT8211 V1.5 (archive supplied by PJRC), physical PDF p.3 orders **PT8211-S = 8 pins SOP, 150mil**; p.6 is the corresponding 8-pin SOP-150mil drawing, without an exposed pad. The schematic/PCB now explicitly name that same IC's SOP variant; not a DAC/circuit substitution. Generic supplier numbers remain manual-match items.
- Both now use `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`. All eight external land coordinates, sizes, UUIDs and nets are unchanged; only the unsupported pad9 and four central paste-only windows per IC were removed. Native library model and schematic assignments agree.
- **U1 is not part of this replacement:** original MCU footprint, exposed-pad geometry, real nine thermal holes and paste geometry are unchanged.

Sources (targeted drawings/ordering pages only; no full PDF committed):

- Microchip: https://ww1.microchip.com/downloads/aemDocuments/documents/MSLD/ProductDocuments/DataSheets/MCP6001-1R-1U-2-4-1-MHz-Low-Power-Op-Amp-DS20001733L.pdf
  PDF SHA256: `4f879ab31115ecfa149dfea62073c9efdbc4beccbdfc3a8d7e10281f3877f8fb`
- Princeton/PJRC archive: https://www.pjrc.com/store/pt8211.pdf
  PDF SHA256: `254d8f3122128c6c587c2926a0aa237baa5098a1fbeb1570fa12770e503b6897`

Physical package evidence is closed for these declared package variants. Assembler catalog/package/rotation preview and actual purchased-part verification remain HOLD items; no order is authorized.
