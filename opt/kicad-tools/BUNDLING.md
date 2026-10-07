# Canonical layout and portable bundles

## Canonical layout

One authoritative home: **`opt/kicad-tools`**. Facade delegates and native parser
imports use canonical paths, not historical aliases.

| Canonical directory | Compatibility/discovery symlink | Exact relative link text |
| --- | --- | --- |
| `opt/kicad-tools/jlcpcb` | `opt/kicad-jlcpcb` | `kicad-tools/jlcpcb` |
| `opt/kicad-tools/skills/kicad-workflow` | `.agents/skills/kicad-workflow` | `../../opt/kicad-tools/skills/kicad-workflow` |
| `opt/kicad-tools/skills/jlcpcb-assembly` | `.agents/skills/jlcpcb-assembly` | `../../opt/kicad-tools/skills/jlcpcb-assembly` |

Edit canonical files only. Historical module callers/imports and skill discovery
continue to resolve to those same files. There are no duplicate authoritative
skills, stub exporters or rewritten frozen module callers. Symlink support is
required: copy/relocate the **whole distribution**, preserving links and layout
(e.g. `cp -a`), not just the facade or an alias directory.

The consolidation preserves `export.py`, `assembly.py`, `catalog.py`,
`bom_audit.py` and `passive_planner.py` byte-for-byte. The production wrapper's
business logic is unchanged; its `REPO = HERE.parents[2]` accounts for the extra
canonical directory level after `__file__.resolve()`. Its module-name / `--all`
behavior still needs a `modules/` tree at the distribution root; a core-only
bundle correctly reports that tree missing. Explicit external project paths
work without a repository. Exporter/assembly code has no `__file__` repository
root assumption; local sibling imports retain their layout.

Frozen design/library/release/source-provenance records are historical evidence,
not files to regenerate during this move. The aliases preserve path access, not
old hashes of changed documentation/tests or the wrapper's root line. Do not
replay a guarded release merely to refresh those records. The narrow
`.gitignore` exception exposes canonical JLCPCB **tool sources** only; ordinary
module `jlcpcb/` outputs and bytecode remain ignored.

## Install by copy (not a global installer)

From the repository or distribution root:

```sh
python3 -B opt/kicad-tools/kicad_tools.py bundle '/tmp/Portable KiCad Toolkit' --dry-run
python3 -B opt/kicad-tools/kicad_tools.py bundle '/tmp/Portable KiCad Toolkit'
python3 -B '/tmp/Portable KiCad Toolkit/opt/kicad-tools/kicad_tools.py' doctor
```

The destination must be **new**, outside the distribution source tree, with no
symlink destination ancestors or overwrite/alias. Dry-run creates **nothing**,
including parent directories. Fixed reviewed payload: toolkit source, stdlib
tests/template/docs, ALL automation/schematic source/docs/tests, canonical JLCPCB scripts/docs/examples/tests, both canonical
skills, MIT LICENSE and a portable root README. Exactly the three relative
compatibility directory symlinks above are recreated; no alias file payloads
are copied or hashed a second time.

No Git, original checkout, Bread circuit/project, history, credentials, outputs,
vendor code, global installation or automatic runtime download is needed.
Checks/bundling are offline. Assembly retains its own explicit network options;
export retains its existing default/overwrite/staging/provenance limits. Hashes
are tooling provenance, **not** signatures, hardware correctness or approval.

## Manifest and symlink safety

`toolkit-manifest.json` uses **schema version 2** (version 1 had files only):

- `files_sha256`: SHA-256 of each regular canonical payload file, LICENSE and
  portable README. `file_count` counts these, not links or the generated manifest.
- `symlinks`: exactly the three owned alias paths; each records `target` and
  `link_text_sha256` (SHA-256 of the UTF-8 relative link text, **not** target bytes).
  `symlink_count` is 3. The target files are covered once in `files_sha256`.
- `routing`, `order_ready: false` and explicit provenance limits remain visible.
  The generated manifest is not self-hashed.

`bundle.regular` still rejects **all** symlink files and ancestors, including
compatibility aliases. Bundling never generically dereferences or recursively
scans links. A separate exact allowlist validates each alias's name, literal
relative link text, real canonical directory and non-symlink in-root ancestors.
Missing/broken/replaced/absolute/escaping links, target directory aliases and
symlinked allowlisted source files fail before destination creation. Extra
unreviewed links/files are ignored, not discovered or copied. A source manifest
cannot grant new symlink permissions; links are revalidated during copying.
As with existing hash checks, this is not protection against adversarial
concurrent filesystem writers; do not bundle while another writer changes inputs.

## Relocate and re-bundle

Keep the relative `opt/` / `.agents/` layout. Quoted paths with spaces and an
unrelated current working directory are supported; input project paths are
explicit, never inferred from the toolkit checkout. From **any** working directory:

```sh
python3 -B '/tmp/Portable KiCad Toolkit/opt/kicad-tools/kicad_tools.py' export --help
python3 -B '/tmp/Portable KiCad Toolkit/opt/kicad-jlcpcb/export.py' --help
python3 -B '/tmp/Portable KiCad Toolkit/opt/kicad-tools/kicad_tools.py' \
  bundle '/tmp/Another Portable Toolkit'
```

Re-bundling validates the canonical sources and exact links afresh, regenerates
its manifest and preserves all payload/link hashes. It does not trust or import
permissions from an earlier manifest. Runtime files, secrets, scratch files and
unreviewed links added to a distribution do not enter the next bundle.

## Optional routing payload (separately owned)

`bundle --include-routing` uses a **fixed reviewed allowlist** for historical
and ordinary-project source, tests and detailed docs: `general_flow.py`,
`general_native.py`, `project_contract.py`, independent project fixture/native
checks, `API.md`, `SUPPORTED_SUBSET.md`, `SAFETY.md`, `TESTING.md`, `SMOKE.md`,
root research and the exact compact evidence files `smoke-summary.json`,
`docs/project-evidence.json`, `docs/premerge-review-evidence.json`.
Core allowlists include all automation/schematic sources, docs, tests and
[CLI handoff regression](tests/native_handoff.py). No broad glob/copy, arbitrary
JSON, runtime/JAR/vendor, work/logs or `*.tmp` payload is authorized.

An optional `bundle-files.json` must include the complete reviewed routing payload
(only the exact routing skill path may be added); it is copied so re-bundling
preserves that contract. Paths are unique repo-relative files, at most 128, with
no symlinks, runtime, secrets or temporary trees. The named JSON files grant no
general JSON permission. The three core aliases grant no routing exceptions.
Missing optional sibling is reported gracefully, never installed automatically.

## Regressions

```sh
python3 -B -m unittest discover -s opt/kicad-tools/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/jlcpcb/tests -v
KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v
```

Keep `KICAD_JLCPCB_INTEGRATION` **unset** for shared-suite discovery: its legacy
opt-in includes real repository-board exports, which tooling-only work must not
execute. The toolkit opt-in invokes only named shared **synthetic** methods.
Relocated copied shared unit tests do not require a `modules/` tree. See
[verification results and limitations](VERIFICATION.md) and [migration inventory](MIGRATION.md).

## Optional TraceMaker (independent of Freerouting)

`bundle NEW --include-tracemaker` includes only the fixed literal
`TRACEMAKER_FILES`: first-party dispatcher/controllers/context helper, existing/new
unit/native tests, README/BUILD and compact pinned signed-package/provenance records.
`--include-routing` is unchanged; choose neither/either/both explicitly and repeat
chosen flags when re-bundling. Manifest `tracemaker` records requested/available/included;
core has neither optional engine and remains usable. An explicitly requested missing
TraceMaker payload fails nonzero before writes. No manifest expands its allowlist.
All regular-source/ancestor and exact-three-link safety/hash/dry-run/no-overwrite rules
apply unchanged. No vendor code, binaries, extracted dependencies, HOME/config, boards,
experiment trees or output artifacts are copied. The compact standalone provisioning
guide does not depend on absent experiment JSON; historical links are repository-only.
[Recommended hybrid workflow and format blocker](HYBRID_ROUTING.md) is always included.
