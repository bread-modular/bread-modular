# TraceMaker — optional bounded hybrid controller

**Recommend hybrid use for compatible ordinary signals**, not full-board routing:
[layout → protect → freeze → selected router work → inspect/manual polish](../HYBRID_ROUTING.md).
Linux/Python 3.11+/KiCad 10 experimental controller; **not production admission/signoff**.
The successful retained 10-net trial used pinned engine
`c5e1e8497ffef194206a012ee98f0ba156827f71`. No engine/source/deps/config are bundled.

```sh
python3 -B opt/kicad-tools/kicad_tools.py tracemaker --help
python3 -B opt/kicad-tools/kicad_tools.py tracemaker doctor
python3 -B opt/kicad-tools/kicad_tools.py tracemaker run --help
python3 -B opt/kicad-tools/kicad_tools.py tracemaker validate --help
python3 -B opt/kicad-tools/kicad_tools.py bundle '/tmp/NEW toolkit' --include-tracemaker
```

`--include-tracemaker` is independent of `--include-routing`. Core runs with neither.
The subprocess dispatcher preserves standalone args/stdout/stderr/nonzero exits:
`freeze|strip|run inspect|route|drc|compare` delegate to `trial.py`;
`validate` delegates to `validate.py` with the same positional input/pcb/output args.
Doctor only reports pin/path/prerequisites, never executes an engine, imports pcbnew,
writes config, downloads or certifies readiness. Existing `route` (Freerouting) is unchanged.

## Compatibility and safety

- **Qualified strict native handoff:** legacy global numeric and KiCad 10 inline
  quoted named nets use one quote-aware resolver in strip/compare/run. `"1"` is a name,
  not code `1`; unknown codes, duplicate/conflicting definitions and malformed/ambiguous
  mixtures reject before writes. Coherent mixed names must match global definitions.
  No format conversion, net inference or upstream patch. A real CPU synthetic test
  closes one deliberate open, then returns through recorded CLI polish and fresh checks.
  This is a supported-subset proof, **not production/full-board qualification**.
- `freeze` preserves PCB bytes and collects bounded same-stem hierarchy/rules/local
  library closure with existing `Plan` helpers. It detects missing sheets/libraries,
  records path rebindings in `_context.json`, seals hashes and creates no symlinks.
  External library/sheet dependencies require explicit trusted `--library-root`.
  Unsupported 3D/image/embedded resources block. Historical board-only freeze has no
  schematic/parity qualification; tables require complete project context.
- `strip` authorizes existing ordinary named nets in the **legacy numeric / native inline-named subset**.
  Default removes all selected-net segments and retains every via; prefer repeated
  exact `--segment-uuid` for bounded rerouting. Both `--regenerate-signal-vias` and
  exact `--via-uuid` lists are required to remove plain 0.7/0.3 mm F/B signal vias.
  Locked/grouped/net0/foreign/mounting/power/unconnected objects remain protected.
  Removal records bind UUIDs/raw definitions/hashes; via-regeneration geometry is nm.
  Canonical net names are always recorded; net codes only when global definitions exist.
- Engine `run route` requires **`--experimental`**, supplied SHA256 matching the
  reviewed pinned CPU build, separately reviewed build/dependency provenance and
  bounded networkless bwrap. Safe fresh copies only, no HOME/source mounts, GPU/KB/
  plugins/placement/`--reroute`, shell commands or engine-default substitution.
- `compare` preserves exact existing raw nodes (including all transforms) and allows
  only explicitly named-net segment/via additions with minimum dimensions/unique UUIDs.
  `--semantic` compares tokens after independent native canonical saves; not a raw gate replacement.
- `validate` rejects unauthorized raw edits before reload; runs all-track native DRC,
  same-stem parity/refill/save and inventories pcbnew geometry/net partition. Native
  config, if supplied, is a reviewed frozen PRIVATE `10.0/` directory, never host HOME.
  Compare exact baseline findings, canonical tokens, assets and net inventory, then full
  native ERC/XML parity and visual review. Route exit 0, baseline warnings/exclusions
  or a successful native no-op are **not automatic acceptance**.

## Provisioning and verification

[Self-contained manual build/license/provenance guide](BUILD.md) ·
[Exact signed-package/index records](provision.json).
The historical manifest is never silently replaced by a signed catalog refresh.
Review refreshed catalogs against **all eight exact pinned records**; dependency changes
are not catalog refreshes. Missing runtime/platform/integration fails nonzero; nothing is installed or downloaded.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s opt/kicad-tools/tracemaker -v
KICAD_TRACEMAKER_NATIVE=1 /usr/bin/python3 -B -m unittest discover \
  -s opt/kicad-tools/tracemaker -p test_native.py -v
# Optional REAL engine proof, only AFTER authorized manual provisioning/review:
KICAD_TRACEMAKER_NATIVE=1 KICAD_TRACEMAKER_ENGINE_NATIVE=1 \
  KICAD_TRACEMAKER_ENGINE='/private/reviewed build/src/app/tracemaker' \
  KICAD_TRACEMAKER_DEPS='/private/reviewed deps' \
  KICAD_TRACEMAKER_SHA256=b469a1502f0f825aa431a7fbee57e19f1cc80f8bb940df7c17d295f81e0669fe \
  /usr/bin/python3 -B -m unittest discover -s opt/kicad-tools/tracemaker -v
```

Tests generate only synthetic designs; they never provision a runtime. The fixture is
initialized **before its first baseline** with explicit 0.2 mm clearance, 0.15 mm track,
0.7/0.3 mm via/drill minima, so engine DRC cannot silently default to zero rules. Those
project/rule bytes remain identical through all stages; no rule lowering or finding waiver.
For optional ignored evidence, `KICAD_TRACEMAKER_SUMMARY` is a NEW summary file path and
`KICAD_TRACEMAKER_ARTIFACTS` a NEW private directory; neither is required or bundled.
Relocated source-only copies use the same test with externally supplied runtime paths.
Repository-only [compact proof](synthetic-verification.json) contains provenance/counts/
log hashes, not boards, libraries, third-party sources or executables.

Historical trial/research links are **repository-only**, not provisioning dependencies:
`docs/kicad-tracemaker-trial.md`, `docs/kicad-tracemaker.md`,
`experiments/tracemaker-8bit/{validated-signals,evidence/final}/`.
No retained experiment candidate, fabrication output or release is changed or copied.
