"""Narrow, install-by-copy imports of the existing transaction/native helpers."""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
_ROOT = Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


native = _load('_pcb_automation_native', _ROOT / 'native.py')
# project.py uses an unqualified native import; do not import the facade or bundle.
_previous = sys.modules.get('native')
sys.modules['native'] = native
try:
    project = _load('_pcb_automation_project', _ROOT / 'project.py')
finally:
    if _previous is None:
        sys.modules.pop('native', None)
    else:
        sys.modules['native'] = _previous
Error = native.Error
