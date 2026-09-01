# Bread Modular "blank" module — tscircuit recreation

This is a 1:1 recreation of `modules/blank` (the Bread Modular blank module, originally
a KiCad project) using [tscircuit](https://tscircuit.com) — electronics designed with
TypeScript/React.

## What's here

| File | Purpose |
|---|---|
| `blank.circuit.tsx` | The full module: board, connectors, holes, nets, silkscreen, schematic |
| `tsci.sh` | Wrapper to run the `tsci` CLI without a global install |
| `render-and-export.sh` | One-shot: build + render SVGs + export JLCPCB fabrication package |
| `out/blank-schematic.svg` | Rendered schematic |
| `out/blank-pcb.svg` | Rendered PCB (copper/silk/holes) |
| `out/blank_jlcpcb.zip` | **Upload-ready JLCPCB package** |
| `out/gerbers/` | Unzipped: gerbers, drill files, `bom.csv`, `pick_and_place.csv` |

## How it maps to the KiCad original

| KiCad (`modules/blank`) | tscircuit (`blank.circuit.tsx`) |
|---|---|
| Board 30.48 × 68.58 mm | `<board width="30.48mm" height="68.58mm">` |
| INPUT1/OUTPUT1 — `PinSocket_1x05` | `<pinheader pinCount={5} gender="female" pcbRotation={-90}>` |
| V_SUPPLY1 / GND1 — `BreadModular:Power_Connector` (1×05) | `<pinheader pinCount={5}>` (horizontal rows) |
| 2 × 3.2 mm NPTH mounting holes | `<hole diameter="3.2mm">` |
| 2 copper bus traces (0.5 mm, F.Cu) | `<trace width="0.5mm">` on `net.VSUPPLY` / `net.GND` |
| R1/R2 1k divider → VMID, C1 0.1uF, RV1 50k, U2 (MCP6002) — schematic only, no footprints | same parts with `doNotPlace` (schematic-only) |
| Silkscreen INPUT / OUTPUT / NAME / BREAD MODULAR / NAME 0.0.0 | `<silkscreentext>` |

Component positions were taken from the KiCad PCB coordinates
(board center = (62.23, 76.46) mm in KiCad space; tscircuit Y axis points up, so
`dy` is negated).

## Usage

```bash
# one-time setup (already done — node_modules is committed? no, install locally):
npm install          # installs tscircuit + bun (bun is required by the CLI)

# render + export everything:
./render-and-export.sh

# or step by step:
./tsci.sh build blank.circuit.tsx                          # build + DRC
./tsci.sh export blank.circuit.tsx -f schematic-svg -o out/sch.svg
./tsci export blank.circuit.tsx -f pcb-svg -o out/pcb.svg
./tsci export blank.circuit.tsx -f gerbers -o out/fab    # JLCPCB zip
```

### Viewing interactively (browser)

```bash
./tsci dev blank.circuit.tsx   # opens the tscircuit dev server (schematic + PCB + 3D)
```

## Ordering from JLCPCB

1. Upload `out/blank_jlcpcb.zip` (gerbers + drills) as the PCB file.
2. For assembly, JLCPCB accepts the included `bom.csv` and `pick_and_place.csv`.
   - The connectors already have JLCPCB part numbers auto-assigned
     (pin header C50950, power connector C492404).
   - **Note:** R1/R2/C1/RV1/U2 are schematic-only (`doNotPlace`) exactly like the
     KiCad original (which has no footprints for them). Remove those rows from
     the BOM/CPL before ordering assembly, or assign footprints in
     `blank.circuit.tsx` and drop the `doNotPlace` flags.

## Differences vs the KiCad original

- Schematic drawing style differs (tscircuit auto-layout vs KiCad's manual A3 sheet);
  the components, values, nets (V_SUPPLY, VMID, GND) and connectivity match.
- The KiCad SPICE-only sources (V1/VDC, V2/VSIN) are not recreated — they are
  simulation scaffolding, not part of the module netlist.
- U2 (MCP6002 dual op-amp) is modeled as two single op-amps `U2A`/`U2B`
  (tscircuit op-amps are single-unit) to mirror the KiCad A/B units visually.
