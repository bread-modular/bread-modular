# Scoped verification and handoff

## Environment / ownership

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

## Final test results

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

## Safe real KiCad / relocation proof

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

## Read-only project selections (no hardware checks/exports)

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

## Source-unchanged evidence / limits

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

Limits remain explicit: optional real routing code is absent from this old-base
workspace; combined `run.py`/research bundling and real DSN/SES smoke are for the
post-merge integration verifier. Optional routing tests here use synthetic stubs
only. No runtime downloads occur. Installed global KiCad libraries and exporter
symlink/scan/provenance behavior are not rewritten or fully captured. Native
DRC graphical/field parity for differently named roots is explicitly not run;
manual critical-net/electrical/production/order signoff is always separate.
