#!/usr/bin/env bash
# Portable, existing runtimes ONLY. No downloads/installations/advisors/GUI loops.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$ROOT/.cache" "$ROOT/reports" "$ROOT/cad" "$ROOT/stl" "$ROOT/previews"
export TMPDIR="$ROOT/.cache"
if [[ -z "${FREECAD_APPDIR:-}" && -z "${FREECAD_PYTHON:-}" ]]; then
  for candidate in "$ROOT/../slide-clips/.runtime/squashfs-root" "$ROOT/../lock-studies/.runtime/squashfs-root"; do
    if [[ -x "$candidate/AppRun" ]]; then export FREECAD_APPDIR="$candidate"; break; fi
  done
  if [[ -z "${FREECAD_APPDIR:-}" ]]; then
    candidate=$(find "$HOME/.okbrain/workspaces/bread-modular-kicad" -maxdepth 8 -path '*/slide-clips/.runtime/squashfs-root/AppRun' -print -quit 2>/dev/null || true)
    if [[ -n "$candidate" ]]; then export FREECAD_APPDIR="$(dirname "$candidate")"; fi
  fi
fi
if [[ -n "${FREECAD_APPDIR:-}" ]]; then
  [[ -x "$FREECAD_APPDIR/AppRun" ]] || { echo 'FREECAD_APPDIR must point to an existing extracted FreeCAD.' >&2; exit 2; }
  export PYTHONPATH="$ROOT:$ROOT/../slide-clips:$FREECAD_APPDIR/usr/lib${PYTHONPATH:+:$PYTHONPATH}"
  FC=("$FREECAD_APPDIR/AppRun" python)
else
  export PYTHONPATH="$ROOT:$ROOT/../slide-clips:/usr/lib/freecad/lib:/usr/lib/freecad-python3/lib${PYTHONPATH:+:$PYTHONPATH}"
  FC=("${FREECAD_PYTHON:-python3}")
fi
"${FC[@]}" -c 'import FreeCAD, Part, Mesh, MeshPart, numpy, shapely, PIL' || { echo 'Supply an existing FreeCAD Python/runtime with numpy/shapely/Pillow; no installations attempted.' >&2; exit 2; }
KP=("${KICAD_PYTHON:-/usr/bin/python3}")
case "${1:-build}" in
  probe) "${FC[@]}" "$ROOT/probe.py" ;;
  screen)
    "${FC[@]}" "$ROOT/probe.py"
    "${KP[@]}" "$ROOT/electronics_survey.py" 2>"$ROOT/.cache/kicad-survey.log"
    "${FC[@]}" "$ROOT/screen.py" ;;
  build)
    # Never leave stale test STLs behind if a changed recipe fails the gate.
    rm -f "$ROOT"/stl/*.stl "$ROOT/reports/exports.json"
    trap 'rm -f "$ROOT"/stl/*.stl; echo "Build failed: no printable exports retained." >&2' ERR
    "${FC[@]}" "$ROOT/probe.py"
    "${KP[@]}" "$ROOT/electronics_survey.py" 2>"$ROOT/.cache/kicad-survey.log"
    "${FC[@]}" "$ROOT/screen.py"
    "${FC[@]}" "$ROOT/build.py"
    "${FC[@]}" "$ROOT/validate.py"
    "${FC[@]}" "$ROOT/export.py"
    "${FC[@]}" "$ROOT/validate.py" --stl-only
    "${FC[@]}" "$ROOT/preview.py"
    python3 "$ROOT/hash_assets.py"
    python3 "$ROOT/hash_assets.py" --verify
    trap - ERR
    ;;
  validate)
    # Verify delivered bytes BEFORE replacing the timestamped validation report.
    python3 "$ROOT/hash_assets.py" --verify
    "${FC[@]}" "$ROOT/validate.py"
    "${FC[@]}" "$ROOT/validate.py" --stl-only
    python3 "$ROOT/hash_assets.py"
    python3 "$ROOT/hash_assets.py" --verify ;;
  preview) "${FC[@]}" "$ROOT/preview.py" ;;
  hashes) python3 "$ROOT/hash_assets.py" --verify ;;
  *) echo 'Usage: run.sh [build|screen|probe|validate|preview|hashes]' >&2; exit 2 ;;
esac
