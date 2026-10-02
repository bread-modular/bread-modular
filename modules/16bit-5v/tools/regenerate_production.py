#!/usr/bin/python3
"""Prepare preserved-source 16bit-5v review outputs, never authorize ordering.

Uses the unchanged repository standalone exporter copied locally from main
(d86bbd5) for proven body-offset support; no shared tool or other module changes.
Gate on actual saved-board DRC/parity/ERC, including exclusions. Supplier fields
may be blank with explicit warnings. Original source is TWO layers, not four;
User approved the retained underside/THT placement; all SMDs remain front.
Physical header lead/pot-case clearance and sourcing/assembler review still gate ordering.
"""
from pathlib import Path
import argparse
import collections
import datetime
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
import pcbnew as p

MOD=Path(__file__).resolve().parents[1]
PCB=MOD/'16bit-5v.kicad_pcb';SCH=MOD/'16bit-5v.kicad_sch'
PROD=MOD/'production';VERIFY=MOD/'verification';JLC=PROD/'assembly'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--review-preparation',action='store_true',required=True)
args=parser.parse_args()
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def run(*args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True)
    if r.returncode:raise SystemExit(f'Command failed: {args}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout

def rows(f):return list(csv.DictReader(f.open(encoding='utf-8-sig')))
def refs(bom):return {r.strip() for row in bom for r in row['Designator'].split(',')}
PROD.mkdir(exist_ok=True);VERIFY.mkdir(exist_ok=True)
review=json.loads((VERIFY/'review-response.json').read_text())
assert str(MOD.parents[1])==review['workspace']
assert run('git','rev-parse','HEAD').strip()==review['authority_ref']
assert run('git','branch','--show-current').strip()==review['branch']
initial={f.name:sha(f) for f in [PCB,SCH]}
assert initial==review['final_source_sha256'],'Final source differs from the reviewed saved/filled layout'
run('kicad-cli','sch','export','netlist','--format','kicadxml','-o',VERIFY/'netlist-final.xml',SCH)
run('kicad-cli','pcb','drc','--format','json','--all-track-errors','--schematic-parity','--severity-all','-o',VERIFY/'drc-final.json',PCB)
run('kicad-cli','sch','erc','--format','json','--severity-all','-o',VERIFY/'erc-final.json',SCH)
drc=json.loads((VERIFY/'drc-final.json').read_text());erc=json.loads((VERIFY/'erc-final.json').read_text())
erv=[v for sheet in erc['sheets'] for v in sheet['violations']]
assert not drc['unconnected_items'] and not drc['schematic_parity']
assert not any(v['severity']=='error' for v in drc['violations']+erv),'Electrical gate failed (no exclusions accepted)'
assert not any(v.get('excluded') for v in drc['violations']+erv),'Excluded findings must not be concealed'
print(run(sys.executable,'-B',MOD/'tools/verify_power.py').strip())
run(sys.executable,'-B',MOD/'tools/jlcpcb_export.py',MOD,'--output',JLC,'--overwrite')
# Full physical BOM/CPL uses the same proven exporter and exact board, without
# assembly-side filtering. Temporary extra fab files are compared, not published.
with tempfile.TemporaryDirectory(prefix='16bit-complete-bom-') as temp:
    full=Path(temp)
    run(sys.executable,'-B',MOD/'tools/jlcpcb_export.py',MOD,'--output',full,'--include-through-hole')
    with zipfile.ZipFile(JLC/'16bit-5v-gerbers.zip') as a,zipfile.ZipFile(full/'16bit-5v-gerbers.zip') as z:
        assert sorted(a.namelist())==sorted(z.namelist())
        def geometry_bytes(data):
            # KiCad timestamps plots at each invocation; strip only these three
            # known metadata comments, never aperture/coordinate/drill content.
            return b'\n'.join(line for line in data.splitlines() if b'TF.CreationDate,' not in line
                and not line.startswith(b'G04 Created by KiCad ') and not line.startswith(b'; DRILL file KiCad '))
        assert all(geometry_bytes(a.read(n))==geometry_bytes(z.read(n)) for n in a.namelist()),'Fabrication geometry differs between selection modes'
    for src,dest in [('bom.csv','bom.csv'),('positions.csv','positions.csv'),('export-report.json','all-components-export-report.json')]:
        shutil.copyfile(full/src,PROD/dest)
shutil.copyfile(JLC/'16bit-5v-gerbers.zip',PROD/'16bit-5v.zip')
run('kicad-cli','pcb','export','ipcd356','-o',PROD/'netlist.ipc',PCB)
b=p.LoadBoard(str(PCB));fps={f.GetReference():f for f in b.GetFootprints()};allrefs=set(fps)
smdbom=rows(JLC/'bom.csv');smdpos=rows(JLC/'positions.csv');fullbom=rows(PROD/'bom.csv');fullpos=rows(PROD/'positions.csv')
smdrefs={f.GetReference() for f in fps.values() if f.GetAttributes()&p.FP_SMD}
assert refs(smdbom)=={r['Designator'] for r in smdpos}==smdrefs and len(smdpos)==len(smdrefs)==56
assert refs(fullbom)=={r['Designator'] for r in fullpos}==allrefs and len(fullpos)==len(allrefs)==62
assert all(r['Layer']=='top' for r in smdpos),'Bottom SMDs may not be hidden by a side filter'
origin=b.GetDesignSettings().GetAuxOrigin()
for row in fullpos:
    f=fps[row['Designator']];fields={v.GetName():v.GetText() for v in f.GetFields()}
    dx=float(fields.get('JLCPCB Position Offset X') or '0');dy=float(fields.get('JLCPCB Position Offset Y') or '0')
    assert abs(float(row['Mid X'])-(p.ToMM(f.GetPosition().x-origin.x)+dx))<.00001
    assert abs(float(row['Mid Y'])-(p.ToMM(origin.y-f.GetPosition().y)+dy))<.00001
    assert abs(float(row['Rotation'])-f.GetOrientationDegrees()%360)<.00001
    assert row['Layer']==('bottom' if f.GetLayer()==p.B_Cu else 'top')
manual=sorted(allrefs-smdrefs)
with (PROD/'manual-assembly.csv').open('w',newline='') as stream:
    w=csv.writer(stream);w.writerow(['Designator','Quantity','Value','Footprint','BodySide','AssemblyInstruction'])
    for ref in manual:
        f=fps[ref];side='bottom' if f.GetLayer()==p.B_Cu else 'top'
        note=('Downward male BASE-mating header; preserve 1..5 pad registration. Do not flip for a one-side claim.' if ref in ['GND1','V_SUPPLY1'] else
              'Downward-facing 1x05 female signal socket; schematic/PCB/BOM all use the actual five-pin intent. Preserve pins 1..5 and mating orientation.' if ref in ['J1','J2'] else
              'Front RV09 potentiometer; retain shaft/control access. Solder tails pass through normally.')
        w.writerow([ref,1,f.GetValue(),f.GetFPID().GetUniStringLibId(),side,note])
(PROD/'designators.csv').write_text(''.join(ref+':1\n' for ref in sorted(allrefs)),encoding='utf-8-sig')
with zipfile.ZipFile(PROD/'16bit-5v.zip') as z:
    assert z.testzip() is None
    layers=sorted(z.namelist());assert all(Path(n).name==n for n in layers)
    assert len([n for n in layers if n.endswith('.gbr')])==9
    assert len([n for n in layers if n.endswith('.drl')])==2
    for token in ['F_Cu','B_Cu','F_Mask','B_Mask','F_Paste','B_Paste','F_Silkscreen','B_Silkscreen','Edge_Cuts','PTH','NPTH']:
        assert any(token in n for n in layers),token
    assert not any('In1' in n or 'In2' in n for n in layers),'Invented internal layer in preserved-source archive'
assert initial=={f.name:sha(f) for f in [PCB,SCH]},'Exporter changed source'
assert sha(JLC/'16bit-5v-gerbers.zip')==sha(PROD/'16bit-5v.zip'),'Stale legacy archive'
report=json.loads((JLC/'export-report.json').read_text());fullreport=json.loads((PROD/'all-components-export-report.json').read_text())
manifest={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'review_response':'verification/review-response.json','release_status':'INTEGRATION-READY — user-approved THT/underside placement; existing 2Cu preserved; ORDERING HOLD, no order authorized',
 'authority_ref':'39f70c646d854e1e43779866c62bead5ab3f003d','workspace_branch':run('git','branch','--show-current').strip(),
 'copper_layers':['F.Cu','B.Cu'],'electrical_gates':{'drc_errors':0,'unconnected':0,'parity':0,'erc_errors':0,
 'drc_warnings':len(drc['violations']),'erc_warnings':len(erv),'drc_exclusions':0,'erc_exclusions':0,
 'drc_warning_types':dict(collections.Counter(v['type'] for v in drc['violations'])),'erc_warning_types':dict(collections.Counter(v['type'] for v in erv)),
 'ignored_drc_checks':[v['key'] for v in drc['ignored_checks']],'ignored_erc_checks':[v['key'] for v in erc['ignored_checks']]},
 'component_body_sides':dict(collections.Counter(b.GetLayerName(f.GetLayer()) for f in fps.values())),
 'smd_assembly_refs':len(smdrefs),'complete_bom_refs':len(allrefs),'manual_tht_refs':manual,
 'smd_missing_supplier_numbers':report['missing_part_numbers'],'all_missing_supplier_numbers':fullreport['missing_part_numbers'],
 'fabrication_archive_entries':layers,'source_sha256':{},'files':{},
 'holds':['Physical header lead/protrusion and pot-case clearance, mating fit and purchased-part compatibility still require human verification; placement approval is not physical-fit approval.', 'Sourcing/catalog/package match and assembler centroid/rotation/polarity, process and assembly-order review still required; no sourcing or assembler-process/order approval is claimed.', 'Final human production review and bench power/USB/audio testing remain outstanding, including retained-inductor winding/orientation and ripple/efficiency; no order authorized.'],
 'exporter_provenance':{'repository_path':'opt/kicad-jlcpcb/export.py','commit':'d86bbd573614210bc119f42224b85dd71f9d608c','local_copy':'tools/jlcpcb_export.py','sha256':sha(MOD/'tools/jlcpcb_export.py')}}
source=[PCB,SCH,MOD/'16bit-5v.kicad_pro',MOD/'Bread16bit.kicad_sym',MOD/'sym-lib-table',MOD/'fp-lib-table',MOD/'MCU_RaspberryPi_RP2350.kicad_sym']
manifest['source_sha256']={str(f.relative_to(MOD)):sha(f) for f in source}
files=[f for root in [PROD,JLC,VERIFY,MOD/'previews',MOD/'tools'] for f in root.rglob('*') if f.is_file() and f.name!='manifest.json' and '__pycache__' not in str(f)]
manifest['files']={str(f.relative_to(MOD)):sha(f) for f in sorted(set(files))}
(PROD/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'PREPARED INTEGRATION-READY / ORDERING HOLD: 0 DRC errors/opens/parity; 0 ERC errors; {len(smdrefs)} top SMD + {len(manual)} documented THT; {len(layers)} ZIP entries; missing catalog numbers {len(report["missing_part_numbers"])} SMD / {len(fullreport["missing_part_numbers"])} total.')
