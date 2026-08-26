#!/usr/bin/env bash
# Build and run the host DSP simulator + tests for the 16bit monosynth app.
#
# The simulator compiles the SAME pico-free DSP core (monosynth_dsp.h) the firmware
# app uses, renders the "audio out" to a WAV, analyses it, and runs self-tests.
# No hardware / firmware required.
#
# Usage:
#   ./tools/run_monosynth_sim.sh            # build + run tests (no output wav)
#   ./tools/run_monosynth_sim.sh --wav      # build + run tests + write monosynth_sim.wav
#   python3 tools/analyze_monosynth_wav.py  # (optional) analyse the wav
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
PROJECT_ROOT="$(dirname -- "$SCRIPT_DIR")"
CXX="${CXX:-g++}"

cd "$PROJECT_ROOT"

build() {
    "$CXX" -std=c++17 -O2 -Wall -Wextra -I includes -o tools/sim_monosynth tools/sim_monosynth.cpp
}

build
echo "==> Running monosynth DSP tests $*"
./tools/sim_monosynth "$@"
