# Safety boundaries and evidence

## Native flow and invariants

Inspect/plan/dry-run have **no writable host mounts, temp/output files or logs**:
read-only Bubblewrap namespace, pipe-only bounded capture, bytecode disabled,
regular-file write limit zero. KiCad may report a denied instance-lock attempt;
it is not suppressed, and no lock/cache is created on the host. No Java is run.
A caller's stdout redirection is an explicit caller action outside the snapshot.

Apply freezes an entire bounded snapshot in `source/`, working context in `before/`,
and copies matching companions into `after/`. Only native `LoadProject`/`LoadBoard`,
two-argument `ExportSpecctraDSN`/`ImportSpecctraSES`, `ZONE_FILLER` and native saving
perform PCB interchange. Structural parsing is validation, never our PCB/DSN/SES
converter or router. Native save skips settings updates; unload uses `aSave=False`.
SWIG work is process-isolated with stderr/cores/budgets controlled. Borrowed removed
copper is retained for one bounded subprocess, avoiding Python `Remove()` ownership
corruption; the process owns no persistent native board state.

Baseline native DRC includes every severity/exclusion, all-track errors and
schematic parity. It must have **only the approved UUID-pair opens**, no other
DRC/parity findings. Apply refills/saves/reloads the baseline and compares it to
source invariants; native schematic XML nodes must equal every physical pad node.
After import: live invariant check before save, refill/native save, CLI refill/save
and all-severity DRC/parity, then disk reload. Acceptance requires zero DRC/parity/
opens, unchanged ignored checks, unchanged project/rules/library bytes/modes,
placements/physical pad-net map, nonrouting/mechanics/origins, zone definitions,
locked copper and every existing/new item on non-authorized nets. Filled-zone data
is not an authority substitution; general zones are currently rejected.

All board/footprint groups are rejected before native inspection/routing, even
unlocked ones. v1 does not infer inherited locks from item `IsLocked` flags.

Only authorized **unlocked** copper is omitted in the export copy. Other copper
is native-exported as fixed; its original UUIDs/geometry and lock state must survive
import. Protection includes additions and deletions, not merely locked items.
A rejected SES placement or protected branch produces no saved candidate; a later
DRC rejection can leave an unaccepted candidate solely as diagnostic evidence.

## Runtime/offline boundary (historical implementation reused)

Explicit `prepare-runtime --allow-downloads` is the only acquisition entry point.
It uses the existing trusted upstream metadata/URL/SHA/size pins for Freerouting
2.5.0 and Temurin HotSpot JRE 25.0.4.1+1, retaining licenses/legal files and original
archives under ignored workspace-local `runtime.tmp/`. No global installs,
PATH/alternatives updates, remote board upload, vendoring or online fallback.
Artifact/metadata/ELF/tree/notices are checked again before execution.

Java runs **only through the existing verified Bubblewrap sandbox**: read-only
runtime/system libraries/source/before/DSN, hidden host home, cleared run-local
environment, only this run writable, isolated PID/IPC/UTS/network namespaces.
Per-run probe verifies distinct network namespace, only loopback, unreachable
external network and host-loopback listener, actual denied writes and writable
run directory. Analytics/telemetry/API/MCP/GUI disabled; max 10 passes; optimizer,
fanout and automatic neckdown off. CLI help/parser warnings fail closed, and merged
job settings/DSN hash are checked rather than trusting saved defaults.

Native CLI/pcbnew stages use their matching source/candidate PCB parent as cwd.
The bounded runner validates and records cwd; omitted cwd retains its previous
`TOOL` default for smoke/runtime/sandbox callers. Source tables/rules are never
rewritten to repair resolution.

Budgets: route 1–120 s, apply stage 240 s (read-only preflight precedes this stage),
512 MiB Java heap/two processors, 4 MiB logs per stream, 16 MiB regular files,
process-group termination on timeout/overflow, no cores. Sandbox/runtime failure
has no alternative engine or networking retry.

Freerouting GPL-3.0 license text and Temurin GPLv2/Classpath Exception plus bundled
notices stay with local acquisition (184 notice files observed). Upstream checksums
are reproducibility/provenance evidence, **not an independent security audit**.

## Session association and retained artifacts

Unique, non-overwritable run ID + nonce, `input-<id>.dsn` session design, source and
context digests/manifests, source/exported-PCB SHA, canonical/raw approval-plan SHA,
DSN/SES SHA and exact SES `session`/`base_design` bind the job. Stale source/context,
plan, DSN, SES, session identity, reused output and unexpected header fail. Native
DSN header is the full absolute path; SES base design is its input stem, not an
arbitrary same-name board. There is no import/resume/rebind CLI.

`run.json` retains full before/after findings, commands/tool/runtime/artifact hashes,
effective settings, sandbox proof, invariants/copper/metrics, immutable-source result
and failure reason. DSN/SES and matching before/after project context remain local.
Read-only preflight rejection intentionally creates **no evidence directory**; its
machine-readable explanation and raw stderr are available to the caller.

Hashes detect stale/tampered associations during this operation; they are not
signatures, adversarial same-UID race protection or a production/security guarantee.
`manufacturing_status: "NOT_ASSESSED"` always; **never release/order approval**.
