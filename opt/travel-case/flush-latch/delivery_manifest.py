"""Hash current mandatory delivery after successful build && validation.
Read-only Git diagnostics. No commits/branch mutations. Hash list excludes itself.
"""
import hashlib
import json
from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent
BASE=R.parent.parent.parent
v=json.loads((R/'reports/validation.json').read_text())
m=json.loads((R/'reports/mesh-export.json').read_text())
assert not v['failures'] and v['status'].startswith('PASS')
assert m['status'].startswith('All written STL checks PASS')
assert (R/'reports/validation.json').stat().st_mtime >= (R/'cad/flush-latch.FCStd').stat().st_mtime
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert v['cad_sha256']==sha(R/'cad/flush-latch.FCStd'),'Validation must match current CAD bytes'
for name,d in v['written_STLs'].items():assert d['sha256']==sha(R/'stl'/name),'Stale mesh '+name
for name in ('latch_features.py','parameters.json','build.py','validate.py'):
    assert v['recipe_sha256'][name]==sha(R/name),'Stale recipe '+name

original=R.parent/'original/case_1.0.0'
handoff=Path('/home/azero/.okbrain/workspaces/bread-modular-kicad/264/opt/travel-case/original/case_1.0.0')
files={p.relative_to(original).as_posix():sha(p) for p in original.rglob('*') if p.is_file()}
if handoff.exists():
    hf={p.relative_to(handoff).as_posix():sha(p) for p in handoff.rglob('*') if p.is_file()}
    assert files==hf,'Upstream handoff bytes changed'

# Check upstream declared release hashes independently of the handoff comparison.
for line in (original/'SHA256SUMS').read_text().splitlines():
    if not line.strip():continue
    digest,name=line.split(None,1);name=name.lstrip('* ').strip()
    path=original/name
    assert path.is_file() and sha(path)==digest,'Upstream SHA mismatch '+name

branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
assert branch=='okbrain/bread-modular-kicad/266-835e3574','Unexpected worker branch'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
base=subprocess.check_output(['git','rev-parse','case-improvements'],cwd=BASE,text=True).strip()
assert head==base,'Commit/base changed'
allowed=('opt/travel-case/flush-latch/','opt/travel-case/original/case_1.0.0/')
staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=BASE,text=True).splitlines()
assert all(n.startswith(allowed) for n in staged),'Unrelated staged assets'

report={'status':'PASS - computational geometry delivery; physical coupon REQUIRED',
    'base':'case-improvements','branch':branch,'head':head,'committed':False,
    'only_intended_stage_paths':True,'staging':'Staging verified separately in final Git status; this script does not stage or commit',
    'mandatory_check_count':v['checks_total'],'failures':v['failures'],
    'envelope':v['envelope'],'cad_sha256':sha(R/'cad/flush-latch.FCStd'),
    'mesh_count':len(v['written_STLs']),'original_handoff_copy_exact':True,'upstream_sha256_verified':True,
    'original_files_sha256':files,'physical_fit_strength_fatigue_tested':False,
    'build_validation_sequence':'run.sh: set -euo pipefail; build.py && validate.py; presentation separate',
    'optional_STEP_or_presentation_clipping_in_build':False,
    'snap_clearance_is_elastic_surrogate_not_FEA':True,
    'nominal_seam_lift_before_load_mm':.6,
    'previews':['previews/assembly.png','previews/exploded.png','previews/local-latch.png']}
(R/'reports/delivery.json').write_text(json.dumps(report,indent=2)+'\n')
# Normal source/delivery assets only; no caches, bytecode or CAD backups.
paths=[]
for p in R.rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(R)
    if '.cache' in rel.parts or '__pycache__' in rel.parts:continue
    if p.name=='SHA256SUMS' or p.suffix in ('.FCBak','.FCStd1') or '.FCStd.' in p.name:continue
    paths.append(p)
text=''.join(sha(p)+'  '+p.relative_to(R).as_posix()+'\n' for p in sorted(paths))
(R/'SHA256SUMS').write_text(text)
print(json.dumps({k:report[k] for k in ('status','mandatory_check_count','mesh_count','original_handoff_copy_exact','upstream_sha256_verified','branch','committed')},indent=2))
