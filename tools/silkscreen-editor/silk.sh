#!/usr/bin/env bash
# silkscreen-editor wrapper — runs every command inside this package with the
# circuit package's toolchain (bun, tsci) on PATH, so the editor and
# `ts-modules/build.sh` always use the same bun + patched node_modules.
#
# Usage:
#   ./silk.sh run inventory 8bit     # M1: headless silkscreen inventory JSON
#   ./silk.sh dev                    # M2: vite dev server (UI + /api middleware)
#   ./silk.sh install                # (re)install this package's deps
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"
TS_MODULES="$REPO_ROOT/ts-modules"

# bun + tsci come from the circuit package (bun is an npm dep there).
export PATH="$TS_MODULES/node_modules/.bin:$PATH"

cd "$DIR"

# Keep the KiCad silkscreen-font patch applied (idempotent, same as build.sh).
node "$REPO_ROOT/scripts/kicad-font/apply-kicad-font-patch.mjs" "$TS_MODULES" >/dev/null 2>&1 || true

if [ ! -d node_modules ]; then
  echo "==> Installing editor deps (bun install)…"
  bun install
fi

CMD="${1:-}"
[ $# -gt 0 ] && shift

case "$CMD" in
  run)      exec bun run "$@" ;;          # ./silk.sh run inventory 8bit
  dev)      exec bun run dev "$@" ;;      # ./silk.sh dev
  install)  exec bun install ;;
  "")
    echo "usage: ./silk.sh run <script> [args…] | ./silk.sh dev | ./silk.sh install" >&2
    exit 2
    ;;
  *)        exec bun run "$CMD" "$@" ;;   # any package.json script
esac
