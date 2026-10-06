---
name: kicad-workflow
description: Common-tool-first portable KiCad native hierarchy/netlist inspection, private ERC/DRC, JLCPCB exports and optional bounded routing without source or approval policy changes.
---

# Portable KiCad workflow

## First choice: common tools, not copied board scripts

Read the [toolkit documentation](../../../opt/kicad-tools/README.md) and actual
`--help` first. Use `opt/kicad-tools/kicad_tools.py` for doctor, private checks,
netlist inspection/comparison and install-by-copy. Use the unchanged shared
[JLCPCB exporter](../../../opt/kicad-jlcpcb/README.md) and
[assembly tools](../../../opt/kicad-jlcpcb/ASSEMBLY.md) directly or through its
transparent facade. Do not generate a new exporter/catalog/parser/router unless
the existing common tool genuinely lacks the narrow required operation.

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor --project-dir '/path/to/project'
python3 -B opt/kicad-tools/kicad_tools.py check --config /path/to/profile.json \
  --reports '/tmp/new check reports' --dry-run
python3 -B opt/kicad-tools/kicad_tools.py check --config /path/to/profile.json \
  --reports '/tmp/new actual check reports'
python3 -B opt/kicad-tools/kicad_tools.py netlist inspect '/tmp/new actual check reports/netlist.xml'
```

## Source, native identity and honest gates

- Explicitly select PCB, **hierarchical root schematic**, project rules and
  dependencies. Profiles are versioned JSON; paths resolve relative to the
  profile. Regular/custom library tables are valid; don't mandate symlinks.
- Keep sources unchanged during inspection/check/export work. New check commands
  stage private copies including rules, hierarchy and local libraries. Missing
  required sheets/dependencies are blockers, **not** silent partial successes.
  Preserve source SHA-256, raw native stdout/stderr and findings on failures too.
- Native KiCad expands repeated sheet references and multi-unit components.
  Compare exact ref/pin/net identities, fields and hierarchy, not coordinates,
  numeric net codes, line counts or flattened regex refs. Retain singleton,
  unconnected, parity, warning/error and excluded findings. XML alone cannot
  establish every omitted/no-connect pin or circuit intent; ERC is required.
- Save full native ERC/DRC. DRC uses refill-in-memory and never saves the board.
  No edits to rules, ignores or exclusions to make a test pass. A different root
  basename means native DRC graphical/field parity is not run; report that limit
  and the separate native XML-to-PCB ref/pin/net result explicitly.
- Source/edit helpers return text in memory; any approved edit must go to a
  distinct explicitly new review output, never overwrite source. Existing user
  approval policies still govern editing, regeneration, routing, manufacturing,
  network/runtime installation, committing and order placement.
- Frozen module finalizers/regenerators/engineering verifiers are board-specific
  evidence, not generic migrations. Don't replay, weaken guards, or replace
  intentionally frozen exporter duplicates. See the
  [migration inventory](../../../opt/kicad-tools/MIGRATION.md).

## Routing sequence (optional, never automatic)

Manually inspect and constrain critical nets **before** optional autorouting:
power/ground returns, decoupling, current/voltage limits, sensitive analog,
clocks/differential pairs, polarity and footprint pin-role mapping. Native DRC
and connectivity are not electrical design approval. Route critical nets
manually first; capture boundaries/keepouts, route only the bounded remaining
work on separate copies, then rerun ERC/DRC/parity, check hashes, and review
physical copper/vias/returns visually. Do not route released hardware as a smoke
test or claim a router proves production readiness.

```sh
python3 -B opt/kicad-tools/kicad_tools.py route doctor
python3 -B opt/kicad-tools/kicad_tools.py route --help
```

The facade only delegates when the optional sibling `opt/kicad-routing/run.py`
exists; otherwise it reports unavailable. Consult the sibling's actual help for
`doctor|prepare-runtime|smoke`. Native synthetic DSN/SES smoke is offline; runtime
downloads must be explicit opt-in. No fallback installation or network fetching
is introduced by this skill. Runtime/JAR/temporary files are not bundled.

## Export, assembly and portability

```sh
python3 -B opt/kicad-tools/kicad_tools.py export '/path/to/project' \
  --output '/tmp/separate assembly export' --require-part-numbers
python3 -B opt/kicad-tools/kicad_tools.py assembly --help
python3 -B opt/kicad-tools/kicad_tools.py bundle '/tmp/Portable KiCad Toolkit' --dry-run
```

The export/assembly pass-through preserves **all** standalone semantics, including
export defaults/overwrite flags and assembly's existing live-network options;
profile paths do not reinterpret those flags. Insist on separate explicit
outputs for this workflow. Export staging/provenance differs from private check
staging: don't call its report a transitive dependency manifest or release gate.
Check actual assembly side/THT/exclusions, BOM/CPL ref parity, rotations, datum,
physical package and manual fabrication/assembly preview; no automatic production
or order claims. Follow the existing
[assembly skill](../jlcpcb-assembly/SKILL.md) for independent catalog evidence,
ratings, Basic/Economy policy and manual approvals.

Install by copy into a **new** destination, retaining the `opt/` and `.agents/`
relative layout. Dry-run writes nothing. Exact source-file hashes plus LICENSE
are tooling provenance, not hardware approval or signatures. No global install,
projects, histories, credentials, outputs, vendor code or runtime is copied.
Run unit/CLI/no-write tests and opt-in **synthetic-only** native relocation tests
as documented before reuse; report passes/skips/failures honestly. Real combined
optional routing code needs its own post-merge integration verification.
