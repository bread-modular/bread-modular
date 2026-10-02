#!/usr/bin/env python3
"""Fresh-process native-document test. Deliberately imports NO project module.
No sys.path registration, feature proxy, deleted design, cache or source mesh needed.
"""
from pathlib import Path
import json
import time
import FreeCAD as App

root = Path(__file__).resolve().parent
start = time.monotonic()
doc = App.openDocument(str(root / 'cad' / 'original-magnet-case.FCStd'))
assert doc is not None
assert not any('Python' in o.TypeId or getattr(o, 'Proxy', None) is not None for o in doc.Objects)
for obj in doc.Objects:
    obj.touch()
doc.recompute()


def check():
    for obj in doc.Objects:
        assert not any(s in ('Invalid', 'Error') for s in obj.State), (obj.Name, obj.State)
    for name in ('Base', 'Lid', 'ReleaseBase', 'ReleaseLid', 'BasePocketRebuildBlank', 'LidPocketRebuildBlank', 'BaseSurfaceFilledShell', 'LidSurfaceFilledShell'):
        shape = doc.getObject(name).Shape
        assert shape.isValid() and shape.isClosed() and len(shape.Solids) == 1, name


check()
assert doc.BaseUndersideFill.TypeId == doc.LidLogoFill.TypeId == 'Part::Extrusion'
assert doc.Base.TypeId == doc.Lid.TypeId == 'Part::Cut'
assert doc.BaseSurfaceFilledShell.TypeId == doc.LidSurfaceFilledShell.TypeId == 'Part::Feature'
base_volume = doc.Base.Shape.Volume
lid_volume = doc.Lid.Shape.Volume
base_depth = float(doc.Parameters.BasePocketDepth)
lid_depth = float(doc.Parameters.LidPocketDepth)
# Exercise native feature edits in memory, then restore; never ship the edit.
doc.Parameters.BasePocketDepth = base_depth + 0.2
doc.Parameters.LidPocketDepth = lid_depth - 0.2
doc.recompute()
check()
assert doc.Base.Shape.Volume < base_volume - 1
assert doc.Lid.Shape.Volume > lid_volume + 1
edit = {'base_depth_plus_0_2_volume_delta_mm3': doc.Base.Shape.Volume - base_volume,
        'lid_depth_minus_0_2_volume_delta_mm3': doc.Lid.Shape.Volume - lid_volume}
doc.Parameters.BasePocketDepth = base_depth
doc.Parameters.LidPocketDepth = lid_depth
doc.recompute()
check()
assert abs(doc.Base.Shape.Volume - base_volume) < 0.00001
assert abs(doc.Lid.Shape.Volume - lid_volume) < 0.00001
report = {
    'passed': True, 'fresh_process': True, 'no_project_module_imports': True,
    'no_python_feature_proxies': True, 'forced_recompute': True,
    'saved_assembly_solids': ['Base', 'Lid'],
    'saved_surface_fill_evidence': {'BaseUndersideFill': doc.BaseUndersideFill.TypeId, 'LidLogoFill': doc.LidLogoFill.TypeId},
    'surface_fills_rebuild_via_script_not_live_parameters': True,
    'saved_surface_fill_depths_mm': {'base': float(doc.Parameters.BaseUndersideFillDepth), 'lid': float(doc.Parameters.LidLogoFillDepth)},
    'saved_print_orientation_links': ['BasePrint', 'LidPrint'],
    'saved_exploded_links': ['BaseExploded', 'LidExploded'],
    'objects': {o.Name: o.TypeId for o in doc.Objects},
    'native_depth_edit_test': edit, 'default_restored_without_saving_edits': True,
    'seconds': time.monotonic() - start,
}
(root / 'reports' / 'reopen.json').write_text(json.dumps(report, indent=2) + '\n')
App.closeDocument(doc.Name)
print('REOPEN / NATIVE DEPTH EDIT PASS', report['seconds'], flush=True)
