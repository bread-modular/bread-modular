#!/usr/bin/env bash
#
# flash.sh — upload the ATtiny1616 firmware via UPDI (no PlatformIO / VSCode).
#
# Usage:
#   ./flash.sh                        # list serial ports and pick one
#   ./flash.sh /dev/cu.usbserial-XXXX # explicit port
#
# Default programmer = "jtag2updi" (avrdude @ 115200 baud). This project's custom
# UPDI programmer board runs the jtag2updi firmware (an ATtiny1616), so it does
# NOT speak the "serialupdi" bit-bang protocol.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/bin:$PATH"

FQBN="megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal"
# Override with e.g. PROGRAMMER=serialupdi (plain USB-serial + 4.7k resistor).
PROGRAMMER="${PROGRAMMER:-jtag2updi}"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli not found. Run ./setup.sh first." >&2
  exit 1
fi

# Resolve the upload port: explicit arg > $PORT env > interactive selection.
PORT="${1:-${PORT:-}}"
if [[ -z "$PORT" ]]; then
  echo "==> Detecting serial ports..."
  # Collect candidate ports (skip Bluetooth / debug-console virtual ports).
  PORTS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && PORTS+=("$line")
  done < <(arduino-cli board list --format json 2>/dev/null | \
    python3 -c 'import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(0)
skip=("bluetooth","debug-console","debug_console")
for b in d.get("detected_ports", []):
    p=b.get("port",{})
    addr=p.get("address","")
    if not addr:
        continue
    if any(s in addr.lower() for s in skip):
        continue
    print(addr)
' 2>/dev/null)

  if [[ ${#PORTS[@]} -eq 0 ]]; then
    echo "No serial ports found. Plug in the UPDI adapter and retry, or pass a port:" >&2
    echo "  ./flash.sh /dev/cu.usbserial-XXXX" >&2
    exit 1
  fi

  if [[ ${#PORTS[@]} -eq 1 ]]; then
    PORT="${PORTS[0]}"
    echo "==> Only one serial port found: $PORT"
  else
    echo "==> Multiple serial ports found. Select the UPDI adapter:"
    for i in "${!PORTS[@]}"; do
      printf "  %d) %s\n" "$((i + 1))" "${PORTS[$i]}"
    done
    while true; do
      printf "Enter number (1-%d): " "${#PORTS[@]}"
      read -r SEL
      if [[ "$SEL" =~ ^[0-9]+$ ]] && (( SEL >= 1 && SEL <= ${#PORTS[@]} )); then
        PORT="${PORTS[$((SEL - 1))]}"
        break
      fi
      echo "Invalid selection. Try again." >&2
    done
  fi
fi

echo "==> Uploading to $PORT (programmer: $PROGRAMMER)"
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

UPLOAD_ARGS=(upload --fqbn "$FQBN" --port "$PORT" --programmer "$PROGRAMMER")
if [[ -n "$EXTRA_FLAGS" ]]; then
  UPLOAD_ARGS+=(--build-property "build.extra_flags=$EXTRA_FLAGS")
fi
UPLOAD_ARGS+=("$SKETCH_DIR")

arduino-cli "${UPLOAD_ARGS[@]}"
echo "✅ Flash complete."
