# Standalone CLI and agent handoff

Use `python3 opt/kicad-routing/run.py <command> --help`. JSON stdout; exit 0 for
successful diagnostics/plans/dry-runs/passed routing, 1 for rejection/failure,
2 for argument errors. Native assertions/diagnostics remain on stderr. Input
rejections use `error: {code, message, hint}`; apply-stage failures also retain
`run.json`. A failed candidate is diagnostic only; only `status: "passed"` is
accepted **within the subset**, not manufacture-ready.

## Commands

| Command | Inputs | Writes / execution |
|---|---|---|
| `doctor` | none | Read-only capabilities/runtime byte validation; no board or Java execution |
| `prepare-runtime` | explicit `--allow-downloads` | Existing pinned acquisition only in ignored `runtime.tmp`; never executes Java |
| `inspect-project` | `--snapshot DIR --pcb REL` | Static admission + project-aware native invariant/net map + native DRC/parity, stdout only |
| `plan-project` | snapshot/PCB, repeated `--reroute-net NAME` | Exact hash/protection/open-pair discovery; stdout only, no implicit authorization |
| `route-project` | snapshot/PCB, `--plan JSON_FILE --run-id ID [--route-timeout 120]` | Default read-only dry-run; **`--apply` required** for a new candidate/run |
| `smoke` | optional run ID/timeout | Unchanged synthetic-only historical native test; no board-input option |

`--pcb` is canonical snapshot-relative, including nested directories/spaces.
`--snapshot` may be caller-independent, outside the tool directory; all context
must be inside that snapshot. Run IDs match `[a-z0-9][a-z0-9-]{0,39}` and cannot
be reused, even after failure. Timeout is 1–120 s for routing, default 120.

## Strict plan v1

`plan-project` emits the plan itself (not a result envelope). Exactly these keys
are accepted; any missing/extra/version-changed key is rejected:

```json
{
  "schema": "bread-local-route-plan/v1",
  "supported_subset": "kicad-10.0.6-two-layer-scalar-v1",
  "pcb": "Controller.kicad_pcb",
  "source_digest": "<discovered SHA256>",
  "context_digest": "<discovered SHA256>",
  "pcb_sha256": "<discovered SHA256>",
  "authorized_reroute_nets": ["DATA"],
  "protected_nets": ["CRITICAL"],
  "baseline_open_pairs": [{"net": "DATA", "uuids": ["<uuid1>", "<uuid2>"]}],
  "ignored_checks": []
}
```

Digest encoding: SHA256 of UTF-8 sorted-key, compact JSON (no ASCII escaping),
containing the full relative file → `{sha256, mode}` manifest. Context digest
excludes only the PCB and its `.kicad_prl` view state, never project/rule/library
files. Source digest includes every admitted source file. Open pairs are native
DRC item UUIDs (pads **or tracks/vias**), sorted; they are not a ratsnest guess.
A completed net may be explicitly authorized too: unlocked copper is rerouted,
locked copper remains invariant. Zero planned opens is valid for such a reroute.

Dry-run re-discovers native baseline and must exactly equal the plan. It does not
prove a route exists or perform DSN export; actual per-input translation checks
occur on apply **before Java routing**. The caller may redirect stdout to a new
approval file; that caller-requested write is not performed by plan/dry-run.
The approval file must be outside the snapshot and not a symlink/hardlink alias.

## Semi-auto / editing-API handoff

1. An agent/native GUI places footprints and routes critical nets on its own new
   editing candidate; lock traces you require even on an authorized net.
2. Freeze that candidate with matching schematic/project/rules/tables/local
   libraries. No automation-worker API is needed or invoked.
3. Inspect and authorize ordinary reroute nets; review the discovered protection
   boundary and baseline open pairs. Supply that file plus explicit `--apply`.
4. Review `after/<REL>` and its matching project context plus `run.json`.

Frozen local table URIs may be `${KIPRJMOD}/` or canonical project-relative
paths (including bounded `../Libraries/...`), as produced by editing candidates.
Absolute/variable/URL/link/escaping/missing paths remain rejected. Any board or
footprint group is rejected with `GROUP_UNSUPPORTED`; inherited locks are not
modeled in v1. Native CLI/pcbnew stages use the matching PCB parent as their
validated/logged cwd to resolve relative tables; no table/source bytes are rewritten.

Only unlocked copper on authorized nets is removed **in the in-memory export
copy**. Other/locked copper is temporarily fixed for native export/import, then
its original locks are restored. The output cannot add, delete or alter copper
on protected nets. SES import can move footprints: live and saved/reloaded
invariants reject that rather than accepting router placement. There is **no
auto-placement algorithm**, generic edit dispatch, standalone SES-import CLI,
resume/rebind, cloud routing, bundle/export integration or class-based selection
facade in this extension. Final integration/allowlists belong to the integrator.
