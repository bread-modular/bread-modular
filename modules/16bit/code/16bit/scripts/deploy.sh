#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/.build}"
BUILD_TARGET="${BUILD_TARGET:-16bit}"
PICO_VOLUME_NAMES="${PICO_VOLUME_NAMES:-RPI-RP2 RP2350}"

usage() {
    cat <<EOF
Usage: ./deploy.sh [firmware.uf2]

Environment overrides:
  BUILD_DIR=/path/to/build          Build directory. Default: .build
  BUILD_TARGET=16bit                Target name. Default: 16bit
  DEPLOY_BUILD=0                    Skip building before upload
  PICO_VOLUME=/Volumes/RPI-RP2      Explicit Pico bootloader volume
  PICO_VOLUME_NAMES="RPI-RP2 RP2350" Bootloader volume names to detect
EOF
}

log() {
    printf '==> %s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

if [ "$#" -gt 1 ]; then
    usage >&2
    exit 1
fi

if [ "$#" -eq 1 ]; then
    UF2_PATH="$1"
    DEPLOY_BUILD="${DEPLOY_BUILD:-0}"
else
    UF2_PATH="${UF2_PATH:-$BUILD_DIR/$BUILD_TARGET.uf2}"
    DEPLOY_BUILD="${DEPLOY_BUILD:-1}"
fi

if [ -d "$BREADMODULAR_HOME/bin" ]; then
    export PATH="$BREADMODULAR_HOME/bin:$PATH"
fi

find_pico_volume() {
    if [ -n "${PICO_VOLUME:-}" ]; then
        if [ -d "$PICO_VOLUME" ] && [ -r "$PICO_VOLUME" ] && [ -f "$PICO_VOLUME/INDEX.HTM" ]; then
            printf '%s\n' "$PICO_VOLUME"
            return 0
        fi
        printf 'ERROR: PICO_VOLUME does not exist, is not readable, or lacks INDEX.HTM: %s\n' "$PICO_VOLUME" >&2
        return 1
    fi

    local matches=()
    local volume
    local name
    local basename
    for volume in /Volumes/*; do
        [ -d "$volume" ] || continue
        basename=$(basename "$volume")
        for name in $PICO_VOLUME_NAMES; do
            if [[ "$basename" == "$name"* ]]; then
                if [ -r "$volume" ] && [ -f "$volume/INDEX.HTM" ]; then
                    matches+=("$volume")
                fi
                break
            fi
        done
    done

    if [ "${#matches[@]}" -eq 0 ]; then
        printf 'ERROR: No Pico bootloader volume found that is readable and contains INDEX.HTM. Looked for: %s\n' "$PICO_VOLUME_NAMES" >&2
        return 1
    fi

    if [ "${#matches[@]}" -gt 1 ]; then
        printf 'ERROR: Multiple Pico bootloader volumes found that are readable and contain INDEX.HTM:\n' >&2
        printf '  %s\n' "${matches[@]}" >&2
        printf 'Set PICO_VOLUME to the one you want to deploy to.\n' >&2
        return 1
    fi

    printf '%s\n' "${matches[0]}"
}

PICO_VOLUME_PATH="$(find_pico_volume || true)"
if [ -z "$PICO_VOLUME_PATH" ]; then
    die "No Pico bootloader volume found that is readable and contains INDEX.HTM. Hold BOOTSEL while plugging in the Pico, then rerun. Looked for: $PICO_VOLUME_NAMES"
fi

log "Found Pico bootloader volume: $PICO_VOLUME_PATH"

if [ "$DEPLOY_BUILD" != "0" ]; then
    [ -x "$PROJECT_ROOT/build.sh" ] || die "build.sh is missing or not executable."
    log "Building firmware before deploy"
    "$PROJECT_ROOT/build.sh"
fi

case "$UF2_PATH" in
    *.uf2) ;;
    *) die "Firmware must be a .uf2 file: $UF2_PATH" ;;
esac

[ -f "$UF2_PATH" ] || die "UF2 firmware not found: $UF2_PATH. Run ./build.sh first or pass a .uf2 path."
[ -d "$PICO_VOLUME_PATH" ] || die "Pico volume disappeared before upload: $PICO_VOLUME_PATH"
[ -w "$PICO_VOLUME_PATH" ] || die "Pico volume is not writable: $PICO_VOLUME_PATH"

log "Uploading $(basename -- "$UF2_PATH") to $PICO_VOLUME_PATH"
cp "$UF2_PATH" "$PICO_VOLUME_PATH/"
sync

log "Upload complete. The Pico should reboot automatically."
