#!/usr/bin/env bash
# flash.sh — upload the ESP32-S3 (32bit) firmware over USB (UART).
#
# Usage:
#   ./flash.sh                        # list serial ports and pick one
#   ./flash.sh pipe                   # build+flash a specific app
#   ./flash.sh /dev/cu.usbmodemXXXX   # explicit port
#   ./flash.sh pipe /dev/cu.usbmodemXXXX
#
set -euo pipefail

# Resolve the real location of this script (follow the symlink).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SELF="${BASH_SOURCE[0]}"
while [[ -L "$SELF" ]]; do
  DIR="$(cd -P "$(dirname "$SELF")" && pwd)"
  TARGET="$(readlink "$SELF")"
  [[ "$TARGET" != /* ]] && TARGET="$DIR/$TARGET"
  SELF="$TARGET"
done
TOOLS_DIR="$(cd -P "$(dirname "$SELF")" && pwd)"

# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

# Parse args: first non-port arg = app name, a /dev/... arg = port.
APP_NAME="${APP_NAME:-}"
PORT="${PORT:-}"
for arg in "$@"; do
  if [[ "$arg" == /dev/* ]]; then
    PORT="$arg"
  else
    APP_NAME="$arg"
  fi
done

activate_idf

# Resolve the upload port if not explicitly given.
if [[ -z "$PORT" ]]; then
  echo "==> Detecting serial ports..."
  PORTS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && PORTS+=("$line")
  done < <(ls /dev/cu.* 2>/dev/null | grep -viE 'bluetooth|debug-console|debug_console' || true)

  if [[ ${#PORTS[@]} -eq 0 ]]; then
    echo "No serial ports found. Plug in the ESP32-S3 over USB and retry, or pass a port:" >&2
    echo "  ./flash.sh /dev/cu.usbmodemXXXX" >&2
    exit 1
  elif [[ ${#PORTS[@]} -eq 1 ]]; then
    PORT="${PORTS[0]}"
    echo "==> Only one serial port found: $PORT"
  else
    echo "==> Multiple serial ports found. Select the ESP32-S3:"
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

if [[ -n "$APP_NAME" ]]; then
  echo "==> Building & flashing firmware (target: $IDF_TARGET, app: $APP_NAME, port: $PORT) ..."
else
  echo "==> Building & flashing firmware (target: $IDF_TARGET, default app, port: $PORT) ..."
fi
cd "$PROJECT_DIR"

FLASH_ARGS=(-p "$PORT" flash)
if [[ -n "$APP_NAME" ]]; then
  idf.py -D "APP_NAME=$APP_NAME" "${FLASH_ARGS[@]}"
else
  idf.py "${FLASH_ARGS[@]}"
fi

echo "✅ Flash complete."
