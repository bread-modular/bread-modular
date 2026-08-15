#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(dirname -- "$SCRIPT_DIR")"
DEFAULT_PICO_SDK_VERSION="2.1.1"
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"

PICO_SDK_VERSION="${PICO_SDK_VERSION:-$DEFAULT_PICO_SDK_VERSION}"
PICO_SDK_ROOT="${PICO_SDK_ROOT:-$BREADMODULAR_HOME/pico-sdk}"
PICO_SDK_PATH="${PICO_SDK_PATH:-$PICO_SDK_ROOT/sdk/$PICO_SDK_VERSION}"
TOOLCHAIN_VERSION="${TOOLCHAIN_VERSION:-14_2_Rel1}"
PICO_TOOLCHAIN_PATH="${PICO_TOOLCHAIN_PATH:-$BREADMODULAR_HOME/toolchain/$TOOLCHAIN_VERSION}"
BUILD_DIR="${BUILD_DIR:-$PROJECT_ROOT/.build}"
BUILD_TARGET="${BUILD_TARGET:-16bit}"
LOCAL_CMAKE_BIN="$BREADMODULAR_HOME/bin/cmake"
if [ -z "${CMAKE_BIN:-}" ] && [ -x "$LOCAL_CMAKE_BIN" ]; then
    CMAKE_BIN="$LOCAL_CMAKE_BIN"
else
    CMAKE_BIN="${CMAKE_BIN:-cmake}"
fi

log() {
    printf '==> %s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

if [ -d "$BREADMODULAR_HOME/bin" ]; then
    export PATH="$BREADMODULAR_HOME/bin:$PATH"
fi

if [ ! -f "$PICO_SDK_PATH/pico_sdk_init.cmake" ]; then
    die "Pico SDK not found at $PICO_SDK_PATH. Run ./scripts/setup.sh first."
fi

if [ ! -x "$PICO_TOOLCHAIN_PATH/bin/arm-none-eabi-gcc" ]; then
    die "ARM toolchain not found at $PICO_TOOLCHAIN_PATH. Run ./scripts/setup.sh first."
fi

if [ -n "${PICO_TOOLCHAIN_PATH:-}" ]; then
    export PATH="$PICO_TOOLCHAIN_PATH/bin:$PATH"
fi

command -v "$CMAKE_BIN" >/dev/null 2>&1 || die "CMake not found. Run ./scripts/setup.sh first or set CMAKE_BIN=/path/to/cmake."

if ! command -v arm-none-eabi-gcc >/dev/null 2>&1 && [ -z "${PICO_COMPILER:-}" ] && [ -z "${CMAKE_C_COMPILER:-}" ]; then
    log "Warning: arm-none-eabi-gcc was not found in PATH; CMake may fail unless a Pico-compatible toolchain is configured."
fi

export PICO_SDK_PATH

CMAKE_CONFIGURE_ARGS=()
if [ -n "${CMAKE_GENERATOR:-}" ]; then
    CMAKE_CONFIGURE_ARGS+=(-G "$CMAKE_GENERATOR")
elif [ -f "$BUILD_DIR/CMakeCache.txt" ]; then
    log "Reusing existing CMake generator from $BUILD_DIR"
elif [ -n "${NINJA_BIN:-}" ]; then
    CMAKE_CONFIGURE_ARGS+=(-G Ninja -DCMAKE_MAKE_PROGRAM="$NINJA_BIN")
elif command -v ninja >/dev/null 2>&1; then
    CMAKE_CONFIGURE_ARGS+=(-G Ninja)
else
    CMAKE_CONFIGURE_ARGS+=(-G "Unix Makefiles")
fi

if [ -n "${PICO_TOOLCHAIN_PATH:-}" ]; then
    CMAKE_CONFIGURE_ARGS+=(-DPICO_TOOLCHAIN_PATH="$PICO_TOOLCHAIN_PATH")
fi

if [ -n "${EXTRA_CMAKE_ARGS:-}" ]; then
    # shellcheck disable=SC2206
    CMAKE_CONFIGURE_ARGS+=($EXTRA_CMAKE_ARGS)
fi

# Resolve APP_NAME for local development. Precedence:
#   1. -DAPP_NAME=<x> passed on the command line (explicit)
#   2. APP_NAME=<x> in $PROJECT_ROOT/.config (local, uncommitted)
#   3. CMakeLists.txt default (polysynth)
CONFIG_FILE="$PROJECT_ROOT/.config"
app_from_cli=0
for arg in "$@"; do
    case "$arg" in
        -DAPP_NAME=*|APP_NAME=*) app_from_cli=1; break ;;
    esac
done

if [ "$app_from_cli" -eq 0 ] && [ -f "$CONFIG_FILE" ]; then
    cfg_app="$(sed -n 's/^[[:space:]]*APP_NAME[[:space:]]*=[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$CONFIG_FILE" | tail -n 1)"
    if [ -n "$cfg_app" ]; then
        log "Using app '$cfg_app' from $CONFIG_FILE"
        set -- "$@" "-DAPP_NAME=$cfg_app"
    fi
fi

CMAKE_CONFIGURE_ARGS+=("$@")
CMAKE_CONFIGURE_ARGS+=(-DPICO_SDK_PATH="$PICO_SDK_PATH")

JOBS="${JOBS:-}"
if [ -z "$JOBS" ]; then
    JOBS="$(sysctl -n hw.ncpu 2>/dev/null || true)"
fi
if [ -z "$JOBS" ] && command -v nproc >/dev/null 2>&1; then
    JOBS="$(nproc)"
fi
if [ -z "$JOBS" ]; then
    JOBS="4"
fi

log "Using Bread Modular tools: $BREADMODULAR_HOME"
log "Using CMake: $CMAKE_BIN"
log "Using Pico SDK: $PICO_SDK_PATH"
log "Configuring build directory: $BUILD_DIR"
"$CMAKE_BIN" -S "$PROJECT_ROOT" -B "$BUILD_DIR" \
    "${CMAKE_CONFIGURE_ARGS[@]}"

log "Building target '$BUILD_TARGET' with $JOBS job(s)"
"$CMAKE_BIN" --build "$BUILD_DIR" --target "$BUILD_TARGET" --parallel "$JOBS"
