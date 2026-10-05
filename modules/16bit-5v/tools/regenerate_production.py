#!/usr/bin/python3
"""Prepare user-authorized 16bit-5v files from the restored hash-bound checkpoint.

Current workspace 292, branch, HEAD and native hashes are pinned independently.
Every unchanged circuit/geometry/mechanical guard is retained. The user accepts
existing engineering for file generation; conservative audit unknowns remain
visible but are not a generation veto. Supplier matching, current stock and
portal/order acceptance are separate. Use ONLY the integrated opt tools.
No old finalizer, advisor, authenticated upload, order or commit is invoked.
"""
from pathlib import Path
import argparse
import collections
import csv
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
import pcbnew as p

MOD=Path(__file__).resolve().parents[1]
ROOT=MOD.parents[1]
PCB=MOD/'16bit-5v.kicad_pcb'; SCH=MOD/'16bit-5v.kicad_sch'; PRO=MOD/'16bit-5v.kicad_pro'
PROD=MOD/'production'; VERIFY=MOD/'verification/basic-economy'; JLC=PROD/'assembly'
COMMON=ROOT/'opt/kicad-jlcpcb'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--review-preparation',action='store_true',required=True)
args=parser.parse_args()
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def run(*args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True)
    if r.returncode: raise SystemExit(f'Command failed: {args}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout

def rows(f): return list(csv.DictReader(f.open(encoding='utf-8-sig')))
def refs(bom): return {ref.strip() for row in bom for ref in row['Designator'].split(',')}
def write_json(path,data): path.write_text(json.dumps(data,indent=2)+'\n')
review=json.loads((VERIFY/'reviewed-source.json').read_text())
assert Path.cwd().resolve()==ROOT.resolve()
assert str(ROOT)==review['workspace']
assert run('git','rev-parse','HEAD').strip()==review['authority_ref']=='17102ba4701cc24b2798b80a08f1f0180c1226aa'
assert run('git','branch','--show-current').strip()==review['branch']
initial={f.name:sha(f) for f in [PCB,SCH,PRO]}
assert initial==review['final_source_sha256'],'Source differs from current reviewed saved/filled evidence'
assert review['release_status']=='FILE_GENERATION_AUTHORIZED'
generation_policy=json.loads((VERIFY/'generation-policy.json').read_text())
assert generation_policy['file_generation_authorized'] is True and generation_policy['existing_engineering_user_accepted'] is True
assert generation_policy['native_source_changes_authorized_for_this_generation']==[]
assert generation_policy['order_ready'] is False and generation_policy['authenticated_upload_or_order_authorized'] is False
assert all(sha(MOD/name)==digest for name,digest in review['evidence_sha256'].items()),'Review evidence changed'
assert all(sha(ROOT/name)==digest for name,digest in review['common_tool_sha256'].items()),'Common tools changed'
# Verify independently before ANY production writes.
print(run(sys.executable,'-B',MOD/'tools/verify_power.py').strip())
run('kicad-cli','sch','export','netlist','--format','kicadxml','-o',VERIFY/'netlist-final.xml',SCH)
run('kicad-cli','pcb','drc','--format','json','--all-track-errors','--schematic-parity','--severity-all','-o',VERIFY/'drc-final.json',PCB)
run('kicad-cli','sch','erc','--format','json','--severity-all','-o',VERIFY/'erc-final.json',SCH)
drc=json.loads((VERIFY/'drc-final.json').read_text()); erc=json.loads((VERIFY/'erc-final.json').read_text())
drcbase=json.loads((VERIFY/'drc-baseline.json').read_text()); ercbase=json.loads((VERIFY/'erc-baseline.json').read_text())
erv=[v for s in erc['sheets'] for v in s['violations']]; erb=[v for s in ercbase['sheets'] for v in s['violations']]
assert not drc['unconnected_items'] and not drc['schematic_parity']
assert not any(v['severity']=='error' or v.get('excluded') for v in drc['violations']+erv)
assert drc['ignored_checks']==drcbase['ignored_checks'] and erc['ignored_checks']==ercbase['ignored_checks']
counts=lambda findings:collections.Counter((v['type'],v['severity']) for v in findings)
assert counts(drc['violations'])==counts(drcbase['violations']) and counts(erv)==counts(erb),'New warning types/counts'
PROD.mkdir(exist_ok=True); JLC.mkdir(exist_ok=True)
# The shared wrapper publishes verified Gerber mirrors; known missing codes are
# explicitly permitted for a HOLD review package, NOT waived by the auditor.
print(run(sys.executable,'-B',COMMON/'add_production_files.py',MOD,'--allow-missing-part-numbers').strip())
staged=MOD/'jlcpcb/16bit-5v'
for name in ['16bit-5v-gerbers.zip','bom.csv','positions.csv','export-report.json']:
    shutil.copyfile(staged/name,JLC/name)
with tempfile.TemporaryDirectory(prefix='16bit-complete-physical-') as temp:
    full=Path(temp)
    run(sys.executable,'-B',COMMON/'export.py',MOD,'--output',full,'--include-through-hole')
    with zipfile.ZipFile(JLC/'16bit-5v-gerbers.zip') as a,zipfile.ZipFile(full/'16bit-5v-gerbers.zip') as z:
        assert sorted(a.namelist())==sorted(z.namelist())
        def geometry_bytes(data):
            return b'\n'.join(line for line in data.splitlines() if b'TF.CreationDate,' not in line and not line.startswith(b'G04 Created by KiCad ') and not line.startswith(b'; DRILL file KiCad '))
        assert all(geometry_bytes(a.read(n))==geometry_bytes(z.read(n)) for n in a.namelist()),'Fab geometry differs between selection modes'
    for src,dest in [('bom.csv','bom.csv'),('positions.csv','positions.csv'),('export-report.json','all-components-export-report.json')]: shutil.copyfile(full/src,PROD/dest)
shutil.copyfile(JLC/'16bit-5v-gerbers.zip',PROD/'16bit-5v.zip')
run('kicad-cli','pcb','export','ipcd356','-o',PROD/'netlist.ipc',PCB)
b=p.LoadBoard(str(PCB)); fps={f.GetReference():f for f in b.GetFootprints()}; allrefs=set(fps)
smdrefs={r for r,f in fps.items() if f.GetAttributes()&p.FP_SMD}
smdbom=rows(JLC/'bom.csv'); smdpos=rows(JLC/'positions.csv'); fullbom=rows(PROD/'bom.csv'); fullpos=rows(PROD/'positions.csv')
assert refs(smdbom)=={r['Designator'] for r in smdpos}==smdrefs and len(smdpos)==len(smdrefs)==56
assert refs(fullbom)=={r['Designator'] for r in fullpos}==allrefs and len(fullpos)==len(allrefs)==62
assert all(r['Layer']=='top' for r in smdpos),'No hidden bottom SMDs'
origin=b.GetDesignSettings().GetAuxOrigin()
for row in fullpos:
    f=fps[row['Designator']]; fields={v.GetName():v.GetText() for v in f.GetFields()}
    dx=float(fields.get('JLCPCB Position Offset X') or '0'); dy=float(fields.get('JLCPCB Position Offset Y') or '0')
    assert abs(float(row['Mid X'])-(p.ToMM(f.GetPosition().x-origin.x)+dx))<.00001
    assert abs(float(row['Mid Y'])-(p.ToMM(origin.y-f.GetPosition().y)+dy))<.00001
    assert abs(float(row['Rotation'])-f.GetOrientationDegrees()%360)<.00001
    assert row['Layer']==('bottom' if f.GetLayer()==p.B_Cu else 'top')
manual=sorted(allrefs-smdrefs)
assert set(manual)=={'GND1','V_SUPPLY1','J1','J2','RV1','RV2'}
# The requested 5V -> 3V3 regulator is ALREADY fitted, wired and exported.
# Prove it before publishing; never add a duplicate based on a stale request.
u6=fps['U6']
u6nets={d.GetNumber():d.GetNetname() for d in u6.Pads()}
assert u6.GetValue()=='AP2112K-3.3' and u6.GetFieldText('LCSC')=='C51118'
assert u6.GetFieldText('MPN')=='AP2112K-3.3TRG1'
assert u6nets['1']==u6nets['3']=='+5V' and u6nets['2']=='GND' and u6nets['5']=='+3V3'
assert sum(f.GetValue()=='AP2112K-3.3' for f in fps.values())==1,'Duplicate regulator'
u6bom=[row for row in smdbom if 'U6' in {r.strip() for r in row['Designator'].split(',')}]
assert len(u6bom)==1 and u6bom[0]['LCSC Part #']=='C51118' and u6bom[0]['MPN']=='AP2112K-3.3TRG1'
assert len([row for row in smdpos if row['Designator']=='U6'])==1
assert u6.GetFPID().GetUniStringLibId()=='Package_TO_SOT_SMD:SOT-23-5'
write_json(VERIFY/'regulator-inclusion.json',{'ref':'U6','mpn':'AP2112K-3.3TRG1','code':'C51118','footprint':u6.GetFPID().GetUniStringLibId(),'pins':u6nets,'included_in_schematic_pcb_bom_cpl':True,'quantity_per_board':1,'duplicate_regulator_added':False,'native_source_changed':False,'generation_user_authorized':True,'order_ready':False})
with (PROD/'manual-assembly.csv').open('w',newline='') as stream:
    w=csv.writer(stream); w.writerow(['Designator','Quantity','Value','Footprint','BodySide','AssemblyInstruction'])
    for ref in manual:
        f=fps[ref]; side='bottom' if f.GetLayer()==p.B_Cu else 'top'
        note=('Downward male BASE-mating header; preserve 1..5 pad registration. Do not flip for a one-side claim.' if ref in ['GND1','V_SUPPLY1'] else 'Downward-facing 1x05 female signal socket; schematic/PCB/BOM all use the actual five-pin intent. Preserve pins 1..5 and mating orientation.' if ref in ['J1','J2'] else 'Front RV09 potentiometer; retain shaft/control access. Solder tails pass through normally.')
        w.writerow([ref,1,f.GetValue(),f.GetFPID().GetUniStringLibId(),side,note])
(PROD/'designators.csv').write_text(''.join(ref+':1\n' for ref in sorted(allrefs)),encoding='utf-8-sig')
with zipfile.ZipFile(JLC/'16bit-5v-gerbers.zip') as z:
    assert z.testzip() is None
    layers=sorted(z.namelist()); assert all(Path(n).name==n for n in layers)
    assert len([n for n in layers if n.endswith('.gbr')])==9 and len([n for n in layers if n.endswith('.drl')])==2
    for token in ['F_Cu','B_Cu','F_Mask','B_Mask','F_Paste','B_Paste','F_Silkscreen','B_Silkscreen','Edge_Cuts','PTH','NPTH']: assert any(token in n for n in layers),token
    assert not any('In1' in n or 'In2' in n for n in layers)
    for name in layers: assert sha(MOD/'jlcpcb/gerber'/name)==hashlib.sha256(z.read(name)).hexdigest(),'Loose Gerber mirror differs'
assert sha(JLC/'16bit-5v-gerbers.zip')==sha(PROD/'16bit-5v.zip')==sha(staged/'16bit-5v-gerbers.zip')==sha(MOD/'jlcpcb/production_files/GERBER-16bit-5v.zip')
# Same common offline API for BOTH native and exported-BOM audits. Reuse the
# imported dated raw evidence; this focused continuation makes NO new release
# queries. Strict-live remains required and therefore FAILS replay, honestly.
sys.path.insert(0,str(COMMON))
from catalog import Catalog, CatalogError
from bom_audit import board_components, bom_components, audit_components
policy=json.loads((VERIFY/'requirements-final.json').read_text())
assert review['production_catalog_mode']=='dated-cache-replay-no-new-requests'
client=Catalog(cache_dir=VERIFY/'catalog-release-raw',offline=True,max_requests=1)
capclient=Catalog(cache_dir=VERIFY/'catalog-final-raw',offline=True,max_requests=1)
for code in ['C23733','C15008']: client.memo[code]=capclient.lookup(code)
exact=client.search('0402WGF1001TCE',12)
match=[part for part in exact['parts'] if part['code']=='C11702' and part['mpn']=='0402WGF1001TCE']
assert not exact['truncated'] and len(match)==1,'Exact complete-page 1k identity unresolved; no retries'
client.memo['C11702']=match[0]  # dated common-API replay response; never relabeled live
report=json.loads((JLC/'export-report.json').read_text())
native=audit_components(board_components(PCB,VERIFY/'netlist-final.xml'),client,policy,1,'top',JLC/'positions.csv',report,True)
native['input_sha256']={str(path.resolve()):sha(path) for path in [PCB,VERIFY/'netlist-final.xml',VERIFY/'requirements-final.json',JLC/'positions.csv',JLC/'export-report.json']}
write_json(VERIFY/'audit-final-native.json',native)
bom_policy={'components':{ref:req for ref,req in policy['components'].items() if ref in smdrefs},'verified_specs':policy['verified_specs']}
bomaudit=audit_components(bom_components(JLC/'bom.csv'),client,bom_policy,1,'top',JLC/'positions.csv',report,True)
bomaudit['input_sha256']={str(path.resolve()):sha(path) for path in [JLC/'bom.csv',JLC/'positions.csv',JLC/'export-report.json',VERIFY/'requirements-final.json']}
bomaudit['requirement_ref_filter']='Exported top SMD refs; same disk policy verified_specs, no requirement relaxation'
write_json(VERIFY/'audit-final-bom.json',bomaudit)
assert not native['order_ready'] and not bomaudit['order_ready']
write_json(VERIFY/'audit-status.json',{'native_conservative_audit_exit':0 if native['catalog_and_requirements_pass'] else 1,'bom_conservative_audit_exit':0 if bomaudit['catalog_and_requirements_pass'] else 1,'actual_live_requests':client.requests,'request_budget':0,'catalog_evidence_mode':'dated cache replay','strict_live_required':True,'new_supplier_requests_in_this_generation':0,'deduplication':'same in-process common offline Catalog memo across native+BOM audits','boards_basis':1,'requested_order_quantity':None,'order_ready':False,'no_missing_reviews_synthesized':True})
known={}
for item in native['components']:
    part=item.get('catalog')
    if not part: continue
    entry=known.setdefault(part['code'],{'catalog':part,'refs':[]})
    entry['refs'].append(item['ref'])
for entry in known.values():
    entry['quantity_per_board']=len(entry['refs']); entry['stock_for_one_board']=entry['catalog']['stock']>=len(entry['refs']); entry['stock_only_max_boards']=entry['catalog']['stock']//len(entry['refs'])
known_max=min((entry['stock_only_max_boards'] for entry in known.values()),default=None)
missing=sorted(item['ref'] for item in native['components'] if not item.get('catalog'))
write_json(VERIFY/'live-supply-summary.json',{'quantity_basis_boards':1,'requested_quantity':None,'by_code':known,'missing_actual_identities':missing,'stock_only_upper_bound_from_known_parts_boards':known_max,'full_board_maximum_verified':None,'attrition_minima_reserved_stock_included':False,'full_board_Economy_claim':False,'evidence_mode':'cache; original retrieval timestamps and raw hashes preserved','statement':'From saved dated evidence, all known assigned codes have observed componentProductType 0 and enough stock for one-board placements only. Missing exact supplier identities and current process/order acceptance remain unresolved; inherited application engineering is user-accepted for file generation only; PT8211 has no assumed attrition reserve.'})
assert initial=={f.name:sha(f) for f in [PCB,SCH,PRO]},'Exporter modified native sources'
fullreport=json.loads((PROD/'all-components-export-report.json').read_text())
manifest={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'reviewed_source':'verification/basic-economy/reviewed-source.json','release_status':'HOLD — partial Basic/Economy sourcing; not an approved manufacture/order package','order_ready':False,'source_branch':'16bit-5v','authority_ref':review['authority_ref'],'workspace_branch':review['branch'],'workspace':review['workspace'],'baseline_source_sha256':review['baseline_source_sha256'],'quantity_basis_boards':1,'requested_order_quantity':None,'copper_layers':['F.Cu','B.Cu'],'assembly_side':'top','datum':'unchanged KiCad drill/place origin, mm Cartesian top view; J5 X0/Y-3.675mm body correction preserved','electrical_gates':{'drc_errors':0,'unconnected':0,'parity':0,'erc_errors':0,'drc_warnings':len(drc['violations']),'erc_warnings':len(erv),'drc_exclusions':0,'erc_exclusions':0,'drc_warning_types':dict(collections.Counter(v['type'] for v in drc['violations'])),'erc_warning_types':dict(collections.Counter(v['type'] for v in erv)),'ignored_drc_checks':[v['key'] for v in drc['ignored_checks']],'ignored_erc_checks':[v['key'] for v in erc['ignored_checks']]},'component_body_sides':dict(collections.Counter(b.GetLayerName(f.GetLayer()) for f in fps.values())),'smd_assembly_refs':56,'complete_bom_refs':62,'manual_tht_refs':manual,'smd_missing_supplier_numbers':report['missing_part_numbers'],'all_missing_supplier_numbers':fullreport['missing_part_numbers'],'fabrication_archive_entries':layers,'catalog_and_requirements_pass':native['catalog_and_requirements_pass'] and bomaudit['catalog_and_requirements_pass'],'stock_only_known_parts_upper_bound_boards':known_max,'full_board_maximum_verified':None,'holds':['Required R7/R8 remain unassigned 27ohm: exact Basic/Economy C25092 22ohm + (C25077 10ohm || C25077 10ohm) investigated, NOT implemented because USB stress/pulse/near-chip layout/AC suitability are unproven. Five capacitors now carry exact supplier review-candidate bindings only: C6/C7/C9/C10 C23733; C21 C15008. Guaranteed effective-C/ESR/ESL and circuit limits remain application/manufacturing HOLD. No new waivers or required R/C Extended, DNP or manual workaround.','D1 generic LED and U5 generic PSRAM exact identities/polarity/package/firmware intent remain unassigned.','Conservative native and BOM audits fail on replay/strict-live, missing exact identities, human attestations and unproven DC-bias/ESR/ESL/external-stress/temperature requirements; no bypass or blanket approval.','PT8211 C92004 stock supports only one board before attrition/minima; actual quantity and full BOM maximum unknown. Dated stock evidence is reused, not fresh or reserved; final live classification/Economy/stock/quantity/attrition/order acceptance recheck required.','Manual connector/pot purchased-part, lead protrusion, case/mating and clearance review; board-level Economy options, via-in-pad/stencil/inspection/reflow process and Gerber/JLC placement-preview human review required.','Bench power/ripple/inductor winding/startup/repetitive resistor pulse, USB and audio testing; final human production/order authorization outstanding.'],'exporter_provenance':{'repository_path':'opt/kicad-jlcpcb/export.py','wrapper':'opt/kicad-jlcpcb/add_production_files.py','integrated_commits':review['tools_commits'],'sha256':sha(COMMON/'export.py'),'wrapper_sha256':sha(COMMON/'add_production_files.py'),'catalog_sha256':sha(COMMON/'catalog.py'),'legacy_private_exporter_used':False},'catalog_evidence_mode':'dated common-API cache replay; strict-live audit intentionally fails; no new supplier queries','required_rc_catalog_bound':41,'required_rc_total':43,'bound_smd_supplier_codes':52,'missing_actual_smd_identities':['R7','R8','D1','U5'],'application_candidate_hold_refs':['C6','C7','C9','C10','C21'],'generation_commands':['/usr/bin/python3 -B modules/16bit-5v/tools/regenerate_production.py --review-preparation','shared wrapper + shared exporter; kicad-cli native netlist/DRC/ERC/IPC; common offline Catalog/audit API with strict-live gate retained'],'source_sha256':{},'files':{}}
# User acceptance changes ONLY generation/release policy, not audit facts or rules.
# Missing identities, dated stock and authenticated matching remain separate.
manifest.update(release_status='FILES_GENERATED_USER_ACCEPTED_EXISTING_DESIGN',file_generation_authorized=True,existing_engineering_user_accepted=True,order_ready=False,generation_policy='verification/basic-economy/generation-policy.json',regulator_inclusion='verification/basic-economy/regulator-inclusion.json',native_design_changed=False)
manifest['holds']=[
    'Upload matching: R7/R8 remain original 27ohm/0402 with blank supplier codes: 41/43 R/C have dated Basic+Economy bindings, not 43/43. No USB network was installed under the latest no-redesign/export-first steering.',
    'Upload matching: original D1 LED and U5 PSRAM rows/code fields retained as-is, without invented identities or omissions.',
    'Current batch size, live classification/Economy/stock/minimum quantities/attrition and authenticated supplier matching still require the user; saved PT8211 C92004 stock was one, not reserved.',
    'User-controlled Economy top-side options and actual placement/Gerber/drill/paste review remain separate from file generation; six listed THT connectors/pots are manual. No upload, order or physical shipping certification performed.'
]
manifest.pop('application_candidate_hold_refs',None)
manifest['accepted_existing_engineering_reviews']=generation_policy['accepted_existing_reviews']
manifest['conservative_audit_boundary']='Audit unknowns retained truthfully; accepted prior LED/capacitor/resistor application checks are not file-generation HOLDs; no reviews or undocumented specs were fabricated.'
source=[PCB,SCH,PRO,MOD/'Bread16bit.kicad_sym',MOD/'sym-lib-table',MOD/'fp-lib-table',MOD/'MCU_RaspberryPi_RP2350.kicad_sym']
manifest['source_sha256']={str(f.relative_to(MOD)):sha(f) for f in source}
# A shell may still be appending the generation log when this code executes;
# never freeze its incomplete bytes. Closeout verification may hash it afterward.
files=[f for root in [PROD,VERIFY,MOD/'jlcpcb',MOD/'tools'] for f in root.rglob('*') if f.is_file() and f.name not in {'manifest.json','production-generation.log','production-generation-focused.log'} and '__pycache__' not in str(f)]
manifest['files']={str(f.relative_to(MOD)):sha(f) for f in sorted(set(files))}
write_json(PROD/'manifest.json',manifest)
print(f'GENERATED USER-AUTHORIZED FILES: 56 top SMD / 62 physical / 6 manual; {len(layers)} ZIP members; 0 DRC/ERC errors/opens/parity; audit native/BOM {native["catalog_and_requirements_pass"]}/{bomaudit["catalog_and_requirements_pass"]}; {len(missing)} identities unresolved; known-stock upper bound {known_max} board before attrition, full maximum unknown.')
