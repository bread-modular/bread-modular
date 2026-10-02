#!/usr/bin/env python3
"""Prepare pristine BReps with source/SHA checks; compact output, no facet arrays.
Verified existing cache is reusable. A missing cache rebuilds directly from the
historical STLs; no dependency on another workspace's rejected edited CAD.
"""
from pathlib import Path
import hashlib,json,time
import FreeCAD as App
import Mesh,Part
R=Path(__file__).resolve().parent
TRANSFORM=App.Matrix(1,0,0,-20.68,0,0,-1,-7.98,0,1,0,15,0,0,0,1)
def prepare():
 start=time.monotonic();provenance=json.loads((R/'cache-provenance.json').read_text())
 (R/'.cache').mkdir(exist_ok=True)
 for name in ('bottom','top'):
  e=provenance[name];source=R.parent/e['source'];cache=R/'.cache'/('raw-'+name+'.brep')
  assert hashlib.sha256(source.read_bytes()).hexdigest()==e['sha256'],'Original source SHA mismatch'
  if cache.exists() and hashlib.sha256(cache.read_bytes()).hexdigest()==e['cache_brep_sha256']:
   s=Part.Shape();s.read(str(cache));mode='SHA-matched pristine cache'
  else:
   mesh=Mesh.Mesh(str(source));mesh.transform(TRANSFORM)
   s=Part.Shape();s.makeShapeFromMesh(mesh.Topology,.00001);s=Part.makeSolid(s).removeSplitter()
   assert s.isValid() and s.isClosed() and len(s.Solids)==1
   assert abs(s.Volume-e['volume_mm3'])<1e-5
   s.exportBrep(str(cache));e['cache_brep_sha256']=hashlib.sha256(cache.read_bytes()).hexdigest()
   e['fresh_mesh_conversion']=True;mode='fresh source STL conversion'
  assert s.isValid() and s.isClosed() and len(s.Solids)==1 and abs(s.Volume-e['volume_mm3'])<1e-5
  print(name,mode,'volume',round(s.Volume,4),'mm3')
 assert hashlib.sha256((R.parent/'original/case_1.0.0/breadmodular-case-1.0.0.f3z').read_bytes()).hexdigest()==provenance['fusion_archive_sha256']
 (R/'cache-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print('Pristine preparation',round(time.monotonic()-start,2),'seconds; archive unchanged')
 return provenance
if __name__=='__main__':prepare()
