#!/usr/bin/env bash
# Existing runtime read-only; no installation, other designs or GUI/offscreen loops.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
: "${FREECAD_APPDIR:?Set FREECAD_APPDIR to an existing extracted FreeCAD directory containing AppRun}"
[[ -x "$FREECAD_APPDIR/AppRun" && -x "$FREECAD_APPDIR/usr/bin/python" ]] || { printf 'Invalid existing FREECAD_APPDIR; nothing installed.\n' >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$FREECAD_APPDIR/usr/lib"
mkdir -p "$ROOT/.cache"
export TMPDIR="$ROOT/.cache"
case "${1:-build}" in
  build)
    "$FREECAD_APPDIR/AppRun" python "$ROOT/build.py"
    "$FREECAD_APPDIR/AppRun" python "$ROOT/reopen.py"
    "$FREECAD_APPDIR/AppRun" python "$ROOT/validate.py"
    "$FREECAD_APPDIR/AppRun" python "$ROOT/preview.py"
    /usr/bin/python3 "$ROOT/compose_preview.py"
    "$FREECAD_APPDIR/AppRun" python "$ROOT/finalize.py"
    ;;
  validate)
    "$FREECAD_APPDIR/AppRun" python "$ROOT/reopen.py"
    "$FREECAD_APPDIR/AppRun" python "$ROOT/validate.py"
    "$FREECAD_APPDIR/AppRun" python "$ROOT/finalize.py"
    ;;
  preview)
    "$FREECAD_APPDIR/AppRun" python "$ROOT/preview.py"
    /usr/bin/python3 "$ROOT/compose_preview.py"
    exit 0
    ;;
  open)
    exec "$FREECAD_APPDIR/AppRun" --user-cfg "$ROOT/.cache/freecad-user.cfg" --system-cfg "$ROOT/.cache/freecad-system.cfg" "$ROOT/Open.FCMacro"
    ;;
  *) printf 'Usage: run.sh [build|validate|preview|open]\n' >&2; exit 2 ;;
esac
/usr/bin/python3 - "$ROOT/reports/validation.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1]))
if not report['overall_passed']:
    print('Native/authorized geometry and lid export validated; base internal engraving mesh check remains FAILED. See VALIDATION.md.')
    sys.exit(3)
PY
