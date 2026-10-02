#!/usr/bin/env python3
"""Build/reopen/export ONLY the extra female. Never rebuild or export a male."""
import FreeCAD as App
import MeshPart
import tight_gauge as T


def build():
    T.baseline_guard()
    for sub, pattern in (('cad', '*.FCStd'), ('stl', '*.stl'), ('reports', '*.json')):
        folder = T.ROOT / sub
        folder.mkdir(exist_ok=True)
        for path in folder.glob(pattern):
            path.unlink()
    (T.ROOT / 'SHA256SUMS').unlink(missing_ok=True)
    d = App.newDocument('CTightGauge')
    pa = d.addObject('App::FeaturePython', 'Parameters')
    pa.Label = 'EDIT GaugeGaps: TOTAL gaps, left to right (per side = G/2)'
    for key, value in T.DEFAULTS.items():
        typ = 'App::PropertyFloatList' if isinstance(value, list) else 'App::PropertyFloat'
        pa.addProperty(typ, key, 'Fits' if key == 'GaugeGaps' else 'Dimensions')
        setattr(pa, key, value)
        if key != 'GaugeGaps':
            pa.setEditorMode(key, 1)
    pa.addProperty('App::PropertyString', 'PrintStatus', 'Evidence').PrintStatus = (
        'EXPERIMENT; new female UNSLICED/UNPRINTED; material unknown; zero gap may bind; NEVER FORCE')
    female = d.addObject('PartDesign::FeaturePython', 'Female')
    T.TightFemale(female, pa)
    female.Label = T.NAME + ' / open channels; reuse existing C_male_8.00'
    d.recompute()
    if female.ViewObject:
        female.ViewObject.ShapeColor = (.28, .65, .51)
    d.saveAs(str(T.CAD))
    App.closeDocument(d.Name)
    d = T.reopened()
    s = d.Female.Shape
    assert s.isValid() and s.isClosed() and len(s.Solids) == 1 and s.Volume > 0
    assert 'Error' not in d.Female.State and abs(s.BoundBox.ZMin) < 1e-8
    MeshPart.meshFromShape(Shape=s, LinearDeflection=T.DEFAULTS['MeshLinearDeflection'],
                           AngularDeflection=T.DEFAULTS['MeshAngularDeflection'], Relative=False).write(str(T.STL))
    App.closeDocument(d.Name)
    T.baseline_guard()
    print('Built/reopened ONE female:', T.STL.name, flush=True)


if __name__ == '__main__':
    build()
