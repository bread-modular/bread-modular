#!/usr/bin/env bash
#
# workspace_init.sh — runs automatically when a new workspace is created.
#   $1 = original project directory (the main repo checkout)
#
# Initializes the git submodules needed to BUILD firmware apps (16bit/32bit).
# KiCad library submodules under opt/ are intentionally skipped — they are only
# used for PCB design, not for building apps.
#
# Speed optimization: instead of cloning each submodule from the network, we
# clone from the already-checked-out copy in the original project directory via
# `git submodule update --reference`. Combined with `--dissociate`, the result
# is a fully standalone local clone (no network, no dangling alternates link).
# Falls back to a normal network clone if the local copy isn't available.

set -euo pipefail

ORIGINAL_DIR="${1:-}"

# Resolve the workspace root (where this script lives).
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log()  { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }

# Prefix of submodules that are KiCad-only and must be skipped.
KICAD_PREFIX="opt/"

# ---------------------------------------------------------------------------
# Discover all submodule paths from .gitmodules and split into build vs KiCad.
# (POSIX-safe loop — avoids bash-only `mapfile`, since macOS ships bash 3.2.)
# ---------------------------------------------------------------------------
BUILD_SUBMODULES=""
while IFS= read -r path; do
    [ -n "$path" ] || continue
    case "$path" in
        "$KICAD_PREFIX"*)
            log "Skipping KiCad submodule: $path"
            ;;
        *)
            BUILD_SUBMODULES="$BUILD_SUBMODULES $path"
            ;;
    esac
done < <(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' \
            | sed 's/^[^ ]* //')

# Trim leading space.
BUILD_SUBMODULES="${BUILD_SUBMODULES# }"

if [ -z "$BUILD_SUBMODULES" ]; then
    log "No build submodules to initialize."
    exit 0
fi

log "Build submodules to initialize:$BUILD_SUBMODULES"

# ---------------------------------------------------------------------------
# Initialize each build submodule.
# ---------------------------------------------------------------------------
for path in $BUILD_SUBMODULES; do
    # Already initialized? (has a .git file or directory and content)
    if [ -e "$path/.git" ] || [ -d "$path/.git" ]; then
        log "Already initialized: $path"
        continue
    fi

    ref=""
    if [ -n "$ORIGINAL_DIR" ] && [ -e "$ORIGINAL_DIR/$path/.git" ]; then
        ref="$ORIGINAL_DIR/$path"
    fi

    if [ -n "$ref" ]; then
        log "Copying local copy of '$path' from original repo (fast path)"
        git submodule update --init --dissociate --reference "$ref" -- "$path"
    else
        warn "No local copy of '$path' found — cloning from network"
        git submodule update --init -- "$path"
    fi
done

# ---------------------------------------------------------------------------
# Install npm modules preferring local cache (ts-modules).
# A fresh worktree lacks node_modules (gitignored), so copy the already-
# installed tree from the original checkout, then let npm fill any gaps
# from its local cache via --prefer-offline.
# ---------------------------------------------------------------------------
log "Installing npm modules..."
if [ -d "$ORIGINAL_DIR/ts-modules/node_modules" ]; then
    echo "Found local node_modules cache, copying..."
    cp -r "$ORIGINAL_DIR/ts-modules/node_modules" ts-modules/ 2>/dev/null || true
fi
(cd ts-modules && npm install --prefer-offline --no-audit --no-fund) ||
    warn "npm install failed — tscircuit builds may not work."

log "Submodule initialization complete."
