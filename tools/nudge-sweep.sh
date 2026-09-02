#!/usr/bin/env bash
# Micro-nudge sweep for 8bit DRC-clean layout (see trick: autorouter cache
# busting + micro-nudge sweep). Applies ONE tiny nudge, rebuilds, counts
# clearance errors, reverts. Run from repo root: tools/nudge-sweep.sh
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/ts-modules/node_modules/.bin:$PATH"  # tsci's shebang needs bun
TSX=ts-modules/src/8bit/8bit.circuit.tsx
BAK=/tmp/8bit-best.tsx
CACHE=ts-modules/.tscircuit/cache

count_errors() {
  python3 - <<'EOF'
import json
d = json.load(open('ts-modules/dist/src/8bit/8bit/circuit.json'))
n = 0
skipped = False
for e in d:
    t = e.get('type','')
    if t == 'pcb_autorouting_error':
        skipped = True
    if 'error' in t and 'warning' not in t and t != 'pcb_autorouting_error':
        n += 1
print(f"{n}{'+SKIPPED' if skipped else ''}")
EOF
}

cp "$TSX" "$BAK"
echo "baseline (current layout): $(count_errors)"

run_candidate() {
  local desc="$1" sedexpr="$2"
  cp "$BAK" "$TSX"
  python3 - "$TSX" "$sedexpr" <<'EOF'
import sys
path, expr = sys.argv[1], sys.argv[2]
old, new = expr.split('=>')
s = open(path).read()
if old not in s:
    print("PATTERN-MISS"); sys.exit(3)
s = s.replace(old, new, 1)
open(path, 'w').write(s)
EOF
  local rc=$?
  if [ $rc -ne 0 ]; then echo "$desc => PATTERN-MISS"; cp "$BAK" "$TSX"; return; fi
  rm -rf "$CACHE"
  ( cd ts-modules/src/8bit && tsci build 8bit.circuit.tsx >/tmp/nudge-build.log 2>&1 )
  local res; res=$(count_errors)
  echo "$desc => $res"
  if [ "$res" = "0" ]; then
    cp "$TSX" /tmp/8bit-zero.tsx
    echo "  *** ZERO ERRORS FOUND — saved to /tmp/8bit-zero.tsx ***"
  fi
  cp "$BAK" "$TSX"
}

# ---- candidates: component micro-nudges (one at a time) ----
run_candidate "U3 x+0.4"      'pcbX={-4.11} pcbY={17.145} => pcbX={-3.71} pcbY={17.145}'
run_candidate "U3 x-0.4"      'pcbX={-4.11} pcbY={17.145} => pcbX={-4.51} pcbY={17.145}'
run_candidate "U3 y+0.4"      'pcbX={-4.11} pcbY={17.145} => pcbX={-4.11} pcbY={17.545}'
run_candidate "U1 x+0.4"      'name="U1" schX={5.5} schY={2} pcbX={5.145} => name="U1" schX={5.5} schY={2} pcbX={5.545}'
run_candidate "U1 x-0.4"      'name="U1" schX={5.5} schY={2} pcbX={5.145} => name="U1" schX={5.5} schY={2} pcbX={4.745}'
run_candidate "RV1 x+0.5"     'label="LOWPASS" schX={3} schY={-4} pcbX={6.858} => label="LOWPASS" schX={3} schY={-4} pcbX={7.358}'
run_candidate "RV1 x-0.5"     'label="LOWPASS" schX={3} schY={-4} pcbX={6.858} => label="LOWPASS" schX={3} schY={-4} pcbX={6.358}'
run_candidate "RV1 y-0.5"     'pcbX={6.858} pcbY={-11.407} => pcbX={6.858} pcbY={-11.907}'
run_candidate "RV2 y+0.5"     'pcbX={-6.985} pcbY={5.6} => pcbX={-6.985} pcbY={6.1}'
run_candidate "RV2 x+0.4"     'pcbX={-6.985} pcbY={5.6} => pcbX={-6.585} pcbY={5.6}'
run_candidate "C1 x-0.5"      'footprint="1206" schX={-8.5} schY={-6.5} pcbX={-4.85} => footprint="1206" schX={-8.5} schY={-6.5} pcbX={-5.35}'
run_candidate "C2 x-0.5"      'footprint="0402" schX={4.5} schY={-5.5} pcbX={-0.9} => footprint="0402" schX={4.5} schY={-5.5} pcbX={-1.4}'
run_candidate "R1 y+0.4"      'pcbX={-12.2} pcbY={14.5} => pcbX={-12.2} pcbY={14.9}'
run_candidate "D1 y+0.4"      'name="D1" footprint="0603" schX={-1} schY={5.5} pcbX={-10.9475} pcbY={-5.08} => name="D1" footprint="0603" schX={-1} schY={5.5} pcbX={-10.9475} pcbY={-4.68}'

cp "$BAK" "$TSX"
echo "sweep done — file restored to baseline"
[ -f /tmp/8bit-zero.tsx ] && echo "ZERO-ERROR LAYOUT: /tmp/8bit-zero.tsx" || echo "no zero-error candidate found"
