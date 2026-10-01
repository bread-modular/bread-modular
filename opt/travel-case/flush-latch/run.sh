#!/usr/bin/env bash
# Always stop on build failure. No semicolon-fallthrough or optional clipping.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
export FREECAD_APPDIR="${FREECAD_APPDIR:-/tmp/astra-freecad-262/squashfs-root}"
export PYTHONPATH="$FREECAD_APPDIR/usr/lib:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
"$FREECAD_APPDIR/AppRun" python "$ROOT/build.py" && \
    "$FREECAD_APPDIR/AppRun" python "$ROOT/validate.py" || {
    status=$?
    printf 'Build/validation failed (exit %s); stopping before presentation and hashes.\n' "$status" >&2
    exit "$status"
}
/usr/bin/blender -b --factory-startup --python "$ROOT/render.py"
python3 "$ROOT/compose_previews.py"
python3 "$ROOT/delivery_manifest.py"
