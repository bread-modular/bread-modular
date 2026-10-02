#!/usr/bin/python3
"""Compact local production export/check. No ordering or independent-review claim.
Uses the actual shared exporter unchanged. Preserves full BOM/CPL and a separate
55-SMD assembly pair; underside connector bodies remain in the full inventory.
"""
from pathlib import Path
import collections,csv,hashlib,json,math,shutil,subprocess,sys,zipfile
import xml.etree.ElementTree as E
import pcbnew as p
sys.excepthook=sys.__excepthook__
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1]
PROD=BASE/'production';VERIFY=BASE/'verification';PCB=BASE/'32bit-5v.kicad_pcb'
def run(*a):subprocess.run(list(map(str,a)),check=True)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return list(csv.DictReader(Path(path).open(encoding='utf-8-sig')))
def refs(data):
    allrefs=[r.strip() for row in data for r in row['Designator'].split(',')]
    assert len(allrefs)==len(set(allrefs)),'duplicate CSV references'
    assert all(int(row['Quantity'])==len(row['Designator'].split(',')) for row in data)
    return set(allrefs)
def outcsv(path,fields,data):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data)
run('kicad-cli','pcb','drc','--format','json','--all-track-errors','--schematic-parity','--severity-all','-o',VERIFY/'final-drc.json',PCB)
run('kicad-cli','sch','erc','--format','json','--severity-all','-o',VERIFY/'final-erc.json',BASE/'32bit-5v.kicad_sch')
run('kicad-cli','sch','export','netlist','--format','kicadxml','-o',VERIFY/'final-netlist.xml',BASE/'32bit-5v.kicad_sch')
u4sch=next(c for c in E.parse(VERIFY/'final-netlist.xml').getroot().find('components') if c.get('ref')=='U4')
assert u4sch.findtext('value')=='ES8388','actual schematic U4 Value must be identifiable'
drc=json.loads((VERIFY/'final-drc.json').read_text());erc=json.loads((VERIFY/'final-erc.json').read_text())
ev=[v for sheet in erc['sheets'] for v in sheet['violations']]
assert not drc['unconnected_items'] and not drc['schematic_parity']
assert not any(v['severity']=='error' for v in drc['violations']+ev),'electrical gate failed'
pro=json.loads((BASE/'32bit-5v.kicad_pro').read_text());assert not pro['board']['design_settings']['drc_exclusions']
b=p.LoadBoard(str(PCB));fps={f.GetReference():f for f in b.GetFootprints()}
assert len(fps)==len(b.GetFootprints())==61
assert b.GetCopperLayerCount()==4
assert fps['U4'].GetValue()==u4sch.findtext('value')=='ES8388'
assert str(fps['U4'].GetFPID().GetLibItemName())=='ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias'
assert not any(f.IsDNP() or f.IsExcludedFromBOM() or f.IsExcludedFromPosFiles() for f in fps.values())
smd={r for r,f in fps.items() if f.GetAttributes()&p.FP_SMD};tht=set(fps)-smd
assert len(smd)==55 and len(tht)==6
assert all(fps[r].GetLayer()==p.F_Cu for r in smd)
assert {r for r,f in fps.items() if f.GetLayer()==p.B_Cu}=={'GND1','V_SUPPLY1','INPUT1','OUTPUT1'}
for sub,extra in [('assembly',[]),('full',['--include-through-hole'])]:
    run(sys.executable,ROOT/'opt/kicad-jlcpcb/export.py',BASE,'--output',PROD/sub,'--overwrite',*extra)
    bom=rows(PROD/sub/'bom.csv');pos=rows(PROD/sub/'positions.csv');selected=smd if sub=='assembly' else set(fps)
    assert refs(bom)=={r['Designator'] for r in pos}==selected
    u4bom=next(q for q in bom if 'U4' in q['Designator'].split(','))
    assert u4bom['Comment']==u4sch.findtext('value')=='ES8388' and u4bom['MPN']=='ES8388'
    assert u4bom['Manufacturer']=='Everest Semiconductor' and 'ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias' in u4bom['Footprint']
    assert len(pos)==len({r['Designator'] for r in pos})
    origin=b.GetDesignSettings().GetAuxOrigin()
    for q in pos:
        f=fps[q['Designator']];point=f.GetPosition()
        assert abs(float(q['Mid X'])-p.ToMM(point.x-origin.x))<.000002
        assert abs(float(q['Mid Y'])+p.ToMM(point.y-origin.y))<.000002
        side='bottom' if f.GetLayer()==p.B_Cu else 'top'
        assert q['Layer']==side
        expected=f.GetOrientationDegrees()%360
        assert abs((float(q['Rotation'])-expected+180)%360-180)<.000002
    report=json.loads((PROD/sub/'export-report.json').read_text())
    assert report['copper_layer_count']==4
    assert report['source_sha256'][str(PCB)]==sha(PCB)
run('kicad-cli','pcb','export','ipcd356','-o',PROD/'netlist.ipc',PCB)
# Keep legacy paths current, not historical stale two/source-state packages.
for name in ['bom.csv','positions.csv']:shutil.copyfile(PROD/'full'/name,PROD/name)
shutil.copyfile(PROD/'assembly/32bit-5v-gerbers.zip',PROD/'32bit-5v.zip')
(PROD/'designators.csv').write_text(''.join(f'{r}:1\n' for r in sorted(fps)),encoding='utf-8-sig')
allpos={q['Designator']:q for q in rows(PROD/'positions.csv')}
manual=[]
for r in sorted(tht):
    f=fps[r];q=allpos[r]
    manual.append(dict(Designator=r,Quantity=1,Value=f.GetValue(),Footprint=str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),Layer=q['Layer'],
        **{'Mid X':q['Mid X'],'Mid Y':q['Mid Y'],'Rotation':q['Rotation']},
        Assembly='THT/manual; underside placement retained as user approved; clearance/process review pending' if r not in {'RV1','RV2'} else 'THT/manual; front-facing shaft preserved'))
outcsv(PROD/'manual-assembly.csv',list(manual[0]),manual)
with zipfile.ZipFile(PROD/'32bit-5v.zip') as z:
    names=z.namelist();assert len(names)==len(set(names)) and all(Path(n).name==n for n in names)
    for layer in ['F_Cu','In1_Cu','In2_Cu','B_Cu','F_Mask','B_Mask','F_Paste','B_Paste','F_Silkscreen','B_Silkscreen','Edge_Cuts']:
        assert any(layer in n for n in names),layer
    assert any('PTH' in n and 'NPTH' not in n and n.endswith('.drl') for n in names)
    assert any('NPTH' in n and n.endswith('.drl') for n in names)
    gerbers=PROD/'gerbers';gerbers.mkdir(exist_ok=True)
    for n in names:(gerbers/n).write_bytes(z.read(n))
# Functional graph invariant excludes only nonexistent aliases of combined USB lands.
def graph(path):
    return {frozenset((i.get('ref'),i.get('pin')) for i in n if i.get('ref')!='J5' or i.get('pin') not in {'B1','B12','B4','B9'}) for n in E.parse(path).getroot().find('nets')}
assert graph(VERIFY/'original-netlist.xml')==graph(VERIFY/'final-netlist.xml')
assembly=json.loads((PROD/'assembly/export-report.json').read_text());full=json.loads((PROD/'full/export-report.json').read_text())
manifest={'source_base_commit':'65e1d7202f22f0ef8b387e9f1e0c1b6740731ead',
 'workspace_branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
 'workspace_path':str(ROOT),'delta_port_inventory':'verification/release-handoff.md',
 'review_response_owner':'Sol Max; current release metadata; no new advisor review or approval',
 'fabrication_data':'ELECTRICAL/EXPORT DATA COMPLETE: exact saved-board four-layer fabrication outputs preserved byte-identically from finished workspace279; no hardware change or rebuild',
 'ordering_status':'NO ORDER AUTHORIZED: user approved keeping THT/underside connector placement as is; all SMD remain front and actual four-copper-layer stack is preserved. Preorder assembler review of GND1 lead trim/pot-case clearance, U4 via-in-pad/stencil/reflow, and source/rotation matching remains required',
 'pcba_status':'ASSEMBLY DATA COMPLETE; NOT ORDER-READY: source/part matching and assembler placement/process review pending',
 'independent_review':{'input':'/tmp/astra-final-delta-20261002/HANDOFF.md','input_sha256':sha('/tmp/astra-final-delta-20261002/HANDOFF.md'),'response':'verification/astra-response.md','status':'Historical Astra review passed pre-EP routing/artwork/identity and requested EP correction; Sol279 applied the project-selected front EP correction. No post-EP Astra approval; this metadata-only closeout adds no advisor approval'},
 'physical_fit':'HOLD: GND1 pins1/2 overlap RV1 courtyard; pins4/5 overlap RV2. Opposite bodies do not prove a collision or clearance. Confirm header lead protrusion/trim and pot-case dimensions physically; U4 assembly process, stencil/reflow and thermal performance not signed off.',
 'u4_identity':'Actual SCH/PCB Value and both BOM Comments=ES8388; MPN ES8388; Everest Semiconductor; Module32 ES8388 nominal 2.60mm front EP corrected; outer28 leads, nine drilled thermal pads, backside 2.40mm pad preserved. Blank LCSC allowed; manual part/rotation matching pending.',
 'u4_identity_evidence':'verification/identity-land-evidence.json',
 'exporter_value_behavior':'Unmodified shared exporter uses native PCB position Val, not a SCH fallback. Wrapper asserts actual fresh SCH Value=PCB Value=both BOM Comments=ES8388.',
 'physical_refs':61,'physical_sides':{'top':57,'bottom':4},'smd_refs':55,'smd_side':'top','manual_refs':sorted(tht),
 'bottom_body_refs':['GND1','INPUT1','OUTPUT1','V_SUPPLY1'],'copper_layers':['F.Cu','In1.Cu','In2.Cu','B.Cu'],
 'drc_errors':0,'opens':0,'parity':0,'drc_warning_types':dict(collections.Counter(v['type'] for v in drc['violations'])),
 'erc_errors':0,'erc_warning_types':dict(collections.Counter(v['type'] for v in ev)),
 'excluded_drc_findings':0,'ignored_checks_audit':'verification/focused-independent-checks.json#expanded_temp_checks',
 'functional_pin_group_graph_unchanged':True,'filled_saved_zones':True,
 'smd_supplier_gaps':assembly['missing_part_numbers'],'full_supplier_gaps':full['missing_part_numbers'],
 'j5_land_correction':'Inherited correction retained: A1/A4/A9/A12 widths 0.600->0.575mm, centers/drills unchanged, actual adjacent clearance 0.200mm; no rule relaxation. Cached exact HRO TYPE-C-31-M-12 drawing p1: recommended-layout 4-0.60mm and explicit PCB-layout +/-0.05mm, giving 0.55..0.65mm; 0.575mm is within this specific dimension tolerance. Not blanket fit/release approval.',
 'j5_dimension_evidence':'verification/identity-land-evidence.json',
 'j5_drawing':'https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948',
 'thermal_and_mounts':'U4 front EP nominal 2.60mm copper/2.65mm mask; four retained rounded paste windows at 60.8254% nominal coverage; backside 2.40mm pad, nine thermal PTH pads and keepouts retained; both original 3.2mm plated-via mount holes retained. Project-selected EP qualification only, not manufacturer recommended land/stencil approval; assembler via-in-pad/stencil/reflow validation remains required.',
 'archive_files':names,'source_sha256':{},'outputs_sha256':{},
 'preview_evidence':'previews/actual-gerber-top.png is rendered from final delivered ZIP; native previews are not fabrication-art proof; historical 3D/4Cu previews inherited from port (not updated EP dimensional evidence); exact-ZIP package/stencil closeups show current EP.'}
for n in ['32bit-5v.kicad_pcb','32bit-5v.kicad_sch','32bit-5v.kicad_pro','32bit-5v.kicad_dru','Module32.kicad_sym','Module32.pretty/HRO-TYPE-C-31-M-12.kicad_mod','Module32.pretty/ES8388_QFN28_4x4_P0.45_EP2.6_ThermalVias.kicad_mod','verification/es8388-ep-delta.json','fp-lib-table','sym-lib-table','tools/regenerate_production.py','verification/release-handoff.md','verification/astra-response.md','verification/identity-land-evidence.json','verification/port-report.json','verification/evidence/ES8388-intended-datasheet.pdf','verification/evidence/HRO-TYPE-C-31-M-12-drawing.pdf']:
    manifest['source_sha256'][n]=sha(BASE/n)
for f in sorted(PROD.rglob('*')):
    if f.is_file() and f.name!='manifest.json':manifest['outputs_sha256'][str(f.relative_to(BASE))]=sha(f)
for n in ['final-drc.json','final-erc.json','final-netlist.xml']:
    f=VERIFY/n
    if f.exists():manifest['outputs_sha256'][str(f.relative_to(BASE))]=sha(f)
manifest['historical_sha256']={}
for f in sorted(VERIFY.rglob('*')):
    n=str(f.relative_to(BASE))
    if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc' and n not in manifest['source_sha256'] and n not in manifest['outputs_sha256']:manifest['historical_sha256'][n]=sha(f)
for n in ['tools/correct_models.py','tools/finish_models.py','tools/finalize_pcb.py']:manifest['historical_sha256'][n]=sha(BASE/n)
manifest['historical_evidence_note']='Inherited migration/baseline and focused-preservation/independent-check reports are prior worker277 history, not post-EP proof; current bounded proof is verification/es8388-ep-delta.json. No historical migration tool rerun.'
(PROD/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Validated/published: preserved 4Cu, 61 full BOM/CPL refs, 55 top SMD refs, 6 user-approved retained THT refs; no order authorized, assembler review pending.')
