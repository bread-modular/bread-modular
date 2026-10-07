# TraceMaker / KiCad — Phase 1 research

Current toolkit integration: [recommended hybrid recipe and native-format blocker](../opt/kicad-tools/HYBRID_ROUTING.md),
[optional CLI/bundle controller](../opt/kicad-tools/tracemaker/README.md).
This page is historical repository-only research/trial evidence, not relocated provisioning instructions.


Inspected 2026-10-07 in isolated workspace 303. **STOP for parent review.** Only this note and ignored `tracemaker-research.tmp/` were created. No downloaded code, installer, build, tests, plugin or routing ran; no global installs, advisors/delegation, commit/merge/push. No `modules/8bit` board was opened or modified; its inventory/constraints remain a separate handoff.

## Pin / evidence

- Live upstream: `https://github.com/DingoOz/TraceMaker`, inspected **`c5e1e8497ffef194206a012ee98f0ba156827f71`** (main, “Basic CI: CPU-only build and tests on push and pull request”). Project version 0.8.0; this is not the release tag. [source](https://github.com/DingoOz/TraceMaker/commit/c5e1e8497ffef194206a012ee98f0ba156827f71)
- **GPL-3.0-or-later**, plus NOTICE's CUDA linking permission; dependency licenses are separate. Keep the engine external, not copied/linked into our toolkit; review obligations before redistribution. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/NOTICE#L4-L29)
- **Verified locally:** pinned clean clone, static build/engine/I/O inspection, read-only native environment/package probes. **NOT verified:** compilation, test results, confinement, 8bit compatibility, routing/DRC success, runtime or memory. Upstream benchmark/test claims are not reproduced evidence for this module.

## Actual APIs / fixed-board fit

- Native file CLI: `tracemaker inspect BOARD [--json FILE]`; `tracemaker route BOARD -o OUTPUT [--json FILE] [--emit-items FILE]`; `tracemaker drc BOARD --json FILE`. No DSN/SES conversion is required. Same-stem adjacent `.kicad_pro` and `.kicad_dru` supply rules; **the router does not copy them to output**. Summary JSON includes routed/connections/tracks/vias/seconds/expansions/failures/variant; items JSON is `{tracks, vias}`, with named nets/layers and **nanometre** geometry. Exit 0 means only engine-counted completion; 3 means partial (output can still exist); exceptions return 1. No exit code certifies native DRC. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/route_job.cpp) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/route_job.hpp#L42-L47)
- Normal `route` adds segments/vias to the original lossless document and **never invokes placement**. It leaves footprints/XY/rotation/front-back, pad nets, outline, rules and zone definitions untouched. Existing copper stays; negotiated rip-up concerns generated routes. This is a source-backed design, **not a tested preservation guarantee**. `--reroute` separately removes **all unlocked segments/vias**, not selected-net copper (arcs/zones remain); require explicit copied-board authorization before enabling it. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/route_job.cpp#L94-L117) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/route_job.cpp#L275-L280)
- Documented board target: KiCad **9/10**; legacy parsing is also present, not a blanket version guarantee. **Two-sided/THT support is implemented:** F/B layers, plated holes on all copper layers, NPTH, correct-side SMD pads, and ordinary through vias. Actual engine: lattice A* with exact geometry checks, generated-route negotiation and a CPU path; not a cloud placer. Prove an opposite-side-SMD/PTH fixture first. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/README.md#L10-L16) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/io/kicad/board_reader.cpp#L314-L386)
- Separate placement CLI: `tracemaker-place BOARD -o OUTPUT --mode full|refine|auto|routable|eco`. It honors explicit locks and heuristic edge-connector freezing; `--flip` permits SMD side changes, while `--keep-side` does **not** fix XY/rotation. Do not infer pot/socket/edge intent from heuristics: for this task freeze **all footprints by routing only**. Python `read_board/route/emit_items/drc` bindings exist but expose fewer controls; the IPC plugin requires KiCad 10. Prefer an external CLI subprocess, not bindings/plugin installation. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/place/place_main.cpp#L579-L645) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/bindings/tracemaker_module.cpp#L230-L240)

## Important limits / security

- **Preserved syntax != enforced rules.** Missing/invalid projects can fall back to defaults/zero minima; unparseable custom-rule conditions are marked invalid and **ignored**, contrary to the design doc's blanket conservative-policy claim. Unknown board syntax/groups may round-trip without being modeled. Reject unproved active rules/geometry; native KiCad must be the referee. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/io/kicad/project_reader.cpp#L44-L77) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/drc/rule_engine.cpp#L300-L311)
- Edge.Cuts loops/cutouts are modeled, but **interior/cutout containment is disabled if any pad centre is outside** (edge-distance checks remain). Native preflight must establish a trusted outline; never alter real edge/connector placement to work around this. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/route/obstacles.cpp#L36-L88)
- Existing filled zones are used for copper/connectivity; CLI routing does not refill. Refill a private native candidate and recheck opens/DRC. Preserve zone **definitions/settings**, allowing only native-derived fills to change; completion before refill is not sufficient. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/io/kicad/board_reader.cpp#L573-L613)
- No required cloud/API or telemetry client was found in the inspected routing path/source scan; **not a security certification**. CLI defaults persist board/run/failure data in `$XDG_DATA_HOME/tracemaker` or `$HOME/.local/share/tracemaker` SQLite: use `--no-kb`. Optional viewer binds **0.0.0.0:8766**; omit viewer/record/hold. `--component-rules off` avoids synthetic classes/keepouts/sidecars. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/learn/knowledge_base.cpp#L46-L68) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/route_job.hpp#L25-L33)
- Reviewed bootstrap, all relevant CMake targets/presets/CI, catalogue embedding, fixture fetcher and Docker wrappers before execution. No CMake dependency downloader/installer found; custom command embeds local JSON. Bootstrap builds/tests and logs; fixtures download datasets and invoke Python; Docker wrapper mounts **entire HOME read-write**. Do not use these or plugin/npm acquisition. Placer `auto` builds shell commands from paths without escaping embedded apostrophes; schematic export also uses `system()`. Neither is needed by file routing. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/scripts/kicad-cli#L3-L11) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/place/place_main.cpp#L703-L722)

## 8bit handoff — concrete trial constraints and loss risks

Parent inventory received at the Phase 1 checkpoint (reported, **not independently opened here**): already fully routed, zero native opens; two layers, 24 fixed footprints (22 F / 2 B); 30.48 × 68.58 mm rectangle at X46.99..77.47 / Y40.64..109.22; 278 segments, 33 electrical vias 0.7/0.3 mm, plus **two net0 vias 4/3.2 mm used as mounting holes**; six slotted pot anchors/custom pads; two net-assigned B.Cu GRAPHIC polygons on V_SUPPLY/GND; **no zones**. Default via diameter 0.6 mm conflicts with the 0.7 mm board minimum. Native baseline warnings/parity details are pending; zero opens is not clean sign-off.

- **Actual destructive path:** `--reroute` deletes every unlocked via, filtering only by lock, not net or diameter. If unlocked, the two mounting-hole surrogate vias are deleted along with electrical vias. Do not use bulk `--reroute`, even as the default copied-board preparation; electrically routing again does not establish restoration of those mechanical objects. Normal append-only route retains their original raw nodes, but their geometry/clearance behavior remains untested. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/route_job.cpp#L100-L113)
- **Actual polygon semantic mismatch:** obstacle construction forcibly sets every copper `Graphic` item to **net0**, regardless of its assigned net. The writer normally retains original polygons, but the router treats them as netless obstacles rather than same-net copper. This risks false connectivity/blocked legal same-net paths around the V_SUPPLY/GND polygons; raw-file preservation alone cannot prove correct routing. Do not erase them or turn them into zones to make admission easier. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/route/obstacles.cpp#L15-L20)
- **Slots/custom pads:** reader branches recognize custom pads and oval drills; exact routing legality around these six anchors has not been demonstrated. Require unchanged original primitive/drill/slot nodes and native clearance/connectivity validation, not merely footprint counts or bounding boxes. No simplification of the anchor geometry.
- **Via rules:** retain the 0.7 mm minimum and original 0.7/0.3 electrical vias; do not lower the minimum to the 0.6 mm default or overwrite netclasses. Independently verify every newly emitted via against effective native rules.

**Practical next evaluation, only after parent approval:** first an unchanged-copy inspect/round-trip/no-op qualification, expecting zero newly required connections and unchanged protected geometry. That is preservation testing, **not a routing achievement**. If the engine invents opens/new work on this natively connected board, reject and diagnose its model rather than silently route them. Then use a separate disposable copy and trusted native preparation to remove only a small, explicitly authorized signal-net segment/via UUID set; preserve the two mechanical vias, all custom pads/polygons, all 24 placements and outline/rules. Use ordinary `route` without `--reroute`; reject additions outside the authorized net(s). Compare against the stripped-copy baseline and independently recheck the completed candidate. No exact UUIDs or safe trial net are invented here; require the inventory manifest and pending native findings first. Only if unusual geometry/effective rules are proved supported should a broader copied-board trial be considered. **Current verdict: conditional preservation/model qualification, not an admitted general 8bit routing run.**

## Build / local readiness

Actual configure requirements: Linux/C++20, CMake >=3.28, Ninja, Boost >=1.81, Eigen >=3.4, nlohmann/json >=3, CLI11, SQLite3, zstd, Threads; Catch2 >=3 for tests, optional pybind11 for bindings. Eigen is required even when building only `tracemaker`. README's TBB/fmt/spdlog/FlatBuffers list is not reflected in these CMake requirements. CPU-only preset exists. GPU defaults target CUDA architectures 60/70; README specifies CUDA 12.x and GCC 12/13 CUDA-host compiler. Do not assume the laptop GPU fits; use CPU initially. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/CMakeLists.txt) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/server/CMakeLists.txt) [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/place/CMakeLists.txt)

Local read-only probes: Ubuntu 26.04.1 x86_64; CLI/pcbnew **10.0.6** (pcbnew import printed three enum-choice assertion diagnostics); GCC 15.2, CMake 4.2.3, Ninja 1.13.2; 24 logical CPUs/~30 GiB RAM; RTX 5060 Laptop GPU/8151 MiB reported. Bubblewrap/timeout exist. **Boost/Eigen/JSON/CLI11/SQLite/zstd dev headers/packages absent** at probed system paths; Catch2/pybind11-dev absent too. Build remains untested. Parent must approve workspace-local dependencies or an isolated build environment; no global installs.

No local runtime/memory measurements. `--time` is per variant, so queued variants can multiply elapsed time; lattice/concurrency drive memory. Use one CPU variant/thread, external timeout and resource/output caps. `--work` permits deterministic-budget repeats, but wall-time guards remain: do not claim determinism if a guard fires. [source](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/src/app/main.cpp#L439-L491)

## Inspect / execution proposal — NOT EXECUTED

Already performed: hooks-disabled shallow clone, `git -C tracemaker-research.tmp rev-parse HEAD`, numbered static source reads, `kicad-cli --version`, `kicad-cli pcb drc --help`, native pcbnew version import and package/header probes. Clone is clean; no fetched executable/module loaded.

After parent approval, reverify the pin and provision reviewed dependencies. The following are **inner-sandbox argv**, not permission to run unconfined. Build sandbox exposes scratch source/build plus reviewed compiler/dependency libraries, **no boards/HOME**. Disable tests/bindings initially; no bootstrap/install target, fixture fetch, npm, Docker wrapper or plugin.

```sh
# $T = isolated pinned source mount; dependencies already available.
cmake --preset cpu-only -S "$T" -DTM_BUILD_TESTS=OFF -DTM_BUILD_PYTHON=OFF
cmake --build "$T/build/cpu-only" --target tracemaker --parallel 4

# First a synthetic F/B-SMD + PTH fixture; only then an approved 8bit snapshot.
# $PCB = exact validated relative PCB path from the separate inventory.
/engine/tracemaker inspect "/input/$PCB" --json /out/inspect.json
/engine/tracemaker route "/input/$PCB" -o "/out/$PCB" \
  --no-gpu --no-kb --component-rules off --threads 1 --variants 1 --time 60 \
  --json /out/route.json --emit-items /out/items.json
```

Proposed boundary: Bubblewrap `--unshare-all --die-with-parent --new-session --clearenv`; read-only engine/runtime + frozen complete input project, only NEW output/private tmp writable, no real HOME/repository/network. Process-group kill/timeout (initially 90 s), memory/core/file/output limits; prove denied source/host writes and network isolation before exposing the copied module. **TraceMaker confinement is not implemented/tested yet.** Fresh non-aliasing output; copy same-stem rules/project/schematic/libraries alongside output, omitting the target PCB. Never expose the live module. If input has no opens, default route is a no-op: stop for explicit copy-only `--reroute` approval.

Native judge on separate private baseline/candidate project copies, in each PCB-parent cwd; reports outside those projects:

```sh
kicad-cli pcb drc --format json --severity-all --all-track-errors \
  --schematic-parity --refill-zones --exit-code-violations \
  -o "$REPORTS/baseline.json" "$BASELINE/$PCB"
kicad-cli pcb drc --format json --severity-all --all-track-errors \
  --schematic-parity --refill-zones --save-board --exit-code-violations \
  -o "$REPORTS/candidate.json" "$CANDIDATE/$PCB"
```

Compare protected raw nodes **before** native reserialization and semantic invariants **after** refill: all footprint UUID/XY/rotation/side/locks/pads/nets, Edge.Cuts, original copper, zone definitions, rules/netclasses and project files. Record hashes, opens/findings, length/vias and runtime. Reduced opens with unchanged protections/no new violations is only partial research; final acceptance requires zero native opens/DRC/parity findings, never engine exit 0 alone. No automatic promotion.

## Recommendation / parent checkpoint

**Worth a bounded CPU file-routing trial, not a success promise.** If demonstrated, add only a small external-CLI controller at `opt/kicad-tools/tracemaker/`: pinned runtime selection, inspect/dry-run/explicit candidate execution, strict argv/output/timeouts and existing snapshot/hash/native-validation/reporting patterns. No new routing algorithm, imported engine code, placer, GUI integration or automatic downloads.

The existing facade delegates routing to sibling `opt/kicad-routing/run.py`; its DSN/SES admission rejects zones/keepouts/groups/complex rules. Do not force native TraceMaker through that conversion or silently relax its gates; the adapter needs its own proven admission subset. Shallow local evidence: [facade API](../opt/kicad-tools/API.md), [routing subset](../opt/kicad-routing/SUPPORTED_SUBSET.md), [sandbox contract](../opt/kicad-routing/SAFETY.md).

Parent review must settle dependency/confinement preparation and receive the immutable 8bit constraint manifest before Phase 2. **Only this note is a deliverable; leave uncommitted for parent integration.**
