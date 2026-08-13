#!/usr/bin/env bash
# compile.sh — build the ESP32-S3 (32bit) firmware for one app.
#
# Usage:
#   ./compile.sh            # build the default app (fxrack)
#   ./compile.sh pipe       # build a specific app
#   APP_NAME=pipe ./compile.sh
#
set -euo pipefail

# Resolve the real location of this script (follow the symlink) so we can find
# common.sh next to it in opt/esp32-tools/. PROJECT_DIR is the symlink's own
# directory, i.e. the firmware project root.
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

# App selection: explicit arg > $APP_NAME env > CMake default (fxrack).
APP_NAME="${1:-${APP_NAME:-}}"

activate_idf

if [[ -n "$APP_NAME" ]]; then
  echo "==> Building firmware (target: $IDF_TARGET, app: $APP_NAME)..."
else
  echo "==> Building firmware (target: $IDF_TARGET, default app)..."
fi
cd "$PROJECT_DIR"
if [[ -n "$APP_NAME" ]]; then
  idf.py -D "APP_NAME=$APP_NAME" build
else
  idf.py build
fi

echo "✅ Build complete."
