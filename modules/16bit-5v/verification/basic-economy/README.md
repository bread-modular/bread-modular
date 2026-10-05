# 16bit-5v Basic/Economy sourcing — partial implementation, HOLD

## Scope and authority

Sol Max only; advisor OFF, no delegation. Focused continuation in workspace 291 /
`okbrain/bread-modular-kicad/291-5d2e00a7`, originating at `16bit-5v`
`1e50e798d68e3d8d3167fb5fb47bdcb7ee436b83`. All changes remain **uncommitted
and unstaged**. No main/other-worktree changes, base-design imports, merge,
push, authentication, upload or order. Read-only handoff hashes and original
native schematic/PCB/project hashes are in `baseline-provenance.json`. Workspace
288 remains the untouched backup: its scoped binary diff and all 207 scoped
untracked paths were imported with symlinks/modes preserved; import hashes are
in `focused-import-provenance.json`. No other module/history/cache was imported.

Common tools/skill were imported BEFORE native edits from
`f43184a620aee47aec456241646d008fb4a65bda`; only catalog.py, ASSEMBLY.md,
tests/test_catalog_voltage.py and its fixture were imported from
`4a77e133af1f1da80b8aed1bf03a5b550f8448d3`. Explicit observed voltage aliases
are handled by that common fix, with ambiguity/conflict fail-closed tests.
No branch-private catalog voltage parsing/supplement or exporter is used.
See the [shared skill](../../../../.agents/skills/jlcpcb-assembly/SKILL.md) and
[common CLI/API](../../../../opt/kicad-jlcpcb/ASSEMBLY.md).

## Native direct assignments

There were 43 assembled R/C without recorded native ratings, 56 top SMD and
62 physical refs. **41/43 R/C now carry actual Basic+Economy codes, including five exact supplier
review candidates on application HOLD. R7/R8 remain unassigned.**
All successful allocations preserve a single existing part, its nominal value,
footprint, pad mapping, location, copper and circuitry. Blank old codes are
shown as `unassigned`, not an invented historical purchase choice. Existing
C25/C26/C27 codes are retained. Native lowercase `f` units on selected C1/C5,
C20/C21/C22/C23 were corrected to SI `F` in BOTH schematic and PCB without changing
capacitance. Required tolerances were not recorded initially; selected tolerances
are explicit below, not represented as previously approved requirements.

| Refs | Value | Old → new exact code | Exact MPN | Retained footprint/package | Recorded ratings |
|---|---|---|---|---|---|
| C1, C2, C5, C8, C11–C18, C24 | 100nF | unassigned → C1525 | CL05B104KO5NNNC | C_0402_1005Metric | 16V, X7R, ±10%, nonpolar |
| C26 | 100nF | C1525 → C1525 | CL05B104KO5NNNC | C_0402_1005Metric | 16V, X7R, ±10%, nonpolar |
| C3, C4 | 15pF | unassigned → C1548 | 0402CG150J500NT | C_0402_1005Metric | 50V, C0G, ±5%, nonpolar |
| C22, C23 | 10nF | unassigned → C15195 | CL05B103KB5NNNC | C_0402_1005Metric | 50V, X7R, ±10%, nonpolar |
| C20 | 10nF | unassigned → C1710 | CL21B103KBANNNC | C_0805_2012Metric | 50V, X7R, ±10%, nonpolar |
| C19 | 10uF | unassigned → C15850 | CL21A106KAYNNNE | C_0805_2012Metric | 25V, X5R, ±10%, nonpolar |
| C25 | 10uF | C15850 → C15850 | CL21A106KAYNNNE | C_0805_2012Metric | 25V, X5R, ±10%, nonpolar |
| C27 | 1uF | C28323 → C28323 | CL21B105KBFNNNE | C_0805_2012Metric | 50V, X7R, ±10%, nonpolar |
| C6, C7, C9, C10 | 4.7uF | unassigned → C23733 | CL05A475MP5NRNC | retained 0402 (C6/C7 small-pad native footprint) | 10V, X5R, ±20%, nonpolar; **review candidate/HOLD** |
| C21 | 100uF | unassigned → C15008 | CL31A107MQHNNNE | retained C_1206_3216Metric | 6.3V, X5R, ±20%, nonpolar; **review candidate/HOLD** |
| R2, R4, R6, R9, R17, R18 | 1k | unassigned → C11702 | 0402WGF1001TCE | R_0402_1005Metric | 50V maximum, 62.5mW, ±1% |
| R3, R11 | 5.1k | unassigned → C23186 | 0603WAF5101T5E | R_0603_1608Metric | 75V maximum, 100mW, ±1% |
| R5 | 33 ohm | unassigned → C25105 | 0402WGF330JTCE | R_0402_1005Metric | 50V maximum, 62.5mW, ±1% |
| R10, R12, R15, R16 | 100k | unassigned → C25741 | 0402WGF1003TCE | R_0402_1005Metric | 50V maximum, 62.5mW, ±1% |
| R14 | 10k | unassigned → C25744 | 0402WGF1002TCE | R_0402_1005Metric | 50V maximum, 62.5mW, ±1% |

These are **nominal/rating allocations, not fabricated guaranteed effective-C,
ESR/ESL or human approval attestations**. Exact metadata is in
`native-sourcing-plan.json`. A failed conservative ratings/reviews audit is still
a genuine HOLD; nominal Basic/catalog success is reported separately.

Known nonpassive exact-code allocations (same circuit/physical footprints):
U1 C42411118/RP2350A, U2 C97521/W25Q128JVSIQ, U3 C116706/MCP6002-I/SN,
U4 C92004/PT8211-S, U6 retained C51118/AP2112K-3.3TRG1,
L1 C42411119/AOTA-B201610S3R3-101-T,
SW1/SW2/SW3 C92589/K2-1808SN-A4SW-01,
Y1 C20625731/ABM8-272-T3 and J5 C165948/TYPE-C-31-M-12.
All nonpassive Extended classifications remain visible; U2 is Basic. Exact
identity/pad/process/ratings/placement-preview human reviews are not inferred
from an MPN or package string.

## Actual application review and exact STOPs

- **Rails:** +5V input feeds AP2112 U6; +3V3 supplies ICs; the RP2350 buck creates
  +1V1 DVDD. Native netlist identifies C6 as local VREG_VIN, C7 as buck output,
  C9 as VREG_AVDD filter after R5, and C10 as additional 1V1 decoupling. Local
  capacitors/PGND return/LX route and all individual HF bypass loops are retained.
  Requirements use nominal 1.1V, a conservative 3.366V regulated rail ceiling
  (3.3V +2%), and 5.25V normal input boundary. Firmware boost, actual supply range,
  ambient/component temperature and external CV/AIN/surge limits still need
  confirmation; these are not measured operating limits.
- **C6/C7/C9/C10 application HOLD:** saved Basic+Economy C23733 is 4.7uF/10V/X5R/0402, ±20%.
  Samsung's exact-MPN characteristic sheet, visually reviewed, shows substantial
  DC-bias loss, especially at 3.3V; it explicitly calls its curves **typical design
  reference data**. It is not a guaranteed worst-case voltage/temperature bound.
  RP2350 hardware guidance requires particular local input/output/filter layout,
  4.7uF nominal and oriented L1; full regulator effective-C/ESR constraints were
  not established (the bounded primary datasheet request returned 403, no retry
  loop). No safe network or larger footprint is approved by nominal sums alone.
  Exact C23733/CL05A475MP5NRNC is now bound in BOTH native sources, explicitly
  labeled a supplier review candidate only. No known electrical contradiction
  or explicit effective-C minimum was established; unknown is not qualification.
- **C21 application HOLD:** saved Basic+Economy C15008 is nominal 100uF/6.3V/X5R/1206, ±20%.
  Manufacturer characteristic data show material DC-bias loss at 3.3V, not a
  guaranteed usable 100uF minimum. Intended effective bulk capacitance, ESR,
  temperature/aging/transient requirements remain unknown. No guessed parallel
  network or series voltage-sharing assertion was made. Exact
  C15008/CL31A107MQHNNNE is now natively bound as a supplier review candidate only;
  existing 1206 footprint/pads/copper retained.
- **R7/R8 STOP:** preserve native 27-ohm USB damping. Bounded 0402/0603/0805
  searches found Preferred Extended C25190/C17594, not actual Basic. Exact
  12+15-ohm series members (C270650/C25083 0402; C22791/C22810 0603) are
  Extended/Preferred Extended and rejected. Common planner tested the small
  available pool through three homogeneous parts and found no exact ±1% Basic
  candidate. The ±1% planning constraint is conservative because original native
  tolerance was absent; USB impedance/value tolerance must not be relaxed to
  force an approximate network. Two NEW bounded common-API searches proved
  C25092/0402WGF220JTCE (22 ohm, stock 4,597,296) and
  C25077/0402WGF100JTCE (10 ohm, stock 1,813,947), both Basic+Economy, 0402,
  ±1%, 62.5mW, maximum 50V. Exact mixed composition is
  `22 + (10 || 10) = 27 ohm`, worst-case 26.73–27.27 ohm. It is **not implemented**:
  USB operating/pulse/hot-corner bounds and collision-free near-chip branch/AC
  suitability are unproven. No route attempt/no-space claim. Shared scalar APIs
  compose all eight tolerance corners; limits are coefficients/conditional limits,
  not invented USB operating conditions. See `usb-mixed-review.json`. This is
  NOT an exhaustive/no-part-exists claim.
- **C25/C27 retained but regulator review HOLD:** Diodes AP2112 specifies testing
  and stability with 1uF ceramic, recommending X5R/X7R. C27's nominal tolerance
  low corner is 0.9uF even before bias/temperature, so the existing 1uF part alone
  cannot prove >=1uF effective local COUT. Remote C21 or a theoretical parallel
  total is not automatic local stability/ESR/layout proof. C25's existing 10uF
  input choice likewise has no manufactured guaranteed-bias/impedance bound.
- **Timing/filter roles:** C3/C4 keep equal 15pF C0G ±5% crystal loads and parasitic
  layout; no high-K timing substitution. C22/C23 retain equal 10nF shunts after
  1k audio resistors (nominal pole about 15.9kHz); bias/AC/temperature accuracy
  remains unqualified, rather than a claimed exact in-circuit pole. C20 retains
  nonpolar shield shunt/isolation topology; ESD/surge proof remains open.
- **Resistors:** manufacturer 0402/0603 table proves 62.5mW/100mW at <=70°C,
  with derating above 70°C. Working voltage is capped by BOTH maximum voltage
  AND sqrt(P*R), not simply the catalog 50V/75V maximum. Shared scalar checks use
  50% power and voltage budgets: 1k at 3.366V is <11.5mW at the 1% low corner,
  5.1k CC termination at 5.25V is <5.5mW, 10k rail pullup <1.15mW. External
  CV/AIN resistor stress limits are left unknown, not guessed from net names.
  R5's steady ~200uA/33-ohm filter current comes from Raspberry Pi guidance;
  startup can put the full rail across it (~0.35W initially). Uniroyal documents
  a five-second 2.5*RCWV short-time overload test, but repetitive pulse/drift and
  hot-corner approval are not inferred from it or a steady-state scalar PASS.
- **D1/U5 STOP:** generic LED and generic PSRAM (with inherited flash description
  and URL) do not prove exact device/color/polarity or memory/firmware intent.
  C125094/LTST-C190KGKT and C5333729/APS6404L-3SQR-SN live results are explicit
  investigation candidates only. Neither was silently installed or made manual.

Manufacturer URLs, UTC retrieval times, HTTP results and raw hashes are in
`manufacturer-evidence.json`; saved exact documents/curves are in `manufacturer/`.
`failed-fetches.json` also preserves the full RP2350 fetch's stored tool failure
(recorded call time only; no fabricated successful retrieval/body hash). Failed
fetches are not disguised as missing-negative proof. No voltage/bias/ESR
supplement or blanket human `reviews.*` was inserted to pass.

## Live catalog, quantity and audit boundary

Common `Catalog`/`audit_components`/`suggest` APIs only. No portal reversal or
retry loops. Searches are one bounded page, exact codes deduplicated; truncation
and failed exact queries remain explicit. C11702's short-code query was ambiguous:
a planned exact-MPN complete-page search must uniquely match BOTH C11702 and
0402WGF1001TCE; only that current in-process live result is memoized. No cache
record is relabeled live. Planner replay is explicitly `cache`/non-strict;
`planner-final-live.json` is a distinct dated live review-candidate record.

`catalog-final-exact.json` retains bounded live candidates and UTC/hash evidence.
`audit-final-native.json` and `audit-final-bom.json` are matched CURRENT native
and production-BOM audits using the common **offline** API against imported
dated raw evidence. This continuation reuses all 36 prior R/C assignments and
capacitor evidence; only TWO new supplier queries were made for the mixed USB
candidate. Original timestamps/hashes remain; replay is never labeled live.
The strict-live gate is retained and intentionally fails replay.
`live-supply-summary.json` (existing filename) is explicitly a dated-cache replay
summary: exact allocations/aggregated per-board stock/class/product type are
separate from current-live and application/manufacturing approval.

- Demand basis is **ONE board**, not an invented order size; requested quantity
  is null. Observed Economic/Standard product type 0 is independent of Basic.
- Four assembled identities remain unresolved (R7, R8, D1, U5); 52/56 codes are bound. Therefore no complete Basic,
  whole-board Economy, order-ready or fully verified maximum-board claim.
- PT8211 C92004 had only one stock unit in the bounded live candidate audit.
  Known-code maximum is only a **stock-only upper bound before attrition/minima**;
  final current numbers are in `live-supply-summary.json`. Full-board maximum is
  unknown until the missing parts are resolved. Observed loss/least-patch fields
  are retained, not assumed zero or accepted order quantities.
- Missing human reviews/bias/ESR/ESL/circuit limits and exporter warnings produce
  audit failure/HOLD. They are NOT a reason to weaken an audit, synthesize an
  attestation, substitute Preferred Extended, DNP or manual installation.

## Verification and guarded production

- Zone refill: pcbnew ZONE_FILLER + saved board, two filled net zones. Tracks,
  vias, lands, paste and footprint geometry compared exactly before save. The
  focused metadata-only continuation retains that exact saved fill/copper; no
  unnecessary refill/save or historical layout/finalization tool is replayed.
- Baseline/final DRC: zero errors, zero opens, zero schematic parity findings;
  75 inherited warnings. ERC: zero errors, 12 inherited warnings. No new
  exclusions, ignored checks or weakened project/severity settings. Not a
  zero-warning board. Baseline/final JSON artifacts retain all findings.
- `tools/verify_power.py` independently compares committed baseline geometry,
  native serialized routing/nets, every physical pad/net, metadata and the
  exported schematic pin graph. All 62 refs, 763 copper items and 237 functional
  pin memberships preserved; 52 sourcing/rating refs synchronized. **1339 checks**
  pass (46 additional exact metadata comparisons; no other guard weakened). Outline,
  two mounts, nine U1 thermal holes, manual connector alignment and J5 assembly
  datum unchanged. Guarded report: `connectivity-final.json`.
- Common unit/fixture tests: 103 total, 97 pass / six optional integration skips.
  Two synthetic real-KiCad integrations are separately run; no unrelated
  main-base integration or copied base module. Logs are retained.
- `tools/regenerate_production.py --review-preparation` is rebound to NEW
  `reviewed-source.json` (current workspace/branch/HEAD/source/evidence/common-tool
  hashes). Old historical finalizers are never run. It uses the existing common
  `add_production_files.py` wrapper/mirrors plus common `export.py` for the
  complete physical BOM; old private exporter is not invoked.
- Match 56 top SMD assembly BOM/CPL refs and 62 physical BOM/CPL refs, six explicit
  manual parts, all coordinates/rotations/datum offsets. Check ZIP integrity,
  nine Gerber + two drill members, all F.Cu/B.Cu, masks/paste/silks/outline, and
  byte-identical canonical/legacy/wrapper ZIP mirrors plus loose member hashes.
- All 11 current Gerber/drill member geometry byte streams equal the committed
  routed release after removing ONLY creation-date comments; current CPL and the
  explicit manual CSV are byte-identical to baseline. This is not human CAM
  process approval. Artifact: `gerber-baseline-geometry-parity.json`.
- Twelve in-memory negative guard tests (workspace, branch, HEAD, source,
  evidence and common-tool binding on BOTH guarded module tools) fail before
  output/network work; protected source/production hashes remain unchanged.
- Module-local `.gitignore` exposes only this module's matched `jlcpcb/` wrapper
  outputs for untracked/unstaged native diff review; other modules' policy is
  unchanged. No generated mirror is silently absent from review.
- `production/manifest.json` pins input/output hashes,
  tool/source provenance, quantities, electrical/audit results and unresolved
  gates. Public catalog evidence is not reservation/order acceptance.
  Authenticated preview/order, manufacturing/physical clearance and bench
  validation remain manual HOLDs.

Run from the assigned workspace root only:

```sh
python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
/usr/bin/python3 -B modules/16bit-5v/tools/verify_power.py
/usr/bin/python3 -B modules/16bit-5v/tools/regenerate_production.py --review-preparation
```

Focused production regeneration replays dated common-API evidence (strict-live
fails honestly), with new plot timestamps and NO supplier requests; source edits/new commits/workspaces require an explicitly new
review binding, not disabling guards. Gerber ZIP hashes are date-sensitive,
whereas same-source BOM/CPL are stable. Never use historical review/approval
claims to approve this unresolved revision.
