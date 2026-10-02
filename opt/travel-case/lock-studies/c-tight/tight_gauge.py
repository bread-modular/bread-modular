"""One additional C female; reuse the baseline gauge helper without relaxing S.check."""
from pathlib import Path
import hashlib
import math
import sys

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
sys.path.insert(0, str(PARENT))
import studies as S
import FreeCAD as App

NAME = 'C_female_G0.40_G0.20_G0.00'
CAD = ROOT / 'cad/C-tight.FCStd'
STL = ROOT / 'stl' / (NAME + '.stl')
REPORT = ROOT / 'reports/validation.json'
DEFAULTS = dict(GaugeRailWidth=8.0, GaugeEngagement=20.0,
                GaugeGaps=[0.40, 0.20, 0.00], BedRelief=0.4,
                MeshLinearDeflection=0.025, MeshAngularDeflection=0.12)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_guard():
    """Pin all original artifacts; permit only the two documented manifest edits."""
    old = (ROOT / 'baseline.SHA256SUMS').read_text().splitlines()
    current = (PARENT / 'SHA256SUMS').read_text().splitlines()
    assert len(old) == len(current) == 22, 'Baseline manifest membership changed'
    hashes = {}
    for before, after in zip(old, current):
        h, name = before.split('  ', 1)
        now, current_name = after.split('  ', 1)
        assert name == current_name, 'Baseline manifest order/names changed'
        assert digest(PARENT / name) == now, 'Parent checksum mismatch: ' + name
        if name not in ('README.md', 'PRINT_TEST_GUIDE.md'):
            assert before == after and now == h, 'Baseline asset changed: ' + name
            hashes[name] = h
    return hashes


def shape(p):
    # gauge() itself supports custom gaps. shape()/check() remain baseline-only.
    assert p['GaugeRailWidth'] == 8 and p['GaugeEngagement'] == 20 and p['BedRelief'] == .4
    assert len(p['GaugeGaps']) == 3 and all(math.isfinite(g) and 0 <= g <= .4 for g in p['GaugeGaps'])
    return S.gauge(p, False)


class TightFemale:
    def __init__(self, obj, parameters):
        obj.addProperty('App::PropertyLink', 'Parameters', 'Recipe').Parameters = parameters
        obj.Proxy = self

    def execute(self, obj):
        obj.Shape = shape(S.values(obj.Parameters))

    def dumps(self):
        return None

    def loads(self, state):
        pass


def reopened():
    d = App.openDocument(str(CAD))
    assert isinstance(d.Female.Proxy, TightFemale), 'Live proxy failed to restore'
    d.Female.touch()
    d.recompute()
    return d


def verify_hashes():
    for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
        h, name = line.split('  ', 1)
        assert digest(ROOT / name) == h, 'Extension checksum mismatch: ' + name


def write_hashes():
    assets = sorted(p for p in ROOT.rglob('*') if p.is_file() and
                    not any(part.startswith('.') or part == '__pycache__'
                            for part in p.relative_to(ROOT).parts) and
                    p.name != 'SHA256SUMS' and p.suffix not in ('.FCStd1', '.FCBak'))
    (ROOT / 'SHA256SUMS').write_text(''.join(digest(p) + '  ' + str(p.relative_to(ROOT)) + '\n' for p in assets))
    verify_hashes()
