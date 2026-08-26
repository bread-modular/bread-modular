#!/usr/bin/env bash
# test.sh — run every host DSP simulator self-test in tools/ (*_sim.cpp).
#
# Each tools/<name>_sim.cpp compiles against the SHARED pico-free DSP headers
# (includes/audio/apps/<app>/...) on the host with plain g++ — no firmware, no
# RP2350 SDK — and returns a non-zero exit code if any of its assertions fail.
#
# This is the reusable pattern for "testing a 16bit app without the firmware":
#   1. Keep the app's DSP in a pico-free header (e.g. includes/audio/apps/monosynth/monosynth_dsp.h).
#   2. Add tools/<name>_sim.cpp that includes that header, renders audio, and
#      runs assertions (white-box dsp state + black-box rendered-audio checks).
#   3. This script discovers it automatically.
#
# Usage:
#   ./scripts/test.sh                 # build & run all *_{sim,test}.cpp drivers
#   CXX=clang++ ./scripts/test.sh     # use a different host compiler
#
# Exit code = number of failing drivers.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
PROJECT_ROOT="$(dirname -- "$SCRIPT_DIR")"
CXX="${CXX:-g++}"

cd "$PROJECT_ROOT"

# Keep the compiled host drivers out of the tree (already git-ignored).
mkdir -p .build/host

total=0
failed=0

for src in tools/*sim*.cpp; do
    [ -e "$src" ] || continue
    name="$(basename "$src" .cpp)"
    bin=".build/host/$name"
    total=$((total + 1))
    echo ""
    echo "============================================================"
    echo "== Building + running: $name"
    echo "============================================================"
    "$CXX" -std=c++17 -O2 -Wall -Wextra -I includes -o "$bin" "$src"
    if "$bin"; then
        echo "  PASS: $name"
    else
        echo "  FAIL: $name"
        failed=$((failed + 1))
    fi
done

echo ""
echo "=== $total driver(s), $failed failure(s) ==="
[ "$failed" -eq 0 ]
