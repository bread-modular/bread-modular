# Read-only JLCPCB catalog, assembly audit and passive alternatives

Use this **common tool first**, before 16bit-5v / 32bit-5v design edits. Python
3.8+, standard library only; catalog/CSV use needs no KiCad installation. Native
PCB/XML parsing reuses `export.py`. These tools never export, modify designs,
refill boards, upload files, authenticate, reserve stock or place orders.

## Branch handoff / integration boundary

Apply the common tooling/skill commit to each worker's **isolated worktree** via
the orchestrator before design work. Run the same commands below from either
branch's repository root; no module names or checkout paths are hard-coded.
Do not switch/edit the shared main checkout or run another worker's board job.

The main-based integration preserves checkpoint `7ae0192`'s `export.py`,
`add_production_files.py`, their tests and assembly-datum documentation unchanged.
Use the wrapper's actual `--help` / [README workflow](README.md#repository-production-files-add_production_filespy)
for production regeneration and mirrors. `assembly.py` consumes its existing
exporter BOM/CPL/report without replacing that workflow. Tooling verification
uses a fresh temporary `--jlcpcb-root`; no automatic schematic/PCB changes or
implicit production writes.

## Exact CLI commands

From repository root (replace illustrative paths/quantities with your files):

```sh
# Exact code lookup; optional dated raw snapshots outside the repository.
python3 -B opt/kicad-jlcpcb/assembly.py lookup C25804 \
  --strict-live --max-requests 1 --cache-dir /tmp/jlcpcb-catalog

# One page only, actual Basic filter after schema validation (NOT Preferred).
python3 -B opt/kicad-jlcpcb/assembly.py search '10k 0603' \
  --basic-only --limit 12 --strict-live --max-requests 1

# Exported grouped BOM, existing CPL, explicit circuit requirements.
python3 -B opt/kicad-jlcpcb/assembly.py audit \
  --bom /tmp/build/bom.csv --cpl /tmp/build/positions.csv \
  --export-report /tmp/build/export-report.json \
  --requirements /tmp/requirements.json --boards 10 --side top --strict-live

# Native module audit includes all electrical footprints, even THT/bottom.
# Supply existing native KiCad XML netlist: no CLI is invoked by the auditor.
python3 -B opt/kicad-jlcpcb/assembly.py audit \
  --project-dir /path/to/isolated/project --board board.kicad_pcb \
  --symbols-xml /tmp/build/symbols.xml --cpl /tmp/build/positions.csv \
  --requirements /tmp/requirements.json --boards 10 --side top --strict-live

# Direct + up to two-part homogeneous series/parallel review candidates.
python3 -B opt/kicad-jlcpcb/assembly.py suggest --codes C25804 \
  --target opt/kicad-jlcpcb/examples/resistor-target.json \
  --boards 10 --max-parts 2 --strict-live

# Or one bounded search, allowing explicitly compatible alternative packages.
python3 -B opt/kicad-jlcpcb/assembly.py suggest --query '100nF' \
  --target opt/kicad-jlcpcb/examples/capacitor-target.json \
  --max-candidates 12 --max-parts 2 --strict-live

# Deliberate replay: preserves original timestamp; cannot pass --strict-live.
python3 -B opt/kicad-jlcpcb/assembly.py lookup C25804 \
  --offline --cache-dir /tmp/jlcpcb-catalog

python3 -B opt/kicad-jlcpcb/assembly.py audit --help
```

JSON is printed to stdout, diagnostics to stderr. Exit 1 means a failed/unknown
required gate or an invalid input. Exit 0 means **only** successful lookup/search
parsing, a limited catalog/requirements audit, or production of review
candidates respectively. **Every command reports `order_ready: false`.** Even
zero-stock/Extended parts can be looked up for investigation; they cannot pass
the R/C audit/planner gates. Search truncation is explicit, not a claim of an
exhaustive search. Suggestions are never automatic approvals.

Limits: one search page, 50 rows max; 32 network requests by default (configurable
1..64), exact code memoization, 15-second timeout (0.1..30), 2 MB response, no
retries/cache fallback. Planner default 12 candidates/2 parts/10 results;
maximum 16 candidates/3 parts/50 results; no mixed networks or zero-ohm math.
Stop at a blocker rather than launching catalog sweeps.

`--max-age-hours` defaults to 24. Stale evidence fails even replay audits;
`--strict-live` additionally rejects all offline/cache evidence. A fresh network
response does not guarantee available inventory after its retrieval instant.

## Python API (same modules, not a separate exporter)

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("opt/kicad-jlcpcb").resolve()))
from catalog import Catalog, load_json
from bom_audit import bom_components, board_components, audit_components
from passive_planner import suggest, equivalent, worst_case_interval

supplier = Catalog(timeout=15, max_requests=20)  # public read-only endpoint
part = supplier.lookup("C25804")
search = supplier.search("100nF", limit=12)
report = audit_components(
    bom_components("/tmp/build/bom.csv"), supplier,
    load_json("/tmp/requirements.json"), boards=10, side="top",
    cpl="/tmp/build/positions.csv",
    export_report=load_json("/tmp/build/export-report.json"), strict_live=True,
)
candidates = suggest([part], load_json(
    "opt/kicad-jlcpcb/examples/resistor-target.json"), boards=10, strict_live=True)
assert not report["order_ready"]
```

`CatalogError` and the existing `export.ExportError` signal invalid/ambiguous
input. `board_components(pcb, xml)` uses `read_board`, `read_xml_symbols`, native
field aliases and conflict checks. CSV audit uses the exporter's `read_csv`,
`indexed`, numeric validation and CPL headers. Caller-injected transports are
for fixture tests, not a way to turn historical evidence into live evidence.

## Requirements and provenance

`examples/` files are **illustrative circuit inputs, not module approvals**.
Copy and tailor them; the audit template has empty reviews deliberately and
cannot pass as-is. Root policy keys: `defaults`, `components` (per reference),
`verified_specs` (per exact C-code). Unknown policy references fail. Native
`JLCPCB Audit Requirements` fields may contain a JSON requirement object.
Sidecars fill missing facts; conflicting explicit native/per-reference facts
fail. Do not change values or LCSC fields only in CSVs.

The BOM value is authoritative. `LCSC` aliases and `MPN` remain separate; codes
must be canonical `C` plus positive digits (no URL, MPN, lowercase/leading zero).
Exact MPN and package must match. Only unambiguous standard imperial/metric chip
footprints are inferred (e.g. `R_0603_1608Metric`). Other land patterns require
an exact `package` plus a human-reviewed footprint and pin/pad mapping. An
explicit package cannot override a known incompatible chip footprint.

R requirements: `kind`, `tolerance_fraction`, `min_voltage_v`,
`operating_voltage_v`, `voltage_derating`, `min_power_w`,
`operating_current_a`, `power_derating`. Audit reads `value_si` from native/BOM
value; planner targets additionally need `value_si`, `compatible_packages`,
optionally `original_package`. Missing stress/rating requirements are unknown,
not assumed safe; circuit voltage/current limits are both conservatively checked.
An explicit datasheet `current_a` limit is also checked; provide
`current_derating` in (0,1] or that extra gate remains unknown.

C requirements: same value/tolerance/voltage keys plus `polarity` (`polar` or
`nonpolar`), `dielectrics` list, `min_effective_capacitance_f`, `max_esr_ohm`,
`max_esl_h`, `role`. Catalog name/MPN text is not a dielectric/polarity proof.
Temperature, bias, frequency, pulse/ripple limits, ESR stability windows and
regulator/decoupling role need circuit/datasheet review. The scalar calculations
are not a stability, AC impedance or thermal simulation.

Each assembled part requires `reviews.land_pattern`, `reviews.pin_mapping`,
`reviews.ratings`; capacitors also require `reviews.role`. Each review must have
`code`, `mpn`, `ref`, `footprint` matching the actual input plus HTTPS `source_url`,
UTC `retrieved_at_utc`, and a meaningful `note`. This is an explicit **human
attestation**, not an automated verification of the linked document. Do not
insert boilerplate notes to clear a gate. Reviews older than one year or future
reviews do not pass. Record actual pad roles, conditions and unresolved limits.
For nonpassive parts, optional `attribute_equals` compares exact catalog
attribute strings; no IC rating inference from a marketing name.

Supplemental datasheet facts for absent catalog specs have this shape:

```json
{
  "C123": {
    "mpn": "EXACT-MPN",
    "source_url": "https://manufacturer.example/datasheet.pdf",
    "retrieved_at_utc": "2026-10-05T00:00:00Z",
    "note": "EXAMPLE ONLY: document worst-case temperature, voltage, frequency and evidence bounds here",
    "specs": {
      "polarity": "nonpolar",
      "dc_bias_factor_min": 0.5,
      "bias_voltage_v": 5,
      "esr_ohm": 0.02,
      "esl_h": 0.000000001
    }
  }
}
```

Use the `verified_specs` map in audit policy or the map file with suggest
`--verified-specs`. Supported extra keys also include `value_si`,
`tolerance_fraction`, `voltage_v`, `power_w`, `dielectric`, `current_a`.
Supplemental facts must be exact-MPN-bound with source/timestamp/note;
conflicting catalog facts are errors, never silently overridden. Bias factors
are **reviewed worst-case bounds over the applied-voltage/temperature range**,
not typical nominal multipliers or an assumption that bias is monotonic.
Audit/planner reports retain the supplement evidence. ESR/ESL numbers likewise
need stated frequency/temperature conditions in the note and circuit review.

Manual installation requires `assembly: "manual"` and a reason. Native DNP,
BOM exclusion and CPL exclusion reasons are retained, and native audit has no
implicit SMD/THT/other-side filter. Manual/excluded refs must be absent from
both assembly CSVs. A CSV cannot reveal parts omitted before export: retain
`export-report.json` and reconcile with a native audit. Metadata mismatch is a
failure even for a manually installed part. No clean claim by hiding required
parts in exclusions. Existing exporter warnings are reported, not silently
waived (including its intentional general production-review warning).

Audit reports per-ref exact C-code/MPN/package/class, observed Economy flag,
stock against **aggregated placements × board quantity**, checks with distinct
`pass`/`fail`/`unknown`, unresolved requirements/reviews, exclusions/manual
reasons, source URL/UTC retrieval/request/hash/mode, and input-file SHA256s.
The stock comparison does **not** reserve parts or include unverified attrition,
reel/minimum assembly quantities. Observed minima/loss fields are retained but
remain manual order gates. Native XML is field/reference parity, not PCB
connectivity/netlist proof; full ERC/DRC/netlist parity is a separate skill gate.

## Observed supplier schema and official service evidence

Public read-only POST endpoint, successfully inspected directly:

`https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`

Request `{ "currentPage": 1, "pageSize": 20, "keyword": "C25804" }`;
response `code: 200`, `data.componentPageInfo.list`, integer `total`.
Fields observed: `componentCode`, `componentModelEn`,
`componentSpecificationEn`, `componentLibraryType`, `preferredComponentFlag`,
`stockCount`, `componentProductType`, and `attributes` entries
`attribute_name_en` / `attribute_value_name`. Native attributes supply passive
value/tolerance/power/voltage when explicitly available. Capacitor voltage accepts
exact `Voltage - Rated` and `Voltage Rating` keys; all present aliases must parse
to the same voltage. Conflicts reject the record; an unparseable alias withholds
voltage and adds a blocking issue. Missing voltage stays unknown, never inferred
from MPN/description; the resistor rating keys remain unchanged.

Frontend schema observed at **2026-10-05T04:51:32.467955Z**:
`https://jlcpcb.com/ssr/js/b1851ed7074a22a7e047.js`

```text
componentProductTypeOptions: [
  {value:0, label:"Economic and Standard"},
  {value:1, label:"Economic Only"},
  {value:2, label:"Standard Only"}
]
componentLibraryType == "base" -> Basic Part; "expand" -> Extended
preferredComponentFlag -> distinct preferred/promotional Extended status
```

Economy is parsed only from that explicit **per-part** product type: 0/1 true,
2 false, missing null/unknown. Basic uses `base`, independently of service flag;
`expand`+preferred is **Preferred Extended, NOT Basic**. A conflicting
Basic+preferred record blocks. Global `economicPart` counts, library names,
price/feeder fee, stock, `assemblyMode`, or a preferred badge are not proofs of
eligibility. Unknown numeric/library encodings fail closed. This is a dated
frontend observation, not a documented stable API contract: recheck on schema
changes; do not silently extend encodings.

Official capabilities page retrieved **2026-10-05T04:52:23Z**:
`https://jlcpcb.com/capabilities/pcb-assembly-capabilities`

The Economic column explicitly says **"Single sided placement (SMT/Thru-hole)"**.
It also lists restrictions for board layers/thickness/size/quantity,
color/finish/standard stack-up, minimum packages/pitch, and reflow temperature.
THT is not categorically forbidden; exact part/process support still needs
verification. Revisit the current official table and actual board quote options
before release; this auditor checks single selected CPL/native side, **not**
all board/process restrictions. Never extrapolate general capabilities to
approval of a specific connector/IC or from contradictory/merged table cells.

Live smoke captured **2026-10-05T05:04:05Z**: C25804 / 0603WAF1002T5E / 0603,
Basic, `componentProductType: 0`, public stock 29,841,132; parsed 10kΩ ±1%,
100mW, 75V. `tests/fixtures/catalog-C25804.json` contains the exact raw response,
request, endpoint, UTC retrieval time and SHA256. This is historical fixture
stock, **not** current/order-accepted availability. Missing product type is
unknown and blocks strict assembly audit, even when Basic is known.

HTTP/API errors, non-JSON/malformed/duplicate fields, wrong identity,
duplicate/truncated exact matches, unsupported encodings and missing required
fields cannot pass a strict audit. Cache snapshots retain original times and
hashes; a hash is an integrity aid, not a supplier signature. No authenticated
endpoints, credentials or anti-bot bypass are supported.

## Passive network calculations and limitations

```text
R series:   R_eq = sum(R_i)
R parallel: R_eq = 1 / sum(1/R_i)
C parallel: C_eq = sum(C_i)
C series:   C_eq = 1 / sum(1/C_i)

Tolerance: evaluate all-low and all-high endpoints (positive monotonic networks),
not RSS/statistical cancellation. Entire interval must fit the circuit interval.
Resistor: enumerate every tolerance corner with voltage-driven AND current-driven
limits; I_i, V_i, P_i = I_i^2 * R_i = V_i^2 / R_i checked against derated ratings.
Capacitor: each series member must survive the FULL applied voltage; never divide
voltage by member count or assume equal sharing. Effective C uses reviewed
bias lower bounds and low tolerance corner.
```

Prefer direct same-package Basic+Economy parts, then compatible common packages,
then few-part electrically safe networks. Rank by part count, original package,
component price and value error; routing impact is a qualitative review, not a
measurement. Price excludes feeder/assembly/attrition/shipping costs.

Capacitor series additionally requires leakage/balancing/startup/transient,
polarity/reverse-voltage and ripple review. Scalar series ESR/ESL sums are only
simple bounds; **parallel ESR/ESL frequency response is not inferred**. Every
capacitor combination has role/impedance/ripple/layout review unresolved;
regulator compensation may require both minimum and maximum ESR. Uncertain
parts/networks remain `review_candidate`, never automatic edits or approvals.
No Basic alternative? Report the blocker; never silently use Preferred Extended.

## Tests and scope

Verification in the isolated common-tool workspace: unit/fixture/exporter
suite and two synthetic real-KiCad integration tests passed. A further live
planner smoke at **2026-10-05T05:17:04Z** returned a direct C25804
`review_candidate`, `order_ready: false` (same public endpoint above).
No module/base or production files were written, no advisor was invoked,
and no wrapper/exporter edits were included.

```sh
python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
# Real exporter integration using synthetic temp boards only; no module writes:
KICAD_JLCPCB_INTEGRATION=1 PYTHONPATH=opt/kicad-jlcpcb/tests \
  python3 -B -m unittest -v \
  test_export.KiCadIntegrationTests.test_native_fields_exclusions_mixed_sides_and_nonzero_origin \
  test_export.KiCadIntegrationTests.test_repeated_hierarchical_sheet_part_numbers
```

The suite covers dated raw schema replay, missing/unknown/malformed fields,
zero stock, Preferred/Extended rejection, API/HTTP errors, stale/offline evidence,
invalid codes, cache integrity, metadata/MPN/value/package conflicts, matched
BOM/CPL and manual policies, all four network equations, tolerance and stress,
capacitor sharing/bias unknowns, bounds and CLI/API behavior. The original
common-tool verification did not run repository/base board integration.

### Combined main-based handoff regression

```sh
# Exactly one real base export through the preserved wrapper, temporary root only:
KICAD_JLCPCB_INTEGRATION=1 PYTHONPATH=opt/kicad-jlcpcb/tests \
  python3 -B -m unittest -v \
  test_shared_handoff.BaseHandoffIntegration.test_real_base_export_and_fail_closed_offline_audit
```

This regression uses the actual exported BOM metadata, CPL and source report;
checks source hashes, checkpoint BOM/CPL bytes, J5's datum and Gerber mirrors;
and confirms all source/production files remain unchanged. Audit replay uses
only `tests/fixtures/catalog-C25744.json`, with **zero network calls**, and must
return exit 1 / `order_ready: false`: unknown ratings/reviews, unavailable live
catalog data and exporter warnings are not approvals. This exact R58/R59 source
BOM code/MPN was captured with **one bounded public lookup** at
`2026-10-05T05:28:38Z`; its unchanged raw response, request and hash are retained.
The earlier C25804 fixture is not a base BOM part and is not substituted into
base metadata. Neither snapshot is current inventory/order acceptance. CLI examples in this
document and the skill are parsed by the combined unit suite without execution.
Basic/Preferred Extended and Economy true/false/unknown gates are unchanged.

For complete design/production release gates, read the discoverable
[assembly skill](../../.agents/skills/jlcpcb-assembly/SKILL.md).
