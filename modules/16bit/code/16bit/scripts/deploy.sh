#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(dirname -- "$SCRIPT_DIR")"
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/.build}"
BUILD_TARGET="${BUILD_TARGET:-16bit}"
PICO_VOLUME_NAMES="${PICO_VOLUME_NAMES:-RPI-RP2 RP2350}"

usage() {
    cat <<EOF
Usage: ./scripts/deploy.sh [firmware.uf2]

Environment overrides:
  BUILD_DIR=/path/to/build          Build directory. Default: .build
  BUILD_TARGET=16bit                Target name. Default: 16bit
  DEPLOY_BUILD=0                    Skip building before upload
  PICO_VOLUME=/Volumes/RPI-RP2      Explicit Pico bootloader volume
  PICO_VOLUME_NAMES="RPI-RP2 RP2350" Bootloader volume names to detect
  PICOTOOL_BIN=/path/to/picotool    Path to picotool for auto-reset deploy
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

find_picotool() {
    if [ -n "${PICOTOOL_BIN:-}" ]; then
        if [ -x "$PICOTOOL_BIN" ]; then
            printf '%s\n' "$PICOTOOL_BIN"
            return 0
        fi
        printf 'WARNING: PICOTOOL_BIN does not exist or is not executable: %s\n' "$PICOTOOL_BIN" >&2
    fi

    local breadmodular_tool
    breadmodular_tool="$BREADMODULAR_HOME/picotool/2.2.0-a4/picotool/picotool"
    if [ -x "$breadmodular_tool" ]; then
        printf '%s\n' "$breadmodular_tool"
        return 0
    fi

    return 1
}

deploy_with_picotool() {
    local picotool_bin uf2
    picotool_bin="$1"
    uf2="$2"

    log "Using picotool for auto-reset deploy: $picotool_bin"
    "$picotool_bin" load -f "$uf2"
    log "Upload complete. The Pico will reboot automatically."
}

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
        printf '\n' >&2
        printf '  ⚠️  No Pico bootloader volume detected.\n' >&2
        printf '\n' >&2
        printf '  Hold BOOT then RESET on your Pico.\n' >&2
        printf '  You will see the "RP2350" directory — then run this script again.\n' >&2
        printf '\n' >&2
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

deploy_with_volume() {
    local uf2 pico_volume
    uf2="$1"
    pico_volume="$2"

    log "Found Pico bootloader volume: $pico_volume"

    case "$uf2" in
        *.uf2) ;;
        *) die "Firmware must be a .uf2 file: $uf2" ;;
    esac

    [ -f "$uf2" ] || die "UF2 firmware not found: $uf2. Run ./scripts/build.sh first or pass a .uf2 path."
    [ -d "$pico_volume" ] || die "Pico volume disappeared before upload: $pico_volume"
    [ -w "$pico_volume" ] || die "Pico volume is not writable: $pico_volume"

    log "Uploading $(basename -- "$uf2") to $pico_volume"
    cp "$uf2" "$pico_volume/"
    sync

    log "Upload complete. The Pico should reboot automatically."
}

if [ "$DEPLOY_BUILD" != "0" ]; then
    [ -x "$PROJECT_ROOT/scripts/build.sh" ] || die "build.sh is missing or not executable."
    log "Building firmware before deploy"
    "$PROJECT_ROOT/scripts/build.sh"
fi

PICOTOOL_PATH="$(find_picotool || true)"

if [ -z "$PICOTOOL_PATH" ]; then
    die "picotool not found. Run ./scripts/setup.sh first."
fi

deploy_with_picotool "$PICOTOOL_PATH" "$UF2_PATH"