#!/usr/bin/env bash
# ============================================================================
# Build & run the crash firmware's host simulator / self-tests.
#
# No hardware, no arduino-cli — compiles the real firmware headers
# (CvRecorder.h, SimpleMIDI.h, CrashSynth.h) against a tiny Arduino API shim
# (sim/Arduino.h) with plain c++ and runs assertions on them.
#
# Usage:
#   ./sim.sh              # build + run all tests (exit 0 = pass)
#   CXX=g++ ./sim.sh      # pick a compiler explicitly
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-c++}"
SRC="sim/test_cv_recorder.cpp"
BIN="sim/test_cv_recorder"

echo ">> building host simulator ($CXX)..."
"$CXX" -std=c++11 -Wall -Wextra -Isim "$SRC" -o "$BIN"

echo ">> running tests..."
"$BIN"
