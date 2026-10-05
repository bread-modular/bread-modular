# 32bit-5v Basic R/C catalog binding — release HOLD

## Scope and authoritative baseline

Work is restricted to isolated workspace 289, based on branch `32bit-5v` tip
`74db23e0aaec4286caaf95eb2c00461ab0999e3e`. Sol Max only; advisor OFF.
No commit/staging/merge/push/order/authenticated upload. No main/base design import.
Common tools/skill were imported first from `f43184a620aee47aec456241646d008fb4a65bda`;
only the four capacitor-voltage-alias paths from
`4a77e133af1f1da80b8aed1bf03a5b550f8448d3` were subsequently imported.
See the [shared skill](../../../../.agents/skills/jlcpcb-assembly/SKILL.md) and
[shared assembly documentation](../../../../opt/kicad-jlcpcb/ASSEMBLY.md).

`baseline/manifest.json` freezes the actual routed source SHA256s and temporary
handoff/inventory hashes. `readonly-handoff.md` is preparation/history, NOT live
availability. `baseline/inventory.json` contains only the handed-off 32bit inventory.
Fresh baseline and final CLI reports, rather than old POWER.md routing statements,
control this delta. Baseline: 61 physical refs; 55 front SMD; 6 manual/THT; 4 copper.

**Implemented scope:** exact native supplier/rating binding of existing nominal
R/C values and footprints, plus exact-identity codes for other assembled parts.
No R/C electrical value, footprint, pin/pad map, topology, position, copper, outline,
connector alignment, manual plan or assembly datum changed. These are sourced
**review candidates**, NOT blanket application approvals. Missing manufacturer
qualification remains a genuine HOLD; required R/C were not converted to Extended,
DNP, exclusion or manual assembly to hide it.

## Native substitutions / bindings

All rows are direct, same-footprint two-terminal bindings. `unassigned` means the
native schematic and PCB previously had no exact supplier code, not a known old MPN.
The three pre-existing capacitor codes are retained; no unavailable Extended R/C
substitution was necessary. `passive-plan.json` records full exact MPN/manufacturer,
old/new fields, role, common-planner target/results and unresolved reviews.

| Refs | Original code | New/retained code | Value / actual package | Recorded rating |
|---|---|---|---|---|
| C1,C4,C6,C21,C22,C26,C34,C36,C39 | unassigned | C1525 | 100nF / 0402 | CL05B104KO5NNNC, 16V X7R ±10% |
| C42 | C1525 | C1525 | 100nF / 0402 | same; +5V input HF bypass |
| C2,C8 | unassigned | C19702 | 10uF / 0603 | CL10A106KP8NNNC, 10V X5R ±10% |
| C3 | unassigned | C52923 | 1uF / 0402 | CL05A105KA5NQNC, 25V X5R ±10% |
| C5,C27,C33,C35,C37,C38 | unassigned | C15525 | 10uF / 0402 | CL05A106MQ5NUNC, 6.3V X5R ±20% |
| C7 | unassigned | C15008 | 100uF / 1206 | CL31A107MQHNNNE, 6.3V X5R ±20% |
| C20 | unassigned | C1710 | 10nF / 0805 | CL21B103KBANNNC, 50V X7R ±10% |
| C40 | C15850 | C15850 | 10uF / 0805 | CL21A106KAYNNNE, 25V X5R ±10% |
| C41 | C45783 | C45783 | 22uF / 0805 | CL21A226MAQNNNE, 25V X5R ±20%; manufacturer NRND |
| R1,R2,R9,R13,R17 | unassigned | C11702 | 1k / 0402 | 0402WGF1001TCE, ±1%, 1/16W, 50V |
| R3 | unassigned | C25744 | 10k / 0402 | 0402WGF1002TCE, ±1%, 1/16W, 50V |
| R4,R11 | unassigned | C23186 | 5.1k / 0603 | 0603WAF5101T5E, ±1%, 1/10W, 75V |
| R5,R6 | unassigned | C25867 | 1.5k / 0402 | 0402WGF1501TCE, ±1%, 1/16W, 50V |
| R7,R8,R14,R18,R26 | unassigned | C25105 | 33 / 0402 | 0402WGF330JTCE, ±1%, 1/16W, 50V; dynamic-load HOLD |
| R10,R12,R16,R19 | unassigned | C25741 | 100k / 0402 | 0402WGF1003TCE, ±1%, 1/16W, 50V |
| R15 | unassigned | C22859 | 10 / 0603 | 0603WAF100JT5E, ±1%, 1/10W, 75V; pulse/inrush HOLD |
| R24,R25 | unassigned | C25900 | 4.7k / 0402 | 0402WGF4701TCE, ±1%, 1/16W, 50V |

Native voltage, tolerance, temperature, resistor power, dielectric, nonpolar status
and datasheet fields are synchronized. Effective-C/ESR fields explicitly say
UNVERIFIED, not invented numbers. Original generic R/C had no specified tolerances
or ratings; new catalog tolerances are recorded, not claimed to be pre-existing
qualified circuit limits. Equal values retain distinct local circuit roles.

Other exact identities: FB1 C5671/GZ2012D121TF; J5 C165948/TYPE-C-31-M-12;
SW1/SW2/SW4 C92589/K2-1808SN-A4SW-01; U3 C116706/MCP6002-I/SN;
U4 C365736/ES8388; U5 retained C51118/AP2112K-3.3TRG1;
U1 C3013946/ESP32-S3-WROOM-1U-N16R8. Ordinary Extended classification is disclosed
and not treated as a prohibition for non-R/C. There are no architecture substitutions.
D1 remains the original assembled generic LED with no chosen color/MPN/code;
its audit is UNKNOWN, not a zero-stock or unavailable-part claim.

## Application review: facts versus unresolved qualification

Manufacturer URLs, retrieval UTC, resolved URL, raw SHA256 and documents are in
`manufacturer/retrievals.json`. Samsung's public exact-family pages explicitly list
packaging suffixes matching the chosen MPNs, sizes, nominal C, tolerance, rated V
and X5R/X7R. They label the page data typical/design-reference data. LCSC PDF URLs
returned HTML, which is retained as failed PDF evidence, not misrepresented as a
manufacturer PDF. The public official pages replace those for nominal/rating facts;
no hidden portal/catalog endpoint was reconstructed.

- **Rails:** the actual fresh pin graph confines +5V to the supply header, U5 VIN/EN
  and C40/C42. +3V3 feeds the main rail, FB1/ESP32 and R15/codec branch. Review uses
  a 6V input envelope (AP2112 recommended-input maximum) and 3.6V low-voltage envelope;
  these are conservative circuit inputs, not measurements. No 6.3V cap is on +5V.
  At 3.6V, the 6.3V rating is below the chosen 75% voltage-utilization ceiling, but
  that does not prove useful effective capacitance or ripple performance.
- **AP2112:** fetched Diodes DS39724 Rev.2-2 states stability with 1uF and recommends
  X5R/X7R ceramic input/output capacitors. Its actual pins are VIN1/GND2/EN3/NC4/VOUT5;
  input recommendation 2.5..6V and fixed 3.3V output are retained. C40 10uF and C41
  22uF remain the original exact parts. A conservative minimum 1uF effective-C target
  is recorded for both, but no manufacturer worst-case DC-bias/temperature/aging
  lower bound or ESR/frequency bound was established. **Do not replace these by a
  nominal 1uF part or assert regulator stability from this catalog check.** Thermal
  and load-transient qualification are still required. C41's NRND warning is disclosed;
  current public stock is not a lifecycle guarantee.
- **C2/C8:** nominal 10uF is not reduced. C2 stays local to the ESP32 feed after FB1;
  C8 remains main-rail bulk. Espressif guidance was fetched, including the external
  10uF/0.1uF supply recommendation. Exact-MPN DC-biased capacitance and module
  load-transient margin remain unverified; no nominal-to-effective equality is used.
- **C3/C4/R3:** original EN/reset parallel 1uF + 100nF with 10k is preserved (nominal
  RC about 11ms). Actual minimum reset delay depends on biased C and rail ramp;
  startup, button discharge and brownout timing are not approved by nominal RC math.
- **Codec C5/C37/C38/C7:** local bulk and R15 isolation remain unchanged. C27 is VREF,
  C33/C34 VMID, C35/C36 ADCVREF; they are not all interchangeable supply capacitors.
  The cached ES8388 manufacturer datasheet identifies these decoupling pins, a
  3.6V recommended upper supply and typical 59mW playback+record at 3.3V, but does not
  give a guaranteed maximum load for this application. Reference noise/startup,
  bias-effective C and impedance must still be qualified.
- **R15 pulse blocker:** typical 59mW/3.3V is about 18mA, not a guaranteed maximum.
  The 0.1W/50%-derated continuous envelope alone does not prove startup. Charging
  the existing nominal 130.4uF directly connected codec rail through 9.9-ohm low
  tolerance at a conservative 3.6V produces an ideal initial 364mA / 1.31W pulse;
  actual regulator ramp/current limiting/biased C change its waveform. No safe
  pulse-curve bound was established. **Application approval stops here; do not
  claim the C22859 binding proves inrush or codec thermal/power safety.**
- **33-ohm digital resistors:** preserve I2S/clock damping (not USB termination).
  Firmware specifies 44.1kHz stereo audio; manufacturer MCLK maximum is not the
  firmware's operating clock. Actual edge current, load C, clock configuration,
  average dissipation and overload pulses are not proven. Requirements deliberately
  leave these stress limits unknown; no full-rail DC/CMOS load assumption clears them.
- **Other resistors:** Uniroyal manufacturer family document gives WG=1/16W,
  WA=1/10W, F=±1%, 0402 50V / 0603 75V and continuous derating above 70C. It also
  says working voltage is limited by sqrt(P*R), NOT solely the maximum-voltage row;
  jumper-current figures are NOT ratings for these nonzero resistors. The planner
  checks both V and I extrema under a 50% continuous-power ceiling and 75% voltage
  ceiling for intended low-voltage signal envelopes; external signal abuse,
  USB compliance, noise, temperature and pulses are not blanket approved.
- **C20:** original 10nF shield-to-ground AC coupling is retained, not pooled with
  decouplers. Operating shield/transient/ESD requirements are not supplied. Its
  50V rating does not certify ESD protection; the voltage-stress requirement remains
  unknown rather than assuming the shield is a 3.3V rail.

No series capacitor network or assumed voltage sharing; no series/parallel R/C
network or alternative land pattern was needed. `audit-requirements.json` intentionally
has no fabricated `verified_specs`, bias/ESR/ESL values or boilerplate review approvals.
The final conservative audit must remain failed/unknown at these genuine gates.

## Catalog and board-level Economy are separate

`catalog/final-live-summary.json` and `final-live-parts.json` contain final bounded,
deduplicated common-API lookups. `catalog/final-raw/` retains each exact response,
request, UTC timestamp and SHA256. Demand is **ONE board only**; requested order
quantity is unknown; no attrition/minimum assembly/reel/reservation is included.
The summary records stock/per-board quantities and max possible sets per exact code.
Do not describe the initial handed-off/public fixture stock as final availability.

All 45 R/C /16 codes must pass live Basic + per-part `componentProductType` Economy
and one-board stock checks; Preferred Extended never counts as Basic. Full audit
and full-board Economy are **not** thereby passed:

- U1 C3013946 is explicitly `componentProductType=2` (**Standard-only**). The exact
  N16R8/1U MCU, circuitry and assembled BOM/CPL membership are retained. The user
  has not chosen manual MCU installation versus Standard assembly. No silent
  manual exclusion or MCU redesign. Complete Economy capacity is **0** as configured.
- D1 still lacks an exact MPN/code; complete stock-limited board capacity is unknown.
  Known-component stock ceilings do not prove complete boards can be ordered.
- Before any user-controlled order, recheck actual quantity + attrition/minima,
  class/service eligibility/stock and PCB quote options, plus all manufacturer,
  physical-fit, thermal, stencil/reflow and placement/polarity gates. No authenticated
  order acceptance, reservation, preview, upload or purchase occurred.

## Native verification and production preparation

`native-proof.json`: 222 unique physical ref/pin mappings agree with fresh schematic
XML; every pin group equals the routed baseline; all selected native fields agree.
An independent normalized native-tree comparison permits ONLY the explicitly
listed supplier/rating fields: all circuitry, placement, pads/copper, zones, outline,
manual connectors, datum, native exclusion flags and DRC/ERC settings are unchanged.
Zone refill was actually executed and saved in private temporary storage; saved
polygon geometry equals the existing native fill exactly (5 zones, 6 filled polygons),
so original saved native polygons were retained without gratuitous serialization.

Fresh baseline and final: **DRC 0 errors, 98 unchanged warnings, 0 unconnected,
0 parity; ERC 0 errors, 16 unchanged library warnings.** Warning identities as well
as counts are compared. No new waiver/severity reduction; existing ignored checks
in the unchanged `.kicad_pro` remain historical, not newly cleared. Do not call this
"DRC clean". Historical original-netlist.xml's USB alias exceptions are not needed
for the actual current routed-baseline symbol; the live proof waives no missing pin.

Ordinary shared suite after the alias import: 103 tests run, 97 pass, 6 optional
integration skips. Two synthetic real-KiCad integration tests also pass. Main/base
checkpoint integration was deliberately not run or satisfied by importing base.

The module-specific guarded wrapper now binds to `reviewed-source.json`, the NEW
in-repo baseline/proof/requirements, and no old `/tmp/.../HANDOFF.md`. All counts,
exact MCU/U4 identity, four-layer, graph, mechanical and metadata guards remain.
Default invocation fails HOLD before publication. Only explicit review preparation:

```sh
/usr/bin/python3 -B modules/32bit-5v/tools/verify_sourcing.py
/usr/bin/python3 -B modules/32bit-5v/tools/regenerate_production.py --review-preparation
```

Production uses the existing shared exporter (explicit top assembly and full physical
inventory) and shared wrapper's `mirror_gerbers` API, not another exporter/client.
Strict `--require-part-numbers` export is genuinely blocked by D1 and captured in
`strict-export-hold.json`; the matched 55-ref review BOM/CPL retains that missing code
and **HOLD** status rather than hiding the part. Four enabled copper layers, masks,
paste, silkscreen, outline and PTH/NPTH drills are mandatory archive guards.
`production/manifest.json` records input/output/tool SHA256s, native/catalog artifacts,
manual refs, quantity basis and unresolved gates. `jlcpcb/` mirrors use the exact
same assembly ZIP/CSV/report, never a separately sourced snapshot. All outputs are
review artifacts, not order/manufacturing release approval.


## Final recorded snapshot (not a reservation)

Final live retrievals: **2026-10-05T06:07:57Z through 2026-10-05T06:08:41Z**;
23 distinct exact-code/MPN bindings, one network request per code in this phase.
All 45 R/C placements /16 codes were observed actual Basic, product type 0
(Economic and Standard), with stock sufficient for ONE board. R/C-only placement
stock ceiling: **362,419 sets** (C25105: 1,812,096 /5 per board). Known-component-only
ceiling: **6,426 sets** (SW1/SW2/SW4 C92589: 19,280 /3). Complete stock capacity is
unknown because D1 is unsourced; complete Economy capacity is **0** due U1.
U1's observed stock is 15,816 but its product type remains 2, Standard-only.
No quantity was ordered or reserved; final quantity/attrition/minima recheck remains HOLD.

An earlier conservative live attempt failed because the C11702 **code-prefix** query
returned a truncated page, and the common audit reissued that uncached failure for
five refs before its 24-request budget was exhausted. That failed report and raw
snapshots remain in `catalog/failed-code-prefix-audit/`; no production was published
from it. The module now prefetched each distinct code once and stops on ambiguity.
C11702 uses ONE documented public exact-MPN search `0402WGF1001TCE`, with exact
C11702 + native MPN identity checked using the unchanged common parser before its
normal common-API memo is populated. No duplicate/private catalog client or
supplier retry/reversing loop. All other final bindings use the common exact lookup.

Actual delivered ZIP was independently parsed and rendered (Gerbonara/CairoSVG
in an isolated temporary viewer environment, no repository/tool installation).
`gerber-views/four-copper.png` and `all-fabrication-layers.png` show all four copper,
mask, paste, silk, outline and drills, in a common top-view datum. Every one of the
13 raw members equals the committed routed-baseline member after removing ONLY
creation-date header lines: `gerber-baseline-comparison.json` records normalized
and raw archive SHA256s. Outline, thermal pads/vias and connectors are retained.
Inherited B.Paste openings are visible and unchanged; archive inclusion is not
approval to assemble a second side. Assembler top-only stencil/connector process
review remains required. The manufacturing/placement approval HOLD is not cleared
by these views or the baseline comparison.

Four local guard tests also pass: default HOLD and source-hash drift refuse before
export, duplicate BOM refs are rejected, and the native proof is stable without
source writes. `waiver-inventory.json` records empty DRC/ERC exclusion lists,
six inherited DRC ignores and four inherited ERC ignores with exact unchanged
project hash; no newly ignored check. `production-proof.json` verifies matched
source/tool/output hashes, all 13 ZIP/loose/mirror members, exact BOM/native fields,
unchanged 55-ref CPL content (shared-exporter CRLF-to-LF normalization only), manual inventory, raw catalog hashes and honest audit HOLD.
