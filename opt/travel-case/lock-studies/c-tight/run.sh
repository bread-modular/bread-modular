#!/usr/bin/env bash
# ONE extra female, isolated cleanup; existing runtime only, no printer commands.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$ROOT/.cache"
export TMPDIR="$ROOT/.cache"
if [[ -z "${FREECAD_APPDIR:-}" ]]; then
  for candidate in "$ROOT/.runtime/squashfs-root" "$ROOT/../.runtime/squashfs-root" "$ROOT/../../slide-clips/.runtime/squashfs-root"; do
    if [[ -x "$candidate/AppRun" ]]; then export FREECAD_APPDIR="$candidate"; break; fi
  done
fi
if [[ -n "${FREECAD_APPDIR:-}" ]]; then
  [[ -x "$FREECAD_APPDIR/AppRun" ]] || { echo 'FREECAD_APPDIR must name an existing AppRun runtime.' >&2; exit 2; }
  export PYTHONPATH="$FREECAD_APPDIR/usr/lib:$ROOT:$ROOT/..${PYTHONPATH:+:$PYTHONPATH}"
  FC=("$FREECAD_APPDIR/AppRun" python)
else
  export PYTHONPATH="$ROOT:$ROOT/..:/usr/lib/freecad/lib:/usr/lib/freecad-python3/lib${PYTHONPATH:+:$PYTHONPATH}"
  FC=("${FREECAD_PYTHON:-python3}")
fi
"${FC[@]}" -c 'import FreeCAD, Part, Mesh, MeshPart, numpy, shapely' || { echo 'Use an existing FREECAD_APPDIR or FREECAD_PYTHON; no downloads.' >&2; exit 2; }
case "${1:-build}" in
  build) "${FC[@]}" "$ROOT/build.py"; "${FC[@]}" "$ROOT/validate.py" ;;
  validate)
    "${FC[@]}" -c 'import tight_gauge as T; T.verify_hashes(); T.baseline_guard()'
    rm -f "$ROOT/SHA256SUMS"
    "${FC[@]}" "$ROOT/validate.py" ;;
  open) "${FC[@]}" -c 'import tight_gauge as T; T.verify_hashes(); T.baseline_guard()'; "${FC[@]}" "$ROOT/Open.FCMacro"; exit 0 ;;
  *) echo 'Usage: run.sh [build|validate|open]' >&2; exit 2 ;;
esac
"${FC[@]}" -c 'import json; import tight_gauge as T; assert json.loads(T.REPORT.read_text())["status"] == "PASS_GEOMETRIC_ONLY_UNSLICED_UNPRINTED"; T.baseline_guard(); T.write_hashes(); print("Parent + extension hashes verified; ONE new female, original male unchanged.")'
