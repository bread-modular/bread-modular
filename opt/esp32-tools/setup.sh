#!/usr/bin/env bash
# setup.sh — one-time setup for compiling & flashing the ESP32-S3 (32bit) firmware.
# Installs ESP-IDF + the esp32s3 toolchain. No PlatformIO / VSCode / Homebrew required.
#
# Safe to re-run (idempotent).
#
set -euo pipefail

# Resolve the real location of this script (follow the symlink) so we can find
# common.sh next to it in opt/esp32-tools/.
SELF="$0"
while [[ -L "$SELF" ]]; do
  DIR="$(cd -P "$(dirname "$SELF")" && pwd)"
  TARGET="$(readlink "$SELF")"
  [[ "$TARGET" != /* ]] && TARGET="$DIR/$TARGET"
  SELF="$TARGET"
done
TOOLS_DIR="$(cd -P "$(dirname "$SELF")" && pwd)"

# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

IDF_VERSION="${IDF_VERSION:-v5.5.1}"
IDF_TARGET="${IDF_TARGET:-esp32s3}"
IDF_DIR="${IDF_DIR:-$HOME/esp/esp-idf}"
IDF_REPO="https://github.com/espressif/esp-idf.git"
IDF_CLONE_BRANCH="${IDF_CLONE_BRANCH:-$IDF_VERSION}"

echo "==> Checking prerequisites (git, python3)"

MISSING=()
for cmd in git python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    MISSING+=("$cmd")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "Missing required tools: ${MISSING[*]}" >&2
  echo "" >&2
  echo "Install them with Homebrew:" >&2
  echo "  brew install ${MISSING[*]}" >&2
  echo "" >&2
  echo "(brew itself can be installed from https://brew.sh if you don't have it)" >&2
  exit 1
fi
echo "==> All prerequisites present."

# --- 1. Clone ESP-IDF ----------------------------------------------------------
if [[ -d "$IDF_DIR/.git" ]]; then
  echo "==> ESP-IDF already cloned at $IDF_DIR"
else
  echo "==> Cloning ESP-IDF ($IDF_VERSION) into $IDF_DIR ..."
  echo "    (this downloads ~1.5 GB, submodules included)"
  git clone --recursive --branch "$IDF_CLONE_BRANCH" --depth 1 "$IDF_REPO" "$IDF_DIR"
fi

# --- 2. Install the esp32s3 toolchain ------------------------------------------
echo "==> Installing ESP-IDF tools for target '$IDF_TARGET' ..."
"$IDF_DIR/install.sh" "$IDF_TARGET"

# --- 3. Install cmake + ninja --------------------------------------------------
# These are "on_request" tools: install.sh does NOT fetch them on macOS/Linux
# (only on Windows), so we request them explicitly. They land in
# ~/.espressif/tools/ and export.sh adds them to PATH.
echo "==> Installing cmake + ninja (on_request tools) ..."
python3 "$IDF_DIR/tools/idf_tools.py" install cmake ninja

echo ""
echo "✅ Setup complete."
echo "   Next: ./compile.sh   (build)"
echo "         ./flash.sh     (upload via USB)"
echo "         ./package.sh   (build + package all apps for the web installer)"
