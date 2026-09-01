#!/usr/bin/env bash
# Render schematic + PCB SVGs and export the full JLCPCB fabrication package.
# Outputs land in tools/tscircuit/out/
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export PATH="$DIR/node_modules/.bin:$PATH"

mkdir -p out

echo "==> Building (circuit JSON + DRC)..."
tsci build blank.circuit.tsx

echo "==> Schematic SVG..."
tsci export blank.circuit.tsx -f schematic-svg -o out/blank-schematic.svg

echo "==> PCB SVG..."
tsci export blank.circuit.tsx -f pcb-svg -o out/blank-pcb.svg

echo "==> Assembly view..."
tsci export blank.circuit.tsx -f assembly-svg -o out/blank-assembly.svg

echo "==> JLCPCB fabrication package (gerbers + drill + BOM + CPL)..."
tsci export blank.circuit.tsx -f gerbers -o out/fabrication
mv -f out/fabrication out/blank_jlcpcb.zip 2>/dev/null || true
mkdir -p out/gerbers && cd out/gerbers && unzip -o ../blank_jlcpcb.zip >/dev/null && cd ../..

echo "==> Done. See tools/tscircuit/out/"
ls -la out/
