# KiCad routing research — Phase 1

**Observed:** 2026-10-06. **Scope:** research and proposal only; no routing implementation or board edits.

**Workspace:** `294`, branch `okbrain/bread-modular-kicad/294-074a1213`, based on `main` at `0c273499ec86fa5b7abcd278f0e9c486a4305806`. At inspection, `HEAD`, `main`, and their merge-base were identical and the working tree was clean. All repository inspection stayed in this workspace. No advisors or delegated chats were used.

## Decision

Reuse **KiCad's native interactive router for critical nets**, with **optional local Freerouting through KiCad's native DSN/SES bindings** for ordinary remaining connections. Do not implement a maze router, a KiCad file converter, or a cloud service. Keep routing separate from the existing production exporter and the core worker's thin dispatcher/config/bundle work.

Three actual alternatives are compared below: KiCad native routing, Freerouting, and Topola. The official Freerouting plugin is examined as an integration example, not counted as a separate routing engine. External tools were researched from upstream docs/source; **none were installed or executed**. Local CLI help and Python binding introspection were exercised, but **DSN export, SES import, and a complete routing round-trip have not been executed**. Those are explicitly next-phase synthetic-board tests.

## 1. Evidence and local capabilities

### Installed host: tested versus documented

These are local observations, not assumptions about another workstation:

| Capability | Local result | Verification level |
|---|---|---|
| KiCad CLI | `/usr/bin/kicad-cli --version` → `10.0.6`; package `10.0.6~ubuntu26.04.1` | Executed version/help only |
| PCB Editor | `/usr/bin/pcbnew` exists | Executable discovered; GUI not opened |
| System Python | `/usr/bin/python3 --version` → `3.14.4` | Executed; use this interpreter, not an unrelated venv |
| Native Python bindings | `import pcbnew` succeeds; module `/usr/lib/python3/dist-packages/pcbnew.py`; build `10.0.6-10.0.6~ubuntu26.04.1` | Import/introspection executed |
| DSN export | `ExportSpecctraDSN(BOARD aBoard, wxString aFullFilename) -> bool`, plus one-argument active-editor overload | Symbol/docstring verified; export itself **not run** |
| SES import | `ImportSpecctraSES(BOARD aBoard, wxString aFullFilename) -> bool`, plus one-argument active-editor overload | Symbol/docstring verified; import itself **not run** |
| Project-aware loading/saving | `GetSettingsManager`, `LoadBoard`, `SaveBoard(filename, board, aSkipSettings=False)`, `ZONE_FILLER` present | Symbols verified; no design loaded/saved |
| CLI DSN/SES | `pcb export --help` has no DSN exporter; `pcb import --help` is foreign-board conversion, listing auto/pads/altium/eagle/cadstar/fabmaster/pcad/solidworks, not SES session merging | Actual installed help inspected; do not invent `kicad-cli pcb export dsn` or SES-import commands |
| CLI DRC | Help exposes JSON, `--all-track-errors`, `--schematic-parity`, `--severity-all`, `--severity-exclusions`, `--exit-code-violations`, `--refill-zones`, `--save-board` | Flags verified; DRC **not run** on any board this phase |
| Interactive router Python API | No `PNS*` or `*Router*` symbols found in `dir(pcbnew)` | No exposed push-and-shove scripting interface found; adding `PCB_TRACK` is not invoking that router |
| Java/Freerouting | No `java`, `javac`, or `freerouting` on PATH; no `/usr/lib/jvm` runtime found | Discovery only; no system-wide exhaustive search or installation |
| Other runtimes/integrations | No `cargo`, `rustc`, `kipy`, `kibot`, or `pcbnew_do` found | No Topola toolchain or IPC Python package assumed |
| Offline sandbox | Installed `bubblewrap 0.11.1`; `bwrap --unshare-net ... /usr/bin/true` returned 0 with `/usr`, `/lib`, `/lib64` read-only | Network-namespace launch of installed `true` tested; Java/board access/egress behavior still needs verification |

**Binding warning:** importing `pcbnew` emitted three `PROPERTY_ENUM(): No enum choices defined` assertions on stderr, despite exiting successfully and returning the expected symbols/version. This is a compatibility warning to retain in evidence, not proof that export/import fails or works. Standalone synthetic I/O must establish whether it remains usable with this Python/KiCad build.

**Sandbox nuance:** `unshare -Urn -- true` failed with an unprivileged UID-map permission error, whereas the installed Bubblewrap network-isolation probe succeeded. Use the verified Bubblewrap path for the proposed offline test; do not assume direct `unshare` is available or request privileged/global changes.

### Existing repository routing-related scripts: inspected, not executed

- `modules/base/tools/apply_power_layout.py`: explicit `PCB_TRACK`/`PCB_VIA` coordinate insertion, SHA-256 pre-upgrade input guard, explicit `.kicad_pro` loading and a clearance assertion, repeated slot routes, and zone refill/save. It is a board-specific historical layout migration, **not a general autorouter**.
- `modules/16bit-5v/tools/finalize_pcb.py`: one-shot historical migration guarded against an exact original board; bounded J5/power/ground changes. `modules/32bit-5v/tools/finalize_pcb.py` is similarly identified as a historical bounded migration. Do not repurpose these to reroute reviewed boards.
- `modules/16bit-5v/tools/apply_review_layout.py`: explicitly disabled replay of a historical partial layout. Its message points to the canonical saved PCB as authority.
- `modules/base/tools/reroute_mux_select_vbus_prot.py`: despite its name, a **schematic-only** migration, with before/after netlist/ERC identity checks; not a PCB router.
- `modules/base/tools/freeze_release.py`: useful validation patterns—native pad/pin net parity, immutable mechanical geometry, project-rule/severity checks, no new exclusions, saved-board DRC. It also writes release evidence and must **not** be invoked for routing experiments.
- `opt/kicad-jlcpcb/export.py` and `add_production_files.py`: production/export tooling, not routing. Leave them unchanged and do not invoke them during a routing smoke test.

A tracked-script search for `freerout`, `autorout`, `specctra`, `ExportSpecctra`, and `ImportSpecctra` found no existing DSN/SES integration. `ts-modules` is absent at this `main` baseline; inherited tscircuit trick titles are not evidence of an available KiCad implementation here.

## 2. Three reusable upstream alternatives

### A. KiCad native interactive routing / critical-net-first workflow

- **Project and license:** KiCad's program is principally **GPL-3.0-or-later**, with separately licensed third-party components; official libraries and documentation have different licenses. Do not conflate the library license with the router/program license. The installed Debian copyright file contains old GPLv2-era material; use the current official licensing statement and source notices for reuse decisions. [source](https://www.kicad.org/about/licenses/)
- **Activity observed 2026-10-06:** the official release announcement verifies **10.0.6**, published **2026-08-29**, matching the installed CLI. This is observed maintenance evidence, not a forecast of another release. [source](https://www.kicad.org/blog/2026/08/KiCad-10.0.6-Release/)
- **Constraints:** native GUI routing needs KiCad, not Java or Python. Automation proposed here uses the matching system `pcbnew` binding. KiCad's official developer docs say SWIG bindings are unstable/deprecated as of 9.0, with removal *planned* for 11.0; that is a stated plan, **not an observed released version**. Isolate the adapter rather than build an entire toolkit around SWIG internals. [source](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/)
- **Workflow:** Shove moves movable obstacles while walking around pads/locked copper; Walk Around leaves neighboring copper unmoved. Native differential-pair routing and length/skew tuning are available. The 9.0 manual also documents `Attempt Finish` and `Attempt Finish Selected`: limited connection completion on the **current layer**, without automatically adding vias/changing layers. These are documented GUI features, not a tested batch-routing command on this host. [source](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html#routing-tracks)
- **Offline/cloud:** routing and DRC operate locally on the installed project; no routing-service upload is required. Library/plugin downloads are separate optional acquisition steps.
- **Strengths:** keeps KiCad's full project/rule context; good control of analog feedback, supply loops, decoupling, differential pairs, return paths, and connector escapes. Best default for the sensitive parts of these synth boards.
- **Limits:** not an unattended whole-board multi-layer autorouter; good placement and engineering decisions still come from the designer. The official manual says some violations cannot be prevented during routing, hence full DRC is still required. [source](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html#design-rule-checking)

### B. Freerouting — local DSN → SES, optionally through its KiCad plugin

- **Project and license:** `freerouting/freerouting`, **GPL-3.0**, verified from the pinned tag's actual `LICENSE`, not just a badge. This proposal runs an unmodified separate program; it does not copy the GPL router or plugin code into this repository. Any later redistribution/derived-code reuse needs its own license/notice review. [source](https://github.com/freerouting/freerouting/blob/v2.5.0/LICENSE)
- **Activity observed 2026-10-06:** GitHub's live release API identifies **v2.5.0**, published **2026-10-05T15:58:39Z**, non-draft/non-prerelease; commit `b647a2f824cfbc54bc4dcaee71b03b7cd945eb76` prepared that release. The fetched releases HTML initially showed 2.4.1; API/tag verification superseded that stale listing. No unverified future version is recommended. [source](https://api.github.com/repos/freerouting/freerouting/releases/latest) [source](https://github.com/freerouting/freerouting/releases/tag/v2.5.0)
- **Constraints:** JAR path requires **Java 25**, verified in tag README and build target; core routing requires no Python. Our Python need is only KiCad's native adapter. The plugin documents KiCad 6+ installation and standard DSN mode; that broad upstream claim is not proof of this host's round-trip compatibility. [source](https://github.com/freerouting/freerouting/blob/v2.5.0/README.md) [source](https://github.com/freerouting/freerouting/blob/v2.5.0/build.gradle) [source](https://github.com/freerouting/freerouting/blob/v2.5.0/integrations/KiCad/README.md)
- **New local alternative inside this same project:** v2.5.0 also publishes GraalVM native CLI binaries, documented as JRE-free. Release assets include a Linux x64 CLI archive. These are **not downloaded or tested**; do not confuse documented availability with installed capability. Prefer the explicitly pinned Java+JAR pair for the first smoke test, with native CLI as a later optional backend. [source](https://github.com/freerouting/freerouting/releases/tag/v2.5.0)
- **Workflow:** standard KiCad DSN export → local Freerouting `-de input.dsn -do result.ses` → native SES import into the **same snapshot** → refill/DRC/review. The official plugin's source already demonstrates both one-argument editor-bound and two-argument board-bound `ExportSpecctraDSN` / `ImportSpecctraSES`; reuse this pattern, not a new file translator. Do not use the optional “remove existing tracks/vias” step on reviewed designs. [source](https://github.com/freerouting/freerouting/blob/v2.5.0/integrations/KiCad/kicad-freerouting/plugins/router_dsn.py)
- **Offline/cloud:** a local CLI/JAR computes locally; hosted REST/MCP workflows upload designs and are not part of this recommendation. Telemetry is a separate concern: CLI documents `-da`; source exposes `usage_and_diagnostic_data.disable_analytics`. Set both explicit opt-out and a network-denying sandbox, with API/MCP servers disabled. “Headless” or “local” alone is not proof of no network traffic. [source](https://github.com/freerouting/freerouting/blob/v2.5.0/docs/command_line_arguments.md) [source](https://github.com/freerouting/freerouting/blob/v2.5.0/src/main/java/app/freerouting/settings/UsageAndDiagnosticDataSettings.java)
- **Strengths:** existing DSN/SES interoperability, multi-layer remaining-net routing, local GUI/CLI operation, configurable routing/optimization, and upstream regression fixtures. Avoids creating our own routing algorithm.
- **Limits:** DSN is not a lossless representation of every KiCad design rule, mask/assembly property, zone behavior, or electrical intent. Board-edge clearance is a known export gap; upstream documents a router-side `--router.copperToEdgeClearanceUm` override. Mirror the existing rule, never lower it. Native KiCad DRC remains authority. [source](https://github.com/freerouting/freerouting/releases/tag/v2.4.1)
- **Version-specific care:** 2.5 documents nested `--router.autorouter.max_passes`; old flat pass settings remain deprecated aliases. Do not paste old tutorial optimizer/thread flags without checking the selected tag's help/settings. Published benchmark/performance claims are upstream measurements, **not this repository's validated results**. [source](https://github.com/freerouting/freerouting/blob/v2.5.0/docs/settings.md)

### C. Topola — independent Rust topological router, experimental comparison

- **Project and license:** canonical repository `codeberg.org/topola/topola`, with an official GitHub mirror. **MIT**, verified from `LICENSES/MIT.txt` and SPDX/source notices at commit `666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb`. Assets are MIT/CC-BY-4.0 dual-licensed; one math file is MIT/Apache-2.0 dual-licensed. GitHub's API returned `license: null`; the actual license files, not that missing detection, establish the license. [source](https://github.com/mikwielgus/topola/blob/666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb/README.md) [source](https://github.com/mikwielgus/topola/blob/666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb/LICENSES/MIT.txt)
- **Activity observed 2026-10-06:** canonical Codeberg and mirror commit queries agreed on the above `develop` tip (mirror committer timestamp **2026-07-01T23:09:03Z**). A **2026-08-31** upstream update says development continues, but performance-driven architectural overhaul prevented the first release. The queried GitHub releases list was empty. Do not call Cargo's `0.1.0` package field a verified stable release. [source](https://codeberg.org/api/v1/repos/topola/topola/commits?limit=3) [source](https://github.com/mikwielgus/topola/commit/666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb) [source](https://topola.dev/blog/2026/08/31/2026-ngi0-commons-grant/)
- **Constraints:** builds with Rust/Cargo, not Java/Python; manifest uses Rust edition 2021 but declares no `rust-version` minimum, so a supported minimum toolchain was **not verified**. Official installation docs describe source builds and a KiCad THT diode-bridge DSN/SES example. No certified KiCad 10 version matrix was found, and Cargo/Rust are absent here. [source](https://github.com/mikwielgus/topola/blob/666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb/Cargo.toml) [source](https://github.com/mikwielgus/topola/blob/666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb/INSTALL.md)
- **Workflow:** CLI reads DSN and writes SES, with explicit output and command-history options; the official docs demonstrate import back into KiCad. It is real implemented interoperability, not just a paper algorithm, but it was not built/run here. [source](https://github.com/mikwielgus/topola/blob/666e06cfd7ba1f1e5daf700288acb9e0a4f84ceb/crates/topola-cli/src/cli.rs) [source](https://topola.dev/blog/2024/07/20/junejuly-2024-development-update/)
- **Offline/cloud:** native CLI is a local file workflow after building dependencies. A hosted browser application exists, but this phase did not audit its requests/storage or establish a confidential-board privacy guarantee. Prefer native/self-hosted evaluation rather than sending project designs to the hosted app. [source](https://topola.dev/)
- **Strengths:** independent open algorithm, permissive source license, any-angle/rubberband approach, GUI/CLI and replayable command history; useful research comparison if native-routing quality warrants future study.
- **Limits:** explicitly work in progress, no stable release verified, additional toolchain/build burden, and no demonstrated full-rule/differential-pair/plane/locked-copper parity on this host. Single-layer upstream examples do not prove production-grade multi-layer capability. **Not the minimal integration choice.**

## 3. How designers combine manual and optional automatic routing

A documented practical pattern is placement first, manual routing of critical tracks, then an optional autorouter pass and hand-tuning—not delegating electrical layout intent to completion percentage. Hackaday's KiCad/Freerouting walkthrough explicitly recommends manually laying out critical tracks first and refining the result afterward. [source](https://hackaday.com/2023/04/14/kicad-autorouting-made-easy/)

For these modules, apply that pattern as engineering policy:

1. Establish schematic/PCB parity, manufacturer rules, stackup, mechanical anchors, connector/pot orientation, and placement before routing. Placement improvements usually beat trying to route an unsuitable placement indefinitely.
2. Route sensitive paths natively: supply/decoupler loops and current-carrying trunks; op-amp feedback and high-impedance nodes; noise-sensitive analog paths/ground topology; clocks and USB/differential paths where applicable. Review return paths and topology, not just trace lengths.
3. Lock approved tracks/vias in the **routing snapshot**, preserve reviewed placement, then optionally route ordinary remaining signals. An ignored net class is not automatically an immutable geometry guarantee.
4. Import only into the corresponding snapshot, inspect the delta, refill zones, run native DRC/parity, then manually fix/review remaining issues. Any change to placement/netlist/rules invalidates the old DSN/SES pair.

### Critical native interchange behavior: verified source, not yet runtime-tested

KiCad **10.0.6** source exports locked tracks/vias as Specctra `type fix`; unlocked copper is `type route`. Its SES importer **deletes/replaces old unlocked tracks and vias while retaining/re-adding locked ones**. It can also apply SES placement data to footprints. Thus SES import is **not merely append-only**, and a lock is not a substitute for a placement invariant check. [source](https://github.com/KiCad/kicad-source-mirror/blob/10.0.6/pcbnew/specctra_import_export/specctra_export.cpp#L1619) [source](https://github.com/KiCad/kicad-source-mirror/blob/10.0.6/pcbnew/specctra_import_export/specctra_import.cpp#L364)

The source also exports netclass rules, zones as planes, and specific keepouts, but that is not evidence that arbitrary `.kicad_dru` conditions or all native pad/zone/clearance overrides survive. Treat DSN as a routing view of the original project, never as the new authority for project rules. [source](https://github.com/KiCad/kicad-source-mirror/blob/10.0.6/pcbnew/specctra_import_export/specctra_export.cpp)

## 4. Preservation and acceptance gates

These gates are proposed for implementation, not claims that boards have passed:

| Preserve/check | Required method |
|---|---|
| Input immutability | Hash source PCB, schematic hierarchy, `.kicad_pro`, `.kicad_dru`, library tables and relevant local footprints. Refuse stale source/DSN/session linkage; never import into an evolving source board. |
| Project context | Keep the **same project basename** in separate before/after directories with all companion files; load its `.kicad_pro` into the native board as needed. Assert actual clearances, netclass assignments, widths/via dimensions before export. A bare PCB loaded under default project settings is not sufficient. |
| Rules and exclusions | Require original project/custom-rule hashes and severity/exclusion settings unchanged. Reject unsupported constraints rather than weakening rules or applying new waivers. Router settings may mirror an existing edge clearance, not alter it. |
| Placement/mechanics | Compare every footprint UUID/ref, anchor X/Y, rotation, side, pad number/position/shape/drill/layers, outline/cutouts, mounting holes, and origins. Reject unexpected SES placement or pad changes. |
| Net parity | Compare complete `(reference, pad number) → net name` mapping and schematic netlist nodes before/after, including duplicated physical pads. Compare names/membership rather than unstable numeric net codes. Run native schematic-parity DRC; a schematic-free fixture must not claim parity proof. |
| Approved critical copper | Snapshot locked geometry/width/net/layer/via drill/span and UUIDs; require unchanged critical copper and no new branches/stubs on protected nets. Test retained `type fix` behavior explicitly. |
| Zones/keepouts | Preserve zone definitions/nets/layers/priorities/thermal settings and keepouts. Refill after import; filled polygons may legitimately change. Inspect plane connectivity, islands, necks and thermals after refill. Do not replace KiCad zones with autorouter plane polygons. |
| DRC before/after | Use installed native JSON DRC with all severities/exclusions, all-track errors, schematic parity and fresh zone fills. Initial planned opens are expected; other initial errors/parity mismatches block routing. Afterward require zero opens, parity findings and errors, and no new unexplained warnings/exclusions. Parse JSON findings; do not equate a process exit code or an SES file with correctness. |
| Quality/production | Review total wirelength/via count, current/thermal margins, noise/return paths, pair coupling/skew/impedance, assembly/mechanical constraints, then human review and later bench/manufacturing signoff. **Autorouter success != production readiness; even zero DRC is not electrical or production certification.** |

Native netclass width/gap settings can be routing defaults rather than enforced DRC bounds. Do not assume DRC proves a netclass's intended current capacity or pair geometry merely because no violation was emitted. This phase makes no rule changes. [source](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html#board-setup-net-classes)

## 5. Exact minimal local integration proposal — next phase only

### Ownership and interface

Add only `opt/kicad-routing/` when the next task authorizes implementation. Proposed files are a small `run.py`, a native `pcbnew_adapter.py`, a README, and synthetic-fixture/tests under that directory. Do not edit the core worker's dispatcher/config/export modules or existing module tools. Expose a read-only `doctor` and a bounded `smoke` operation producing a JSON run manifest; a dispatcher can invoke those later without taking ownership of the routing algorithm.

The adapter should use native **two-argument** `ExportSpecctraDSN(board, filename)` / `ImportSpecctraSES(board, filename)` after project-aware load. Do not fall back to editor-bound overloads in headless code, hand-generate production DSN, or write a custom SES merger. Fail closed if the installed API is unavailable or native I/O fails. Save only the isolated candidate, skipping project-settings rewrites and then verifying companion-file hashes.

Keep runtime archives/JAR/extraction, configs, logs and generated boards under an ignored workspace-local directory, e.g. `.kicad-routing-research.tmp/runtime/` and `.kicad-routing-research.tmp/runs/`. The existing `*.tmp` ignore rule covers this directory; no `.gitignore` edit is needed. No global package/plugin installation, changes to Java alternatives/PATH, source builds, or third-party binaries in tracked files.

### Verified artifact pins (metadata/license verification only)

Use explicit URLs/hashes, **not `latest` download URLs**:

| Artifact | Pin and provenance |
|---|---|
| Freerouting JAR | `freerouting-2.5.0.jar`; release asset SHA-256 `f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7`; release published 2026-10-05. [source](https://api.github.com/repos/freerouting/freerouting/releases/tags/v2.5.0) |
| Download URL | `https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar` |
| Local JRE | Eclipse Temurin Linux x64 HotSpot **25.0.4.1+1**, `OpenJDK25U-jre_x64_linux_hotspot_25.0.4.1_1.tar.gz`; Adoptium API and GitHub asset digest agree on SHA-256 `1731a34baadec5479258ea0202e4d5d865d2efeee60cb0c7d7eb056fe96ca219`. Release published 2026-08-19; selected asset updated 2026-08-21. Host architecture verified `x86_64`. [source](https://api.adoptium.net/v3/assets/latest/25/hotspot?architecture=x64&image_type=jre&os=linux&vendor=eclipse) [source](https://api.github.com/repos/adoptium/temurin25-binaries/releases/tags/jdk-25.0.4.1%2B1) |
| Download URL | `https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jre_x64_linux_hotspot_25.0.4.1_1.tar.gz` |
| JRE license | Adoptium states **GPLv2 with Classpath Exception**, subject to included notices/licenses. Verify the actual extracted `legal/`, license/notice files and archive contents before execution in Phase 2. [source](https://adoptium.net/docs/faq#is-eclipse-temurin-free-to-use) |

**No bytes of either executable artifact were downloaded or hashed locally in Phase 1.** These checksums are verified upstream metadata, not proof of an already-verified local download. Phase 2 must hash the downloaded bytes, validate archive paths/symlinks before extraction, retain license/provenance records, and invoke the extracted Java by absolute workspace-local path. A checksum from the same upstream improves pinning/reproducibility; it is not an independent security audit.

### Synthetic fixture and execution contract

Create a new, isolated **40 × 30 mm, two-copper-layer** project, not a stripped/copy-derived released board. Use two ordinary 1×04 pinheaders with four nets: `CRITICAL`, crossing `SIG_A`/`SIG_B`, and `GND`. Seed one approved locked critical connection, a bottom GND zone and a small keepout. Include a matching schematic and same-stem project/custom-rule files. Define fixture-only constraints once (proposed 0.20 mm clearance, 0.25 mm signal track, 0.60/0.30 mm through via, 0.50 mm copper-to-edge); freeze those files throughout the round-trip. These numbers are test-fixture inputs, not recommendations or changes to production rules.

The `smoke` contract is:

1. Require a known synthetic-fixture identity and workspace-local run paths. Reject `modules/`, production packages, symlink escapes, and arbitrary real-board inputs. Acquire/hash/pin runtime artifacts in a separate preparation step; **no network during routing**.
2. Preserve `before/synthetic.*` and `after/synthetic.*` with identical project basenames/companions. Capture invariants, refill/save the **synthetic copy**, run pre-DRC/parity and export DSN using native APIs. Inspect exported nets/classes/layers/widths/vias/keepouts/`type fix` against the fixture's actual project rules.
3. Run bounded local Freerouting, with no hosted API/SDK/agent dependency. Candidate command shape, to be checked against the selected executable's actual help/effective settings before routing:

   ```sh
   "$LOCAL_JRE/bin/java" -jar "$LOCAL_RUNTIME/freerouting-2.5.0.jar" \
     -de "$RUN/input.dsn" -do "$RUN/result.ses" -da \
     --gui.enabled=false --api_server.enabled=false --mcp_server.enabled=false \
     --usage_and_diagnostic_data.disable_analytics=true \
     --user_data_path="$RUN/freerouting-config" \
     --router.autorouter.max_passes=10 \
     --router.optimizer.enabled=false --router.fanout.enabled=false \
     --router.copperToEdgeClearanceUm=500
   ```

   Initial tests disable fanout/optimization to minimize moving parts; enable them only in separately evidenced follow-up experiments. `500` mirrors the proposed fixture's 0.50 mm edge rule, not an override for real boards. Impose a 120-second subprocess timeout, bounded memory/log sizes, and a clean per-run config/environment. Check that all flags are accepted; fail rather than silently ignore unknown settings. Canonical settings and telemetry options are documented but **this exact invocation is not yet runtime-tested**. [source](https://github.com/freerouting/freerouting/blob/v2.5.0/docs/settings.md) [source](https://github.com/freerouting/freerouting/blob/v2.5.0/docs/command_line_arguments.md)

4. Wrap execution in installed Bubblewrap with `--unshare-net`, runtime/system libraries read-only, and only this run directory writable. Use run-local HOME/XDG/TMP/JVM temporary paths; hide global user config and do not expose other workspaces. Verify network denial and telemetry opt-out/effective settings before allowing a routing job. Do not treat `-da` alone as an offline guarantee.
5. Import the resulting SES into an in-memory board from the **same exported snapshot**. Verify placement/rules/nets/critical geometry before saving an isolated `after/synthetic.kicad_pcb`. Refill/save it and run post-DRC with native schematic parity:

   ```sh
   kicad-cli pcb drc --format json --severity-all --all-track-errors \
     --schematic-parity --refill-zones --save-board \
     --exit-code-violations -o "$RUN/after/drc.json" \
     "$RUN/after/synthetic.kicad_pcb"
   ```

   The initial report uses the same checks, but planned unrouted connections are classified separately from infrastructure/DRC/parity failures. `--save-board` is used **only on synthetic copies**, never source/released boards. Reload the saved candidate before invariant checks so evidence describes disk state, not just a transient in-memory fill.
6. Emit `run.json`: artifact URL/version/hash/license provenance, KiCad/Python versions, commands/effective settings, input/DSN/SES/candidate hashes, before/after native DRC findings, invariant deltas, via count/wirelength, sandbox status, elapsed time and failure reason. Mark success only when the fixture is connected, native DRC/parity passes, critical copper/placement/rules remain unchanged and no new exclusions appear. Never mark manufacture/order approval.

Test negative cases as part of that small harness: mismatched/stale session input, changed placement or pad-net mapping, weakened rule/severity, missing runtime/API, malformed/empty SES, subprocess timeout, and source-path/symlink escape. Failed runs must leave the source fixture untouched and retain diagnostic evidence. No production exports/bundles are generated by this adapter.

## 6. Blockers, uncertainties and stopping point

- **Runtime absent:** Java/Freerouting are not installed. Trusted upstream pins/licenses/checksum metadata are available for a later workspace-local download; local byte hashes, extracted runtime notices and startup compatibility remain untested.
- **Native I/O not exercised:** binding presence and upstream source inspection establish a plausible integration, not a working round-trip. The import assertions must be checked on a synthetic project; native export/import booleans, emitted DSN rules and saved candidate behavior are acceptance gates.
- **Rule/zone translation limits:** no blanket KiCad `.kicad_dru`, copper-plane, differential-pair or pad-override parity claim. Complex production boards require explicit supported-rule evidence and engineering review before any future opt-in.
- **Offline execution:** Bubblewrap network-namespace launch succeeded for installed `true`, but the scoped Java sandbox, actual network denial, run-local writes and telemetry behavior still require synthetic testing. Refuse online fallback if that cannot be established.
- **Alternative maturity:** Topola is implemented but unreleased/WIP; native Freerouting CLI and modern IPC integration are newly documented in the observed release. Neither is silently substituted for the pinned JAR/native-DSN smoke path.
- **Phase boundary:** this phase changes only `docs/kicad-routing-research.md` as a reviewable repository edit. Inert source/metadata research excerpts are ignored workspace-local evidence, not vendored dependencies. No boards/rules/production files were changed, no external downloads were executed, and no commit/merge/push was made. Await the next task before implementing `opt/kicad-routing/`.
