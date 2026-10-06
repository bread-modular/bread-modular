# Scoped verification and handoff

## Final bounded integration — main `9291e420`, isolated workspace 302

Source, physically relocated/re-bundled suites and actual CLI handoffs passed. No delegation/advisors, released input, frozen module
migration, real manufacturing export, global install, commit/merge/push or other
worker-workspace access. Installed Linux x86_64 / Python 3.14.4 / KiCad CLI +
pcbnew 10.0.6 / Bubblewrap 0.11.1. Older versions/platforms were not tested.

### Current source results (separate processes)

| Suite | Run | Pass | Skip | Failure/error |
| --- | ---: | ---: | ---: | ---: |
| Core default (50 existing + 5 facade/payload regressions) | 55 | 53 | 2 native opt-in | 0 |
| Core native | 55 | 55 | 0 | 0 |
| PCB automation unit / native | 13 / 13 | 13 / 13 | 0 | 0 |
| Schematic (15 unit + 12 native) | 27 | 27 | 0 | 0 |
| Router unit (75 existing + same-nickname regression) / native | 76 / 15 | 76 / 15 | 0 | 0 |
| Shared canonical / legacy, each | 103 | 97 | 6 native opt-in | 0 |
| Explicit real facade PCB→router + schematic handoff | 1 runner, 2 workflows | passed | 0 | 0 |

Exact commands (repository root; unset shared native opt-in for **all discovery**):

```sh
unset KICAD_JLCPCB_INTEGRATION PYTHONPATH
python3 -B -m unittest discover -s opt/kicad-tools/tests -v
KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/automation/tests -p test_unit.py -v
KICAD_AUTOMATION_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/automation/tests -p test_native.py -v
KICAD_SCHEMATIC_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/schematic/tests -v
python3 -B -m unittest discover -s opt/kicad-routing/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/jlcpcb/tests -v
python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
python3 -B opt/kicad-routing/run.py prepare-runtime --allow-downloads
python3 -B opt/kicad-routing/tests/native_project_checks.py --run-prefix final302-src3
python3 -B opt/kicad-tools/tests/native_handoff.py --run-id final302-handoff3
```

Core native tests invoke ONLY
`KiCadIntegrationTests.test_native_fields_exclusions_mixed_sides_and_nonzero_origin`
and `KiCadIntegrationTests.test_repeated_hierarchical_sheet_part_numbers`, through
canonical and legacy paths (4 nested synthetic passes per core-native run).
Shared all-native discovery includes released boards and was **never enabled**.

### Real cross-component proof and narrow fixes

The independent routing generator creates Orchard Controller with opposite-side
SMDs, a real local symbol/footprint context, locked **and unlocked** SENSITIVE
copper. Facade inspect/plan/apply moves J2 `[34,10]` → `[33,11]` and adds non-copper
text. Original copper UUID/geometry/lock records stay identical: moves do not drag traces.
Explicit `--allow-draft-opens` gives exit 1 / `draft` / `accepted: false` with a
hash-bound completion marker, no ERC findings and equal ref/pin/net parity.
Its **complete `inputs/` subtree**, unchanged by hand, is the actual router
snapshot; CLI derives the fresh DATA net plan then dry-run and offline apply.
Final native DRC violations / schematic parity / opens = **0 / 0 / 0**, one real
DATA through-via, invariant deltas `[]`, original and handoff sources immutable,
locked/non-authorized copper and placements/settings protected.

First handoff correctly rejected the generator's off-grid pins/missing symbol
context. Fix: generate on-grid pins and matching symbol library/table at source,
not hand-repair the generated input or waive ERC. That exposed symbol and
footprint nickname shadowing in router admission. Fix: validate both URI closures,
resolve PCB FPIDs only through the footprint table. One unit regression covers
same nicknames with bounded relative/`${KIPRJMOD}` URIs and proves missing
footprints still fail. Existing 75 unit + 15 native routing gates still pass.
Current help/doctor reports ordinary supported routing; historical smoke evidence
is retained, not rewritten as a general-board claim.

Separate schematic facade inspect/plan/apply adds an actual wire, verifies changed
pin/net identities and native force-save/reload, and honestly returns
`draft_erc_findings`, exit 1, `accepted: false`. An unrelated input PCB sentinel
is neither read/copied nor changed: no silent PCB synchronization claim. Both
real Python APIs also inspect these fixtures from an unrelated cwd in a fresh
process. Standalone/facade help, JSON, exact nonzero stdout/stderr/return codes,
missing optional controllers and subprocess module isolation have regressions.

Runtime preparation used only the explicit existing downloader in this workspace:
Freerouting SHA-256 `f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7`;
JRE SHA-256 `1731a34baadec5479258ea0202e4d5d865d2efeee60cb0c7d7eb056fe96ca219`.
Trusted metadata/checksums matched; preparation executed **nothing**. Java routing
runs only inside offline Bubblewrap. Runtime/JAR/work/logs never enter bundles.
Native PROPERTY_ENUM and read-only lock diagnostics remain retained in raw logs.

Evidence is local and ignored: `.integration.tmp/suites-source-final.json`,
`opt/kicad-tools/integration.tmp/final302-handoff3/summary.json` and full hashed
command logs; router `work.tmp/native-tests-final302-src3/summary.json` / runs.
The current runner and detailed [workflow/API](API.md) reproduce the proof.

### Completed relocation, exact payload and protected audit

All rows in the source table also passed from the **physically relocated and
re-bundled combined distribution**, separate processes, quoted absolute paths
and unrelated cwd; no original checkout/Git/modules tree was required. Copied
core native **55/55**, automation **13+13**, schematic **27** (12 native), router
**76+15**, shared canonical/legacy **97 pass + 6 skip each**, actual PCB→router
and schematic facade workflows all passed. Each core-native run also passed
both named synthetic shared methods through both paths, never all-native discovery.
Core-only default: **55 run / 51 pass / 4 intentional skips** (2 native opt-in,
2 optional-routing cases); missing route reports JSON exit 2, no installation.

The exact source commands above were repeated with absolute paths rooted at
`.integration.tmp/Rebundled Toolkit with spaces`, from
`.integration.tmp/Unrelated cwd with spaces`; router native prefix `final302-copy`,
handoff ID `final302-copyflow`. Pinned runtime was independently prepared there,
**inside this own workspace**, not copied from or accessed in another worker.
Exact argv/env/cwd/results live in `.integration.tmp/suites-copied.json`.

Bundles: **64 core / 87 combined regular files + exactly 3 validated relative
symlinks + schema-2 manifest**. All automation/schematic source/docs/tests,
router general source/new tests/detailed docs including SMOKE and exact compact
evidence are covered by literal allowlists. Physical relocation, unrelated-cwd
CLI/Python APIs, actual native suites, exact file/link hashes and identical
re-bundle manifests passed. No runtime/work/logs/arbitrary JSON or symlink
traversal permission. Unknown secrets/aliases stay excluded; unsafe/changed owned
links and sources fail. Final evidence refresh re-bundles source again; only
workflow/verification docs and expanded doc-link regression differ from the
full-suite tested copy, never native/assembly/business logic. Final core native
suites are re-run on source and that final copy; manifest integrity/re-bundling
are rechecked after the evidence refresh.

Protected tracked audit before/after: **2142 entries, zero changed/added/removed**:
1982 regular file SHA-256s, 153 literal symlink texts (no dereference), 7 gitlink
pins (not an inventory of untracked submodule contents). Designs/libraries/releases
and all non-owned tracked paths included. Both sorted manifests have SHA-256:
`651d496a093625bf784404d5a64ab564d99aa4b4a630e3ff04cc691097270cb7`.
Evidence: `.integration.tmp/{protected-before,protected-after,protected-audit}.json`.
All canonical JLCPCB source/docs/tests, core `native.py` / `project.py` and ALL
merged automation/schematic tracked files remain byte-identical. Router diff is
only its current doctor limit, fixture/ERC context, same-nickname resolution +
regression, and the fixture test-doc note. No settings/rules/scope gate relaxed.

Source handoff summary SHA-256: `b71ef4e0062f627067a08171af80ebc977278c26e029d95c586cba3734fa66d9`.
Copied handoff summary SHA-256: `495e7d98d7cb2728da2b6f88e1921fffa1f7e34abf9cd51750ef9f8e3d93a011`.
Both retain full command stdout/stderr hashes and original/snapshot inventories;
raw reports/logs/runtime stay ignored and out of the bundle. Early failing probes
remain local evidence; only the fresh successful IDs above are completion proofs.
Repeat native runners with NEW IDs; existing candidates/runs are never overwritten.

### Limits

Real geometry is not live GUI/IPC push-and-shove; no automatic placement, trace
drag, net inference or PCB synchronization. Supported flat schematic and ordinary
router subset only (groups/zones/complex rules reject). Acceptance is native
checks within scope, never electrical, physical, fabrication, release or order
approval. Historical evidence below records earlier capabilities, not current
limits. Tool hashes are provenance, not signatures/concurrent-writer security.

## Historical file consolidation — isolated main-based workspace 298

Scope: canonical files in `opt/kicad-tools`, three relative compatibility links,
facade/bundle/tests/docs and concise root/toolkit landing pages. Detailed content
is retained in [GUIDE.md](GUIDE.md), [BUNDLING.md](BUNDLING.md), JLCPCB docs and
both canonical skills. No advisors/delegation, board migrations, real-board
exports, routing implementation/runtime work, global installs, commits, merges
or pushes. The original checkout and unrelated `.history` dirt are not edited.
Observed local Python **3.14.4** and KiCad CLI **10.0.6**; older Python/platforms
were not executed. Historical verification sections below remain historical.

### Actual regression results

| Scope | Run | Passed | Skipped | Failures/errors |
| --- | ---: | ---: | ---: | ---: |
| Source toolkit default discovery | 50 | 48 | 2 native opt-in | 0 |
| Source toolkit `KICAD_TOOLS_INTEGRATION=1` (synthetic only) | 50 | 50 | 0 | 0 |
| Source shared suite, canonical and legacy paths (each) | 103 | 97 | 6 native opt-in | 0 |
| Relocated/rebundled core-only toolkit default | 50 | 47 | 2 native + 1 optional routing | 0 |
| Relocated/rebundled combined toolkit default | 50 | 48 | 2 native opt-in | 0 |
| Relocated/rebundled shared suite, canonical and legacy paths (each) | 103 | 97 | 6 native opt-in | 0 |

Source commands (separate processes, `KICAD_JLCPCB_INTEGRATION` unset for discovery):

```sh
python3 -B -m unittest discover -s opt/kicad-tools/tests -v
KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/jlcpcb/tests -v
python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
```

The toolkit native test explicitly invokes only the two named **synthetic**
shared methods for fields/exclusions/sides/nonzero origin and repeated hierarchy,
through both canonical and legacy paths (**4 nested passes**, no skips).
Never discover the shared suite with its native opt-in during tooling-only work;
that legacy switch also includes repository-board methods.

### Path, export and bundle checks

- `test_consolidation.py`: exact three links, canonical parser import, identical
  old/new/facade help, frozen-style sibling imports without executing frozen
  scripts, corrected wrapper root and synthetic-only module/sweep dry-runs.
- Link rejection: missing/directory-replaced/broken/retargeted/absolute/equivalent
  nonallowlisted/escaping aliases; symlinked canonical targets, skill ancestors,
  source files and roots. Unknown links/secret-like files are not copied.
  `regular()` still rejects even owned alias traversal; routing receives no new
  symlink exception. Mutation during copy fails and cleans only the new output.
- Core bundle: **40 regular payload files + 3 relative links + manifest**.
  Combined bundle: **50 regular payload files + 3 relative links + manifest**,
  using the unchanged reviewed routing allowlist. Schema **2** separately hashes
  canonical file bytes and UTF-8 link text. Exact inventory and every hash match.
- Physical relocation, re-bundling twice, spaces in distribution/output/cwd and
  no Git/`modules/`/original-checkout assumptions succeed. Combined re-bundle
  manifests match exactly; core payload/link hashes match even when source
  routing availability diagnostics change. Dry-run writes nothing; overwrite
  refusal is exit **2**. Current README/guide/skill links work from canonical and
  compatibility locations; routing/research remain explicitly optional.
- On a temporary non-Bread fixture, the re-bundled facade and direct canonical /
  legacy exporter produce byte-identical BOM/CPL and equal component/count/side/
  exclusion/warning/source-hash semantics; ZIP member sets validate. Gerber ZIP
  timestamps are intentionally not treated as byte-reproducible.
- Native checks retain expected restrictive-rule/open findings (exit **1**),
  equal ref/pin/net parity and unchanged fixture sources. No production readiness
  inferred. Optional routing is only bundled/help-tested; no downloads or smoke
  execution as part of this consolidation.

### Protected-file and byte-preservation audit

Before/after SHA-256 plus no-dereference link inventories cover **2315 protected
file/link entries**, including designs, local submodule libraries, frozen tools,
release/evidence and routing: **0 changed/added/removed**. The sole extra root
change is a narrow `.gitignore` exception for canonical tool sources previously
hidden by `**/jlcpcb/`; module outputs and bytecode remain ignored.

`export.py`, `assembly.py`, `catalog.py`, `bom_audit.py`, `passive_planner.py` match
the pre-move bytes/hashes. The entire wrapper matches its pre-move bytes except
exactly `REPO = HERE.parents[1]` → `REPO = HERE.parents[2]`. Tests/docs adjust root
and canonical paths. Frozen hash manifests are not refreshed or executed: path
compatibility does not assert unchanged hashes for revised wrapper/docs/tests.
Git whitespace/scope checks pass; changes remain uncommitted for parent diff.

Host-local evidence: `/tmp/kicad-consolidation-298-wjrfaarp/` contains baseline,
protected hash audit, portable-proof JSON and copied-suite logs. These are
execution evidence, not bundle payload. Symlinks must be preserved when copying;
no hostile concurrent-writer security guarantee, full installation provenance,
new editing API or electrical/release/order approval is claimed.

## Historical post-merge combined verification — main `55e8a204`, workspace 297

Synthetic-only integration, isolated workspace 297; no advisors/subagents,
other jobs/projects, frozen migration execution, released-board tests/exports,
commits, pushes or merges. Observed Linux x86_64, Python 3.14.4, KiCad CLI/system
`pcbnew` 10.0.6, Bubblewrap 0.11.1. Routing separately requires Python **3.9+**
(`Path.is_relative_to`), this exact native binding/platform and Bubblewrap;
core Python 3.8+ support does not imply a routing runtime on that interpreter.
No older Python or other platform was executed.

### Exact suites (separate processes; no generic-module import collisions)

| Scope | Run | Passed | Skipped | Failures/errors |
| --- | ---: | ---: | ---: | ---: |
| `KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v` | 37 | 37 | 0 | 0 |
| `python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v` | 103 | 97 | 6 | 0 |
| `python3 -B -m unittest discover -s opt/kicad-routing/tests -v` | 32 | 32 | 0 | 0 |
| Shared two explicit native synthetic methods (command retained below) | 2 | 2 | 0 | 0 |
| Routing suite from unrelated relocated bundle/cwd | 32 | 32 | 0 | 0 |
| Final relocated combined core default suite | 37 | 35 | 2 | 0 |
| Final relocated intentionally core-only default suite | 37 | 34 | 3 | 0 |

The added core test covers the **real** reviewed routing payload, hashes, unchanged
correct `../../docs/kicad-routing-research.md` link, evidence link, imported
`route --help`, complete-contract requirement and re-bundling a supplied
contract. Unreviewed Python, arbitrary JSON and runtime paths are rejected.
The formerly absent-sibling test now creates an explicitly core-only source;
no assumption that routing is absent on merged main. The real routing regression
is skipped only when running an intentionally core-only distribution.

### Relocation / combined native smoke

A new unrelated directory with spaces received **47 allowlisted payload files +
manifest**. All hashes and the exact on-disk inventory matched; no Git, checkout,
Bread project/name convention, binaries, vendor, history or secrets were needed.
Re-bundling that distribution preserved every payload hash, even after its own
local runtime/work files existed: none were installed in the next bundle.
Source and relocated real `route --help`/`doctor` succeeded; missing-runtime
`smoke` failed closed (exit 1), creating no native fixture or runtime/download.
Bundle/check dry-runs wrote nothing. Bundle/check overwrite refusal remained
exit 2; shared-export refusal remained its unchanged exit 1.

From an unrelated cwd, the relocated facade's `doctor`, `check` and `export`
ran on a non-Bread temporary project. Check exit 1 was **expected findings**:
ERC 1 warning, DRC 2 edge-clearance violations + 1 open, parity 0; source
unchanged, exact XML/PCB parity, no operational errors. Export exit 0: 2
components, 1 BOM row, valid Gerber ZIP/BOM/CPL. No released artifacts exported.

Only the relocated scratch bundle performed one authorized
`route prepare-runtime --allow-downloads`, through unchanged pinned acquisition
code: exact Freerouting 2.5.0 / Temurin 25.0.4.1+1 URL/SHA pairs, verified metadata,
184 notice files; **no Java during preparation**, no global install/PATH change.
Doctor revalidated bytes; another prepare refused overwrite without download.
Its real facade `route smoke --run-id combined-relocated --route-timeout 120`
completed in **6.543 s**, exit 0:

- Before: **2 planned opens, 0 violations/parity**, ignored checks `[]`.
- After native SES import/refill/save/reload: **0 opens/violations/parity**,
  identical ignored checks, invariant deltas `[]`, frozen source unchanged.
- Actual bwrap probe: distinct network namespace, only `lo`, egress errno 101,
  host-loopback errno 111, all three read-only write probes errno 30. Both Java
  processes used bwrap `--unshare-net`; no online routing fallback.
- Wirelength 28.0 → 91.287654 mm; **zero vias**, front-layer detours only.
  PROPERTY_ENUM stderr assertions remained visible/retained (18 in smoke).

Compact evidence (SHA-256; inventories/invariants use sorted compact JSON):

- Source/before/after invariants, all equal:
  `1e46a1c4aa758ca32b78818edef2f11ec1a8bf7c7dec021fd062790d66dcc843`.
- Frozen synthetic source hash inventory:
  `8663d8eb7cc578fe853789e888316140e443d411d3a630ddec8160196bcdfae0`.
- Combined run record:
  `229f34f9625e9914b5b1bcf9de46619ca802281605480130fd7958041ca326fd`.
- DSN / SES:
  `2d3451e0f0ebcd515da7e320637f126062e6fb0b35d0422bc780a28aa4b7058b` /
  `e1d32e917424c041898f79f6df91be09383c3a6f3a7932feed398303092c1602`.

### Protected sources / bounded changes / limits

Before/after SHA-256 snapshots cover **all 2170 tracked files/symlinks outside
the six scoped integration paths**, including every tracked native design,
project, table, library, frozen tool and production artifact: **0 changed**.
Symlink targets are recorded without external traversal; all 7 tracked history
submodule gitlinks remain unchanged and were not entered. Aggregate protected
inventory SHA-256 before = after:
`f18ba3a1dd84c96114344153c025abfc74abacdf940fe1b907f49b482da0cd7c`.

Only `opt/kicad-tools/{bundle.py,tests/test_cli.py,README.md,BUNDLE_README.md,
VERIFICATION.md}` and `opt/kicad-routing/README.md` changed. No routing engine,
pins, native gates, design rules or production tooling changed. Existing research
link depth **was correct and is unchanged**. Bundling uses exact reviewed names,
including routing tests and the specific historical `smoke-summary.json`; a
supplied `bundle-files.json` is validated/copied, not broad JSON permission.
Only these compact combined notes are retained in the integration diff, not
runtime binaries, fixture boards or full logs. No uncommitted unrelated files.

No blocking integration gap remains in this scope. Synthetic success is **not**
production approval: actual vias/layer changes, arbitrary boards/custom rules,
differential routing, electrical/thermal/manufacturing intent and other native
versions/platforms remain unvalidated. Historical evidence below describes the
prior core-only implementation, not the current combined status.

## Historical core-only verification — workspace 295

### Environment / ownership

Implementation stayed in isolated workspace 295, on main base
`0c273499ec86fa5b7abcd278f0e9c486a4305806`. Main advanced separately to routing
research `8d49b96e11a1c89a550adc99d4224b46642b3e7f`; this work was **not** rebased,
cherry-picked, committed, merged or pushed. No advisors/subagents, network or
catalog lookups were used. Routing code/research are separately owned and were
not edited. KiCad CLI reports **10.0.6**; runtime tests used Python **3.14.4**.
All new Python/test files also parse under the Python 3.8 grammar; actual older
Python/platform runtimes have not been exercised.

Changed scope only:

- `opt/kicad-tools/`: four stdlib implementation files, profile template, four
  docs and five synthetic fixture/test files (14 regular files).
- `.agents/skills/kicad-workflow/SKILL.md`: native common-tool-first workflow.
- Root `README.md`: one toolkit/skill link.
- `.gitignore`: toolkit bytecode only; no native DRC/ERC ignore/rule changes.

The standalone shared JLC scripts, docs, tests, examples and assembly skill are
unmodified. No circuit/PCB/project/library/production files were edited or
released artifacts regenerated. Frozen module tools were neither imported nor
executed. In particular the guarded 16bit exporter duplicate remains untouched.

### Final test results

| Command / scope | Run | Passed | Skipped | Failed / errors |
| --- | ---: | ---: | ---: | ---: |
| `python3 -B -m unittest discover -s opt/kicad-tools/tests -v` | 36 | 34 | 2 | 0 |
| `KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v` | 36 | 36 | 0 | 0 |
| `python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v` | 103 | 97 | 6 | 0 |
| Existing exporter native synthetic methods, explicit command below | 2 | 2 | 0 | 0 |

The default toolkit skips are its two explicitly opt-in native tests. The six
shared default skips are existing opt-in native integrations; their released
board/mirroring methods were deliberately **not** invoked. The existing shared
synthetic methods were run independently and again from the relocated bundle:

```sh
KICAD_JLCPCB_INTEGRATION=1 python3 -B opt/kicad-jlcpcb/tests/test_export.py \
  KiCadIntegrationTests.test_native_fields_exclusions_mixed_sides_and_nonzero_origin \
  KiCadIntegrationTests.test_repeated_hierarchical_sheet_part_numbers -v
```

Development regressions caught and fixed a synthetic inventory expectation (9,
not 8 files), a same-net clearance test that could not prove rule application
(replaced by an intentionally restrictive edge-clearance fixture), and a path
variable-shadowing bug. Final suites above have no unresolved failures. Source
rules/ignores were not weakened to address any finding.

Coverage includes exact pass-through args/status/help, native CLI vs optional
`pcbnew` failure, shallow selection, config-relative paths, repeated hierarchy,
cycles/missing sheets/libraries/variables, malformed native inputs/schema, private
rules/library copies, no source links, output/alias/overwrite refusal, dry-run
no writes, source hash mutation detection, lossless source-block/path operations,
exclusive edit outputs, XML ref/pin/net/hierarchy comparison and UTF-8/DTD guards,
optional routing unavailability and synthetic stub/bundle integration.

### Safe real KiCad / relocation proof

Both real toolkit integrations use **temporary non-Bread synthetic projects**:
repeated hierarchical child sheets expanding R1/R2, local regular library tables,
a local symbol/footprint library, native project JSON, an intentionally restrictive
`.kicad_dru`, and an unrouted SIGNAL net. The external-dependency case also uses
an absolute child-sheet path outside the project and absolute local library URIs;
only staged path tokens are rebound. Actual native findings are retained.

An independent CLI proof bundled **37 payload files plus the hash manifest** into
a directory with spaces, ran from an unrelated working directory with spaces,
and selected a non-Bread fixture outside the distribution. Every bundle payload
hash matched. No Git/original checkout dependency, source bytecode, project writes,
runtime or vendor files were needed. Actual observed exit codes:

| Operation | Exit | Observation |
| --- | ---: | --- |
| relocated `doctor` | 0 | Native CLI available; optional interpreter reported independently |
| relocated `check` | 1 | Expected findings, not a false clean or failed test |
| relocated `export` | 0 | Shared exporter: 2 components, 1 BOM row, 2 copper layers; valid Gerber ZIP/BOM/CPL |
| relocated `netlist inspect` | 0 | Native-expanded refs R1/R2 and exact SIGNAL pins |
| relocated `netlist compare` (same identity) | 0 | Identity matches |
| `route doctor` without sibling | 2 | Clear unavailable message, no routing/download/runtime action |

The proof's native netlist/ERC/DRC return codes were **0 / 5 / 5**. Raw counts:
ERC **1 warning**; DRC **2 copper-edge-clearance violations + 1 unconnected item**,
all three DRC findings error level; native schematic parity **0** findings, and
separate native XML-to-PCB ref/pin/net parity equal. Restrictive edge rules really
ran on staged project inputs. There were no operational errors/native stderr.
Source content remained identical. These are known fixture findings, **not**
claims about released boards or a production/order approval.

### Read-only project selections (no hardware checks/exports)

These commands were run for all three selections, with no report directories
created by dry-run and no native ERC/DRC on these released boards:

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --project-dir modules/base
python3 -B opt/kicad-tools/kicad_tools.py check --project-dir modules/base \
  --reports /tmp/kicad-toolkit-295-uncreated-base --dry-run
python3 -B opt/kicad-tools/kicad_tools.py doctor --project-dir modules/16bit-5v
python3 -B opt/kicad-tools/kicad_tools.py check --project-dir modules/16bit-5v \
  --reports /tmp/kicad-toolkit-295-uncreated-16bit-5v --dry-run
python3 -B opt/kicad-tools/kicad_tools.py doctor --project-dir modules/32bit-5v
python3 -B opt/kicad-tools/kicad_tools.py check --project-dir modules/32bit-5v \
  --reports /tmp/kicad-toolkit-295-uncreated-32bit-5v --dry-run
```

All six exited 0. Base resolved **2 sheet files / 71 native dependency files**;
16bit-5v **1 / 69**; 32bit-5v **1 / 71**. The custom **regular** 32bit footprint table
was accepted. The actual optional `/usr/bin/python3` `pcbnew` import succeeded and
reported its installed build, with native PROPERTY_ENUM assertion diagnostics
retained in doctor JSON rather than hidden. No `pcbnew` binding is required for
checks/exports.

### Source-unchanged evidence / limits

SHA-256 and leaf-symlink snapshots for **225 protected tracked design/project/
table/symbol/frozen-tool/shared-JLC/skill/LICENSE files** were captured before
implementation and checked afterward: **0 changed**. The three doctor closure
inventories were separately rechecked, including every selected local library
file: all hashes identical. Synthetic checks/export also compare complete
bounded fixture file inventories. Scoped Git diff/status review and whitespace
checks show only the new owned toolkit/skill and the two small root changes;
no history, source/production, routing or unrelated paths are included.

Host-local detailed logs/proof records are reproducible from the commands above:
`/tmp/kicad-toolkit-295-{toolkit-default,toolkit-native,shared-default}.log`,
`/tmp/kicad-toolkit-295-final-cli-proof.json`, and doctor/source-baseline JSON
records. They are temporary execution evidence, not files to install or merge.

Historical limit: real routing was absent from workspace 295 and its routing
tests used synthetic stubs only, with no runtime downloads. The combined
post-merge verification above supersedes that untested-integration status. Installed global KiCad libraries and exporter
symlink/scan/provenance behavior are not rewritten or fully captured. Native
DRC graphical/field parity for differently named roots is explicitly not run;
manual critical-net/electrical/production/order signoff is always separate.
