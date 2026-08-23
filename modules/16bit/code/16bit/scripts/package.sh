#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(dirname -- "$SCRIPT_DIR")"
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/.build}"
DIST_DIR="${DIST_DIR:-$PROJECT_ROOT/dist}"

# Keep in sync with VALID_APPS in CMakeLists.txt
VALID_APPS=(noop sampler polysynth fxrack elab bass)

VERSION_FILE="$PROJECT_ROOT/../../VERSION"
if [ -f "$VERSION_FILE" ]; then
    VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
else
    VERSION="0.0.0"
fi

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<EOF
Usage: ./scripts/package.sh [app ...]

Builds one firmware per app (each app is compiled into its own binary) and
packages each .uf2 under dist/<app>_<version>/.

  app   Optional. One of: ${VALID_APPS[*]}
        If omitted, all apps are built.

Environment:
  BUILD_DIR  Build directory (default: .build)
  DIST_DIR   Output directory (default: dist)
EOF
}

for arg in "$@"; do
    if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
        usage
        exit 0
    fi
done

APPS=("$@")
if [ "${#APPS[@]}" -eq 0 ]; then
    APPS=("${VALID_APPS[@]}")
fi

for app in "${APPS[@]}"; do
    valid=0
    for v in "${VALID_APPS[@]}"; do
        if [ "$app" = "$v" ]; then valid=1; fi
    done
    [ "$valid" -eq 1 ] || die "Invalid app: $app (valid: ${VALID_APPS[*]})"
done

if [ -d "$BREADMODULAR_HOME/bin" ]; then
    export PATH="$BREADMODULAR_HOME/bin:$PATH"
fi

for app in "${APPS[@]}"; do
    log "Building firmware for app: $app"
    "$PROJECT_ROOT/scripts/build.sh" -DAPP_NAME="$app"

    UF2="$BUILD_DIR/16bit.uf2"
    [ -f "$UF2" ] || die "Build produced no firmware at $UF2 for app '$app'"

    out="$DIST_DIR/${app}_${VERSION}"
    mkdir -p "$out"
    cp "$UF2" "$out/16bit.uf2"
    log "Packaged $out/16bit.uf2"
done

log "Done. Firmwares written to $DIST_DIR"
