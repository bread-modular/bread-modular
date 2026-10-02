#!/usr/bin/env python3
"""Hash only this delivery, excluding ignored cache/backups and this manifest."""
from pathlib import Path
import hashlib,sys
R=Path(__file__).resolve().parent;manifest=R/'SHA256SUMS'
def eligible(p):
 rel=p.relative_to(R)
 return p.is_file() and p!=manifest and not any(x in ('.cache','__pycache__') for x in rel.parts) and not p.name.endswith(('.FCStd1','.FCBak'))
if '--verify' in sys.argv:
 rows=[line.split('  ',1) for line in manifest.read_text().splitlines() if line]
 for digest,name in rows:
  p=R/name
  assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest,'SHA mismatch: '+name
 assert {name for _,name in rows}=={str(p.relative_to(R)) for p in R.rglob('*') if eligible(p)},'Manifest inventory mismatch'
 print('SHA256 verified',len(rows),'delivery files; ignored cache/backups excluded')
else:
 rows=[]
 for p in sorted(R.rglob('*')):
  if eligible(p):rows.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(R)))
 manifest.write_text('\n'.join(rows)+'\n');print('SHA256 recorded',len(rows),'delivery files')
