# TraceMaker copied-board experiment helper

**Experimental Linux-only controller, not a production routing facade/gate.** Tested pinned external engine: `c5e1e8497ffef194206a012ee98f0ba156827f71`; do not download/install automatically. [Actual trial and limits](../../../docs/kicad-tracemaker-trial.md). No upstream source/binaries are bundled. Route output is never automatically promoted.

Files: `trial.py` (freeze/explicit strip/bounded engine/raw comparison), `validate.py` (private native DRC + exact baseline finding comparison), `native_snapshot.py` (trusted pcbnew inventory/canonical save), `test_trial.py` (27 unit tests). Dependencies: Python 3.11+, Bubblewrap with user namespaces and `--size`, native KiCad CLI/pcbnew, separately reviewed CPU TraceMaker and extracted runtime dependencies. No shell execution in the controller. It does not run placement, `--reroute`, plugins, KB/viewer/GPU or weaken rules.

## Reproduce the tested UDPI subset

Run from repository root. All named output directories must be NEW; `*.tmp` is ignored. Provision/build separately using the exact retained signed-package and sandbox build provenance. These commands use example scratch paths; build afresh in your own ignored directory (see below), never access a prior workspace. Verify pin, clean upstream checkout, signed packages, provenance and the recorded binary digest first.

```sh
python3 opt/kicad-tools/tracemaker/trial.py freeze \
  modules/8bit/8bit.kicad_pcb repeat.tmp/frozen --library-root opt

python3 opt/kicad-tools/tracemaker/trial.py run inspect \
  repeat.tmp/frozen 8bit.kicad_pcb repeat.tmp/inspect \
  --engine tracemaker-trial.tmp/build/src/app/tracemaker \
  --sha256 b469a1502f0f825aa431a7fbee57e19f1cc80f8bb940df7c17d295f81e0669fe \
  --deps tracemaker-trial.tmp/deps

python3 opt/kicad-tools/tracemaker/validate.py \
  repeat.tmp/frozen 8bit.kicad_pcb repeat.tmp/baseline \
  --config tracemaker-trial.tmp/native-config

python3 opt/kicad-tools/tracemaker/trial.py strip \
  repeat.tmp/frozen 8bit.kicad_pcb repeat.tmp/stripped --net UDPI

python3 opt/kicad-tools/tracemaker/validate.py \
  repeat.tmp/stripped 8bit.kicad_pcb repeat.tmp/stripped-native \
  --config tracemaker-trial.tmp/native-config
# Expected nonzero validation exit here: the deliberately stripped board has one open.

python3 opt/kicad-tools/tracemaker/trial.py run route \
  repeat.tmp/stripped 8bit.kicad_pcb repeat.tmp/output --experimental --only-net UDPI \
  --engine tracemaker-trial.tmp/build/src/app/tracemaker \
  --sha256 b469a1502f0f825aa431a7fbee57e19f1cc80f8bb940df7c17d295f81e0669fe \
  --deps tracemaker-trial.tmp/deps

python3 opt/kicad-tools/tracemaker/validate.py \
  repeat.tmp/stripped 8bit.kicad_pcb repeat.tmp/judged \
  --candidate repeat.tmp/output/8bit.kicad_pcb --net UDPI \
  --config tracemaker-trial.tmp/native-config \
  --baseline-report repeat.tmp/baseline/drc.json

python3 opt/kicad-tools/tracemaker/trial.py compare \
  repeat.tmp/stripped-native/canonical.kicad_pcb \
  repeat.tmp/judged/canonical.kicad_pcb --semantic --net UDPI

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover \
  -s opt/kicad-tools/tracemaker -p 'test_*.py' -v
```

`--config` is a frozen PRIVATE directory containing `10.0/{fp-lib-table,sym-lib-table,kicad_common.json}` copied from the existing reviewed configuration, **not host HOME**. Original config is never mounted/written. It is not bundled because paths are machine-specific. Standard libraries come from installed `/usr/share/kicad` read-only; only actually referenced local footprint files are frozen. `--library-root opt` explicitly authorizes dereferencing the repository's migrated footprint/table symlinks within that trusted boundary; frozen inputs contain no symlinks.

## Interpret results correctly

- Freeze seals inputs by file hash; engine gets read-only input, read-only binary/dependencies/system runtime, fresh private output, no network/HOME/real source, fixed safe argv and external caps. Caps/provenance are written to `*.command.json`. A digest verifies binary identity, **not source/build trust on its own**.
- `strip` supports the tested legacy numbered-net PCB subset: named ordinary nets, segments by default, exact removal UUID/definition/hash manifest. Requires an existing `.kicad_pcb` basename before input reads/output creation. Rejects locked or grouped selected segments before output creation, as well as power/unconnected nets; retains all vias by default. The narrow opt-in below only regenerates explicitly authorized ordinary signal electrical vias; mechanical holes remain protected. Preserves graphics, footprints and all other copper.
- `compare` requires exact existing raw nodes, allows only named-net F/B segment/via additions at tested minimum dimensions, checks all nested UUID uniqueness. `--semantic` compares parsed tokens after separately native-canonicalizing both boards; does not replace raw pre-reload protection.
- `validate.py` refuses unauthorized raw changes BEFORE native reload, copies complete frozen project context into its private output, checks unchanged existing assets, runs native all-track DRC/parity/refill/save and inventories geometry. It diagnoses native failures but exits nonzero for active errors or new findings versus `--baseline-report`. Relative DRC success is **not full semantic acceptance**: run the canonical comparison and inspect native footprint/pad/net/via inventory too.
- Inspect is inventory, not connectivity qualification. First qualify unchanged-copy engine `drc` and no-op preservation. **Route exit 0 is not completion/sign-off**: the expanded real trial returned 0 while both independent engine `drc` and KiCad found a TX open and two dangling retained vias.
- Native DRC exit 5 can mean only existing warnings. The tested board retains 30 baseline warnings and schematic ERC exclusions. No result certifies general custom-pad/polygon/rule support or production readiness. No automatic cleanup, promotion, package installation or integration with existing router admission gates.


## Explicit signal-via regeneration (experimental)

Final trials genuinely rebuilt four nets, then one broader **10-signal** subset; both passed exact native baseline comparison. This is not full-board routing. Best artifact: `experiments/tracemaker-8bit/validated-signals/`; the four-net `validated-digital/` and historical `REJECTED-digital/` are retained separately. [Exact final authorization/manifests/provenance](../../../experiments/tracemaker-8bit/evidence/final/).

Default `strip` still retains **every via**. Via removal requires **both** `--regenerate-signal-vias` and repeated exact `--via-uuid` arguments. Only reviewed plain **0.7/0.3 mm F/B through vias** on the explicitly named signal nets can be stripped. Locked/grouped/net0/foreign-net/mounting/nonstandard vias, unknown/duplicate UUIDs, power/unconnected nets and unsupported syntax are rejected before writes. Every removed object records its source digest, UUID, raw hash/definition, net and integer-nm geometry. This does not edit pad nets or rules.

```sh
# NEW output directory, original frozen source; removes 36 segments and just two TX vias.
python3 opt/kicad-tools/tracemaker/trial.py strip \
  repeat.tmp/frozen 8bit.kicad_pcb repeat.tmp/digital-stripped \
  --net UDPI --net TX --net MIDI --net GATE_OUT \
  --regenerate-signal-vias \
  --via-uuid e6d7d2f7-5ce8-46c7-960f-7058698c8002 \
  --via-uuid 3fa8dbb6-c6f1-4dd8-a765-12076b794876
```

Run ordinary `run route ... --experimental` **without** `--only-net UDPI`, then judge the complete same-stem candidate with all four `--net` arguments using the preceding native/semantic workflow. Run a separate engine `drc` against a sealed **complete** candidate project copy too. Never delete objects from a failing output after routing; explicit stripping is pre-route authorization, not warning/open suppression. The project's default via is 0.6 mm but minimum is 0.7; pinned engine emitted 0.7/0.3 mm without altering project/rules. Reject any output failing raw preservation, native geometry, parity or exact findings.

Broader selected UUIDs/nets and exclusions are in `evidence/final/broader-signals/authorization.json` and `evidence/final/common/broader-selection.json`; do not infer permission to strip additional power/RESET/custom-pad/feedback nets. Mechanical 4/3.2 mm net0 holes are never allowed.

## Reproduce the pinned CPU build (explicit authorization only)

No bootstrap, installer or upstream shell wrapper. Use **a NEW ignored `tracemaker-rebuild.tmp/` in the current workspace**, never a prior workspace. The final reproduced binary digest equals the historical one; actual build was 37.894 s. Final source/package/build/confinement records are in `experiments/tracemaker-8bit/evidence/final/common/`.

1. Read `provision.json`: exact eight package records (version, archive pool filename, SHA256, suite/component). Verify archive `InRelease` with `gpgv --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg`; use **explicit Ubuntu archive origin**, not a wildcard matching a PPA. Extract the signed Release to a private file. Decompress each corresponding installed apt index with `/usr/lib/apt/apt-helper cat-file`; verify its uncompressed byte size/SHA256 against that signed Release. Match the exact package/version/architecture/filename/SHA256 stanza. Stop if any record/signature is unavailable or differs; never waive authentication or add signing keys.
2. Download each exact `https://archive.ubuntu.com/ubuntu/<Filename>` into private `packages/`; SHA256 must match the verified record. Extract with `dpkg-deb --extract FILE tracemaker-rebuild.tmp/deps`. This does **not** execute maintainer scripts or globally install. Never use `apt install`, sudo or system package changes.
3. `git -c core.hooksPath=/dev/null init tracemaker-rebuild.tmp/upstream`; fetch **only** `c5e1e8497ffef194206a012ee98f0ba156827f71` with `git -c core.hooksPath=/dev/null -C ... fetch --depth 1 https://github.com/DingoOz/TraceMaker PIN`; detached checkout `FETCH_HEAD`. Verify exact HEAD, clean status and source hashes before/after. No source patches/submodules/installers.
4. Replay the **reviewed** argv in `common/build.json`, replacing only the outer private source/deps/build paths with the new current-workspace paths. The inner mounts/argv are:

```text
bwrap --unshare-all --die-with-parent --new-session --clearenv
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib --ro-bind /lib64 /lib64
  --proc /proc --dev /dev --tmpfs /tmp --dir /etc
  --ro-bind /etc/ld.so.cache /etc/ld.so.cache
  --ro-bind PRIVATE_UPSTREAM /source --ro-bind PRIVATE_DEPS /deps --bind PRIVATE_BUILD /build
  --setenv PATH /usr/bin --setenv HOME /tmp/home --setenv LC_ALL C
  --setenv PKG_CONFIG_PATH /deps/usr/lib/x86_64-linux-gnu/pkgconfig
  --setenv LD_LIBRARY_PATH /deps/usr/lib/x86_64-linux-gnu --chdir /build
```

Inside that same mount plan, first `/usr/bin/cmake -S /source -B /build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/g++-15 -DCMAKE_PREFIX_PATH=/deps/usr -DTM_ENABLE_CUDA=OFF -DTM_BUILD_TESTS=OFF -DTM_BUILD_PYTHON=OFF`; then `/usr/bin/cmake --build /build --target tracemaker --parallel 4`. No HOME/repository/network exposure. Apply recorded 360 s wall, 4 GiB AS, 256 MiB file and 900 MiB aggregate build-output limits (private trusted parent supervision); probe denied writes/network as in confinement records. Do not drop isolation to fix a failure. Binary: `PRIVATE_BUILD/src/app/tracemaker`; verify pin/provenance plus digest before runner use. No third-party engine/source/runtime is a git deliverable; engine remains external GPL.
