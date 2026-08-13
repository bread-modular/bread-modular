#!/usr/bin/env bash
#
# compile.sh — build the ATtiny1616 firmware (no PlatformIO / VSCode).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/bin:$PATH"

# megaTinyCore board = grouped "atxy6" (16 KB flash family), chip = ATtiny1616,
# 20 MHz internal oscillator (matches the original PlatformIO build).
FQBN="megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli not found. Run ./setup.sh first." >&2
  exit 1
fi

arduino-cli compile --fqbn "$FQBN" "$SCRIPT_DIR/midi/"
