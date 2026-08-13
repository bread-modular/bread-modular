#!/usr/bin/env bash
# package.sh — build ALL apps and package each as a release bundle for the
# ESP Web Tools installer (into dist/<app>_<version>/).
#
# Usage:
#   ./package.sh                  # build all apps + package
#   ./package.sh --skip-build     # only package existing build artifacts
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

activate_idf

echo "==> Packaging firmware(s) for the web installer..."
cd "$PROJECT_DIR"
python3 scripts/make_installer.py "$@"

echo "✅ Packaging complete."
