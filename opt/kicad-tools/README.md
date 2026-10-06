# Portable KiCad toolkit (thin facade)

Use common tools first, not copied module finalizers. Python **3.8+**, stdlib only;
private native checks require **KiCad CLI 10+**. `pcbnew` is optional and belongs
to a particular interpreter, not to `kicad-cli`. Shared export requirements and
commands remain [unchanged](../kicad-jlcpcb/README.md).

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor
python3 -B opt/kicad-tools/kicad_tools.py doctor --pcbnew-python /usr/bin/python3
python3 -B opt/kicad-tools/kicad_tools.py export --help
python3 -B opt/kicad-tools/kicad_tools.py assembly --help
```

## Select inputs, not an entire repository

No Git, module naming convention or Bread-specific paths are required. Selection
is either an explicit project directory (only top-level `*.kicad_pcb` candidates)
or an optional versioned JSON profile. Ambiguity/missing root schematics fail.
`--board` and `--schematic` are filenames, relative to `--project-dir`; absolute
paths work. The root schematic is **not** a flattened symbol-instance guess.

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --project-dir /path/to/project
python3 -B opt/kicad-tools/kicad_tools.py check --project-dir /path/to/project \
  --board control.kicad_pcb --schematic root.kicad_sch \
  --reports '/tmp/new check reports' --dry-run
python3 -B opt/kicad-tools/kicad_tools.py check --config /path/to/profile.json \
  --reports '/tmp/new actual check reports'
```

Copy and edit [examples/project.json](examples/project.json). It is an intentionally
nonexistent **template**, not a hardware recipe. Every manifest path (including
`project_dir`, board, root schematic and dependencies) is relative to the JSON
file, **not** to the working directory or `project_dir`. Only schema version 1 and
documented keys are accepted. CLI selection and config selection cannot mix.
Optional `variables` resolve `${NAME}` **dependency paths**, not arbitrary native
CLI parameters. `KIPRJMOD` always denotes the relevant native project directory.

The automatic closure includes all hierarchical Sheetfile targets, associated
`.kicad_pro` / `.kicad_dru`, project-local `fp-lib-table` / `sym-lib-table`, and
the local KiCad libraries those tables declare. Extra `dependencies` are explicit
native files or `.pretty` directories (immediate `.kicad_mod` files only). No
whole-tree discovery: `.history`, `.git`, code, vendor, node_modules, production,
jlcpcb, verification and backup trees are forbidden. Bounds are 256 sheet files,
64 active hierarchy levels, 4096 dependency files and 128 MiB of native input.
Repeated instances of the same sheet are legal; cycles are not.

Both **regular** and symlinked local library tables are valid (including custom
32bit-5v tables). Missing sheets/libraries, unresolved variables, empty `.pretty`
libraries, remote/plugin URIs and unsupported rule includes fail clearly before
native work. Installed global KiCad libraries remain runtime dependencies; this
is not a package manager or a complete installation-provenance capture. Declare
custom local libraries explicitly; the toolkit does not infer them from a user's
global settings. A project lacking `.kicad_pro` / `.kicad_dru` uses native defaults,
and its input inventory makes their absence visible.

## Native checks and honest findings

`check` requires an **explicitly new** report directory outside source and
dependency directories; overwrite/alias/symlink outputs are refused. `--dry-run`
resolves/parses/hashes inputs, executes **no** native commands and writes nothing.
`doctor` writes no project/output files; version and optional interpreter probes
run in temporary working directories. It reports missing `pcbnew` independently
of usable native CLI, and preserves import diagnostics rather than hiding them.

Actual checks copy the dependency closure to a private temporary tree, with no
symlinks back to the original inputs. Project settings, rules, exclusions and
source designs are not weakened or rewritten. Only sheet/library path tokens
are rebound in staged copies; those bindings are recorded. Native commands use
private HOME/config/cache directories. DRC refills zones in memory, never saves
the board, and includes all track errors. All severity levels/exclusions,
unconnected items, native parity, stdout/stderr, source SHA-256 and return codes
are retained in explicit output:

- `erc.json`, `drc.json`: native JSON reports.
- `netlist.xml`: native-expanded hierarchy/reference/pin/net identity.
- `summary.json`: requested-check scope, findings counts, native XML inspection,
  PCB ref/pin/net comparison, hashes, staged path changes, errors and source check.

`--only erc` / `--only drc` are explicit partial checks, recorded as such. Native
DRC `--schematic-parity` is used when the selected root has the PCB's basename
and directory; KiCad's DRC flag cannot select a differently named root. Otherwise
this unrun graphical/field gate is reported explicitly, not called a pass; the
separate XML-to-PCB ref/pin/net comparison still runs. PCB-only mechanical refs
and pads absent from the netlist are reported conservatively, never waived.

Exit codes: **0** means no findings in the *requested* checks (or successful
inspection/dry-run), **1** means findings or a netlist difference, **2** means
selection/dependency/native/schema/operational failure. Raw native violation code
5 is preserved in logs. Excluded findings still count in this conservative
summary. No result asserts production readiness, electrical correctness or
approval. Source hashes are checked after native work even on failure. Hashes
check captured file content/leaf links, not every directory entry, external
configuration, or adversarial concurrent filesystem manipulation; do not run
concurrent source writers. Native programs are trusted installed tools, not an
OS security sandbox.

## Native schematic/netlist helpers

```sh
python3 -B opt/kicad-tools/kicad_tools.py netlist inspect '/tmp/check/netlist.xml'
python3 -B opt/kicad-tools/kicad_tools.py netlist compare /tmp/before.xml /tmp/after.xml \
  --output /tmp/new-net-delta.json
```

Input must be native `kicadxml`, normally obtained by `check` on private inputs.
Comparison preserves expanded refs, pin strings, exact net names (including
hierarchical names), fields, exclusion flags and sheet identity. Numeric net
codes/dates/source filenames are not identity. Duplicate refs/net names/codes,
unknown refs, duplicate pin membership, malformed XML and DTD/entities fail.
Singleton and `unconnected-*` nets are **not** filtered. XML does not enumerate
every omitted/no-connect pin: ERC and manual intent review are still necessary.

`native.py` reuses the shared exporter's S-expression tokenizer/parser and XML
component parser, rather than duplicating these parsers. It factors the narrow
ref/pin/net validation pattern repeated by board engineering scripts; those
scripts stay untouched. Its `source_blocks(text)` yields lossless **character**
spans of direct children independent of indentation. `replace_paths` changes
only matching URI/Sheetfile string atoms and returns text in memory. Any caller
writing an edited schematic must use a distinct explicitly new output;
`write_new_text(source, destination, text)` refuses overwrite/aliases. There is
no generic schematic generator, circuit-migration replay or source-edit CLI.

## Shared export and assembly pass-through

```sh
python3 -B opt/kicad-tools/kicad_tools.py export '/path/to/project' \
  --output '/tmp/separate assembly export' --require-part-numbers
python3 -B opt/kicad-tools/kicad_tools.py assembly --help
```

Arguments/help/exit codes are delegated unchanged to `../kicad-jlcpcb/export.py`
and `assembly.py` using the current Python interpreter. Their standalone commands
remain supported. Config profiles apply to **doctor/check**, not shared export
or assembly flags. Prefer explicit `--output` outside sources; the pass-through
**retains** the exporter's own default output and `--overwrite` semantics and
does not retroactively enforce check's stricter boundary. `assembly` can access
the network when its existing catalog options request it; the facade never adds
a lookup. No catalogs/networks are needed for local checks or bundling.

The existing exporter has its own isolated staging, not this dependency closure.
Its current stage can walk project descendants and uses read-only-intended
library symlinks; absolute/external hierarchical dependencies are not promised.
Its report hashes are not a complete transitive dependency/installation manifest
and export is not DRC/ERC or release signoff. Keep the standalone behavior;
validate with `check`, inspect Gerbers/BOM/CPL manually, and read
[ASSEMBLY.md](../kicad-jlcpcb/ASSEMBLY.md) for sourcing/provenance/approval gates.
The repository mirror wrapper is packaged unmodified for compatibility but its
Bread/module mirroring command is **not** this generic install workflow.

## Optional routing integration

```sh
python3 -B opt/kicad-tools/kicad_tools.py route doctor
python3 -B opt/kicad-tools/kicad_tools.py route --help
```

When `../kicad-routing/run.py` exists, `route <args>` is a transparent pass-through
with the same interpreter/arguments/exit status. Otherwise it returns an
explicit unavailable diagnostic (2); it does not create runtime files, fetch,
route a board, or try an alternative router. The sibling owns
`doctor|prepare-runtime|smoke` semantics; consult its real `--help` before use.
Downloads must remain explicit opt-in in that tool. Unlike the core's Python
3.8+ support, routing requires **Python 3.9+** (`Path.is_relative_to`), **Linux
x86_64**, the supported **KiCad 10.0.6 system `pcbnew` binding**, matching native
CLI and `/usr/bin/bwrap`; see the [routing README](../kicad-routing/README.md).
Routing runtime/JAR/temp files are never bundled. Read optional
[routing research](../../docs/kicad-routing-research.md) when installed; absent
code/research in a core-only distribution is not a failed electrical gate.

## Portable install by copy (not a global installer)

```sh
python3 -B opt/kicad-tools/kicad_tools.py bundle '/tmp/Portable KiCad Toolkit' --dry-run
python3 -B opt/kicad-tools/kicad_tools.py bundle '/tmp/Portable KiCad Toolkit' --include-routing
python3 -B '/tmp/Portable KiCad Toolkit/opt/kicad-tools/kicad_tools.py' doctor
```

The destination must be new and outside the distribution source tree. Dry-run
creates **nothing**, including parent directories. Regular allowlisted files
only: the toolkit, its stdlib tests/template/docs, unchanged shared JLCPCB
scripts/docs/examples/tests, both skills, MIT LICENSE, a portable root README
and `toolkit-manifest.json` with exact file SHA-256. Relative `opt/` / `.agents/`
layout is retained for imports and skill links. No Git, original checkout,
Bread circuit, project, history, credentials, outputs, vendor code, global
installation or automatic runtime download is needed. Hashes are not signatures.

Optional routing uses a **fixed reviewed allowlist**: six Python source files,
README, `tests/test_routing.py`, root research doc, and exactly the historical
`smoke-summary.json` evidence file. No glob/recursive discovery, arbitrary JSON,
runtime or `*.tmp` is copied. An optional `bundle-files.json` must include the full
reviewed payload (only the explicit routing skill path may be added); it is copied so
re-bundling preserves the contract. Paths are unique repo-relative files, at
most 128, no symlinks/runtime/vendor/secret/temporary trees. The two exact JSON
paths are not general JSON permission. Missing sibling is reported gracefully.
Combined facade/bundle/native synthetic verification is recorded separately
from historical core-only results in [VERIFICATION.md](VERIFICATION.md).

See [migration inventory](MIGRATION.md), the discoverable
[workflow skill](../../.agents/skills/kicad-workflow/SKILL.md), and
[exact verification results/limitations](VERIFICATION.md). Run regressions:

```sh
python3 -B -m unittest discover -s opt/kicad-tools/tests -v
KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v
python3 -B -m unittest discover -s opt/kicad-jlcpcb/tests -v
```

Native toolkit integrations are synthetic-only, private and offline; missing
CLI/opt-in is reported as a skip, never a pass. Shared tests' default native
repository integrations stay opt-in; do not regenerate released board artifacts.
