#!/usr/bin/env bash
# Launch the tscircuit live UI (dev server) for a single module.
#
# Usage:
#   npm run ui <module-name>        e.g.  npm run ui blank
#
# Maps <module-name> -> src/<module>/<module>.circuit.tsx and starts the
# interactive dev server. The live URL is printed at the bottom of the output.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
export PATH="$DIR/node_modules/.bin:$PATH"

MODULE="${1:-}"
if [ -z "$MODULE" ]; then
  echo "Usage: npm run ui <module-name>" >&2
  exit 1
fi

FILE="src/$MODULE/$MODULE.circuit.tsx"
if [ ! -f "$FILE" ]; then
  echo "!! No entry file for module '$MODULE' (expected $FILE)" >&2
  echo "Available modules:" >&2
  find src -mindepth 1 -maxdepth 1 -type d -printf '  - %f\n' | sort >&2
  exit 1
fi

exec tsci dev "$FILE"
