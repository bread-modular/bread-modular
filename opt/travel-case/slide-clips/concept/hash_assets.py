#!/usr/bin/env python3
"""Hash phase-one review assets only; exclude runtime, caches and backup saves."""
from pathlib import Path
import hashlib
R=Path(__file__).resolve().parent
paths=[]
for path in sorted(R.rglob('*')):
 if not path.is_file():continue
 rel=path.relative_to(R)
 if any(p in ('.cache','.runtime','__pycache__') for p in rel.parts):continue
 if path.name=='SHA256SUMS' or path.name.endswith(('.log','.FCStd1','.FCBak')):continue
 paths.append(path)
(R/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(R))+'\n' for p in paths))
print('Hashed',len(paths),'phase-one review assets; no runtime/cache/backups.')
