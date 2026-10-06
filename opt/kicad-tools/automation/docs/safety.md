# Safety contract and deliberate limits

## Source isolation and reproducibility

- Only `opt/kicad-tools/automation` is this implementation's ownership scope.
  No schematic editing primitives, facade/routing/JLC export changes, releases,
  native runtime binaries, global installation or Git commits.
- Controller imports only existing `project.Plan`/native parser/netlist helpers,
  not the facade/bundle. `pcbnew` lives in a separate `python -I -B` subprocess.
  Only matching CLI/pcbnew **10.0.x** is currently supported; tool hashes and
  native patch versions are preconditions. SWIG is version-sensitive/deprecated.
- Inspect/plan are read-only probes with HOME/config/cache directed to `/dev/null`;
  they write no plans, boards or temporary stages. Native startup assertions and
  denied config-directory attempts are retained in `native_diagnostics`, not
  redirected away or represented as successful GUI actions.
- Hashes cover the complete **supported** native closure: selected PCB, root and
  hierarchical sheets, companion projects/rules, local library tables and all
  local `.pretty`/symbol library files, explicit native config dependencies,
  config/operations JSON, added `.kicad_mod` inputs and automation/shared code.
  Symlink identity is recorded; copies are dereferenced. Changed bytes, closure,
  path bindings, inspector identities, ops or tool/native versions require a new
  plan. Unresolved variables, unsupported table kinds, rule includes, cyclic or
  oversized hierarchies/dependencies fail, never silently fall back to inference.
- Source designs are never opened for writing. Apply rehashes original sources
  before and after. A fresh directory outside **every input/dependency directory**
  is created exclusively; existing output, source-tree placement and symlink
  ancestors are refused. Stage contains byte copies, never source hardlinks or
  symlinks; candidate link/alias checks precede native operations and completion.
- This is process/transaction isolation, **not an OS security sandbox**. Do not
  use hostile executables or run while another process mutates inputs/candidate
  paths. A concurrent hostile symlink/TOCTOU attack is outside the contract.
  No rollback to or commit into source ever occurs. Failure directories/logs are
  retained for diagnosis, not called accepted.

## Relocatability and preservation

`Plan.stage` normally binds table/sheet strings to absolute staging paths. This
API immediately rebinds those exact tokens to per-file **relative** paths,
checks that their targets stay inside `inputs`, and rechecks before completion.
No temporary-stage paths are published. The final candidate directory is used
from creation (no unsafe rename). The completion marker stores board/schematic
paths relative to it. `result.json` command logs/original input hash records may
contain absolute provenance paths; these are diagnostic, not runtime bindings.
Synthetic tests relocate the directory, delete the original dependencies, then
run native XML/ERC/DRC again successfully.

Schematic/library/project/rules bytes are preserved exactly except reported
relative table/Sheetfile token rebindings. Project settings are never rewritten:
`SaveBoard(..., aSkipSettings=True)` avoids native helper project normalization.
CLI refill/save can materialize project text variables into root board properties;
only **new** properties exactly matching those declared variables are removed
and logged before reload. Existing properties/global settings still must compare
equal. Unknown normalization is a failure, not blanket stripping of properties.

Native item serialization compares all untouched top-level copper/footprints/
drawings/groups before/after operations and save/reload. Existing pad UUIDs,
number/net assignments and field identities survive transformations. Net names
and native net codes are preserved. Raw board-global settings/properties/nets
also compare equal. Refilling is allowed to replace only zone filled-polygon
caches/filled-state metadata; zone outlines/rule settings/UUIDs must not change.
No geometry snapshots are checked merely by item totals. Formatting/native
version metadata may normalize; this API is not a lossless byte editor of PCB
syntax. Historic or noncanonical boards whose native parser/save would normalize item
properties or unsupported settings fail closed. Before editing, raw source items
must exactly match native item serialization, including unknown-field checks.

## Checks and statuses

Apply runs a baseline on the untouched staged candidate, then operations, native
connectivity/save/reload, candidate XML netlist/ERC and all-severity DRC with
refill + save, all track errors and same-stem schematic parity. Saved candidate
is reloaded again. It compares XML ref/pin/net identities independently of native
DRC; electrical additions must match their schematic ref/value/footprint/pad-net
membership. Native XML does not enumerate every omitted/no-connect pin: no
symbols/pins/nets are invented to paper over that limitation.

Findings are compared by type/category/severity, item UUIDs/descriptions/
positions and ERC sheet identity, retaining multiplicity. Added/removed/retained
identities are reported; an old short cannot offset a new short via equal totals.
All final ERC findings, parity problems, shorts, clearances, exclusions and other
DRC findings block acceptance, even if already present at baseline. Unknown
native JSON schema/exit status is operational failure. Explicitly ignored project
severity settings are unsupported because they could hide constraints. Custom
self-contained native rules are retained and checked; rules are never relaxed.

Default policy rejects any open. `plan --allow-draft-opens` permits ONLY native
`unconnected_items`, `track_dangling`, `via_dangling` error/warning findings;
returns `draft`, `accepted:false`, CLI exit **1**. Opens may be new or preexisting
and their exact identities/deltas are reported. No severity-exclusion or other
finding is waived. Never label a draft clean. `accepted` / exit **0** means no
findings in the implemented checks, **not** production/fabrication approval.

`result.json` exists for completed attempts; `completion.json` is written LAST
only after verified accepted/draft checks, save/reload, relocatability and source
hash invariance. Failure/rejection has no completion marker. Interrupted partial
candidates must never be consumed as accepted. The marker checks the
result hash; consumers must also review status, not just directory existence.

## Geometry, locking and unsupported surface

Placement changes component origin/rotation/side **without dragging attached
copper**. A routed footprint move may therefore create a deliberate draft open.
No native interactive router, GUI transaction, IPC session, live edit/push-and-
shove, auto-placement or GUI parity is claimed. Three-point copper arcs are
explicitly deferred rather than only partially validated.

Existing locks are honored on items and **all ancestor groups/footprints**, plus
locked children of footprint transformations. Individual unsaved PAD.SetLocked
flags are not serialized by the installed native version: offline edits cannot
observe GUI-only/unsaved locks; persisted footprint/group/graphic locks and all
native in-memory flags are honored. No lock/unlock op exists; unknown
lock operations fail. Group membership/cyclic parenting and grouped deletion
are not bypassed. New routes read endpoint geometry but do not modify/split the
existing track/pad (including locked endpoint copper). Existing locked zones or protected zone ancestors fail planning because native
refill globally recomputes derived fills. Their outlines/settings are not bypassed.

Simple polygons/through-vias/straight routes/board edges only; no thermal options,
keepouts, arbitrary curves/shapes, net ties, arbitrary field/settings updates,
blind/buried vias or net code creation. No automatic component numbering,
schematic synchronization, fabrication exports or component-library downloads.
Models, images, embedded files, external drawing sheets/resource paths and
nonlocal libraries are currently unsupported so a full closure is not falsely
promised for them. Explicit extensions requiring unsupported constraint/resource
semantics fail closed. Electrical additions with omitted/no-connect pins cannot
be inferred. Mechanical-only footprints must not have electrical pads/refs.
