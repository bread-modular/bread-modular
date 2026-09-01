#!/usr/bin/env bash
# Build Bread Modular tscircuit modules.
#
# Usage:
#   ./build.sh            # build EVERY module found under src/
#   ./build.sh blank      # build only the `blank` module
#   ./build.sh blank foo  # build several named modules
#
# Convention: each module lives in src/<name>/ with an entry file
# src/<name>/<name>.circuit.tsx — all outputs land in src/<name>/out/.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export PATH="$DIR/node_modules/.bin:$PATH"

if [ $# -ge 1 ]; then
  MODULES="$*"
else
  MODULES="$(find src -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)"
fi

for m in $MODULES; do
  if [ ! -f "src/$m/$m.circuit.tsx" ]; then
    echo "!! No entry file for module '$m' (expected src/$m/$m.circuit.tsx)" >&2
    exit 1
  fi
  out="src/$m/out"
  mkdir -p "$out"
  out_abs="$DIR/$out"   # tsci resolves -o relative to the entry file's dir

  # Run tsci from inside the module dir so `tsci build`'s dist/ output
  # also lands inside src/<m>/dist.
  pushd "src/$m" >/dev/null

  echo "==> [$m] Building (circuit JSON + DRC)..."
  tsci build "$m.circuit.tsx"

  echo "==> [$m] Schematic SVG..."
  tsci export "$m.circuit.tsx" -f schematic-svg -o "$out_abs/$m-schematic.svg"

  echo "==> [$m] PCB SVG..."
  tsci export "$m.circuit.tsx" -f pcb-svg -o "$out_abs/$m-pcb.svg"

  echo "==> [$m] Assembly view..."
  tsci export "$m.circuit.tsx" -f assembly-svg -o "$out_abs/$m-assembly.svg"

  echo "==> [$m] JLCPCB fabrication package (gerbers + drill + BOM + CPL)..."
  tsci export "$m.circuit.tsx" -f gerbers -o "$out_abs/fabrication"
  mv -f "$out_abs/fabrication" "$out_abs/${m}_jlcpcb.zip" 2>/dev/null || true

  # JLCPCB order flow wants BOM + pick&place as separate uploads — pull
  # them out of the zip next to it.
  if [ -f "$out_abs/${m}_jlcpcb.zip" ]; then
    unzip -o -j "$out_abs/${m}_jlcpcb.zip" bom.csv -d "$out_abs" >/dev/null
    mv -f "$out_abs/bom.csv" "$out_abs/${m}-bom.csv"
    unzip -o -j "$out_abs/${m}_jlcpcb.zip" pick_and_place.csv -d "$out_abs" >/dev/null
    mv -f "$out_abs/pick_and_place.csv" "$out_abs/${m}-pick-and-place.csv"
  fi

  popd >/dev/null

  echo "==> [$m] Done -> $out/"
done
