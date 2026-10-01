#!/usr/bin/python3
"""Regenerate/verify BASE release outputs without modifying any circuit sources.

Run only after freeze_release.py has proven final DRC/parity and independently
preserved mechanical invariants. JLCPCB files contain eligible SMD assembly only;
production BOM/CPL/designators inventory ALL physical footprints, including DNP.
Successful software export is NOT an order, bench or placement-preview signoff.
--verify-only rechecks source pins, live DRC/parity, published files and hashes.
"""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import pcbnew as p
from assembly_datum import expected_position

BASE=Path(__file__).resolve().parents[1]; ROOT=BASE.parents[1]
PROD=BASE/'production'; VERIFY=BASE/'verification'; PCB=BASE/'base.kicad_pcb'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--verify-only',action='store_true')
parser.add_argument('--refresh-manifest-only',action='store_true',help='Revalidate current exports and refresh hashes after final docs/evidence; no re-export')
parser.add_argument('--render',action='store_true',help='Refresh aspect-correct PCB and independently parsed Gerber renders (requires optional Gerbonara)')
args=parser.parse_args()
if args.refresh_manifest_only: args.verify_only=True
def run(*cmd): subprocess.run(list(map(str,cmd)),check=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def natural(s): return [int(k) if k.isdigit() else k for k in re.split(r'(\d+)',s)]
def require(ok,msg):
    if not ok: raise SystemExit('Refusing production export: '+msg)
def rows(path): return list(csv.DictReader(Path(path).open(encoding='utf-8-sig')))
def write_csv(path,header,data):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(header);w.writerows(data)
def jlc_flag(value): return value.strip().lower() in {'1','yes','true','dnp','x'}
def csv_refs(data):
    refs=[r.strip() for row in data for r in row['Designator'].split(',')]
    require(len(refs)==len(set(refs)),'Duplicate BOM references')
    require(all(len(row['Designator'].split(','))==int(row['Quantity']) for row in data),'BOM quantity mismatch')
    return set(refs)

frozen=json.loads((VERIFY/'fixed-geometry.json').read_text())
require(sha(PCB)==frozen['routed_pcb_sha256'],'Saved PCB does not match validated frozen source')
source_names=['base.kicad_pcb','base.kicad_sch','slot.kicad_sch','base.kicad_pro','base.kicad_dru']
source_hashes={n:sha(BASE/n) for n in source_names}
b=p.LoadBoard(str(PCB));fps={f.GetReference():f for f in b.GetFootprints()};physical=set(fps)
require(len(physical)==len(list(b.GetFootprints())),'Duplicate physical footprint')
spec=json.loads((PROD/'hand-solder.json').read_text())
hand_list=[r for g in spec['groups'] for r in g['refs']];hand=set(hand_list)
require(len(hand_list)==len(hand),'Duplicate hand-solder references')
for g in spec['groups']: require(len(g['refs'])==g['qty'],f'Bad hand-solder group {g["id"]}')
require(spec['release']==(BASE/'VERSION').read_text().strip(),'Hand-solder release version is stale')
dnp={r for r,f in fps.items() if f.IsDNP()}
eligible={r for r,f in fps.items() if f.GetAttributes() & p.FP_SMD and not f.IsDNP()
          and not f.IsExcludedFromBOM() and not f.IsExcludedFromPosFiles()}
require(dnp=={'J23'},'Unexpected DNP policy; explicitly review before exporting')
require(not(hand & dnp or hand & eligible or dnp & eligible),'Assembly policy overlaps')
require(physical==hand|dnp|eligible,'Unaccounted physical references')
require(all(not(fps[r].GetAttributes() & p.FP_SMD) and any(q.GetDrillSize().x for q in fps[r].Pads()) for r in hand),'Hand-solder list contains non-THT reference')
require(all(re.fullmatch(r'C\d+',fps[r].GetFieldText('LCSC')) for r in eligible),'Missing/invalid eligible LCSC field')
run(sys.executable,BASE/'tools/verify_stack_height.py',*(['--report',VERIFY/'stack-height.json'] if not args.verify_only else []))
run(sys.executable,BASE/'tools/verify_power.py',*(['--report',VERIFY/'connectivity.json'] if not args.verify_only else []))
# Real DRC on EXACT saved release source. No severities/exclusions are changed.
with tempfile.TemporaryDirectory(prefix='base-release-drc-') as temp:
    report=Path(temp)/'drc.json' if args.verify_only else VERIFY/'drc-after.json'
    run('kicad-cli','pcb','drc','--format','json','--schematic-parity','--severity-all','-o',report,PCB)
    drc=json.loads(report.read_text())
    require(not drc['unconnected_items'] and not drc['schematic_parity'] and not any(q['severity']=='error' for q in drc['violations']),'DRC/parity/opens failure')

run(sys.executable,BASE/'tools/verify_bounded_improvements.py')

# Parse every Excellon hit/slot and compare to the PCB, not only ZIP filenames.
def drill_key(diameter,start,end=None):
    start=tuple(round(q,9) for q in start)
    if end is None: return round(diameter,3),start,start
    end=tuple(round(q,9) for q in end)
    return (round(diameter,3),*sorted([start,end]))
def read_drill(text):
    require('METRIC' in text and 'M48' in text and 'M30' in text,'Invalid Excellon/units')
    tools={};tool=None;start=None;data=collections.Counter()
    for line in text.splitlines():
        if m:=re.fullmatch(r'T(\d+)C([\d.]+)',line): tools[int(m[1])]=float(m[2])
        elif m:=re.fullmatch(r'T(\d+)',line): tool=int(m[1])
        elif m:=re.fullmatch(r'(G00|G01)?X([-\d.]+)Y([-\d.]+)',line):
            q=float(m[2]),float(m[3]);require(tool in tools,'Unknown drill tool')
            if m[1]=='G00': start=q
            elif m[1]=='G01':
                require(start is not None,'Route without start');data[drill_key(tools[tool],start,q)]+=1;start=q
            else: data[drill_key(tools[tool],q)]+=1
    return data
origin=b.GetDesignSettings().GetAuxOrigin()
def cart(q): return p.ToMM(q.x-origin.x),p.ToMM(origin.y-q.y)
def expected_drills():
    data={name:collections.Counter() for name in ['PTH','NPTH']}
    for f in fps.values():
        for q in f.Pads():
            dx,dy=p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y)
            if not dx: continue
            name='NPTH' if q.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH'
            x,y=cart(q.GetPosition())
            if abs(dx-dy)<1e-7: key=drill_key(dx,(x,y))
            else:
                angle=math.radians(q.GetOrientationDegrees());half=abs(dx-dy)/2
                vx,vy=(half*math.cos(angle),half*math.sin(angle)) if dx>dy else (half*math.sin(angle),-half*math.cos(angle))
                key=drill_key(min(dx,dy),(x-vx,y-vy),(x+vx,y+vy))
            data[name][key]+=1
    for q in b.GetTracks():
        if q.GetClass()=='PCB_VIA': data['PTH'][drill_key(p.ToMM(q.GetDrillValue()),cart(q.GetPosition()))]+=1
    return data

def drill_match(have,expected):
    # KiCad Excellon decimal output quantizes coordinates to 0.001 mm. Match
    # one-to-one at half of that LSB (plus floating-point epsilon), preserving
    # diameter, plating class, slot endpoints/orientation and feature counts.
    pending=list(expected.elements())
    for diameter,start,end in have.elements():
        found=next((i for i,(d,a,z) in enumerate(pending) if abs(d-diameter)<.000001 and
                    all(abs(x-y)<=.000501 for u,v in [(start,a),(end,z)] for x,y in zip(u,v))),None)
        if found is None: return False
        pending.pop(found)
    return not pending

def validate_published():
    report=json.loads((BASE/'jlcpcb/base/export-report.json').read_text())
    bom=rows(BASE/'jlcpcb/base/bom.csv');cpl=rows(BASE/'jlcpcb/base/positions.csv')
    require(csv_refs(bom)==eligible,'JLCPCB BOM reference set != eligible assembly')
    require({q['Designator'] for q in cpl}==eligible and len(cpl)==len(eligible),'JLCPCB CPL reference set != eligible assembly')
    require(report['component_count']==len(eligible) and report['bom_row_count']==len(bom),'Exporter count mismatch')
    require(set(report['excluded'])==hand|dnp,'Exporter exclusions != hand-solder + DNP')
    require(all('not an smd' in report['excluded'][r].lower() for r in hand),'Hand-solder exclusion reason')
    require(all('populate' in report['excluded'][r].lower() for r in dnp),'DNP exclusion reason')
    require(not report['missing_part_numbers'],'Exporter reports missing part numbers')
    source_report={Path(path).name:digest for path,digest in report['source_sha256'].items()}
    require(source_report=={name:source_hashes[name] for name in ['base.kicad_pcb','base.kicad_sch']},'Stale exporter input hashes')
    for row in bom:
        for ref in [q.strip() for q in row['Designator'].split(',')]:
            f=fps[ref]
            require(row['LCSC Part #']==f.GetFieldText('LCSC') and row['Comment']==f.GetValue() and row['Footprint']==str(f.GetFPID().GetLibItemName()),f'{ref}: BOM part/package mismatch')
            for key in ['MPN','Manufacturer']:
                native=f.GetFieldText(key).strip() if f.HasField(key) else ''
                require(row[key]==('' if native=='~' else native),f'{ref}: BOM {key} mismatch (optional absent native field must remain blank)')
    for row in cpl:
        f=fps[row['Designator']];x,y=expected_position(f,origin);offset=float(f.GetFieldText('JLCPCB Rotation Offset')) if f.HasField('JLCPCB Rotation Offset') else 0
        require(abs(float(row['Mid X'])-x)<.000002 and abs(float(row['Mid Y'])-y)<.000002,f'{f.GetReference()}: CPL coordinates/origin')
        require(abs(float(row['Rotation'])-(f.GetOrientationDegrees()+offset)%360)<.000002 and row['Layer']==('top' if f.GetLayer()==p.F_Cu else 'bottom'),f'{f.GetReference()}: CPL rotation/side')
    full_bom=rows(PROD/'bom.csv')
    require(csv_refs(full_bom)==physical,'Full physical BOM lost DNP/THT footprint')
    overrides={r for g in spec['groups'] if g.get('override_bom') for r in g['refs']}
    for row in full_bom:
        for ref in [q.strip() for q in row['Designator'].split(',')]:
            f=fps[ref];part=spec['bom_override']['value'] if ref in overrides else (f.GetFieldText('LCSC') if f.HasField('LCSC') else '')
            require(row['Value']==f.GetValue() and row['Footprint']==str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()) and row['LCSC Part #']==part,f'{ref}: full physical BOM metadata mismatch')
            require(jlc_flag(row['DNP'])==f.IsDNP(),f'{ref}: full BOM DNP flag')
    designators=(PROD/'designators.csv').read_text(encoding='utf-8-sig').splitlines()
    require(designators==[f'{r}:1' for r in sorted(physical,key=natural)],'Incomplete/incorrect physical designator quantities')
    inventory=rows(PROD/'assembly-policy.csv')
    require(len(inventory)==len(physical) and {r['Designator'] for r in inventory}==physical,'Incomplete physical policy inventory')
    for row in inventory:
        ref=row['Designator'];expected='JLCPCB-SMD' if ref in eligible else 'DNP' if ref in dnp else 'hand-solder'
        require(row['Policy']==expected and jlc_flag(row['DNP'])==fps[ref].IsDNP(),f'{ref}: physical policy mismatch')
    full_cpl=rows(PROD/'positions.csv')
    require({r['Designator'] for r in full_cpl}==physical and len(full_cpl)==len(physical),'Full physical CPL lost/duplicated DNP/THT footprint')
    for row in full_cpl:
        f=fps[row['Designator']];x,y=expected_position(f,origin)
        require(abs(float(row['Mid X'])-x)<.000002 and abs(float(row['Mid Y'])-y)<.000002 and abs(float(row['Rotation'])-f.GetOrientationDegrees()%360)<.000002 and row['Layer']==('top' if f.GetLayer()==p.F_Cu else 'bottom'),f'{f.GetReference()}: physical placement data mismatch')
    hands=rows(PROD/'hand-solder.csv')
    require(len(hands)==len(hand) and {r['Designator'] for r in hands}==hand and sum(int(r['Qty']) for r in hands)==len(hand),'Hand-solder inventory mismatch')
    for g in spec['groups']:
        group=[r for r in hands if r['Group']==g['id']]
        require(len(group)==g['qty'] and {r['Designator'] for r in group}==set(g['refs']) and all(int(r['GroupQty'])==g['qty'] and int(r['Qty'])==1 for r in group),f'Invalid hand-solder CSV group {g["id"]}')
    archives=[BASE/'jlcpcb/base/base-gerbers.zip',PROD/'base.zip',BASE/'jlcpcb/production_files/GERBER-base.zip']
    require(len({sha(q) for q in archives})==1,'Published fabrication ZIPs differ')
    names={f'base-{n}.gbr' for n in ['F_Cu','B_Cu','F_Mask','B_Mask','F_Paste','B_Paste','F_Silkscreen','B_Silkscreen','Edge_Cuts']}|{'base-PTH.drl','base-NPTH.drl'}
    with zipfile.ZipFile(archives[0]) as z:
        require(z.testzip() is None and set(z.namelist())==names and len(z.namelist())==len(names),'Corrupt/unexpected ZIP content')
        expected=expected_drills();counts={}
        for name in names:
            data=z.read(name);require(data==(BASE/'jlcpcb/gerber'/name).read_bytes(),'Loose fabrication copy differs from ZIP')
            if name.endswith('.gbr'): require(b'%MOMM*%' in data and data.rstrip().endswith(b'M02*'),'Invalid Gerber format/units/end')
        for kind in ['PTH','NPTH']:
            have=read_drill(z.read('base-'+kind+'.drl').decode())
            require(drill_match(have,expected[kind]),f'{kind} drill geometry/diameters/slot endpoints mismatch (Excellon coordinate tolerance 0.000501 mm)')
            counts[kind]=sum(have.values())
    orientation=json.loads((VERIFY/'assembly-orientation.json').read_text()) if args.verify_only else None
    if orientation:
        require(orientation['pcb_sha256']==sha(PCB),'Stale polarity/rotation evidence')
        for ref,item in orientation['components'].items():
            require(item['pad_nets']=={q.GetNumber():q.GetNetname() for q in fps[ref].Pads()},f'{ref}: polarity/pad data changed')
    render_path=VERIFY/'render-review.json'
    if render_path.exists():
        rr=json.loads(render_path.read_text());require(rr['pcb_sha256']==sha(PCB),'Stale PCB render source')
        if rr.get('gerber_review'):
            require(rr['gerber_review']['zip_sha256']==sha(archives[0]),'Gerber review is stale for published ZIP; rerun with --render')
        for name,item in rr['images'].items(): require(sha(VERIFY/name)==item['sha256'],f'Stale render image: {name}')
    return {'physical_references':len(physical),'jlcpcb_assembled_refs':len(eligible),'jlcpcb_bom_rows':len(bom),'hand_solder_refs':len(hand),'dnp_refs':sorted(dnp),'zip_entries':len(names),'drill_features':counts,'cpl_origin_mm':[p.ToMM(origin.x),p.ToMM(origin.y)],'assembly_rotation_check':'Documented HRO J5 body centre independently checked; other KiCad anchors/angles/pad polarity checked; JLCPCB library placement-preview NOT performed'}

if not args.verify_only:
    # Repository standalone exporter uses private CLI copies and native fields.
    run(sys.executable,ROOT/'opt/kicad-jlcpcb/export.py',BASE,'--overwrite','--require-part-numbers')
    loader=importlib.util.spec_from_file_location('jlc_release',ROOT/'opt/kicad-jlcpcb/export.py')
    jlc=importlib.util.module_from_spec(loader);loader.loader.exec_module(jlc)
    with tempfile.TemporaryDirectory(prefix='base-production-') as temp:
        temp=Path(temp);cli_board,cli_sch=jlc.stage_cli_project(PCB,BASE/'base.kicad_sch',temp)
        run('kicad-cli','pcb','export','ipcd356','-o',PROD/'netlist.ipc',cli_board)
        run('kicad-cli','sch','export','bom','--fields','Reference,Footprint,${QUANTITY},Value,LCSC,${DNP}','--labels','Designator,Footprint,Quantity,Value,LCSC Part #,DNP','--group-by','Footprint,Value,LCSC,DNP','--ref-range-delimiter','','-o',PROD/'bom.csv',cli_sch)
        # KiCad's full BOM also contains simulation/load symbols excluded from
        # the board. Filter ONLY after proving each exclusion in a fresh native
        # netlist; never drop unknown extras simply because they lack a PCB ref.
        meta=temp/'symbols.xml';run('kicad-cli','sch','export','netlist','--format','kicadxml','-o',meta,cli_sch)
        symbols=jlc.read_xml_symbols(meta)
        full=[]
        for row in rows(PROD/'bom.csv'):
            rr=[r.strip() for r in row['Designator'].split(',')]
            for ref in set(rr)-physical:
                require(ref in symbols and (symbols[ref]['__EXCLUDE_FROM_BOARD']=='1' or not symbols[ref]['Footprint']),f'Unexpected nonphysical BOM reference: {ref}')
            kept=[ref for ref in rr if ref in physical]
            if kept:
                row['Designator']=','.join(kept);row['Quantity']=str(len(kept));full.append(row)
        require(csv_refs(full)==physical,'Native full physical BOM ref mismatch')
        overrides={r for g in spec['groups'] if g.get('override_bom') for r in g['refs']};touched=set()
        for row in full:
            refs={r.strip() for r in row['Designator'].split(',')}
            if refs<=overrides: row[spec['bom_override']['field']]=spec['bom_override']['value'];touched|=refs
            else: require(not(refs&overrides),'Mixed hand-solder/assembly BOM row')
        require(touched==overrides,'Incomplete hand-solder sourcing override')
        write_csv(PROD/'bom.csv',full[0].keys(),[r.values() for r in full])
        require(not any(code in (PROD/'bom.csv').read_text(encoding='utf-8-sig') for code in ['C2894928','C2894966']),'Legacy male socket PN leaked into full BOM')
        raw=temp/'positions.csv';run('kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both','--use-drill-file-origin','-o',raw,cli_board)
        positions=rows(raw);require({r['Ref'] for r in positions}==physical and len(positions)==len(physical),'Native physical position ref mismatch')
        write_csv(PROD/'positions.csv',['Designator','Mid X','Mid Y','Rotation','Layer'],[[r['Ref'],*[f'{v:.6f}' for v in expected_position(fps[r['Ref']],origin)],f"{float(r['Rot'])%360:.6f}",r['Side']] for r in sorted(positions,key=lambda r:natural(r['Ref']))])
    (PROD/'designators.csv').write_text(''.join(f'{r}:1\n' for r in sorted(physical,key=natural)),encoding='utf-8-sig')
    write_csv(PROD/'assembly-policy.csv',['Designator','Footprint','DNP','Policy','Native LCSC','Ordering note'],[[r,str(fps[r].GetFPID().GetLibNickname())+':'+str(fps[r].GetFPID().GetLibItemName()),str(fps[r].IsDNP()).lower(),'JLCPCB-SMD' if r in eligible else 'DNP' if r in dnp else 'hand-solder',fps[r].GetFieldText('LCSC') if fps[r].HasField('LCSC') else '', 'Not ordered/fitted' if r in dnp else 'Builder supplied; socket sourcing override applies' if r in hand else 'Placement preview pending'] for r in sorted(physical,key=natural)])
    hand_data=[]
    for g in spec['groups']:
        for r in sorted(g['refs'],key=natural):
            f=fps[r];hand_data.append([r,1,g['id'],g['qty'],str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),f.GetValue(),g['assembly'],g['supply'],'excluded (through hole)',g.get('required',g.get('part','')),g.get('recommended','')])
    write_csv(PROD/'hand-solder.csv',['Designator','Qty','Group','GroupQty','Footprint','Value','Assembly','Supply','JLCPCB','Part to fit','Recommended'],hand_data)
    archive=BASE/'jlcpcb/base/base-gerbers.zip'
    for dest in [PROD/'base.zip',BASE/'jlcpcb/production_files/GERBER-base.zip']: shutil.copyfile(archive,dest)
    loose=BASE/'jlcpcb/gerber';loose.mkdir(exist_ok=True)
    for q in loose.iterdir():
        if q.suffix.lower() in ['.gbr','.drl','.pdf','.gbrjob']: q.unlink()
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist(): require(Path(name).name==name,'Non-flat ZIP');(loose/name).write_bytes(z.read(name))

if not args.verify_only:
    placements={q['Designator']:q for q in rows(BASE/'jlcpcb/base/positions.csv')}
    orientation={'pcb_sha256':sha(PCB),'coordinate_frame':'Drill/place origin (30.48,177.8); Cartesian Y; no bottom-X negation',
        'JLCPCB_placement_preview_performed':False,'components':{}}
    for ref in sorted(eligible,key=natural):
        f=fps[ref]
        orientation['components'][ref]={'footprint':str(f.GetFPID().GetLibItemName()),'LCSC':f.GetFieldText('LCSC'),
            'native_anchor_board_mm':[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)],
            'assembly_CPL_centre_mm':list(expected_position(f,origin)),
            'XY_datum':'HRO nominal shell centre' if ref=='J5' else 'native KiCad anchor',
            'pcb_rotation_deg':f.GetOrientationDegrees()%360,'CPL_rotation_deg':float(placements[ref]['Rotation']),
            'pad_nets':{q.GetNumber():q.GetNetname() for q in f.Pads()},
            'pin1_position_mm':[cart(q.GetPosition()) for q in f.Pads() if q.GetNumber()=='1']}
    (VERIFY/'assembly-orientation.json').write_text(json.dumps(orientation,indent=2)+'\n')
    if args.render: run(sys.executable,BASE/'tools/plot_power.py','--gerber')
result=validate_published()
require(source_hashes=={n:sha(BASE/n) for n in source_names},'A circuit source changed during export/validation')
if args.verify_only and not args.refresh_manifest_only:
    manifest=json.loads((PROD/'manifest.json').read_text())
    require(manifest['source_sha256']==source_hashes,'Manifest source hashes are stale')
    for name,digest in manifest['files'].items(): require(sha(BASE/name)==digest,f'Stale published file: {name}')
    for name,digest in manifest['repository_tools_sha256'].items(): require(sha(ROOT/name)==digest,f'Stale repository exporter/tool: {name}')
else:
    (VERIFY/'manufacturing-validation.json').write_text(json.dumps(dict(result,source_sha256=source_hashes,result='PASS'),indent=2)+'\n')
    manifest={'schema':'bread-modular/base/release-manifest/2','release_version':(BASE/'VERSION').read_text().strip(),'release_status':'software-checked candidate; NOT order authorization','source_sha256':source_hashes,'pcb_sha256':source_hashes['base.kicad_pcb'],'schematic_sha256':source_hashes['base.kicad_sch'],'slot_schematic_sha256':source_hashes['slot.kicad_sch'],**result,'drc':{'errors':0,'unconnected_items':0,'schematic_parity':0,'warnings':dict(collections.Counter(q['type'] for q in drc['violations']))},'erc':dict(collections.Counter(q['severity'] for sheet in json.loads((VERIFY/'erc-after.json').read_text())['sheets'] for q in sheet['violations'])),'review_status':{'prior_1.3.12':'Astra copper/connectivity/fabrication PASS; assembly HOLD J5 mouth-based datum','current_1.3.13':'targeted independent confirmation pending; no advisor invoked'},'signoffs':{'independent_review':False,'bench_reset_startup_audio':False,'physical_mating_trial':False,'JLCPCB_placement_preview':False,'order_authorized':False},'cost_stock_status':'Historical cost-estimate.json explicitly STALE; no live stock or price check','files':{}}
    files=[PROD/n for n in ['netlist.ipc','designators.csv','positions.csv','bom.csv','assembly-policy.csv','hand-solder.csv','hand-solder.json','base.zip','cost-estimate.json','RELEASE_STATUS.md','EXPORT_BLOCKER.md']]
    files+=list((BASE/'jlcpcb/base').iterdir())+[BASE/'jlcpcb/production_files/GERBER-base.zip']+list((BASE/'jlcpcb/gerber').iterdir())
    files+=[BASE/n for n in ['VERSION','CHANGELOG','POWER.md','POWER-HISTORICAL-pre-1.3.12.md']]+list((BASE/'tools').glob('*.py'))
    manifest['repository_tools_sha256']={name:sha(ROOT/name) for name in ['opt/kicad-jlcpcb/export.py','opt/kicad-jlcpcb/README.md','opt/kicad-jlcpcb/tests/test_export.py']}
    files+=list(VERIFY.glob('*.json'))+list(VERIFY.glob('*.png'))+list(VERIFY.glob('*.svg'))+list(VERIFY.glob('*.pdf'))+list(VERIFY.glob('*.xml'))+list(VERIFY.glob('*.md'))+[VERIFY/'README.md',VERIFY/'warnings.md',VERIFY/'changed-files.txt',VERIFY/'netlist-after.kicadsexpr']
    manifest['files']={str(q.relative_to(BASE)):sha(q) for q in sorted(files,key=lambda q:natural(str(q))) if q.is_file()}
    (PROD/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('PASS: '+json.dumps(result,sort_keys=True))
