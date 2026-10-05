# STANDARD JLCPCB package — user-approved existing design

The user approved STANDARD: **"This is okay. 32bit is Standard anyway."**
The latest instruction is **"Just don't worry about it. It was already good. The only
change here is to add a 5V to 3.3V regulator. Create the JLCPCB files."**

Existing design acceptance authorizes package generation, not a claim that absent
bias/ESR/pulse/identity/manufacturing evidence was tested, qualified or accepted by
JLCPCB. Inherited D1/capacitor/resistor application concerns are user-accepted existing
design and do not block generation. Requested quantity remains unknown; no stock,
attrition, order acceptance or shipping certification. Sol Max only; advisor OFF.

## Confirmed current source

Exactly one regulator already exists: **U5 AP2112K-3.3TRG1 / C51118** (SOT-23-5),
VIN pin1 and EN pin3 on **+5V**, GND pin2, VOUT pin5 on **+3V3**, NC pin4 isolated.
It is synchronized in schematic/PCB and occurs once in both assembly BOM and CPL.
No regulator is added or duplicated, and no native design/geometry/binding is changed.

U1 C3013946 / ESP32-S3-WROOM-1U-N16R8 stays assembled:
**ACCEPTED FOR SELECTED SERVICE**. Its true raw type2/Economy=false observation is
unchanged. All 45 R/C refs /16 codes remain actual Basic with recorded Economy
compatibility. Standard selection does not alter global common Economy semantics.

## Generation and evidence scope

```sh
/usr/bin/python3 -B modules/32bit-5v/tools/regenerate_production.py --generate-package
```

The existing module guard runs bounded fresh DRC/ERC/parity/netlist checks, exact
source/binding guards, existing shared top/full exporter APIs and shared Gerber-mirror
API. It rejects concrete source/connectivity/BOM/CPL/Basic/geometry drift. It uses only
unchanged dated catalog bindings offline: **zero supplier queries**. Native settings,
inherited warnings/ignores, manual selection and D1's original row/code are retained.
Every BOM/CPL byte is guarded against the prior source-identical snapshot; fabricated
artwork/drills match the routed baseline ignoring only dated creation headers.

`production/manifest.json` and `basic-economy/package-review.json` describe the current
**FILES_GENERATED_NOT_ORDER_ACCEPTED** package. `standard-service-policy.json` binds
approval and preserved source/history. `basic-economy/final-audit.json`, catalog summary,
planner, strict audit failures and older handoffs are archived Economy/application
observations, not the current generation status. Missing evidence is not relabelled as
qualified, and an old complete Economy capacity zero is not Standard capacity.

## Standard upload instructions

Use only this matched current assembly set (paths relative to `modules/32bit-5v`):

- PCB: `production/assembly/32bit-5v-gerbers.zip` (13 members, 4 copper layers,
  front/back mask/paste/silk, outline and PTH/NPTH drills).
- Assembly BOM: `production/assembly/bom.csv`.
- Pick/place CPL: `production/assembly/positions.csv`.
- SHA-256/input/output manifest: `production/manifest.json`.
- Loose Gerbers/drills: `production/gerbers/`; identical upload mirror:
  `jlcpcb/32bit-5v/` and `jlcpcb/production_files/GERBER-32bit-5v.zip`.

Select **Standard PCBA**, **top-side assembly**; preserve the existing datum/rotations
and match all **55 assembled refs**. U1 is included. **D1's supplier code is blank**
exactly as before: match that original LED row during JLC upload; do not invent a code,
silently omit it or label the uploader as accepted. The six manual/THT refs are GND1,
INPUT1, OUTPUT1, RV1, RV2, V_SUPPLY1. `production/full/` and root full BOM/CPL include all
61 physical refs for inventory only, not the top assembly upload.

Choose the real quantity yourself; recheck stock/attrition/minima, PCB quote options,
placement/polarity/fit and assembler process before any order. No upload or order has
been performed. All changes remain UNCOMMITTED/UNSTAGED for native diff review.
