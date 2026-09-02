#!/usr/bin/env bash
# Round-2 sweep: baseline = current 8bit tsx (C2 x-0.5 applied, 1 error left:
# U2.pin6->D1 trace vs U2.pin7->RV1 trace). Nudge D1 / U2 / RV1 / R6.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/ts-modules/node_modules/.bin:$PATH"
TSX=ts-modules/src/8bit/8bit.circuit.tsx
BAK=/tmp/8bit-r2.tsx
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
echo "round-2 baseline: $(count_errors)"

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
  ( cd ts-modules/src/8bit && tsci build 8bit.circuit.tsx >/tmp/nudge2-build.log 2>&1 )
  local res; res=$(count_errors)
  echo "$desc => $res"
  if [ "$res" = "0" ]; then
    cp "$TSX" /tmp/8bit-zero.tsx
    echo "  *** ZERO ERRORS FOUND — saved to /tmp/8bit-zero.tsx ***"
  fi
  cp "$BAK" "$TSX"
}

run_candidate "D1 x+0.4"  'pcbX={-10.9475} pcbY={-5.08} => pcbX={-10.5475} pcbY={-5.08}'
run_candidate "D1 x-0.4"  'pcbX={-10.9475} pcbY={-5.08} => pcbX={-11.3475} pcbY={-5.08}'
run_candidate "D1 y-0.4"  'pcbX={-10.9475} pcbY={-5.08} => pcbX={-10.9475} pcbY={-5.48}'
run_candidate "U2 x+0.4"  'name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.83} => name="U2" schX={0} schY={0.5} pcbX={-3.1} pcbY={-7.83}'
run_candidate "U2 x-0.4"  'name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.83} => name="U2" schX={0} schY={0.5} pcbX={-3.9} pcbY={-7.83}'
run_candidate "U2 y+0.4"  'name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.83} => name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.43}'
run_candidate "U2 y-0.4"  'name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.83} => name="U2" schX={0} schY={0.5} pcbX={-3.5} pcbY={-8.23}'
run_candidate "RV1 y+0.4" 'pcbX={6.858} pcbY={-11.407} => pcbX={6.858} pcbY={-11.007}'
run_candidate "R6 x+0.4"  'name="R6" resistance="330" footprint="0402" schX={0.5} schY={5.5} pcbX={-8.13} => name="R6" resistance="330" footprint="0402" schX={0.5} schY={5.5} pcbX={-7.73}'
run_candidate "R6 x-0.4"  'name="R6" resistance="330" footprint="0402" schX={0.5} schY={5.5} pcbX={-8.13} => name="R6" resistance="330" footprint="0402" schX={0.5} schY={5.5} pcbX={-8.53}'

cp "$BAK" "$TSX"
echo "round-2 done — file restored to round-2 baseline"
[ -f /tmp/8bit-zero.tsx ] && echo "ZERO-ERROR LAYOUT: /tmp/8bit-zero.tsx" || echo "no zero-error candidate found"
