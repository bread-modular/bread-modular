# TraceMaker / 8bit — final bounded CPU trial

**Final best scope: 10 explicitly selected signal nets genuinely rebuilt and independently native-validated relative to the original baseline. NOT full-board routing, production sign-off or general engine admission.** Final trial on base `4ae33a93` in isolated workspace 305, Sol Max only; no advisor/subagents, commit/merge/push, production modification or fabrication export. Two new ordinary routing experiments, no tuning sweep, upstream patches, hand routing, component movement or dangerous `--reroute`. [Pinned upstream review and unsupported cases](kicad-tracemaker.md).

Original PCB SHA256: `e7e2987c6d4fe80e914160363cb04a598f151b704ecac2d5542f4059db44c4c7`. New original complete same-stem source copy is retained, **unaltered**, in `experiments/tracemaker-8bit/evidence/final/original/`. Engine-written candidates are also retained **before native reload/save**, not replaced with native rewrites.

## Final experiments and comparison

| Scope | Exact preparation | Engine route / external runtime | Native KiCad | Board totals: segments / vias / segment length |
|---|---|---|---|---|
| Original | No modification | Independent engine DRC exit 0 | 0 opens/active errors/parity; 30 original warnings | 278 / 35 / 777.579374 mm |
| New digital: **4 nets** | Remove 36 exact segments + **only two authorized TX electrical vias** | exit 0, 6/6; 21 segments + 2 vias; 3.032589 s / 3.113 s | stripped opens **6 → 0**; exactly the same 30 diagnostic identities; separate engine DRC exit 0 | 263 / 35 / 763.138059 mm |
| New broader signals: **10 nets** | Remove 72 exact segments + 6 enumerated electrical vias | exit 0, 15/15; 52 segments + 5 vias; 3.777542 s / 3.815 s | stripped opens **15 → 0**; exactly the same 30 diagnostic identities; separate engine DRC exit 0 | 258 / 34 / 750.331497 mm |

**Best retained candidate:** [`validated-signals/8bit.kicad_pcb`](../experiments/tracemaker-8bit/validated-signals/8bit.kicad_pcb); SHA256 `dd34315b8613d719c641e62f2951ac551eea98b350a15007066ef62da23285f4`. Segment length decreases **27.247877 mm (3.504%)**, with one fewer via; this is a measured comparison, not proof of global optimization or signal-integrity improvement.

The four-net candidate remains separately retained as [`validated-digital/`](../experiments/tracemaker-8bit/validated-digital/), SHA256 `83b481a9d9af69e19a4b0253e2054b6ef986122b7783b8b3dbecab12165481ce`.

Exact broader authorization: **UDPI, TX, MIDI, GATE_OUT, CV1, CV2, AUDIO_OUT, Net-(U2-PA6), Net-(U1B-+), Net-(D1-K)**. Four-net scope is the first four. The six broader removed via UUIDs are enumerated with original raw hashes, definitions, integer-nm geometry/net codes and source digest in `evidence/final/broader-signals/removal.json`; exact segment UUIDs and pre-execution authorization are retained too. Digital explicitly includes TX UUIDs `e6d7d2f7-5ce8-46c7-960f-7058698c8002` and `3fa8dbb6-c6f1-4dd8-a765-12076b794876`.

Excluded/fixed: GND, V_SUPPLY, V_MID, all unconnected nets, RESET's pre-existing name spelling, analog-input/feedback nets and newly unproved custom-pad nets BUFF_CV1/BUFF_CV2/Net-(D1-A)/Net-(SW1-B). MIDI's custom pad is only the already locally tested exception, **not blanket custom-pad support**. There was no unsupported/cap issue in either new trial; the authorized two-experiment budget is exhausted and no further routing ran.

## Independent native review and preservation

Original, historical `validated-udpi`, and historical `REJECTED-digital` were independently rerun in **private complete same-stem project copies**, with private read-only reviewed KiCad configuration and installed libraries read-only. Actual source SHA256s, removal UUID/raw-node hashes and **exact JSON finding identities** were compared, not saved outcome claims. The prior merge changed **no production module/design/rule paths**. Historical UDPI still passes; historical digital still has **one TX open + two dangling retained TX vias**. Independently rebuilt engine DRC confirms the latter with exit 5. Historical rejection/evidence are untouched.

Native DRC used JSON, `--severity-all --all-track-errors --schematic-parity --refill-zones --save-board --exit-code-violations`. **Exit 5 is expected even for the passing boards because the original warnings remain:** 4 silk_overlap, 8 silk_over_copper, 18 lib_footprint_mismatch; zero active errors/opens/parity. The actual finding identities match, not merely counts. Each new retained artifact was independently reopened and judged again in a second private copy; native inventories also match the first judgment exactly.

ERC was independently reproduced: **4 warnings + 16 already excluded errors**. Fresh native schematic XML export and PCB ref/pin partitions agree after deduplicating repeated physical pads with the same reference/pin. Original RESET `{slash}` versus `/` spelling remains unmodified. ERC exclusions and baseline footprint/silkscreen warnings prevent clean production sign-off.

Before reload, every retained top-level raw node must survive exactly; additions may only be authorized-net F/B signal segments/vias at native minimum dimensions, and all nested UUIDs must be unique. After private native reload/save, canonical parsed-node comparison plus native inventory verifies **all 24 footprints (22 front/2 back), 116 pads, transforms/sides/UUIDs/net membership, slot/custom primitives, 30.48 × 68.58 mm outline, six slotted pot anchors, eight custom QFN pads, two netted B.Cu polygons, power copper and untouched copper**. Pots/sockets/edge components are fixed. Project/schematic/library assets are unchanged; no rules were weakened. There are no zones on 8bit.

**Mechanical exceptions are NOT removable signal routing vias:** both net0 4/3.2 mm mounting-hole vias remain exact raw and native objects at **(62.377580,43.815)** and **(62.784908,106.045)**. Source has 33 electrical 0.7/0.3 mm vias plus these two holes. Digital retains **33 original vias + 2 regenerated TX vias**; broader retains **29 original vias + 5 new electrical vias**. The two holes are included in both retained-original counts. All new vias are 0.7/0.3 mm despite the unchanged project's default diameter being 0.6 mm (< native minimum 0.7).

Trusted strip's opt-in `--regenerate-signal-vias` **also requires exact `--via-uuid` arguments**. Default behavior retains every via. It rejects locked/grouped/net0/foreign-net/nonstandard/mounting vias, unknown or duplicate UUIDs and power/unconnected nets before writing output. Manifests reconcile independently against actual source slices. Original **18 helper tests rerun successfully; 27 tests now pass**, including nine regeneration/negative test cases. No broad controller rewrite or router facade/default/bundle promotion.

## Build, runtime confinement and provenance

Pinned external GPL engine **`c5e1e8497ffef194206a012ee98f0ba156827f71`** was fetched afresh; **no prior workspace accessed**. Clean upstream and all source hashes were unchanged before/after execution. CPU Release target `tracemaker` only, tests/bindings/CUDA off, GCC 15.2.0 / CMake 4.2.3 / Ninja 1.13.2, native KiCad 10.0.6. Fresh build **37.894 s** (configure 0.207 s), reproduced exact engine SHA256 **`b469a1502f0f825aa431a7fbee57e19f1cc80f8bb940df7c17d295f81e0669fe`**.

Same eight reviewed Ubuntu packages were downloaded by exact version/file/digest and `dpkg-deb --extract` into **this workspace's ignored `tracemaker-final.tmp/` only**: Boost, Eigen, JSON, CLI11, SQLite dev/runtime and zstd dev/runtime. Ubuntu archive `gpgv` signatures, signed uncompressed Packages SHA256/size, package-record identities and every .deb SHA256 were reverified. A first index-selection attempt encountered a KiCad PPA signature and **aborted before download/extract**; corrected to explicit `lk.archive.ubuntu.com` indexes, never bypassed authentication. No installers/maintainer scripts/global changes/sudo. [Exact final provenance](../experiments/tracemaker-8bit/evidence/final/common/) and [reproduction guide](../opt/kicad-tools/tracemaker/README.md).

Build/runtime used `bwrap --unshare-all --die-with-parent --new-session --clearenv`: network unavailable, actual host HOME/repository absent, upstream/dependencies/system runtime/input read-only; only private output writable. Fresh trusted probes verified both mount plans and denied writes. Ordinary routing: `--no-gpu --no-kb --component-rules off --threads 1 --variants 1 --time 100 --seed 1`; no pitch sweep. External 120 s wall cap, per-process 4 GiB AS, CPU cap, core disabled, per-file 16 MiB, aggregate output 64 MiB polling, private tmpfs 32 MiB. Build: 360 s, per-file 256 MiB, aggregate 900 MiB. **No cap fired.** These are process/polled limits, not cgroup guarantees or security certification.

Reviewed global fp/symbol-table hashes match historical provenance. Actual `kicad_common.json` had already changed since that run; its new reviewed hash was frozen and recorded rather than falsely claiming historical equality. Its environment vars are null; library context and exact native findings match historical results. Host config was neither mounted nor written by engine/native code.

## Historical evidence (retained, not revised into a pass)

- Synthetic F/B SMD + PTH + via-required fixture: engine 3/3, five segments/one 0.7/0.3 via; native opens 3 → 0, same two text warnings, raw/native preservation pass (0.011114 s engine).
- Unchanged 8bit: 24 footprints/116 pads/278 segments/35 vias/33 named nets; engine DRC exit 0; route 0/0 with **byte-identical no-op**, not a routing achievement (0.001444 s engine).
- UDPI rebuild: two actual segments recreated, length 4.729815 mm unchanged, native one open → zero; 30 exact baseline identities (0.006654 s engine). Still retained as `validated-udpi`.
- Prior four-net rebuild retaining every original via: 36 segments removed; engine exit 0, 6/6, 21 segments/two new vias (5.789562 s); **native TX open and two dangling original TX vias**, 32 warnings. Separate engine DRC also rejected. Still labelled `REJECTED-digital` with all historical evidence intact. The new explicit via-regeneration authorization is materially different; the prior failure is not hidden or re-labelled.

## Deliverables and limitations

New complete candidate folders `validated-digital` and **`validated-signals`**, exact original source freeze, compact `evidence/final/` native JSON/manifests/snapshots/commands/provenance, and **fresh native front/back before/after** plots + [retained PNG](../experiments/tracemaker-8bit/overview-final/before-after-signals.png) / [shareable comparison](/uploads/89a4c98e-79ca-4830-abcc-6e7f365cfd7c.webp). Plot source/candidate and before/after hashes are recorded; back is consistently mirrored. Small experimental runner README/discovery link only.

Tested: these exact two new signal scopes and the native-independent historical review. **Not tested/admitted:** all-board rerouting, moved placement, production manufacturing, arbitrary custom rules/geometry, power/polygon-net routing, newly excluded custom-pad nets, GPU/placer/plugins, electrical timing/analog performance or optimization. The pinned polygon-as-net0 modeling mismatch still exists; preserving its bytes is not proving its model. No upstream patches, schematic/pad-net changes or mechanical deletions were used to obtain a pass. Engine remains external GPL; **no engine binaries, third-party sources/dependencies or runtime enter git**.
