# BASE 1.3.13 — visible findings and dispositions

## PCB DRC on exact saved release source

KiCad CLI 10.0.6, `--schematic-parity --severity-all`: **0 error-level violations,
0 unconnected, 0 parity**, with **70 `lib_footprint_mismatch` warnings**. No
exclusions or severity changes were made. Silkscreen, dangling copper, courtyard,
clearance and solder-mask findings introduced during routing were resolved.

67 of the 70 retained instances have the same nominal pad positions/sizes/drills/
shapes/orientations/layers as the installed library. The remaining three are:

- J5: preserved intentional A1→B12 / A4→B9 contact renumbering needed by the
  power-only symbol, not moved copper or mechanical pads.
- 5V14 and INPUT1: preserved legacy oval-vs-circle THT annulus shape flags at
  equal X/Y dimensions; anchors, pad extents, pitch and drills are unchanged.

Graphics/metadata/library-copy differences are intentionally retained instead
of wholesale replacing approved mechanical/silk instances. Full source mechanical
invariants and physical pad-to-net parity remain checked. Detailed before/library
pad data is in `library-differences.json`; library-copy-validation.json pins the
exact source and installed library files. C50-C52 copy the exact C15 pad
geometry and differ only in metadata/reference stroke. J5 adds HRO nominal
F.Fab shell art and assembly-only XY fields; physical pads remain fixed. These warnings are **not suppressed**.

Every remaining warning reference is enumerated below:

| Footprint family | References |
|---|---|
| `BreadModular_AudioJacks:Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical` | `J1`, `J2`, `J4`, `J6` |
| `BreadModular_MISC:K2-1808SN-A4SW-01` | `SW1` |
| `BreadModular_TypeC:HRO-TYPE-C-31-M-12` | `J5` |
| `Capacitor_SMD:C_0402_1005Metric` | `C1`, `C15`, `C16`, `C21`, `C50`, `C51`, `C52` |
| `Capacitor_SMD:C_0603_1608Metric` | `C18`, `C19` |
| `Capacitor_SMD:C_0805_2012Metric` | `C2`, `C4`, `C5`, `FB1`, `FB2` |
| `Capacitor_SMD:C_1206_3216Metric` | `C3`, `C6`, `C7`, `C8`, `C9`, `C10`, `C11`, `C12`, `C13`, `C14`, `C17`, `C20` |
| `Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical` | `J7`, `J8`, `J9`, `J10`, `J11`, `J12`, `J13`, `J14`, `J15`, `J16`, `J17`, `J18` |
| `Connector_PinSocket_2.54mm:PinSocket_1x05_P2.54mm_Vertical` | `INPUT1` |
| `Connector_PinSocket_2.54mm:PinSocket_2x05_P2.54mm_Vertical` | `5V14` |
| `LED_SMD:LED_0603_1608Metric` | `D1` |
| `Package_TO_SOT_SMD:SOT-23-5` | `U5` |
| `Resistor_SMD:R_0402_1005Metric` | `R1`, `R4`, `R5`, `R6`, `R7`, `R8`, `R9`, `R14`, `R15`, `R16`, `R17`, `R20`, `R21`, `R24`, `R26`, `R27` |
| `Resistor_SMD:R_0603_1608Metric` | `R2`, `R3`, `R18`, `R19` |
| `Resistor_SMD:R_1206_3216Metric` | `R10`, `R12` |

## ERC — unchanged finding identities, NOT zero ERC

Actual ERC has **11 findings: 7 errors, 4 warnings**. It is identical to the
pre-R58/R59 circuit by finding identity; no no-connect/power flags or suppression
were invented to make this release appear clean.

| Severity / type | Affected item | Explanation / disposition |
|---|---|---|
| error `pin_not_connected` (4) | J2.R, J2.T, J4.R, J4.T | Deliberately unused ring/tip of the ground-only jacks; source has no explicit no-connect markers. Preserved, not electrically used. |
| error `power_pin_not_driven` | U5.1 VIN / LDO_VIN | Upstream power passes through passive fuse/ferrite; ERC lacks a power-output driver/flag on this separate net. The physical path is checked. |
| error `power_pin_not_driven` | #PWR025 / +3.3V | Regulator VOUT is on Net-(U5-VOUT), then passive FB2 reaches +3.3V; ERC does not propagate a power-output driver through that filter. |
| error `power_pin_not_driven` | #PWR026 / GND | Externally supplied USB ground/passive return has no ERC power-output source/flag. |
| warning `lib_symbol_mismatch` (4) | RV1, RV2, D1, J5 | Preserved cached symbol copies differ from installed Device/Connector libraries. Current netlist and PCB parity are authoritative. |

`erc-after.json` contains the real findings. These explanations are not bench
proof. Independent schematic review can decide whether to explicitly annotate
unused contacts / supply flags later; such edits are outside this bounded pass. The only new circuit pins are six
supply/GND capacitor pins; the live ERC finding UUID/type/severity identities
are identical to the imported candidate, proved by verify_bounded_improvements.py.

## Parser / assembly / physical risks

Gerbonara accepts KiCad's Excellon `G90` after the header delimiter but reports
one syntax notice for each drill file. Both files parse; all 440 drill/slot
features are independently compared to PCB geometry. Those notices are recorded
in `render-review.json`; they are not DRC errors or missing drill commands.

Part numbers, package names and source polarity are carried from the circuit;
J5 body-centre CPL is checked against independent HRO dimensional evidence, not
its raw anchor. Other anchor/angle/side math is checked exactly. JLCPCB library orientation/centroid
corrections and placement preview have **not** been approved. No stock/price
claims are made. 1.3.2 cost artifacts are explicitly stale.

Accepted electrical/physical holds are in `../POWER.md` and
`../production/RELEASE_STATUS.md`: no per-slot ILIM, surge gap, residual backfeed,
shared input-rail transients, unperformed bench reset/startup/audio checks,
calculated-not-measured stack, header/socket depth assumptions, preserved slot-1
misalignment and the top-mounted module-header exceptions.
