#!/usr/bin/env bash
# FINAL release only: a failed build/validation cannot proceed to previews/hashes.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
FREECAD_APPDIR="${FREECAD_APPDIR:-$ROOT/.runtime/squashfs-root}"
[[ -x "$FREECAD_APPDIR/AppRun" ]] || { printf 'Set FREECAD_APPDIR to an existing extracted FreeCAD AppImage directory. No automatic install.\n' >&2; exit 2; }
export FREECAD_APPDIR PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$FREECAD_APPDIR/usr/lib:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$ROOT/.cache";export TMPDIR="$ROOT/.cache"
case "${1:-}" in
  --clean) rm -f "$ROOT/cad/slide-clips.FCStd" "$ROOT/stl/"*.stl "$ROOT/reports/build.json" "$ROOT/reports/validation.json" "$ROOT/reports/delivery.json" "$ROOT/SHA256SUMS" "$ROOT/.cache/release-"* ;;
  '') ;;
  *) printf 'Usage: run.sh [--clean]\n' >&2;exit 2 ;;
esac
"$FREECAD_APPDIR/AppRun" python "$ROOT/build.py"
"$FREECAD_APPDIR/AppRun" python "$ROOT/validate.py"
# Exercise the portable FINAL opener headlessly; GUI view styling remains optional.
"$FREECAD_APPDIR/AppRun" python "$ROOT/Open.FCMacro"
/usr/bin/blender -b --factory-startup --python "$ROOT/render_final.py"
python3 "$ROOT/compose_previews.py"
python3 "$ROOT/hash_assets.py"
