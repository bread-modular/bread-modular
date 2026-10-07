# TraceMaker copied-board experiment helper

**Experimental Linux-only controller, not a production routing facade/gate.** Tested pinned external engine: `c5e1e8497ffef194206a012ee98f0ba156827f71`; do not download/install automatically. [Actual trial and limits](../../../docs/kicad-tracemaker-trial.md). No upstream source/binaries are bundled. Route output is never automatically promoted.

Files: `trial.py` (freeze/explicit strip/bounded engine/raw comparison), `validate.py` (private native DRC + exact baseline finding comparison), `native_snapshot.py` (trusted pcbnew inventory/canonical save), `test_trial.py` (18 unit tests). Dependencies: Python 3.11+, Bubblewrap with user namespaces and `--size`, native KiCad CLI/pcbnew, separately reviewed CPU TraceMaker and extracted runtime dependencies. No shell execution in the controller. It does not run placement, `--reroute`, plugins, KB/viewer/GPU or weaken rules.

## Reproduce the tested UDPI subset

Run from repository root. All named output directories must be NEW; `*.tmp` is ignored. Provision/build separately using the exact retained signed-package and sandbox build provenance. These commands assume the trial's ignored binary/dependencies still exist; verify pin, clean upstream checkout, build provenance and the recorded binary digest first.

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
- `strip` supports the tested legacy numbered-net PCB subset: named ordinary nets, SEGMENTS ONLY, exact removal UUID/definition/hash manifest. Requires an existing `.kicad_pcb` basename before input reads/output creation. Rejects locked or grouped selected segments before output creation, as well as power/unconnected nets; never removes any via. Preserves mechanical holes, graphics, footprints and all other copper.
- `compare` requires exact existing raw nodes, allows only named-net F/B segment/via additions at tested minimum dimensions, checks all nested UUID uniqueness. `--semantic` compares parsed tokens after separately native-canonicalizing both boards; does not replace raw pre-reload protection.
- `validate.py` refuses unauthorized raw changes BEFORE native reload, copies complete frozen project context into its private output, checks unchanged existing assets, runs native all-track DRC/parity/refill/save and inventories geometry. It diagnoses native failures but exits nonzero for active errors or new findings versus `--baseline-report`. Relative DRC success is **not full semantic acceptance**: run the canonical comparison and inspect native footprint/pad/net/via inventory too.
- Inspect is inventory, not connectivity qualification. First qualify unchanged-copy engine `drc` and no-op preservation. **Route exit 0 is not completion/sign-off**: the expanded real trial returned 0 while both independent engine `drc` and KiCad found a TX open and two dangling retained vias.
- Native DRC exit 5 can mean only existing warnings. The tested board retains 30 baseline warnings and schematic ERC exclusions. No result certifies general custom-pad/polygon/rule support or production readiness. No automatic cleanup, promotion, package installation or integration with existing router admission gates.
