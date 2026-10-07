# TraceMaker / 8bit — bounded CPU trial

**Verdict: one genuinely rebuilt signal net validated relative to the native baseline; broader copied-board routing rejected. NOT production sign-off or general admission.** Completed in workspace 304, only Sol Max; no advisors/subagents, commits, merge/push, production changes or fabrication exports. Prior pinned review: [kicad-tracemaker.md](kicad-tracemaker.md).

## Exact outcomes

All routing was ordinary `route` on frozen copies, **never `--reroute`**. Source SHA256: `e7e2987c6d4fe80e914160363cb04a598f151b704ecac2d5542f4059db44c4c7`.

| Experiment | Engine route | Native KiCad outcome | Verdict |
|---|---|---|---|
| Synthetic F/B SMD + PTH + separate via-required net | exit 0; 3/3 connections; 5 segments, 1 via (0.7/0.3 mm); 0.011114 s engine / 0.101 s external | opens 3 → 0; 0 active errors; same 2 existing nonmirrored-back-text warnings; raw and native-canonical preservation pass | Qualified this fixture, not all custom geometry |
| Unchanged 8bit | inspect: 24 footprints, 116 pads, 278 segments, 35 vias, 33 nets; engine DRC exit 0, no opens/violations; route exit 0, 0/0 connections, no new copper; 0.001444 s engine / 0.101 s external | 0 opens/parity; original 30 warnings; output **byte-identical** to source; native preservation pass | No-op qualification, **not routing achievement** |
| Real UDPI rebuild | remove 2 manifested segments; route exit 0, 1/1; emit 2 segments, 0 vias; 0.006654 s engine / 0.101 s external | stripped: 1 open; candidate: 0 opens/parity/active errors; **exact same 30 diagnostic identities**; all protections pass | Validated research candidate |
| Expanded UDPI/TX/MIDI/GATE_OUT | remove 36 segments, retain all 35 original vias; route exit 0, 6/6; emit 21 segments + 2 valid 0.7/0.3 mm TX vias; 5.789562 s engine / 5.821 s external | stripped: 8 opens + 2 dangling-via warnings; candidate: **1 TX open + 2 dangling original TX vias**, 0 parity findings; 32 warnings including original 30; geometry/rules still preserved | **REJECTED** |

Native DRC commands used JSON, `--severity-all --all-track-errors --schematic-parity --refill-zones --save-board --exit-code-violations` (parity omitted for the schematic-free synthetic fixture). Native CLI **exit 5 in every row**: baseline warnings alone cause nonzero exit; JSON identities/severities and opens, not exit 0, determine the relative verdict. No zones exist on 8bit.

Native baseline: 4 `silk_overlap`, 8 `silk_over_copper`, 18 `lib_footprint_mismatch` warnings, zero active errors/opens/parity. ERC independently reproduced **4 warnings + 16 already excluded errors**, not clean sign-off. Schematic/PCB ref-pin partitions match after deduplicating multiple physical pads with the same reference/pin. The pre-existing RESET `{slash}` versus `/` spelling remains untouched.

## Preservation and useful limits

Before native reload, every retained top-level raw node must match exactly: all footprint/pad definitions and nested UUIDs, original copper except specifically removed segments, net definitions, outline, graphics, setup, and the two net0 4/3.2 mm mounting-hole vias. Added copper must be on manifested nets, legal F/B layers and minimum dimensions; duplicate UUIDs are rejected. After native reload/save, canonical parsed-node comparison and full native inventory confirm transforms, sides, pad sizes/drills/layers/net membership, slots/custom primitives, outline and original vias. Project/schematic/library assets are unchanged; only native-derived `.kicad_prl` files appeared privately.

Both real candidates preserve all **24 footprints (22 F/2 B), 116 pads (81 SMD/35 PTH), all 35 original vias**, six custom/slotted anchors and two netted B.Cu graphic polygons. Rectangle edge centres remain X46.99..77.47, Y40.64..109.22: **30.48 × 68.58 mm**. pcbnew's bounding box includes the 0.05 mm outline stroke; that is not a size change. Pots, sockets and edge components did not move/flip/rotate. No rules were weakened. Default via diameter remains 0.6 mm in the unchanged project; emitted vias obey the native 0.7 mm minimum.

UDPI connects INPUT1 pin5 to R1 pin2. Its rebuilt two segments have fresh UUIDs and 0.2 mm width versus original 0.15 mm; length remains 4.729815 mm. Board totals: **278 segments / 35 vias**, 777.579374 mm segment length. This demonstrates actual routing, not an optimized new topology.

Expansion totals: **263 segments / 37 vias**, 763.138059 mm segment length. The remaining TX connection concerns original via `e6d7d2f7-5ce8-46c7-960f-7058698c8002` at (60.974966,80.528878); dangling vias are that via and `3fa8dbb6-c6f1-4dd8-a765-12076b794876` at (59.563,80.254). Route completion covered six planned connections but did not restore these retained copper islands. Crucially, **TraceMaker's separate post-route `drc` also exits 5 and finds one open/two violations**. Do not trust route exit 0. No hand repair or via deletion was used to disguise this failure. Two real routing trials only; no parameter sweep or wider expansion after rejection. The validated scope therefore stays UDPI only.

The pinned review's netted-polygon obstacle/net0 mismatch and unproved custom-geometry enforcement remain limitations. The unchanged board did **not** invent opens; the successful UDPI route does not establish correctness for every net near those features. A further focused trial could investigate reconnecting retained TX via islands, but general whole-board promotion is not justified.

## Build, confinement and provenance

Pinned clean upstream **`c5e1e8497ffef194206a012ee98f0ba156827f71`**, GCC 15.2.0 / CMake 4.2.3 / Ninja 1.13.2, native KiCad 10.0.6. CPU-only Release, tests/bindings off, **target `tracemaker` only**, four build jobs. Successful build 38.14 s. Initial configure failed because `/bin/sh` was absent from the sandbox; adding read-only `/bin` fixed it without changing upstream. Engine SHA256: `b469a1502f0f825aa431a7fbee57e19f1cc80f8bb940df7c17d295f81e0669fe`.

Dependencies were `apt-get download` + `dpkg-deb --extract` into ignored workspace-local `tracemaker-trial.tmp/`, never installed: Boost 1.90.0-6ubuntu1, Eigen 3.4.0-5, JSON 3.12.0.really.3.12.0.really.3.11.3-3build1, CLI11 2.6.1+ds-1, SQLite development/runtime 3.46.1-9ubuntu0.3, zstd development/runtime 1.5.7+dfsg-3. Ubuntu archive keyring `gpgv` verified InRelease signatures; uncompressed Packages SHA256/size matched signed metadata, then every downloaded .deb matched its package SHA256. Exact package origins, digests, signatures, compiler/build argv and failure/fix provenance are retained in `evidence/common/`. No maintainer scripts, sudo/global install, Docker, plugin, placement executable or upstream shell wrapper ran. No third-party engine/dependency sources or binaries are deliverables.

Build and runtime used tested `bwrap --unshare-all --die-with-parent --new-session --clearenv`: network unavailable (connect errno 101), host HOME/real repo absent, compiler/system libraries and sources/dependencies/input read-only. Trusted probes demonstrated denied writes for both actual mount plans. Engine mounts **only frozen project copy + private output** alongside read-only engine/dependencies/system runtime. Runtime options: `--no-gpu --no-kb --component-rules off --threads 1 --variants 1 --time 100 --seed 1`; UDPI alone additionally `--only-net UDPI`. External wall cap 120 s, per-process address-space 4 GiB, core disabled, CPU cap, per-file 16 MiB, aggregate output 64 MiB with polling, private tmpfs 32 MiB. Build used a 360 s wall cap, per-process 4 GiB / per-file 256 MiB / aggregate build-output 900 MiB. Limits are process/polled bounds, **not a system-wide cgroup guarantee/security certification**. No cap fired; actual engine routing total under 6 s. Downloads/build/logs stay ignored.

## Retained deliverables

- `opt/kicad-tools/tracemaker/`: small standalone preparation/CLI runner, native snapshot/judge and **18 passing unit tests**; no facade integration or changes to frozen router gates. [Usage](../opt/kicad-tools/tracemaker/README.md).
- `experiments/tracemaker-8bit/validated-udpi/`: NEW exact engine candidate plus unchanged project/schematic and only used local footprint files. Not a production replacement.
- `experiments/tracemaker-8bit/REJECTED-digital/`: labelled copied-board candidate for diagnosis only.
- `experiments/tracemaker-8bit/evidence/`: removal UUID/definition manifests, engine summaries/items/argv, native baseline/stripped/candidate DRC, native semantic inventories/comparisons, ERC/netlist check, signed-package/build/confinement provenance and original-node hashes. Roughly 2.25 MB including both project copies and overviews; no irrelevant standard libraries.
- Native front/back before/after plots and comparison image: [retained PNG](../experiments/tracemaker-8bit/overview/before-after-udpi.png); [shareable overview](/uploads/7993620d-795f-4268-8c43-088c1a36dc35.webp).

Earlier synthetic field-UUID generation and missing global-library context were harness qualification issues, fixed using a once-native-canonicalized fixture and a private read-only copy of existing KiCad config. Final baseline reproduces the actual 18 footprint mismatches, not missing-library warnings. Original module/library/global files remain unchanged. Parent/native-independent review remains the next approval boundary.

Parent-review preparation fix: shared existing-PCB-basename validation rejects absolute, traversal, nested and missing names before input reads/output creation. Locked or grouped selected segments are rejected before output creation. All 18 tests pass; no additional routing was run and all runtime scratch is retained until parent merge.
