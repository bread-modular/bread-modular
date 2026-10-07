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

- **Concrete native handoff blocker:** PCB API/pcbnew 10.0.6 saves name-only nets,
  not top-level numbered net definitions. `strip` and all engine `run` actions reject
  this encoding **before output creation**. No number/rule guessing or conversion.
  Native freeze/no-op compare/validation and return-to-CLI polish are tested, but that
  is **not** qualified engine interoperability. This is an **adapter-only blocker**,
  not source/runtime evidence that the upstream engine cannot read/write named nets;
  no pinned reader/writer research was redone here. See the hybrid recipe's explicit stop.
- `freeze` preserves PCB bytes and collects bounded same-stem hierarchy/rules/local
  library closure with existing `Plan` helpers. It detects missing sheets/libraries,
  records path rebindings in `_context.json`, seals hashes and creates no symlinks.
  External library/sheet dependencies require explicit trusted `--library-root`.
  Unsupported 3D/image/embedded resources block. Historical board-only freeze has no
  schematic/parity qualification; tables require complete project context.
- `strip` authorizes existing ordinary named nets in the **legacy numbered subset**.
  Default removes all selected-net segments and retains every via; prefer repeated
  exact `--segment-uuid` for bounded rerouting. Both `--regenerate-signal-vias` and
  exact `--via-uuid` lists are required to remove plain 0.7/0.3 mm F/B signal vias.
  Locked/grouped/net0/foreign/mounting/power/unconnected objects remain protected.
  Removal records bind UUIDs/raw definitions/hashes; via-regeneration geometry is nm.
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
Missing runtime/platform/integration fails nonzero; nothing is installed or downloaded.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s opt/kicad-tools/tracemaker -v
KICAD_TRACEMAKER_NATIVE=1 /usr/bin/python3 -B -m unittest discover \
  -s opt/kicad-tools/tracemaker -p test_native.py -v
```

Historical trial/research links are **repository-only**, not provisioning dependencies:
`docs/kicad-tracemaker-trial.md`, `docs/kicad-tracemaker.md`,
`experiments/tracemaker-8bit/{validated-signals,evidence/final}/`.
No retained experiment candidate, fabrication output or release is changed or copied.
