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

### Adding a new module

1. `mkdir src/<name>` and create `src/<name>/<name>.circuit.tsx`
2. Start from `<BreadModule>` (see `src/blank/blank.circuit.tsx`)
3. `./build.sh <name>`

### Viewing interactively (browser)

```bash
./tsci.sh dev src/blank/blank.circuit.tsx
```
