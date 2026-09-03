#!/usr/bin/env bash
# silkscreen-editor wrapper — runs every command inside this package with the
# circuit package's toolchain (bun, tsci) on PATH, so the editor and
# `ts-modules/build.sh` always use the same bun + patched node_modules.
#
# Single-entry mode: the editor works on ONE .circuit.tsx per process.
# Pass its path to `dev` or `run inventory` — it becomes SILK_ENTRY.
#
# Usage:
#   ./silk.sh dev ../src/drive/drive.circuit.tsx   # UI + /api (vite :5175)
#   ./silk.sh run inventory ../src/drive/drive.circuit.tsx   # M1 JSON
#   ./silk.sh install                              # (re)install this package's deps
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TS_MODULES="$(cd "$DIR/.." && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"

# bun + tsci come from the circuit package (bun is an npm dep there).
export PATH="$TS_MODULES/node_modules/.bin:$PATH"

# User-land for the worker eval (react/tscircuit/circuit-to-svg). Default: the
# real ts-modules — entries under ts-modules/src/ would resolve there anyway,
# and fixture copies (e2e/fixtures/) need it explicitly. Explicit env wins.
export SILK_TS_MODULES_DIR="${SILK_TS_MODULES_DIR:-$TS_MODULES}"

cd "$DIR"

# Keep the KiCad silkscreen-font patch applied (idempotent, same as build.sh).
node "$REPO_ROOT/scripts/kicad-font/apply-kicad-font-patch.mjs" "$TS_MODULES" >/dev/null 2>&1 || true

if [ ! -d node_modules ]; then
  echo "==> Installing editor deps (bun install)…"
  bun install
fi

# First non-flag arg that names an existing .circuit.tsx becomes SILK_ENTRY.
# (Lets `./silk.sh dev <path>` and `./silk.sh run inventory <path>` share one
# convention; explicit SILK_ENTRY in the environment wins.)
maybe_claim_entry() {
  if [ -n "${SILK_ENTRY:-}" ]; then return 0; fi
  for a in "$@"; do
    case "$a" in
      -*) continue ;;
      *.circuit.tsx)
        if [ -f "$a" ]; then
          export SILK_ENTRY="$(cd "$(dirname "$a")" && pwd)/$(basename "$a")"
          return 0
        fi
        ;;
    esac
  done
  return 1
}

# Strip the claimed entry path from $@ — downstream scripts (vite, bun run)
# must never see it as a positional arg (vite treats one as [root] and would
# serve the wrong directory with no middleware).
strip_entry() {
  local out=()
  for a in "$@"; do
    if [ -z "${STRIPPED:-}" ]; then
      case "$a" in
        -*) out+=("$a"); continue ;;
        *.circuit.tsx)
          if [ -n "${SILK_ENTRY:-}" ] && [ "$(cd "$(dirname "$a")" 2>/dev/null && pwd)/$(basename "$a")" = "$SILK_ENTRY" ]; then
            STRIPPED=1
            continue
          fi
          out+=("$a") ;;
        *) out+=("$a") ;;
      esac
    else
      out+=("$a")
    fi
  done
  if [ "${#out[@]}" -gt 0 ]; then
    printf '%s\n' "${out[@]}"
  fi
}

CMD="${1:-}"
[ $# -gt 0 ] && shift

case "$CMD" in
  dev)
    maybe_claim_entry "$@" || {
      echo "usage: ./silk.sh dev <path-to.circuit.tsx>" >&2
      exit 2
    }
    mapfile -t REST < <(strip_entry "$@")
    exec bun run dev "${REST[@]}" ;;               # ./silk.sh dev <entry>
  run)
    maybe_claim_entry "$@" || {
      echo "usage: ./silk.sh run <script> <path-to.circuit.tsx>" >&2
      exit 2
    }
    mapfile -t REST < <(strip_entry "$@")
    exec bun run "${REST[@]}" ;;                   # ./silk.sh run inventory <entry>
  install)
    exec bun install ;;
  "")
    echo "usage: ./silk.sh dev <path-to.circuit.tsx> | ./silk.sh run <script> <path-to.circuit.tsx> | ./silk.sh install" >&2
    exit 2
    ;;
  *)        exec bun run "$CMD" "$@" ;;            # any package.json script
esac
