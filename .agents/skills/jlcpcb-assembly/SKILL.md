---
name: jlcpcb-assembly
description: Common-tool-first JLCPCB Basic/Economy sourcing, read-only BOM audits, conservative passive alternatives and honest KiCad assembly release gates across isolated branches.
---

# JLCPCB assembly: common tools before design edits

## Scope and safety

Use for any Bread Modular KiCad/assembly sourcing task, especially the 16bit-5v
and 32bit-5v branches. Read [tool commands/API/policy and dated supplier
schema evidence](../../../opt/kicad-jlcpcb/ASSEMBLY.md) and the
[existing exporter README](../../../opt/kicad-jlcpcb/README.md) first.

Work only in the assigned isolated worktree. Never switch branches or change
files in another job's checkout. Common tooling/skill commits must be made
available to both workers **before** module design edits. The orchestrator
integrates them; do not merge or duplicate the tooling yourself. If a separate
job owns exporter/production-wrapper changes, leave those files alone and
consume their resulting interface after integration. Do not recreate a missing
`add_production_files.py` from memory or fork another exporter.

Do not invoke other-model agents when the user requires Sol Max only. If the
user disables advisors, do not delegate review. Do not commit without explicit
permission; when authorized, stage only the scoped files and provide commit IDs.
No automated orders, purchases, authenticated API calls, design uploads or
credentials. Public catalog lookup is read-only. JLC preview/order signoff is
manual/user-controlled and must not be claimed done by this tooling.

## Mandatory sourcing gates

- Every JLC-assembled R/C must be **actual JLCPCB Basic** AND explicitly observed
  **Economic/Economy PCBA eligible**, independently. Preferred/promotional
  Extended is still Extended, never Basic. No silent relaxation.
- Audit **every other assembled part** too: exact C-code and MPN, package/land
  pattern, ratings/application, stock and part/service/process eligibility.
  Nonpassive Extended parts may be allowed only by the user's policy and only
  with explicit service evidence; do not hide their classification/fees.
- Use native LCSC/MPN/value/footprint metadata or the existing exported BOM/CPL.
  Do not source by descriptions alone or confuse an MPN with a catalog code.
- Keep supplier source URL, UTC retrieval timestamp, request and raw snapshot
  hash. Web stock is transient, not authenticated order acceptance/reservation.
  Check aggregated quantities per C-code: quantity per board × requested boards;
  separately recheck attrition/minimum assembly/reel and order rules.
- Parse the **observed schema**, not a badge/name or global search count. The
  public adapter has separately observed library and per-part product-type
  fields; missing eligibility is **unknown**, not true and not false. Unknown
  schemas/malformed replies, HTTP/API failures, missing fields, invalid codes,
  ambiguity, stale/offline evidence fail required live gates.
- Cache/raw snapshots are dated replay evidence, never fresh/live. Use
  `--strict-live` for assembly checks. No automatic offline fallback, retries,
  anti-bot bypass or bulk portal reversal. Search bounds are deliberate. Stop
  and report genuine unknowns/blockers instead of expensive research loops.
- Exclusions/DNP/manual assembly need reference-specific reasons, kept out of
  **both** assembly BOM and CPL and listed for the user. Do not silently omit a
  required THT/bottom-side part via the exporter's SMD/side default.

## Common-tool-first sequence

Run from each isolated branch's repository root after the common commit lands:

```sh
python3 -B opt/kicad-jlcpcb/assembly.py lookup C25804 --strict-live --max-requests 1
python3 -B opt/kicad-jlcpcb/assembly.py search '10k 0603' --basic-only --limit 12 --strict-live
python3 -B opt/kicad-jlcpcb/assembly.py audit \
  --bom /tmp/build/bom.csv --cpl /tmp/build/positions.csv \
  --export-report /tmp/build/export-report.json \
  --requirements /tmp/requirements.json --boards 10 --side top --strict-live
python3 -B opt/kicad-jlcpcb/assembly.py suggest --codes C25804 \
  --target opt/kicad-jlcpcb/examples/resistor-target.json --boards 10 --max-parts 2 --strict-live
```

Examples are illustrative, not approvals. For native board/reference/field
parity, also use `audit --project-dir ... --board ... --symbols-xml ... --cpl ...`.
The auditor uses `export.py` parsers; it invokes no KiCad CLI and writes no
production/design files. It supports either branch without module-specific
logic. Python callers can import `Catalog`, `audit_components`, `suggest` as
documented in `ASSEMBLY.md`. Run focused unit tests and existing exporter tests
before distribution; re-run after exporter/wrapper integration.

Use the existing `export.py` for Gerbers/BOM/CPL, and integrated
`add_production_files.py` for the module production/mirror workflow. Read that
wrapper's actual README/`--help`; do not infer its arguments from another job.
During tooling-only work, do not regenerate board outputs at all.

## Electrically constrained alternatives (planning only)

Try direct Basic+Economy parts with the existing land pattern first; search
explicitly compatible common alternative footprints if none is suitable. Then
consider few-part series/parallel networks, bounded to small candidate pools.
Prefer few parts, common footprint, low cost and low routing impact. No
sourcing tool automatically changes schematics/PCBs or approves alternatives.

```text
R series:   R_eq = sum(R_i)
R parallel: R_eq = 1 / sum(1/R_i)
C parallel: C_eq = sum(C_i)
C series:   C_eq = 1 / sum(1/C_i)
```

Check the **entire** worst-case tolerance interval (not RSS or cancellation).
For resistors enumerate tolerance corners under voltage- and current-driven
limits; check each member's V, I and `P = I^2 * R = V^2 / R`, rated working
voltage/power and temperature/pulse derating. Do not assume average power or
nominal sharing is safe. Missing circuit stress/rating requirements block an
assembly audit; uncertain networks are review candidates only.

For capacitors preserve rated voltage, polarity/reverse voltage, dielectric,
worst-case DC-bias effective capacitance over voltage/temperature, ESR/ESL,
ripple, frequency and regulator/decoupling/compensation role. Nominal summed C
is not effective C. A regulator may require an ESR window, not merely low ESR.
Parallel ESR/ESL cannot be approved from simple DC reciprocal formulas; layout
inductance, antiresonance and frequency response need review.

**Never assume capacitor-series voltage sharing.** The planner checks each
member against the FULL applied voltage; leakage/tolerance/balancing and
startup/transient conditions still require review. Polarized networks require
orientation/reverse-stress review. Scalar capacitance math is not a balancing,
thermal or stability simulation. Store exact-MPN-bound reviewed datasheet/bias
facts with real source/timestamp/conditions, never guessed characteristic
curves. If no safe Basic alternative exists, explicitly report that blocker.

## Native metadata and implementation gates (only after authorization)

Record the approved electrical requirements, exact C-code, exact MPN,
manufacturer, value/tolerance/rating and footprint in native symbols. Update
PCB from schematic and synchronize native fields; retain reference/net identity
and hierarchy. No CSV-only substitution or stale PCB metadata. The optional
native `JLCPCB Audit Requirements` JSON is circuit metadata, not a bypass for
catalog checks. Sidecars may fill missing facts but cannot contradict native
requirements/values. Missing MPN/rating/package facts remain unresolved.

After a footprint substitution:

- Inspect real manufacturer land pattern/dimensions, pin/pad numbers and roles,
  polarity/markings and assembly orientation. Matching package names alone are
  not enough; KiCad and catalog symbol conventions can differ (e.g. diode pad
  numbering, pot wiper, exposed pad).
- Preserve electrical net connections via actual pin/pad mapping; do not copy
  rotations blindly. Reroute affected traces/vias, replace obsolete copper,
  reconsider placement/courtyards/paste/soldermask and keepouts. Verify rail
  polarity and any regulator or high-speed/decoupling routing role.
- Preserve physical footprint anchors/pads. Use supported **native** assembly
  datum/position/rotation fields only when a supplier placement mismatch is
  verified, synchronize schematic and PCB, then use the common exporter. Do
  not move PCB anchors to fake CPL alignment or hand-edit exported centroids.
- Refill all zones and save. Run ERC, DRC, unconnected checks and independent
  schematic↔PCB netlist parity. Reference/field parity in the auditor is **not**
  netlist-connectivity verification. Compare baseline and final connectivity.
- Keep honest existing waivers: reference/rule/severity, rationale, baseline
  count and remaining count. Do not say "DRC clean" while hiding violations,
  exclusions or legacy unconnected nets. No new waiver without explicit review.

Human reviews in audit policy are exact-code/MPN/ref/footprint-bound
attestations with source/timestamp/note, not automated document validation.
Do not fill placeholder blanket "checked" notes to make the audit green.
Land-pattern, pin mapping and ratings reviews are required for all assembled
parts; capacitors additionally require role/impedance review. Check actual
operating conditions for other parts (ICs, diodes, inductors, connectors, etc.).

## Production and service gates

Economic single-side restriction was explicitly observed at official
`https://jlcpcb.com/capabilities/pcb-assembly-capabilities` at
**2026-10-05T04:52:23Z**: Economic column says
**"Single sided placement (SMT/Thru-hole)"**. Recheck the current official page
and live board options before release; service capabilities can change.
Verify layers, thickness, dimensions, quantity, finish/color/stackup, minimum
package/pitch, castellations/gold fingers/edge plating, reflow and exact
THT/part/process support against current official evidence. Do not infer
Economic support from Basic/preferred status or general assembly marketing.
If required options cannot be proven, record **unknown** and block order-ready.
Manual parts may be on another side only by explicit plan; JLC-assembled parts
must all be on the one selected side and supported by that process.

Use one matched source snapshot and common origin/units/top-view convention for
BOM/CPL. Exactly equal reference sets; grouped quantities must equal listed
refs. Validate native side, all coordinates/rotations and verified datum offsets.
Reconcile omitted/manual refs with native BOM/PCB and export exclusions.

Gerber ZIP must contain **all enabled copper layers**, masks, silkscreen,
paste/outline as appropriate and PTH/NPTH drills with consistent origin. Single
assembly side must not discard bottom/inner copper. Inspect every copper layer,
zone fill, slots/drills, outline and paste in a viewer; no stale plots mixed
with current files. Use the common exporter rather than a one-side copper hack.

Keep a production manifest: source commit/worktree, source SHA256s, generated
Gerber ZIP/BOM/CPL/report hashes, generation commands/tool version, copper layer
count, side/origin/units, requested quantity, manual/excluded refs, ERC/DRC/
netlist/refill artifacts and honest waivers, catalog/review evidence times,
unresolved gates and manual release approval. Keep production/mirror outputs
matched via the existing wrapper; verify hash equality rather than copying
unrelated historical files. Do not claim that exporter/auditor automatically
produces or validates all these manifest/signoff gates.

Immediately before a user-controlled order: recheck stock, classification,
Economy support and actual quantity/attrition, actual parts matched to C-codes,
centroids/rotations/pin 1/polarity on every JLC preview placement, BOM/CPL/Gerber
snapshot consistency and manufacturing options. Manual authenticated preview
and supplier/order acceptance are separate final gates. This tool does none of
those authenticated actions. A public stock count or passing audit is never
an order-ready claim.

## Completion report

Report changed tooling/skill/docs paths, exact CLI/API handoff, tests actually
run (and skipped), dated live evidence, explicit unknowns/limitations and scoped
commit IDs. No board edits before common-tool integration/authorization. Never
claim "Basic", "Economy supported", "DRC clean" or "order-ready" when the
corresponding independent gate remains unknown or failed.
