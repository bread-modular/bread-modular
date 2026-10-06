# Scoped verification and handoff

## Post-merge combined verification — main `55e8a204`, workspace 297

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
