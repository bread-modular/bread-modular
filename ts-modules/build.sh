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
#
# Reusing the routed board (avoid re-running the autorouter each build):
#   `tsci build` derives the PCB routing from the layout, so we keep the routed
#   board as a git-tracked artifact and only re-route when the layout changes:
#     - src/<name>/<name>.routed.json   the routed circuit (PCB traces included)
#     - src/<name>/<name>.sig           a placement+netlist signature
#   - If the placement+netlist signature is unchanged, the saved routing
#     (pcb_trace / pcb_via) is merged onto the fresh eval and reused (no
#     autorouter); only the fab outputs are regenerated.
#   - A placement / footprint / net change produces a different signature -> the
#     board is re-routed and the artifact is refreshed.
#   - Silkscreen / schematic-annotation changes are excluded from the signature,
#     so they reuse the routed board without re-routing.
#
# NOTE: `tsci export` only renders a circuit.json when it lives at its canonical
# dist/.../circuit.json path, so exports are always run from that path.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export PATH="$DIR/node_modules/.bin:$PATH"

# Apply the KiCad silkscreen-font patch to node_modules (idempotent; no-op if
# already patched). tscircuit only ships its own stroke font, but the gerber
# silkscreen must match the KiCad originals — see scripts/kicad-font/.
node ../scripts/kicad-font/apply-kicad-font-patch.mjs . >/dev/null 2>&1 || true

# placement signature: hash only the circuit elements that define the ROUTING
# problem — component placement, pads, holes, board bounds, and the netlist /
# connectivity (source/schematic traces). Everything else is EXCLUDED so it never
# forces a re-route:
#   - source_project_metadata (a whole-project filesystem hash -> unstable!)
#   - pcb_trace / routed silkscreen (routing output & visuals)
#   - schematic_text / schematic_net_label (annotations)
#   - pcb_solder_paste / pcb_courtyard_rect (derived renders)
#   - *_warning / *_error (diagnostics), simulation_* (simulation)
sig_of() {
  python3 -c '
import json, sys, hashlib
d = json.load(sys.stdin)
PLACEMENT = {
    # placement & connections that define the routing problem
    "pcb_component", "pcb_smtcomponent", "pcb_port", "pcb_board",
    "pcb_plated_hole", "pcb_hole", "pcb_cutout", "pcb_keepout",
    "source_component", "source_port", "source_net", "source_trace", "schematic_trace",
}
f = [e for e in d if e.get("type", "") in PLACEMENT]
f.sort(key=lambda e: json.dumps(e, sort_keys=True))
print(hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest())
'
}

# Merge routing-only elements (pcb_trace / pcb_via) taken from the saved
# <m>.routed.json ONTO the freshly-evaluated (--routing-disabled) circuit JSON.
# We CAN'T reuse the whole saved artifact: it still carries the OLD silkscreen
# text/annotations, so a silkscreen-only change would re-export stale text. The
# fresh eval holds the NEW text; the saved file only contributes the routing
# geometry (sig equality guarantees the referenced port/component ids match).
# The merged result is written back over $1 (the fresh dist circuit).
merge_routes() {   # $1=fresh dist circuit.json, $2=saved <m>.routed.json
  python3 -c '
import json, sys
fresh = json.load(open(sys.argv[1]))
saved = json.load(open(sys.argv[2]))
ROUTE_TYPES = {"pcb_trace", "pcb_via"}
# fresh eval first (keeps NEW silkscreen/annotations/placement), then append the
# routing output pulled from the saved routed board.
merged = [e for e in fresh if e.get("type", "") not in ROUTE_TYPES]
merged += [e for e in saved if e.get("type", "") in ROUTE_TYPES]
json.dump(merged, open(sys.argv[1], "w"))
' "$1" "$2"
}

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

  entry="src/$m/$m.circuit.tsx"
  out="src/$m/out"
  mkdir -p "$out"
  out_abs="$DIR/$out"                      # tsci resolves -o relative to entry dir
  dist_circuit="dist/src/$m/$m/circuit.json"
  routed_json="$DIR/src/$m/$m.routed.json"
  sig_file="$DIR/src/$m/$m.sig"

  # 1) Fast eval (no autoroute) to get the CURRENT placement+netlist signature.
  #    tsci build writes the circuit to dist/.../circuit.json.
  echo "==> [$m] Checking placement (eval, no routing)..."
  tsci build --routing-disabled "$entry" >/dev/null 2>&1

  if [ -s "dist/src/$m/$m/circuit.json" ]; then
    curr_sig="$(sig_of < "$dist_circuit")"
  else
    curr_sig=""                              # no circuit -> force a fresh route
  fi

  # 2) Reuse the saved routed board if the placement is unchanged, else re-route.
  if [ -f "$routed_json" ] && [ -f "$sig_file" ] && [ "$(cat "$sig_file")" = "$curr_sig" ]; then
    echo "==> [$m] Placement unchanged — reusing saved $m.routed.json (no re-route)"
    # Populate dist with fresh placement + NEW silkscreen + the saved routing.
    merge_routes "$dist_circuit" "$routed_json"
  else
    echo "==> [$m] Routing..."
    tsci build "$entry"                     # full autoroute -> dist
    cp "$dist_circuit" "$routed_json"       # save the routed artifact
    echo "$curr_sig" > "$sig_file"          # record the placement signature
  fi

  # 3) Generate all outputs FROM the routed board. tsci export won't re-run the
  #    autorouter for a circuit.json that already carries its pcb_trace output.
  echo "==> [$m] Schematic SVG..."
  tsci export "$dist_circuit" -f schematic-svg -o "$out_abs/$m-schematic.svg"

  echo "==> [$m] PCB SVG..."
  tsci export "$dist_circuit" -f pcb-svg -o "$out_abs/$m-pcb.svg"

  echo "==> [$m] Assembly view..."
  tsci export "$dist_circuit" -f assembly-svg -o "$out_abs/$m-assembly.svg"

  echo "==> [$m] JLCPCB fabrication package (gerbers + drill + BOM + CPL)..."
  tsci export "$dist_circuit" -f gerbers -o "$out_abs/fabrication"
  mv -f "$out_abs/fabrication" "$out_abs/${m}_jlcpcb.zip" 2>/dev/null || true

  # JLCPCB order flow wants BOM + pick&place as separate uploads — pull
  # them out of the zip next to it.
  if [ -f "$out_abs/${m}_jlcpcb.zip" ]; then
    unzip -o -j "$out_abs/${m}_jlcpcb.zip" bom.csv -d "$out_abs" >/dev/null
    mv -f "$out_abs/bom.csv" "$out_abs/${m}-bom.csv"
    unzip -o -j "$out_abs/${m}_jlcpcb.zip" pick_and_place.csv -d "$out_abs" >/dev/null
    mv -f "$out_abs/pick_and_place.csv" "$out_abs/${m}-pick-and-place.csv"
  fi

  echo "==> [$m] Done -> $out/"
done
