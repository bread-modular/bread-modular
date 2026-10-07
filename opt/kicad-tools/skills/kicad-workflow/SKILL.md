---
name: kicad-workflow
description: Common-tool-first portable KiCad native hierarchy/netlist inspection, offline PCB/schematic edits, private ERC/DRC, JLCPCB exports and recommended hybrid TraceMaker signal routing (with explicit format blockers) without source or approval policy changes.
---

# Portable KiCad workflow

Canonical skill home: `opt/kicad-tools/skills/kicad-workflow`.
`.agents/skills/kicad-workflow` is a relative discovery symlink, not a second copy.
See [layout and portability](../../BUNDLING.md).

## First choice: common tools, not copied board scripts

Read the [toolkit documentation](../../README.md) and actual
`--help` first. Use `opt/kicad-tools/kicad_tools.py` for doctor, private checks,
netlist inspection/comparison, `pcb inspect|plan|apply`, flat
`schematic inspect|plan|apply` and install-by-copy. Discover only the relevant
command first; [workflow/API](../../API.md) links the detailed schemas. Use the unchanged shared
[JLCPCB exporter](../../jlcpcb/README.md) and
[assembly tools](../../jlcpcb/ASSEMBLY.md) directly or through its
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
  [migration inventory](../../MIGRATION.md).

## Candidate edits before routing

Use [PCB](../../automation/docs/api.md) geometry operations for explicit native
move/rotate/flip, copper/vias/zones, outline/text and bounded deletion. They are
not live GUI/IPC push/shove and do not automatically place components; moving a
footprint does **not** drag traces. Keep requests/plans separate, inspect first,
review plan then apply to a NEW output. Only a completed `completion.json`
candidate with explicit `--allow-draft-opens` may hand off connectivity opens;
shorts, clearances, ERC and parity are never waived. Do not call drafts accepted.

[Flat schematic primitives](../../schematic/docs/api.md) add only wire polylines,
junctions and local labels. Review native pin/net delta/ERC/save-reload evidence.
They never load or synchronize a PCB: perform explicit downstream synchronization
and PCB DRC/parity before accepting a circuit change. Existing approval policies
still govern every operation; no source overwrite or frozen migration.

## Recommended hybrid TraceMaker sequence (optional, never automatic)

Actively **recommend the hybrid approach for compatible ordinary signal work**, not
an autorouter-first/full-board workflow. See the [exact recipe](../../HYBRID_ROUTING.md)
and the optional [TraceMaker controller](../../tracemaker/README.md).

1. Inspect circuit intent and fixed mechanical constraints, outline, pots/sockets,
   edge clearances, top/bottom and orientation/polarity/pin roles. Use `pcb inspect`
   to obtain actual refs/UUIDs/nets/layers; never infer permission from a trial.
2. Explicitly place core ICs, power/decouplers and interfaces via reviewed `pcb plan/apply`
   to NEW candidates; no automatic placement. Route/protect critical power/returns,
   analog/feedback, clocks/differential and constrained copper yourself. Existing locks
   are rejected; there is **no lock/unlock API**. Moves do not drag attached traces.
3. Freeze the approved layout as an immutable router baseline: **every transform and
   non-authorized raw node** must survive exactly. Verify complete hierarchy/local
   library/rule closure. Missing/unsupported dependencies are blockers, not silent drops.
4. Choose explicit ordinary signal nets. For rerouting authorize only inspected copper
   UUIDs (`strip --segment-uuid`); without that option ALL segments on selected nets are
   authorized. Vias stay unless both exact via UUIDs and the narrow regeneration flag
   are approved. Preserve power, critical copper, mechanics and mounting holes.
5. Use pinned reviewed external CPU build/provenance and bounded offline `tracemaker
   run route --experimental`. No implicit install, router switch or fallback. Independently
   run engine DRC, exact raw preservation before native reload, canonical semantic
   preservation, native DRC/parity/ERC/XML and footprint/pad/net/via inventory; inspect
   physical copper/returns. Route exit zero is not completion or automatic acceptance.
6. Fine-tune explicitly with `pcb inspect/plan/apply`: selected deletion/replacement
   polylines/vias and approved transforms, not trace dragging, live GUI or push/shove.
   Every edited geometry baseline needs reviewed operations/plan/completion and new
   freeze/final checks; don't blindly compare an intentional edit to the original.
   Preserve the whole authorization/hash/removal/command/findings audit chain.

**Current concrete blocker:** matching pcbnew/CLI 10.0.6 `pcb apply` saves name-only
nets, without the legacy top-level numeric netdefs required by our legacy adapter. This is not proof of upstream engine incompatibility.
`tracemaker strip/run` block it before writes; do not imply the full apply→engine→polish
loop is qualified, down-save, invent net/rule mappings or weaken gates. Synthetic native
freeze/no-op comparison/validation/back-to-CLI polish is tested, not engine interoperability.
Native saves cannot pass the current first-party strip/run admission gate until the adapter handoff is separately qualified.
The pinned engine itself supports named nets; that does not qualify this controller's end-to-end handoff. No engine runtime test was performed in this integration. No DIY downgrade/conversion. Any incompatible
snapshot/format or known ERC/baseline-policy conflict stays explicit blocked/draft.
Only opens-only completed PCB drafts with explicit policy may proceed where supported;
never waive shorts, clearance, ERC, parity or known warnings/exclusions to gain admission.

## Explicit Freerouting alternative


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

The separate unchanged `route` facade only delegates when the optional sibling `opt/kicad-routing/run.py`
exists; otherwise it reports unavailable. Consult the sibling's actual help for
`doctor|prepare-runtime|inspect-project|plan-project|route-project|smoke`. Ordinary supported-project DSN/SES routing is offline; runtime
downloads must be explicit opt-in. No fallback installation or network fetching
is introduced by this skill. Runtime/JAR/temporary files are not bundled. Freerouting is an explicitly chosen
alternative for that tested subset, never a silent fallback from blocked TraceMaker.

Use the completed PCB candidate's **`inputs/` subtree** as `--snapshot`; derive
`--pcb` from its completion record relative to `inputs/`. No hand-edits to board,
rules or library tables are needed. Inspect and `plan-project --reroute-net NAME`
from actual planned nets, review the hash-bound plan outside that subtree, then
explicit offline `route-project --apply`. The sibling accepts bounded relative
or `${KIPRJMOD}` local library URIs and uses the PCB parent's cwd. Read its subset:
groups, zones, complex rules/stackups are rejected. Verify source hashes, locked
and non-authorized copper, placements/settings and final native DRC/parity/opens.
See the [exact CLI handoff](../../API.md).

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
as documented before reuse; report passes/skips/failures honestly. Combined source/relocation and real CLI handoff evidence is retained in
[verification](../../VERIFICATION.md); earlier synthetic-only routing evidence
is historical, not a current capability limit.
