#!/usr/bin/env bash
# E2E test for build.sh's "reuse the routed board" behaviour.
#
# Verifies that build.sh only re-runs the autorouter when the placement changes:
#   1. First build ROUTES and saves src/<m>/<m>.routed.json + <m>.sig
#   2. A second, identical build REUSES the saved board (no re-route)
#   3. A silkscreen-only change REUSES the saved board (no re-route)
#   4. A placement (board-size) change RE-ROUTES and refreshes the artifact
#   5. A silkscreen-only change on the new placement REUSES again
#
# Run from the repo root:  ./ts-modules/test/e2e-routing-reuse.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"   # ts-modules root
cd "$DIR"

MODULE="_e2e_routing"
FIXTURE="src/$MODULE/$MODULE.circuit.tsx"
ARTIFACT="src/$MODULE/$MODULE.routed.json"

pass=0; fail=0
ok()   { echo "  PASS: $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL: $1"; fail=$((fail+1)); }

# capture a build run under a given env; echoes the message flow
run_build() { "$@"; }   # caller sets env inline, e.g.  E2E_NAME="x" run_build ./build.sh "$MODULE"

reused() { echo "$1" | grep -q "reusing saved"; }
routed() { echo "$1" | grep -q "Routing\.\.\."; }

echo "[e2e-routing-reuse] preparing fixture module..."
mkdir -p "src/$MODULE"
cat > "$FIXTURE" <<'EOF'
/**
 * E2E fixture (created by e2e-routing-reuse.sh, removed afterwards).
 * E2E_NAME -> board silkscreen (must NOT trigger a re-route).
 * E2E_W    -> board size (moves every placement, MUST trigger a re-route).
 */
import { BreadModule } from "../../lib";

export default () => (
  <BreadModule
    name={process.env.E2E_NAME || "E2E"}
    version="0.0.1"
    width={process.env.E2E_W ? Number(process.env.E2E_W) : undefined}
    height={process.env.E2E_W ? Number(process.env.E2E_W) : undefined}
  />
);
EOF
rm -f "$ARTIFACT" "src/$MODULE/$MODULE.sig"
rm -rf "dist/src/$MODULE"

echo "[e2e-routing-reuse] 1) first build should ROUTE + save the routed board"
out=$(E2E_NAME="E2E" run_build ./build.sh "$MODULE" 2>&1)
routed "$out" && ok "first build routed" || bad "first build did not route"
[ -f "$ARTIFACT" ]               && ok "routed board artifact saved" || bad "no artifact saved"
[ -s "src/$MODULE/$MODULE.sig" ] && ok "placement signature saved"    || bad "no signature saved"

echo "[e2e-routing-reuse] 2) identical build should REUSE (no re-route)"
out=$(E2E_NAME="E2E" run_build ./build.sh "$MODULE" 2>&1)
reused "$out" && ! routed "$out" && ok "identical build reused" || bad "identical build re-routed"

echo "[e2e-routing-reuse] 3) silkscreen change should REUSE (no re-route)"
out=$(E2E_NAME="E2E-CHANGED" run_build ./build.sh "$MODULE" 2>&1)
reused "$out" && ! routed "$out" && ok "silkscreen change reused" || bad "silkscreen change re-routed"
# the REUSED output must carry the NEW silkscreen text (not the stale one), and
# must still contain the routed traces from the saved board.
grep -q 'E2E-CHANGED' "dist/src/$MODULE/$MODULE/circuit.json" \
  && ok "reused output shows new silkscreen" || bad "reused output shows stale silkscreen"
grep -q '"pcb_trace"' "dist/src/$MODULE/$MODULE/circuit.json" \
  && ok "reused output preserves routing" || bad "reused output lost routing"

echo "[e2e-routing-reuse] 4) placement (board-size) change should RE-ROUTE"
out=$(E2E_NAME="E2E-CHANGED" E2E_W=22 run_build ./build.sh "$MODULE" 2>&1)
routed "$out" && ok "placement change re-routed" || bad "placement change did not re-route"

echo "[e2e-routing-reuse] 5) silkscreen change on the new placement should REUSE (no re-route)"
out=$(E2E_NAME="E2E" E2E_W=22 run_build ./build.sh "$MODULE" 2>&1)
reused "$out" && ! routed "$out" && ok "silkscreen-only change reused" || bad "silkscreen-only change re-routed"

# clean up the fixture so it never shows up as a real module / build target
rm -rf "src/$MODULE" "dist/src/$MODULE"

echo ""
if [ "$fail" -eq 0 ]; then
  echo "[e2e-routing-reuse] ALL PASSED ($pass checks)"
  exit 0
else
  echo "[e2e-routing-reuse] FAILED: $fail failed, $pass passed"
  exit 1
fi
