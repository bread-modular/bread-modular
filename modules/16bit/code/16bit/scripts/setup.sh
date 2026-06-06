#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(dirname -- "$SCRIPT_DIR")"
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"

PICO_SDK_VERSION="${PICO_SDK_VERSION:-2.1.1}"
PICO_SDK_REPO="${PICO_SDK_REPO:-https://github.com/raspberrypi/pico-sdk.git}"
PICO_SDK_ROOT="${PICO_SDK_ROOT:-$BREADMODULAR_HOME/pico-sdk}"
PICO_SDK_PATH="${PICO_SDK_PATH:-$PICO_SDK_ROOT/sdk/$PICO_SDK_VERSION}"

DEFAULT_CMAKE_VERSION="4.3.3"
DEFAULT_CMAKE_SHA256="5221a13450c7a0219a2a0d1b6c9085eb06489721fafd8488ccebc1584175d2fb"
CMAKE_VERSION="${CMAKE_VERSION:-$DEFAULT_CMAKE_VERSION}"
CMAKE_PACKAGE="${CMAKE_PACKAGE:-cmake-${CMAKE_VERSION}-macos-universal}"
CMAKE_ARCHIVE="${CMAKE_ARCHIVE:-$CMAKE_PACKAGE.tar.gz}"
CMAKE_URL="${CMAKE_URL:-https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/${CMAKE_ARCHIVE}}"
CMAKE_DOWNLOAD_DIR="${CMAKE_DOWNLOAD_DIR:-$BREADMODULAR_HOME/downloads}"
CMAKE_ROOT="${CMAKE_ROOT:-$BREADMODULAR_HOME/cmake}"
CMAKE_INSTALL_DIR="${CMAKE_INSTALL_DIR:-$CMAKE_ROOT/$CMAKE_PACKAGE}"
CMAKE_BIN_DIR="${CMAKE_BIN_DIR:-$BREADMODULAR_HOME/bin}"

PICOTOOL_VERSION="${PICOTOOL_VERSION:-2.2.0-a4}"
PICOTOOL_PACKAGE="${PICOTOOL_PACKAGE:-picotool-${PICOTOOL_VERSION}-mac}"
PICOTOOL_ARCHIVE="${PICOTOOL_ARCHIVE:-${PICOTOOL_PACKAGE}.zip}"
PICOTOOL_URL="${PICOTOOL_URL:-https://github.com/raspberrypi/pico-sdk-tools/releases/download/v2.2.0-3/${PICOTOOL_ARCHIVE}}"
PICOTOOL_DOWNLOAD_DIR="${PICOTOOL_DOWNLOAD_DIR:-$BREADMODULAR_HOME/downloads}"
PICOTOOL_ROOT="${PICOTOOL_ROOT:-$BREADMODULAR_HOME/picotool}"
PICOTOOL_INSTALL_DIR="${PICOTOOL_INSTALL_DIR:-$PICOTOOL_ROOT/$PICOTOOL_VERSION}"
PICOTOOL_BIN="${PICOTOOL_BIN:-$PICOTOOL_INSTALL_DIR/picotool/picotool}"

if [ -z "${CMAKE_SHA256+x}" ]; then
    if [ "$CMAKE_VERSION" = "$DEFAULT_CMAKE_VERSION" ] && [ "$CMAKE_ARCHIVE" = "$CMAKE_PACKAGE.tar.gz" ]; then
        CMAKE_SHA256="$DEFAULT_CMAKE_SHA256"
    else
        CMAKE_SHA256=""
    fi
fi

log() {
    printf '==> %s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

need() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

install_cmake() {
    local archive_path="$CMAKE_DOWNLOAD_DIR/$CMAKE_ARCHIVE"
    local cmake_bin="$CMAKE_INSTALL_DIR/CMake.app/Contents/bin/cmake"

    need curl
    need tar
    if [ -n "$CMAKE_SHA256" ]; then
        need shasum
    fi

    mkdir -p "$CMAKE_DOWNLOAD_DIR" "$CMAKE_ROOT" "$CMAKE_BIN_DIR"

    if [ ! -f "$archive_path" ]; then
        log "Downloading CMake $CMAKE_VERSION from $CMAKE_URL"
        curl -fL --retry 3 --retry-delay 2 -o "$archive_path.tmp" "$CMAKE_URL"
        mv "$archive_path.tmp" "$archive_path"
    else
        log "Using cached CMake archive: $archive_path"
    fi

    if [ -n "$CMAKE_SHA256" ]; then
        log "Verifying CMake archive checksum"
        printf '%s  %s\n' "$CMAKE_SHA256" "$archive_path" | shasum -a 256 -c -
    fi

    if [ ! -x "$cmake_bin" ]; then
        log "Installing CMake $CMAKE_VERSION to $CMAKE_INSTALL_DIR"
        rm -rf "$CMAKE_INSTALL_DIR"
        tar -xzf "$archive_path" -C "$CMAKE_ROOT"
        xattr -dr com.apple.quarantine "$CMAKE_INSTALL_DIR" 2>/dev/null || true
    else
        log "CMake already installed: $CMAKE_INSTALL_DIR"
    fi

    [ -x "$cmake_bin" ] || die "CMake install failed: $cmake_bin was not found"

    ln -sf "$cmake_bin" "$CMAKE_BIN_DIR/cmake"
    ln -sf "$CMAKE_INSTALL_DIR/CMake.app/Contents/bin/ctest" "$CMAKE_BIN_DIR/ctest"
    ln -sf "$CMAKE_INSTALL_DIR/CMake.app/Contents/bin/cpack" "$CMAKE_BIN_DIR/cpack"

    log "CMake ready: $cmake_bin"
}

install_picotool() {
    local archive_path="$PICOTOOL_DOWNLOAD_DIR/$PICOTOOL_ARCHIVE"
    local picotool_bin="$PICOTOOL_INSTALL_DIR/picotool/picotool"

    need curl
    need unzip

    mkdir -p "$PICOTOOL_DOWNLOAD_DIR" "$PICOTOOL_ROOT"

    if [ ! -f "$archive_path" ]; then
        log "Downloading picotool $PICOTOOL_VERSION from $PICOTOOL_URL"
        curl -fL --retry 3 --retry-delay 2 -o "$archive_path.tmp" "$PICOTOOL_URL"
        mv "$archive_path.tmp" "$archive_path"
    else
        log "Using cached picotool archive: $archive_path"
    fi

    if [ ! -x "$picotool_bin" ]; then
        log "Installing picotool $PICOTOOL_VERSION to $PICOTOOL_INSTALL_DIR"
        rm -rf "$PICOTOOL_INSTALL_DIR"
        unzip -q "$archive_path" -d "$PICOTOOL_INSTALL_DIR"
        xattr -dr com.apple.quarantine "$PICOTOOL_INSTALL_DIR" 2>/dev/null || true
    else
        log "picotool already installed: $PICOTOOL_INSTALL_DIR"
    fi

    [ -x "$picotool_bin" ] || die "picotool install failed: $picotool_bin was not found"

    log "picotool ready: $picotool_bin"
}

need git

if git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 && \
   git -C "$PROJECT_ROOT" ls-files --stage -- lib/lfs | grep -q '^160000 '; then
    log "Downloading project submodule: lib/lfs"
    git -C "$PROJECT_ROOT" submodule sync -- lib/lfs
    git -C "$PROJECT_ROOT" submodule update --init --recursive -- lib/lfs
fi

mkdir -p "$(dirname -- "$PICO_SDK_PATH")"

if [ -d "$PICO_SDK_PATH/.git" ]; then
    log "Updating Pico SDK at $PICO_SDK_PATH"
    git -C "$PICO_SDK_PATH" remote set-url origin "$PICO_SDK_REPO"
    git -C "$PICO_SDK_PATH" fetch --tags --force origin
else
    if [ -e "$PICO_SDK_PATH" ]; then
        die "$PICO_SDK_PATH exists but is not a git checkout. Move it aside or set PICO_SDK_PATH."
    fi

    log "Downloading Pico SDK $PICO_SDK_VERSION from $PICO_SDK_REPO"
    git clone --branch "$PICO_SDK_VERSION" --depth 1 "$PICO_SDK_REPO" "$PICO_SDK_PATH"
fi

log "Checking out SDK version $PICO_SDK_VERSION"
git -C "$PICO_SDK_PATH" checkout --detach "$PICO_SDK_VERSION"

log "Downloading SDK submodules"
git -C "$PICO_SDK_PATH" submodule sync
git -C "$PICO_SDK_PATH" submodule update --init

install_cmake
install_picotool

ENV_FILE="$PROJECT_ROOT/.pico-sdk-env"
{
    printf 'export BREADMODULAR_HOME=%q\n' "$BREADMODULAR_HOME"
    printf 'export PICO_SDK_PATH=%q\n' "$PICO_SDK_PATH"
    printf 'export PICO_SDK_VERSION=%q\n' "$PICO_SDK_VERSION"
    printf 'export CMAKE_BIN=%q\n' "$CMAKE_BIN_DIR/cmake"
    printf 'export PICOTOOL_BIN=%q\n' "$PICOTOOL_BIN"
} > "$ENV_FILE"

log "Bread Modular tools ready: $BREADMODULAR_HOME"
log "Pico SDK ready: $PICO_SDK_PATH"
log "Environment file written: $ENV_FILE"
log "Run ./scripts/build.sh to build the firmware."
