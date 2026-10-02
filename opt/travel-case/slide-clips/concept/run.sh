#!/usr/bin/env bash
# Local approval concept ONLY. Stop before presentation/hashes on any failure.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
if [[ -z "${FREECAD_APPDIR:-}" ]]; then
    if [[ -x /tmp/astra-freecad-262/squashfs-root/AppRun ]]; then
        FREECAD_APPDIR=/tmp/astra-freecad-262/squashfs-root
    else
        FREECAD_APPDIR="$ROOT/.runtime/squashfs-root"
    fi
fi
[[ -x "$FREECAD_APPDIR/AppRun" ]] || { printf 'Provide FREECAD_APPDIR; no automatic install.\n' >&2; exit 2; }
export FREECAD_APPDIR
export PYTHONPATH="$FREECAD_APPDIR/usr/lib:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$ROOT/.cache"
export TMPDIR="$ROOT/.cache"
if [[ ! -s "$ROOT/.cache/release-bottom.brep" || ! -s "$ROOT/.cache/release-top.brep" || ! -s "$ROOT/reports/pristine-measurements.json" ]]; then
    "$FREECAD_APPDIR/AppRun" python "$ROOT/inspect_geometry.py"
fi
"$FREECAD_APPDIR/AppRun" python "$ROOT/build_concept.py"
/usr/bin/blender -b --factory-startup --python "$ROOT/render_concept.py"
python3 "$ROOT/compose_preview.py"
python3 "$ROOT/hash_assets.py"
