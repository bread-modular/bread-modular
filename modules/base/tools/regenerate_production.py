#!/usr/bin/python3
"""Regenerate base production files from the saved, filled, DRC-checked PCB.

Keeps the legacy fab ZIP paths synchronized with the standalone JLCPCB exporter.
Does NOT approve ordering: read verification/README.md and its mechanical hold.
"""
from pathlib import Path
import collections
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import pcbnew as p

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[1]
PROD=BASE/'production'
VERIFY=BASE/'verification'
PCB=BASE/'base.kicad_pcb'
SCH=BASE/'base.kicad_sch'
def run(*args):subprocess.run(list(map(str,args)),check=True)
def natural(s):return [int(k) if k.isdigit() else k for k in re.split(r'(\d+)',s)]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
run(sys.executable,BASE/'tools/verify_power.py','--report',VERIFY/'connectivity.json')
run('kicad-cli','pcb','drc','--format','json','--schematic-parity','--severity-all','-o',VERIFY/'drc-after.json',PCB)
drc=json.loads((VERIFY/'drc-after.json').read_text())
if drc['unconnected_items'] or drc['schematic_parity'] or any(v['severity']=='error' for v in drc['violations']):
    raise SystemExit('Refusing production export: DRC/parity failure (including excluded errors).')
run(sys.executable,ROOT/'opt/kicad-jlcpcb/export.py',BASE,'--overwrite','--require-part-numbers')
run('kicad-cli','pcb','export','ipcd356','-o',PROD/'netlist.ipc',PCB)
run('kicad-cli','sch','export','bom','--fields','Reference,Footprint,${QUANTITY},Value,LCSC',
    '--labels','Designator,Footprint,Quantity,Value,LCSC Part #','--group-by','Footprint,Value,LCSC',
    '--ref-range-delimiter','','--exclude-dnp','-o',PROD/'bom.csv',SCH)
b=p.LoadBoard(str(PCB));refs={f.GetReference() for f in b.GetFootprints()}
# Fabrication Toolkit's historical file is a one-column mapping, not an
# assembly BOM; preserve its ref:1 shape and include all physical components.
(PROD/'designators.csv').write_text(''.join(f'{ref}:1\n' for ref in sorted(refs,key=natural)),encoding='utf-8-sig')
with tempfile.TemporaryDirectory(prefix='base-production-') as tmp:
    positions=Path(tmp)/'positions.csv'
    run('kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both',
        '--use-drill-file-origin','--exclude-dnp','-o',positions,PCB)
    rows=list(csv.DictReader(positions.open()))
    if {r['Ref'] for r in rows} != refs:raise SystemExit('Production CPL / footprint reference mismatch')
    with (PROD/'positions.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['Designator','Mid X','Mid Y','Rotation','Layer'])
        for r in sorted(rows,key=lambda r:natural(r['Ref'])):
            w.writerow([r['Ref'],r['PosX'],r['PosY'],f"{float(r['Rot'])%360:.6f}",{'top':'top','bottom':'bottom','front':'top','back':'bottom'}[r['Side']]])
# BOM must describe the same physical ref set; simulation-only parts excluded.
bomrefs={ref.strip() for r in csv.DictReader((PROD/'bom.csv').open(encoding='utf-8-sig')) for ref in r['Designator'].split(',')}
if bomrefs != refs:raise SystemExit(f'Production BOM differs: {bomrefs^refs}')
authoritative=BASE/'jlcpcb/base/base-gerbers.zip'
for dest in [PROD/'base.zip',BASE/'jlcpcb/production_files/GERBER-base.zip']:
    shutil.copyfile(authoritative,dest)
legacy=BASE/'jlcpcb/gerber'
# These are generated outputs only; historical production/backups stay intact.
for old in legacy.iterdir():
    if old.suffix.lower() in ['.gbr','.drl','.pdf','.gbrjob']:old.unlink()
with zipfile.ZipFile(authoritative) as z:
    for name in z.namelist():
        if Path(name).name!=name:raise SystemExit('Unexpected non-flat fabrication archive')
        (legacy/name).write_bytes(z.read(name))
files=[PROD/n for n in ['netlist.ipc','designators.csv','positions.csv','bom.csv','base.zip']]
files += list((BASE/'jlcpcb/base').iterdir())+[BASE/'jlcpcb/production_files/GERBER-base.zip']+list(legacy.iterdir())
export=json.loads((BASE/'jlcpcb/base/export-report.json').read_text())
manifest={'pcb_sha256':sha(PCB),'schematic_sha256':sha(SCH),'slot_schematic_sha256':sha(BASE/'slot.kicad_sch'),'project_sha256':sha(BASE/'base.kicad_pro'),'custom_rules_sha256':sha(BASE/'base.kicad_dru'),'production_refs':len(refs),
          'assembly_hold':True,'assembly_hold_reason':'Actual female socket, assembled board gap and shunt height require owner confirmation.',
          'files':{str(f.relative_to(BASE)):sha(f) for f in sorted(files) if f.is_file()}}
(PROD/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Regenerated IPC-D-356, {len(refs)} designators, full BOM/CPL and synchronized all three fabrication archives.')
print('DO NOT ORDER: mechanical hold remains; generation is not release approval.')
