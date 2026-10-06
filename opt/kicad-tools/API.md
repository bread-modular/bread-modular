# Facade API and candidate workflow

## Discover a task, not every detailed API

`python3 -B /path/opt/kicad-tools/kicad_tools.py --help` lists capabilities.
Use `pcb --help`, `schematic --help`, `route --help`, then the operation's help.
All five controllers (`pcb`, `schematic`, `route`, `export`, `assembly`) run in
**separate subprocesses**, with unchanged arguments, inherited stdout/stderr and
exact return codes. No import-time native/module-name collision or implicit
installation. A missing controller returns JSON and exit 2. `--` before delegate
arguments is stripped once, as before. Selection flags belong to each command,
not a shared global parser.

Standalone entrypoints still work: `automation/run.py`, `schematic/cli.py`,
`../kicad-routing/run.py`, `jlcpcb/{export,assembly}.py`. Python APIs are linked
below; no facade import is required. Quoted absolute paths work from any cwd,
including repository-free copied distributions.

## PCB edit → supported routing snapshot

Start from a complete independent project, not a live repository/released board.
Inspect actual UUID/ref/net/layer identities, then explicit operations JSON per
[PCB schema](automation/docs/api.md). Example: move an unlocked `J2` without
moving its traces, or add non-copper documentation text. Choose NEW candidates;
requests/plans must be outside source and dependency directories.

```sh
python3 -B /tool/opt/kicad-tools/kicad_tools.py pcb inspect --project-dir '/input/Bench A'
python3 -B /tool/opt/kicad-tools/kicad_tools.py pcb plan --project-dir '/input/Bench A' \
  --ops /requests/move.json --allow-draft-opens > /plans/edit.json
python3 -B /tool/opt/kicad-tools/kicad_tools.py pcb apply --plan /plans/edit.json \
  --output '/candidates/new placement'
```

Apply exit 0 = checked/accepted; **exit 1 can be an explicit opens-only draft**
or rejection. Read `result.json` and require `completion.json` before consuming
anything. A draft completion has `accepted: false`; it is not clean or fabrication
approval. Other findings, ERC, shorts/clearances or parity cannot be waived.

The complete candidate's `inputs/` subtree is the routing snapshot, **not** the
candidate root containing reports/runtime. `completion.json.board` is relative
to candidate root: remove its leading `inputs/` component to obtain `--pcb`.
Do not edit generated board/library tables/rules. Staging retains local context;
the router accepts canonical bounded relative and `${KIPRJMOD}` library URIs
and executes native commands in the actual PCB-parent cwd.

```sh
python3 -B /tool/opt/kicad-tools/kicad_tools.py route inspect-project \
  --snapshot '/candidates/new placement/inputs' --pcb 'Orchard Controller.kicad_pcb'
python3 -B /tool/opt/kicad-tools/kicad_tools.py route plan-project \
  --snapshot '/candidates/new placement/inputs' --pcb 'Orchard Controller.kicad_pcb' \
  --reroute-net DATA > /plans/routing.json
python3 -B /tool/opt/kicad-tools/kicad_tools.py route route-project \
  --snapshot '/candidates/new placement/inputs' --pcb 'Orchard Controller.kicad_pcb' \
  --plan /plans/routing.json --run-id reviewed-placement-001 --dry-run
python3 -B /tool/opt/kicad-tools/kicad_tools.py route route-project \
  --snapshot '/candidates/new placement/inputs' --pcb 'Orchard Controller.kicad_pcb' \
  --plan /plans/routing.json --run-id reviewed-placement-001 --route-timeout 120 --apply
```

Use the **actual** planned net authorization, not invented UUID/hash pairs.
[Supported subset](../kicad-routing/SUPPORTED_SUBSET.md) rejects groups, zones,
complex rules, unsupported pads/stackups and other unproved inputs; it does not
simplify or weaken them. [Router API](../kicad-routing/API.md) owns the gates.
Only explicit `prepare-runtime --allow-downloads` acquires the pinned runtime;
it is never bundled or acquired by inspect/plan/apply. Execution is offline in
Bubblewrap. New run output only: require immutable source, no locked/non-authorized
copper or placement/settings deltas, final native DRC/parity/opens zero and
physical review. Geometry operations are not live GUI push/shove; no automatic
placement, trace dragging or electrical/manufacturing approval.

## Separate flat schematic workflow

```sh
python3 -B /tool/opt/kicad-tools/kicad_tools.py schematic inspect --input /input/demo.kicad_sch
python3 -B /tool/opt/kicad-tools/kicad_tools.py schematic plan --input /input/demo.kicad_sch \
  --edits /requests/wires.json --output-dir /candidates/new-sheet > /plans/sheet.json
python3 -B /tool/opt/kicad-tools/kicad_tools.py schematic apply --plan /plans/sheet.json
```

Only explicit flat-sheet wire polylines, junctions and local labels are supported.
Review `result.json` exact pin/net changes, full before/after ERC and native
save/reload evidence. **Every result remains a schematic draft (`accepted: false`),
even exit 0. No PCB is loaded, copied or silently synchronized.** Explicit
PCB synchronization followed by DRC/parity is required before design acceptance.

## Python and verification links

| API | Entry / contract |
| --- | --- |
| PCB | `from automation import inspect, plan, apply, Error, validate` — [schema/API](automation/docs/api.md), [safety](automation/docs/safety.md) |
| Schematic | `from schematic import inspect_sheet, plan_edits, apply_plan, strict_json` — [API/safety](schematic/docs/api.md) |
| Native identity / closure | `native.py`, `project.py` — [guide](GUIDE.md) |
| Assembly / export | Existing [assembly APIs](jlcpcb/ASSEMBLY.md), [exporter](jlcpcb/README.md); own output/network policies unchanged |
| Real CLI integration | [Synthetic handoff runner](tests/native_handoff.py), [exact results](VERIFICATION.md) |

Add the **copied** `opt/kicad-tools` to `sys.path`; PCB/schematic APIs share the
core helpers but keep native workers subprocess-isolated. Run each test suite
in a separate process: their `fixtures`/`native` module names are not a combined
in-process discovery contract. Never enable shared all-native discovery; only
its two named synthetic methods are authorized by toolkit native tests.
