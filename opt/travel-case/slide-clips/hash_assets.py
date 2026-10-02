#!/usr/bin/env python3
"""Final delivery evidence + SHA256 manifest, verified immediately after writing.
Exclude caches/runtimes/bytecode/backups; provenance source bytes independently checked.
"""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
v=json.loads((R/'reports/validation.json').read_text());b=json.loads((R/'reports/build.json').read_text())
assert v['status'].startswith('PASS') and not v['failures']
assert hashlib.sha256((R/'cad/slide-clips.FCStd').read_bytes()).hexdigest()==v['cad_sha256']==b['cad_sha256']
for n,row in v['written_STLs'].items():assert hashlib.sha256((R/'stl'/n).read_bytes()).hexdigest()==row['sha256']
original=R.parent/'original/case_1.0.0'
for line in (original/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split(maxsplit=1);name=name.lstrip('* ')
    assert hashlib.sha256((original/name).read_bytes()).hexdigest()==digest, 'Original changed '+name
report={'status':'PASS - clean build, reopened/recomputed geometry, written STL and hash evidence; physical tests pending',
        'cad':'cad/slide-clips.FCStd','cad_sha256':v['cad_sha256'],
        'stls':{n:q['sha256'] for n,q in v['written_STLs'].items()},
        'source_provenance':b['source_provenance'],'transform':b['transform'],'toolchain':b['toolchain'],
        'geometry_checks_passed':v['checks_passed'],'geometry_checks_total':v['checks_total'],
        'body_dimensions_mm':v['envelope']['body_dimensions_mm'],
        'fitted_dimensions_mm':v['envelope']['diagonal_pair_dimensions_mm'],
        'first_print_bom':{'coupon_bottom.stl':1,'coupon_lid.stl':1,'clip_nominal.stl':1},
        'full_case_intended_minimum_bom':{'case_bottom.stl':1,'case_lid.stl':1,'identical_chosen_fit_clip':2},
        'previews':['previews/assembly.png','previews/exploded-test.png'],
        'mandatory_small_refinement':v['mandatory_refinement'],
        'native_history_recovered':False,'source_kind':'Frozen original mesh facets + analytical new editable features',
        'physical_fit_tested':False,'friction_force_certified':False,'carrying_strength_certified':False,
        'tabletop_stability_tested':False,'slicer_supports_tested':False,'safety_rated':False,
        'limits':v['limitations'],'original_sha256_manifest_verified':True}
(R/'reports/delivery.json').write_text(json.dumps(report,indent=2)+'\n')
paths=[]
for path in sorted(R.rglob('*')):
    if not path.is_file():continue
    rel=path.relative_to(R)
    if any(p in ('.runtime','.cache','__pycache__') for p in rel.parts):continue
    if path.name=='SHA256SUMS' or path.suffix in ('.FCBak','.FCStd1','.pyc','.log') or path.name.endswith('~'):continue
    paths.append((str(rel),path))
for rel in ('../README.md','../flush-latch/README.md'):paths.append((rel,R/rel))
lines=[hashlib.sha256(path.read_bytes()).hexdigest()+'  '+rel for rel,path in paths]
(R/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
for line in (R/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert hashlib.sha256((R/name).read_bytes()).hexdigest()==digest,name
print('FINAL SHA256 VERIFIED',len(paths),'assets; all original source hashes verified')
