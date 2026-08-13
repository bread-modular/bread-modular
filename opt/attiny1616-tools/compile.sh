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

# Auto-detect the sketch directory: find the single .ino file under $SCRIPT_DIR
# and use its parent directory as the sketch dir. Hidden dirs (e.g. .pio, .git)
# are skipped so build artifacts / vendored examples are ignored.
SKETCH_INO=()
while IFS= read -r f; do
  [[ -n "$f" ]] && SKETCH_INO+=("$f")
done < <(find "$SCRIPT_DIR" -name '.*' -prune -o -type f -name '*.ino' -print 2>/dev/null)

if [[ ${#SKETCH_INO[@]} -eq 0 ]]; then
  echo "Error: no .ino sketch found under $SCRIPT_DIR" >&2
  exit 1
elif [[ ${#SKETCH_INO[@]} -gt 1 ]]; then
  echo "Error: multiple .ino sketches found under $SCRIPT_DIR (expected exactly one):" >&2
  printf '  %s\n' "${SKETCH_INO[@]}" >&2
  exit 1
fi

SKETCH_DIR="$(dirname "${SKETCH_INO[0]}")"

# Load compile-time defines from an optional .config file (KEY=VALUE lines).
# Each entry becomes -DKEY=VALUE passed to the compiler, e.g. MIDI_CHAN_START=9.
EXTRA_FLAGS=""
if [[ -f "$SCRIPT_DIR/.config" ]]; then
  while IFS='=' read -r key val; do
    key="${key//[[:space:]]/}"
    val="${val//[[:space:]]/}"
    [[ -z "$key" || "$key" == \#* ]] && continue
    EXTRA_FLAGS+=" -D${key}=${val}"
  done < "$SCRIPT_DIR/.config"
fi

COMPILE_ARGS=(compile --fqbn "$FQBN")
if [[ -n "$EXTRA_FLAGS" ]]; then
  COMPILE_ARGS+=(--build-property "build.extra_flags=$EXTRA_FLAGS")
fi
COMPILE_ARGS+=("$SKETCH_DIR")

arduino-cli "${COMPILE_ARGS[@]}"
