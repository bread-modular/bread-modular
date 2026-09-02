# Bread Modular — tscircuit modules

Bread Modular modules built with [tscircuit](https://tscircuit.com) —
electronics designed with TypeScript/React.

## Layout

```
ts-modules/
├── package.json        # scripts + deps (tscircuit)
├── build.sh            # module-aware build: ./build.sh [module ...]
├── tsci.sh             # wrapper around the `tsci` CLI (no global install)
├── lib/                # shared building blocks for all modules
│   ├── constants.ts        # standard board size, net & pin-count constants
│   ├── module-frame.tsx    # BreadModule: board, power rails, bus connectors, silkscreen
│   ├── analog-starter.tsx  # schematic-only starter parts (R1/R2, C1, RV1, U2A/U2B)
│   ├── rv09-pot.tsx        # RV09Pot + RV09Footprint (Alpha 9mm vertical pot)
│   ├── mcp6002.tsx         # MCP6002: dual op-amp as one SOIC-8 (JLC C7377)
│   ├── sma-diode.tsx       # SMADiode (SS14 = C2480, SS210 = C14996)
│   └── index.ts
└── src/
    └── blank/             # one directory per module
        ├── blank.circuit.tsx  # module entry: <module-name>.circuit.tsx
        └── out/               # build outputs land here
```

## The shared module frame (`lib/module-frame.tsx`)

Every module starts from the same skeleton, `<BreadModule>`:

| Feature | Default | Prop to disable |
|---|---|---|
| Standard board 30.48 × 68.58 mm | on | `width` / `height` (mm) to resize |
| Top/bottom power rails (`V_SUPPLY1`/`GND1`, 0.5mm copper bus) | on | `powerRails={false}` |
| Left/right bus connectors (`INPUT1`/`OUTPUT1`, 1×05 female) | on | `leftConnector={false}` / `rightConnector={false}` |
| 4mm plated mounting holes (top/bottom center) | on | `mountingHoles={false}` |
| `NAME` + version silkscreen | on | `name` / `version` props (empty `version` hides it) |
| INPUT/OUTPUT edge labels | on | `edgeLabels={false}` |
| BREAD/MODULAR brand block | on | `brand={false}` |

Silkscreen conventions (matching the KiCad originals):

- Global silkscreen font is **1 mm** (`pcbStyle.silkscreenFontSize` on the board) —
  every auto reference designator and label shares one size, like KiCad.
- **KiCad font**: `scripts/kicad-font/` contains the "KiCad Font: Sans" glyph
  geometry, extracted from KiCad itself and patched into
  `@tscircuit/alphabet` (the font tscircuit's gerber writer uses) — so the
  fabricated silkscreen matches the KiCad originals letter-for-letter.
  `build.sh` re-applies the patch (idempotent) before every build;
  `npm install` re-applies it via the `postinstall` hook. To regenerate the
  glyph data: `python3 scripts/kicad-font/extract-glyphs.py > kicad-alphabet.json`
  (needs `pcbnew` python from KiCad).
- Pot labels: `<RV09Pot>` prints the designator + resistance (e.g. `RV2 500k`)
  inside the pot body, and an optional knob label (`label="GAIN"`) below the pins.
- Add bus pin-function labels (e.g. `AUDIO` / `MULT` / `DIRTY` / `CLEN`) as
  module-specific `<silkscreentext>` next to the connectors, rotated 90° where
  the KiCad board has them vertical.

A new module is then just:

```tsx
import { BreadModule, AnalogStarter } from "../../lib";

export default () => (
  <BreadModule name="MYMOD" version="0.1.0">
    {/* module-specific circuitry here */}
    <AnalogStarter />          {/* optional shared starting parts */}
  </BreadModule>
);
```

## JLCPCB fabrication rules (`lib/constants.ts`)

Every module inherits JLCPCB-safe manufacturing tolerances automatically —
`<BreadModule>` spreads `JLCPCB_FAB_BOARD_PROPS` onto the board, which feeds
tscircuit's routing-tolerance props (`minTraceWidth`, `minViaHoleDiameter`,
`minViaPadDiameter`, the `min*Clearance` family and
`autorouter.traceClearance`). The tscircuit defaults (0.2/0.3mm vias,
0.1mm clearance) are **below** JLCPCB's spec sheet and get flagged or
fabricated out of spec on standard 2-layer orders.

| Constant | Value | Why |
|---|---|---|
| `JLCPCB_VIA_HOLE_DIAMETER` | 0.3 mm | Via drill (default 0.2 is at JLCPCB's absolute limit) |
| `JLCPCB_VIA_PAD_DIAMETER` | 0.5 mm | Via pad — 0.1 mm annular ring (JLCPCB min 0.075 mm) |
| `JLCPCB_TRACE_CLEARANCE` | 0.15 mm | Copper-to-copper spacing (JLCPCB 2-layer spec ≥ 0.127 mm) |
| `JLCPCB_MIN_TRACE_WIDTH` | 0.15 mm | Thinnest trace (spec ≥ 0.127 mm) |
| `JLCPCB_PAD_EDGE_CLEARANCE` | 0.15 mm | Trace/pad edge to pad edge |
| `JLCPCB_VIA_EDGE_CLEARANCE` | 0.15 mm | Via edge to trace/pad edge |
| `JLCPCB_VIA_HOLE_EDGE_CLEARANCE` | 0.2 mm | Drill edge to drill edge |

Rules of thumb when designing modules:

- **Don't override these per module.** They live in `lib/constants.ts` so
  every board ships JLCPCB-clean. If a trace can't route with 0.15 mm
  clearance, move the components apart rather than lowering the constants.
- Never place vias manually — if you must, keep the 0.3/0.5 mm size and
  ≥ 0.15 mm copper clearance from other nets.
- `<platedhole>` mounting holes (4 mm pad / 3.2 mm drill) and PTH connector
  drills (1.0 mm pins, 1.1 × 2.3 mm slots) are already JLCPCB-standard.
- After layout changes, re-check the gerbers: the drill file should list
  `T13C0.300000` for vias and `F_Cu.gbr` should flash vias with the 0.5 mm
  aperture; `tsci build` runs DRC (0 errors expected).
- Reference audit: `src/drive/AUDIT.md` documents the gerber-level checks
  (annular ring, spacing histogram, via-in-pad distance) used to validate
  these values.

## Building

```bash
npm install          # one-time (installs tscircuit + bun)

./build.sh           # build every module under src/
./build.sh blank     # build a single module
npm run build:blank  # same, via npm
```

Each build produces, inside `src/<module>/out/`:

| File | Purpose |
|---|---|
| `<m>-schematic.svg` / `<m>-pcb.svg` / `<m>-assembly.svg` | Renders |
| `<m>_jlcpcb.zip` | **JLCPCB fabrication package** (gerbers, drill, plus `bom.csv` & `pick_and_place.csv` inside) |
| `<m>-bom.csv` | BOM extracted for JLCPCB's separate BOM upload |
| `<m>-pick-and-place.csv` | Placement (CPL) file for JLCPCB's assembly upload |
| `circuit JSON + DRC` | From `tsci build` (in `src/<module>/dist/`) |

> Note: schematic-only `doNotPlace` parts (like the blank's R1/R2/C1/RV1/U2)
> appear in the BOM/PnP without a JLCPCB part # — delete those rows before
> ordering assembly for a board with real parts.

### Reusing the auto-routed board (`.tscircuit/cache`)

`tsci build` runs the PCB autorouter and caches the routed traces in
`ts-modules/.tscircuit/cache/`, keyed by `routes:core@<version>:srj:<hash>` of
the layout (SimpleRouteJson). Because `out/` and `dist/` are gitignored, a
fresh clone or CI machine would otherwise re-run the autorouter every build.

To keep that work, the autorouter cache **is committed to git** (`ts-modules/.gitignore`
tracks `.tscircuit/cache/` but still ignores the rest of `.tscircuit/`). On any clone/machine,
building an *unchanged* layout hits the cache and reuses the saved traces instead of re-routing.

Rules of thumb:

- Commit your `.tscircuit/cache/` after a build so the routed board is preserved.
- If you change a module's layout, its `srj` hash changes → a new cache entry is
  generated (old ones stay in git but are ignored). Commit the new cache files.
- To force a fresh route (e.g. after a tricky DRC hit), `rm -rf .tscircuit/cache/ && ./build.sh <module>`,
  then commit the regenerated cache.

### Adding a new module

1. `mkdir src/<name>` and create `src/<name>/<name>.circuit.tsx`
2. Start from `<BreadModule>` (see `src/blank/blank.circuit.tsx`)
3. `./build.sh <name>`

### Viewing interactively (browser)

```bash
./tsci.sh dev src/blank/blank.circuit.tsx
```
