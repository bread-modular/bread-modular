#!/usr/bin/env bash
# No install, no stale export success, no full case, no remote printing.
set -euo pipefail
ROOT="$(dirname "$(readlink -f "$0")")"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$ROOT/.cache"
export TMPDIR="$ROOT/.cache"
if [[ -n "${FREECAD_APPDIR:-}" ]]; then
  [[ -x "$FREECAD_APPDIR/AppRun" ]] || { echo 'FREECAD_APPDIR needs existing extracted AppImage with AppRun.' >&2; exit 2; }
  export PYTHONPATH="$FREECAD_APPDIR/usr/lib:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
  FC=("$FREECAD_APPDIR/AppRun" python)
elif [[ -x "$ROOT/.runtime/squashfs-root/AppRun" ]]; then
  export FREECAD_APPDIR="$ROOT/.runtime/squashfs-root"
  export PYTHONPATH="$FREECAD_APPDIR/usr/lib:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
  FC=("$FREECAD_APPDIR/AppRun" python)
else
  # A system Python environment exposing FreeCAD (and numpy/shapely for validation).
  export PYTHONPATH="$ROOT:/usr/lib/freecad/lib:/usr/lib/freecad-python3/lib${PYTHONPATH:+:$PYTHONPATH}"
  FC=("${FREECAD_PYTHON:-python3}")
fi
"${FC[@]}" -c 'import FreeCAD, Part, Mesh, MeshPart, numpy, shapely, matplotlib' || { echo 'Use FREECAD_APPDIR or FREECAD_PYTHON pointing to an existing FreeCAD Python runtime; no downloads.' >&2; exit 2; }
case "${1:-build}" in
  build) "${FC[@]}" "$ROOT/build.py"; "${FC[@]}" "$ROOT/validate.py"; "${FC[@]}" "$ROOT/diagram.py"; python3 - "$ROOT" <<'PYHASH'
from pathlib import Path
import sys,json,hashlib
r=Path(sys.argv[1])
assert json.loads((r/'reports/validation.json').read_text())['status']=='PASS_GEOMETRIC_ONLY_UNSLICED_UNPRINTED'
assets=[r/n for n in ('.gitignore','README.md','RESEARCH.md','PRINT_TEST_GUIDE.md','parameters.json',
 'studies.py','build.py','validate.py','diagram.py','run.sh','Open.FCMacro','comparison.svg',
 'cad/lock-studies.FCStd','reports/validation.json')]+list((r/'stl').glob('*.stl'))
assert len(assets)==22 and len(list((r/'stl').glob('*.stl')))==8
(r/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(r))+'\n' for f in sorted(assets)))
# Check each just-written hash, without changing shell cwd.
for line in (r/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1); assert hashlib.sha256((r/name).read_bytes()).hexdigest()==digest
print('22 asset hashes verified; 8 STL pieces; UNSLICED / UNPRINTED.')
PYHASH
    ;;
  validate) "${FC[@]}" "$ROOT/validate.py" ;;
  open) "${FC[@]}" "$ROOT/Open.FCMacro" ;;
  *) echo 'Usage: run.sh [build|validate|open]' >&2; exit 2 ;;
esac
