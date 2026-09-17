#!/usr/bin/python3
"""Regenerate base production files from the saved, filled, DRC-checked PCB.

Keeps the legacy fab ZIP paths synchronized with the standalone JLCPCB exporter.
Applies the hand-maintained hand-solder override (production/hand-solder.json) to
the *generated* BOM only - the schematic and the PCB are never rewritten - and
records the resulting release state in production/manifest.json.

Read production/RELEASE_STATUS.md and verification/README.md before ordering.
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
HANDSOLDER=PROD/'hand-solder.json'
def run(*args):subprocess.run(list(map(str,args)),check=True)
def natural(s):return [int(k) if k.isdigit() else k for k in re.split(r'(\d+)',s)]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fail(message):raise SystemExit(f'Refusing production export: {message}')

# ---------------------------------------------------------------- guards -----
# The routed board is the deliverable and is pinned byte-identical. The pin lives
# in verification/fixed-geometry.json so a future release moves it deliberately.
baseline=json.loads((VERIFY/'fixed-geometry.json').read_text())
pinned=baseline.get('routed_pcb_sha256')
if pinned is None:fail('verification/fixed-geometry.json has no routed_pcb_sha256 pin.')
if sha(PCB)!=pinned:fail(f'base.kicad_pcb changed ({sha(PCB)} != pinned {pinned}). Copper must not move.')
spec=json.loads(HANDSOLDER.read_text())
hand_groups={g['id']:g for g in spec['groups']}
hand_ref_list=[ref for g in spec['groups'] for ref in g['refs']]
hand_refs=set(hand_ref_list)
override_ref_list=[ref for g in spec['groups'] if g.get('override_bom') for ref in g['refs']]
override_refs=set(override_ref_list)
if len(hand_ref_list)!=len(hand_refs):fail('duplicate reference in hand-solder.json')
if len(override_ref_list)!=len(override_refs):fail('duplicate reference in a hand-solder override row')
for g in spec['groups']:
    if len(g['refs'])!=g['qty']:fail(f'group {g["id"]}: qty {g["qty"]} != {len(g["refs"])} refs')

run(sys.executable,BASE/'tools/verify_stack_height.py','--report',VERIFY/'stack-height.json')
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

# ------------------------------------------------- hand-solder override ------
# KiCad exported the legacy sourcing field of every socket symbol. Those symbols
# cannot be re-substituted: base.kicad_pcb carries the same LCSC/MPN fields and
# tools/verify_power.py asserts schematic/PCB field parity, and the routed board
# is pinned byte-identical. The override therefore rewrites only the generated
# BOM rows, exactly like the jacks and pots that already read NOT-JLC.
rows=list(csv.DictReader((PROD/'bom.csv').open(encoding='utf-8-sig')))
field=spec['bom_override']['field']
if field not in rows[0]:fail(f'hand-solder override field {field!r} missing from the KiCad BOM')
touched=set()
for row in rows:
    refs=[r.strip() for r in row['Designator'].split(',')]
    if set(refs)<=override_refs:
        row[field]=spec['bom_override']['value']
        touched|=set(refs)
    elif set(refs)&override_refs:
        fail(f'BOM row mixes hand-solder and assembly refs: {row["Designator"]}')
if touched!=override_refs:fail(f'hand-solder override missed refs: {sorted(override_refs-touched)}')
with (PROD/'bom.csv').open('w',newline='',encoding='utf-8-sig') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
bom_text=(PROD/'bom.csv').read_text(encoding='utf-8-sig')
for legacy in ['C2894928','C2894966']:
    if legacy in bom_text:fail(f'legacy male part {legacy} still present on the hand-assembly BOM')

b=p.LoadBoard(str(PCB));refs={f.GetReference() for f in b.GetFootprints()}
fps={f.GetReference():f for f in b.GetFootprints()}
# Fabrication Toolkit's historical file is a one-column mapping, not an
# assembly BOM; preserve its ref:1 shape and include all physical components.
(PROD/'designators.csv').write_text(''.join(f'{r}:1\n' for r in sorted(refs,key=natural)),encoding='utf-8-sig')
with tempfile.TemporaryDirectory(prefix='base-production-') as tmp:
    positions=Path(tmp)/'positions.csv'
    run('kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both',
        '--use-drill-file-origin','--exclude-dnp','-o',positions,PCB)
    rows=list(csv.DictReader(positions.open()))
    if {r['Ref'] for r in rows} != refs:fail('Production CPL / footprint reference mismatch')
    with (PROD/'positions.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['Designator','Mid X','Mid Y','Rotation','Layer'])
        for r in sorted(rows,key=lambda r:natural(r['Ref'])):
            w.writerow([r['Ref'],r['PosX'],r['PosY'],f"{float(r['Rot'])%360:.6f}",{'top':'top','bottom':'bottom','front':'top','back':'bottom'}[r['Side']]])
# BOM must describe the same physical ref set; simulation-only parts excluded.
bomrefs={ref.strip() for r in csv.DictReader((PROD/'bom.csv').open(encoding='utf-8-sig')) for ref in r['Designator'].split(',')}
if bomrefs != refs:raise SystemExit(f'Production BOM differs: {bomrefs^refs}')

# ------------------------------------------- JLCPCB assembly lines -----------
export=json.loads((BASE/'jlcpcb/base/export-report.json').read_text())
jlc_bom=list(csv.DictReader((BASE/'jlcpcb/base/bom.csv').open(encoding='utf-8-sig')))
jlc_pos=list(csv.DictReader((BASE/'jlcpcb/base/positions.csv').open(encoding='utf-8-sig')))
jlc_refs={r.strip() for row in jlc_bom for r in row['Designator'].split(',')}
if jlc_refs & hand_refs:fail(f'hand-solder refs leaked onto the JLCPCB BOM: {sorted(jlc_refs & hand_refs)}')
if {row['Designator'] for row in jlc_pos} & hand_refs:fail('hand-solder refs leaked onto the JLCPCB CPL')
if set(export['excluded']) != hand_refs:
    fail(f'JLCPCB exclusion list differs from the hand-solder list: {sorted(set(export["excluded"]) ^ hand_refs)}')
if len(jlc_refs) != export['component_count'] or len(jlc_pos) != export['component_count']:
    fail('JLCPCB BOM/CPL component count differs from the export report')
if not all('not an smd' in reason.lower() for reason in export['excluded'].values()):
    fail('a hand-solder ref is excluded from JLCPCB for a reason other than through-hole mounting')

# ------------------------------------------- derived hand-solder list --------
with (PROD/'hand-solder.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f,lineterminator='\n')
    w.writerow(['Designator','Qty','Group','GroupQty','Footprint','Value','Assembly','Supply','JLCPCB','Part to fit','Recommended'])
    for g in spec['groups']:
        for ref in sorted(g['refs'],key=natural):
            fp=fps[ref]
            w.writerow([ref,1,g['id'],len(g['refs']),str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName()),
                        fp.GetValue(),g['assembly'],g['supply'],'excluded (through hole)',
                        g.get('required',g.get('part','')),g.get('recommended','')])
written=list(csv.DictReader((PROD/'hand-solder.csv').open(encoding='utf-8-sig')))
if len(written)!=len(hand_refs):fail(f'hand-solder.csv has {len(written)} rows, expected {len(hand_refs)}')
if sorted(r['Designator'] for r in written)!=sorted(hand_refs):fail('hand-solder.csv references are not unique/complete')
if sum(int(r['Qty']) for r in written)!=len(hand_refs):fail('hand-solder.csv Qty does not sum to the hand-solder reference count')
if {r['Group'] for r in written}!={g['id'] for g in spec['groups']}:fail('hand-solder.csv groups differ from hand-solder.json')
for g in spec['groups']:
    rows_g=[r for r in written if r['Group']==g['id']]
    if len(rows_g)!=g['qty'] or any(int(r['GroupQty'])!=g['qty'] for r in rows_g):
        fail(f'hand-solder.csv group {g["id"]} does not match qty {g["qty"]}')
    if sorted(r['Designator'] for r in rows_g)!=sorted(g['refs']):
        fail(f'hand-solder.csv group {g["id"]} references differ from hand-solder.json')

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
stack=json.loads((VERIFY/'stack-height.json').read_text())
manifest={'release_version':(BASE/'VERSION').read_text().strip(),
          'release_status':'fab-ready' if stack['clearance_ok'] else 'DO-NOT-ORDER',
          'pcb_sha256':sha(PCB),'routed_pcb_sha256_pinned':pinned,
          'schematic_sha256':sha(SCH),'slot_schematic_sha256':sha(BASE/'slot.kicad_sch'),
          'project_sha256':sha(BASE/'base.kicad_pro'),'custom_rules_sha256':sha(BASE/'base.kicad_dru'),
          'production_refs':len(refs),'jlcpcb_assembled_refs':len(jlc_refs),
          'jlcpcb_bom_rows':len(jlc_bom),'hand_solder_refs':len(hand_refs),
          'hand_solder_override_sha256':sha(HANDSOLDER),
          'hand_solder_override_field':field,'hand_solder_override_value':spec['bom_override']['value'],
          'hand_solder':{'list':'production/hand-solder.csv',
                         'slot_socket_refs':hand_groups['slot-rail-socket']['refs']+hand_groups['slot-ground-socket']['refs'],
                         'aux_input_socket_refs':hand_groups['aux-input-socket']['refs'],
                         'power_expansion_socket_refs':hand_groups['power-expansion-socket']['refs'],
                         'groups':[{'id':g['id'],'qty':g['qty'],'refs':g['refs']} for g in spec['groups']]},
          'schema_note':'Schematic and PCB are unchanged; the hand-solder LCSC value exists only in the generated production/bom.csv.',
          'stack_height':stack,
          'physical_validation_pending':['Mated stack height has not been measured on real hardware: a mating trial of one base plus one module is still advised.',
                                         'Module-side male header part number is not annotated on the module PCBs (assumed mechanical twin of PZ254-1-05-Z-8.5).',
                                         'Slot 1 socket row is offset -0.12 mm in X / -0.10 mm in Y from the common module registration (pre-existing, preserved).',
                                         'Module 4mix and imix place their power headers on F.Cu (top side) and cannot mate downwards as drawn.'],
          'files':{}}
files=[PROD/n for n in ['netlist.ipc','designators.csv','positions.csv','bom.csv','hand-solder.csv',
                        'hand-solder.json','base.zip']]
files += [f for f in (BASE/'jlcpcb/base').iterdir()]+[BASE/'jlcpcb/production_files/GERBER-base.zip']+list(legacy.iterdir())
if (PROD/'cost-estimate.json').is_file():files.append(PROD/'cost-estimate.json')
manifest['files']={str(f.relative_to(BASE)):sha(f) for f in sorted(files,key=lambda f:natural(str(f))) if f.is_file()}
(PROD/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Regenerated IPC-D-356, {len(refs)} designators, full BOM/CPL and synchronized all three fabrication archives.')
print(f'JLCPCB assembles {len(jlc_refs)} refs in {len(jlc_bom)} BOM rows; builder hand-solders {len(hand_refs)} refs.')
print(f'Release status: {manifest["release_status"]}; stack clearance {stack["clearance_nominal_mm"]} mm nominal.')
