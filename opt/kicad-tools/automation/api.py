"""Agent-facing PCB transactions. All native writes are confined to a NEW candidate."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

try:
    from ._bridge import Error, native, project
    from . import schema
except ImportError:
    from _bridge import Error, native, project
    import schema

HERE = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load_json(path):
    return schema.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_json(path, value):
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def isolated_env(directory=None):
    env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','KIPRJMOD') and not k.startswith('KICAD')}
    env.update(PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C',HOME='/dev/null',XDG_CONFIG_HOME='/dev/null',XDG_CACHE_HOME='/dev/null')
    if directory:
        env.update(HOME=str(directory/'home'),XDG_CONFIG_HOME=str(directory/'config'),XDG_CACHE_HOME=str(directory/'cache'))
    return env


def executable(value):
    result=shutil.which(str(Path(value).expanduser()))
    if not result: raise Error(f'Executable not found: {value}')
    return str(Path(result).resolve())


def command(argv, cwd='/', env=None, stdin=None):
    try:
        proc=subprocess.run([str(v) for v in argv],input=stdin,cwd=cwd,env=env or isolated_env(),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    except subprocess.TimeoutExpired as error:
        raise Error(f'Native command timed out: {argv}; stdout={error.stdout!r}; stderr={error.stderr!r}') from error
    return {'command':list(map(str,argv)),'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}


def probe(action, board, operations=None, python='python3', env=None):
    payload={'action':action,'board':str(board)}
    if operations is not None: payload['operations']=operations
    result=command([executable(python),'-I','-B',HERE/'_worker.py'],env=env,stdin=canonical(payload))
    try: response=json.loads(result['stdout'])
    except ValueError as error: raise Error(f'Native worker returned invalid JSON: {result}') from error
    if result['returncode'] != 0 or not response.get('ok'):
        raise Error(f'Native worker failed: {response.get("error")}; stderr: {result["stderr"]}; returncode: {result["returncode"]}')
    # Never hide the known startup assertions or any other native diagnostic.
    return response['result'], result


def select(*, project_dir=None, board=None, schematic=None, config=None):
    return project.select_project(SimpleNamespace(project_dir=project_dir,board=board,schematic=schematic,config=config))


def _closure(selection, operations=None):
    closure=project.Plan(selection)
    if selection.board.with_suffix('.kicad_sch') != selection.schematic:
        raise Error('Same-directory, same-stem root schematic and PCB required for native parity')
    if operations:
        for op in operations['operations']:
            if op['op']=='add_footprint': closure.dependency(Path(op['file']))
        closure.anchor=Path(os.path.commonpath([str(p.parent) for p in closure.files]))
    # Full closure cannot be promised for unsupported secondary native resources.
    def walk(node):
        if isinstance(node,list):
            if node and node[0] in ('model','embedded_files','image'):
                raise Error('3D models, embedded files and images are unsupported dependencies; fail closed')
            for child in node: walk(child)
    for path in closure.files:
        if path.suffix in ('.kicad_pcb','.kicad_mod'):
            ast=native.kicad.parse_sexpr(path.read_text(encoding='utf-8-sig')); walk(ast)
            if path.suffix=='.kicad_pcb': _global_and_items(path)
        if path.suffix=='.kicad_pro':
            settings=load_json(path)
            def check(value,key=''):
                if isinstance(value,dict):
                    for k,v in value.items(): check(v,k)
                elif isinstance(value,list):
                    for v in value: check(v,key)
                elif isinstance(value,str):
                    if value=='ignore' and key: raise Error('Ignored project rule severities are unsupported; do not weaken checks')
                    if value and (key in ('page_layout_descr_file','drawing_sheet') or value.endswith(('.kicad_wks','.kicad_sch','.kicad_pcb','.kicad_sym','.kicad_mod','.step','.wrl'))):
                        raise Error(f'Unsupported project resource path {key}: {value}')
            check(settings)
    return closure


def _operations(operations, ops_base=None):
    path=None
    if isinstance(operations,(str,Path)):
        path=project.absolute(operations)
        data=load_json(path); base=path.parent
    else:
        data=operations; base=ops_base
    try: data=schema.validate(data,base)
    except (TypeError,ValueError) as error: raise Error(f'Invalid operations JSON: {error}') from error
    return data,path


def inspect(*, python='python3', **selection):
    """Read-only inspection of selected project: UUID/ref/net/placement/layer identities."""
    closure=_closure(select(**selection)); before=closure.snapshot()
    result,log=probe('inspect',closure.project.board,python=python)
    closure.verify_sources(before)
    result.update(selection=closure.describe(),native_diagnostics=log['stderr'],source_writes=False)
    return result


def plan(operations, *, ops_base=None, allow_draft_opens=False, python='python3', kicad_cli='kicad-cli', **selection):
    """No writes: strict schema, full native dependency/input hashes and in-memory validation."""
    if type(allow_draft_opens) is not bool: raise Error('allow_draft_opens must be bool')
    document,ops_file=_operations(operations,ops_base)
    closure=_closure(select(**selection),document); before=closure.snapshot()
    input_hashes=dict(before)
    if ops_file:
        input_hashes[str(ops_file)]={'sha256':native.sha256(ops_file),'symlink':os.readlink(ops_file) if ops_file.is_symlink() else None}
    view,read_log=probe('inspect',closure.project.board,python=python)
    validation,validate_log=probe('validate',closure.project.board,document,python)
    cli_path=executable(kicad_cli); cli_log=command([cli_path,'version'])
    cli_version=cli_log['stdout'].strip()
    if cli_log['returncode'] or not re.match(r'^10\.0\.\d+(?:\D|$)',cli_version): raise Error('Only tested kicad-cli 10.0.x is supported')
    if re.match(r'^\d+\.\d+\.\d+',cli_version)[0] != re.match(r'^\d+\.\d+\.\d+',view['pcbnew_version'])[0]:
        raise Error('pcbnew and CLI patch versions must match')
    closure.verify_sources(before)
    if ops_file and native.sha256(ops_file)!=input_hashes[str(ops_file)]['sha256']: raise Error('Operations file changed during planning')
    preconditions={'input_hashes':input_hashes,'dependency_bindings':{str(k):v[1] for k,v in closure.rewrites.items()},'inspection_sha256':digest(view),
                   'native_versions':{'pcbnew':view['pcbnew_version'],'cli':cli_version},'operations_sha256':digest(document),
                   'tool_hashes':{str(p):native.sha256(p) for p in sorted(set(HERE.glob('*.py')) | {Path(native.__file__),Path(project.__file__),Path(native.kicad.__file__)})},
                   'selection':{'project_dir':str(closure.project.directory),'board':str(closure.project.board),'schematic':str(closure.project.schematic),'config':str(closure.project.config) if closure.project.config else None},
                   'policy':{'allow_draft_opens':allow_draft_opens,'all_other_findings_block':True}}
    # Resolve bindings into JSON paths, rather than Path objects.
    preconditions['dependency_bindings']={k:{name:str(path) for name,path in v.items()} for k,v in preconditions['dependency_bindings'].items()}
    result={'schema_version':1,'kind':'pcb_edit_plan','operations':document,'preconditions':preconditions,
            'changes':validation['changes'],'source_writes':False,'status':'planned_not_checked',
            'caveats':['Placement does not drag attached copper','Native ERC/DRC and XML parity run only on apply','No live GUI, IPC, push/shove or automatic placement'],
            'native_diagnostics':{'inspect':read_log['stderr'],'validation':validate_log['stderr'],'cli':cli_log['stderr']}}
    result['plan_sha256']=digest({k:v for k,v in result.items() if k not in ('native_diagnostics','plan_sha256')})
    return result


def _identities(report, kind):
    if not isinstance(report,dict): raise Error('Unrecognized native check report')
    if kind=='erc':
        sheets=report.get('sheets')
        if not isinstance(sheets,list) or any(not isinstance(s,dict) or not isinstance(s.get('violations'),list) for s in sheets): raise Error('Unknown ERC JSON schema')
        buckets=[('violations',s['violations'],{k:v for k,v in s.items() if k!='violations'}) for s in sheets]
    else:
        buckets=[(k,report.get(k),None) for k in ('violations','unconnected_items','schematic_parity')]
    identities=[]
    for category,findings,sheet in buckets:
        if not isinstance(findings,list): raise Error('Unknown DRC JSON schema')
        for finding in findings:
            if not isinstance(finding,dict) or not isinstance(finding.get('type'),str) or finding.get('severity') not in ('error','warning','exclusion','excluded') or not isinstance(finding.get('items'),list):
                raise Error(f'Unsupported finding schema: {finding}')
            # Finding identities include UUIDs, descriptions, positions and sheet path,
            # so an unrelated new short cannot replace an old short at the same total.
            identity={k:finding[k] for k in sorted(finding) if k not in ('excluded','severity')}
            if sheet is not None: identity['sheet']=sheet
            identities.append({'category':category,'severity':finding['severity'],'identity':identity,'sha256':digest({'category':category,'identity':identity})})
    return sorted(identities,key=canonical)


def compare_findings(before,after):
    left,right=Counter(canonical(v) for v in before),Counter(canonical(v) for v in after)
    return {'added':[json.loads(k) for k,v in sorted((right-left).items()) for _ in range(v)],
            'removed':[json.loads(k) for k,v in sorted((left-right).items()) for _ in range(v)],
            'retained':[json.loads(k) for k,v in sorted((left&right).items()) for _ in range(v)]}


def _rebind(closure, directory):
    """Repair Plan.stage absolute staging paths to per-file relative bindings."""
    rewrites=[]
    for source,(head,targets) in closure.rewrites.items():
        copy=directory/'inputs'/source.relative_to(closure.anchor)
        mapping={str(directory/'inputs'/p.relative_to(closure.anchor)):os.path.relpath(directory/'inputs'/p.relative_to(closure.anchor),copy.parent) for p in targets.values()}
        text=native.replace_paths(copy.read_text(encoding='utf-8-sig'),head,mapping)
        copy.write_text(text,encoding='utf-8')
        rewrites.append({'file':str(copy.relative_to(directory)),'kind':head,'bindings':mapping})
    return rewrites


def _relocatable(root):
    for pth in root.rglob('*'):
        if pth.is_symlink(): raise Error(f'Candidate contains symlink: {pth}')
        if pth.is_file() and pth.stat().st_nlink!=1: raise Error(f'Candidate contains linked/aliased file: {pth}')
        if pth.name not in ('fp-lib-table','sym-lib-table') and pth.suffix!='.kicad_sch': continue
        ast=native.kicad.parse_sexpr(pth.read_text(encoding='utf-8-sig'))
        def walk(node):
            if not isinstance(node,list): return
            if len(node)>1 and node[0]=='uri': check(node[1])
            if len(node)>2 and node[0]=='property' and node[1] in ('Sheetfile','Sheet file'): check(node[2])
            for child in node: walk(child)
        def check(value):
            target=pth.parent/value
            if Path(value).is_absolute() or '${' in value or not target.exists() or root.resolve() not in target.resolve().parents:
                raise Error(f'Candidate is not relocatable/self-contained: {pth}: {value}')
        walk(ast)


def _checks(cli,board,schematic,directory,env,commands,refill_save):
    directory.mkdir()
    xml=directory/'netlist.xml'
    record=command([cli,'sch','export','netlist','--format','kicadxml','--output',xml,schematic],schematic.parent,env); commands.append(record)
    if record['returncode'] or not xml.is_file(): raise Error('Native XML netlist export failed; see command logs')
    netlist=native.read_netlist(xml)
    parity=native.board_parity(board,netlist)
    findings={}
    for kind in ('erc','drc'):
        output=directory/(kind+'.json')
        argv=[cli,'sch' if kind=='erc' else 'pcb',kind,'--format','json','--units','mm','--severity-all','--exit-code-violations','--output',output]
        if kind=='drc':
            argv+=['--refill-zones','--all-track-errors','--schematic-parity']
            if refill_save: argv+=['--save-board']
        argv+=[schematic if kind=='erc' else board]
        record=command(argv,schematic.parent if kind=='erc' else board.parent,env); commands.append(record)
        if record['returncode'] not in (0,5) or not output.is_file(): raise Error(f'Native {kind.upper()} failed; see command logs')
        findings[kind]=_identities(load_json(output),kind)
    return {'parity':parity,'findings':findings},netlist


def _global_and_items(board):
    root=native.kicad.parse_sexpr(Path(board).read_text(encoding='utf-8-sig'))
    items={}; headers=[]
    def strip_fills(node):
        if not isinstance(node,list): return node
        if node and node[0]=='fill': node=[node[0]]+[c for c in node[1:] if c!='yes']
        return [strip_fills(c) for c in node if not (isinstance(c,list) and c and c[0] in ('filled_polygon','fill_segments','filled_areas_thickness'))]
    def all_uuids(node):
        if isinstance(node,list):
            if node and node[0]=='uuid': yield node[1]
            for c in node: yield from all_uuids(c)
    ids=list(all_uuids(root))
    for key in ids: schema.identifier(key)
    if len(set(ids)) != len(ids): raise Error('Duplicate serialized board UUIDs')
    item_heads={'footprint','module','segment','arc','via','zone','group','gr_line','gr_arc','gr_rect','gr_circle','gr_poly','gr_text','gr_text_box','dimension','target'}
    for child in root[1:]:
        if isinstance(child,list) and child and child[0] in item_heads and not native.kicad.atom(child,'uuid'): raise Error('All existing editable PCB items must carry explicit UUIDs')
    for child in root[1:]:
        if not isinstance(child,list): continue
        item_id=native.kicad.atom(child,'uuid')
        if item_id: items[item_id]=strip_fills(child)
        elif child[0] not in ('version','generator','generator_version'): headers.append(child)
    return headers,items


def _restore_materialized_variables(board, before_headers, project_file):
    # KiCad CLI SaveBoard copies project text variables into board properties.
    # Remove ONLY newly materialized, exactly matching declared text variables;
    # existing board properties and every other header still have to compare equal.
    variables=load_json(project_file).get('text_variables',{}) if project_file.is_file() else {}
    after_headers,_=_global_and_items(board)
    added=[v for v in after_headers if v not in before_headers]
    if not added: return []
    if any(len(v)!=3 or v[0]!='property' or variables.get(v[1])!=v[2] for v in added):
        raise Error('Native refill introduced unexpected board properties/settings')
    text=board.read_text(encoding='utf-8-sig')
    for head,start,end in reversed(list(native.source_blocks(text))):
        if head=='property' and native.kicad.parse_sexpr(text[start:end]) in added:
            text=text[:start]+text[end:]
    board.write_text(text,encoding='utf-8')
    return added


def _check_additions(document, netlist):
    for op in document['operations']:
        if op['op']!='add_footprint' or op['mechanical_only']: continue
        ref=op['reference']; component=netlist['components'].get(ref)
        if component is None or component['__EXCLUDE_FROM_BOARD']: raise Error(f'Added electrical reference not in on-board schematic: {ref}')
        pins={pin:name for (r,pin),name in netlist['pins'].items() if r==ref}
        if pins!=op['pad_nets']: raise Error('Added footprint pad_nets do not exactly match native schematic XML')
        if component.get('Footprint')!=op['footprint_id'] or component.get('Value')!=op['value']: raise Error('Added footprint value/library ID must match schematic XML')


def apply(edit_plan, output, *, operations=None, python='python3', kicad_cli='kicad-cli'):
    """Apply a previously emitted plan. Returns accepted/draft/rejected/failed, never overwrites."""
    expected=load_json(edit_plan) if isinstance(edit_plan,(str,Path)) else edit_plan
    schema.fields(expected,{'schema_version','kind','operations','preconditions','changes','source_writes','status','caveats','native_diagnostics','plan_sha256'})
    if expected['kind']!='pcb_edit_plan' or expected['schema_version']!=1: raise Error('Expected PCB edit plan schema_version 1')
    actual_digest=digest({k:v for k,v in expected.items() if k not in ('native_diagnostics','plan_sha256')})
    if actual_digest!=expected['plan_sha256']: raise Error('Plan was modified or corrupted')
    prec=expected['preconditions']; selection=prec['selection']
    arguments={'config':selection['config']} if selection['config'] else {k:v for k,v in selection.items() if k!='config'}
    for name,record in prec['input_hashes'].items():
        path=Path(name)
        link=os.readlink(path) if path.is_symlink() else None
        if not path.is_file() or native.sha256(path)!=record['sha256'] or link!=record['symlink']: raise Error(f'Stale input hash: {path}')
    fresh=plan(operations if operations is not None else expected['operations'],allow_draft_opens=prec['policy']['allow_draft_opens'],python=python,kicad_cli=kicad_cli,**arguments)
    # Passing original ops file is optional; original hashes are still enforced.
    original_hashes=prec['input_hashes']; fresh_hashes=fresh['preconditions']['input_hashes']
    if not set(fresh_hashes).issubset(original_hashes) or any(original_hashes[k]!=v for k,v in fresh_hashes.items()): raise Error('Dependency closure changed since plan')
    fresh['preconditions']['input_hashes']=original_hashes
    fresh['plan_sha256']=digest({k:v for k,v in fresh.items() if k not in ('native_diagnostics','plan_sha256')})
    if fresh['plan_sha256']!=expected['plan_sha256']: raise Error('Stale native/tool/operation preconditions; re-plan')
    closure=_closure(select(**arguments),expected['operations']); before=closure.snapshot()
    destination=project.new_output(output,closure)
    # Also disallow source operations/plan directories and aliases, including hardlinks.
    extra_paths={Path(k) for k in original_hashes}
    if isinstance(edit_plan,(str,Path)): extra_paths.add(project.absolute(edit_plan))
    for path in extra_paths:
        if path.parent.resolve()==destination or path.parent.resolve() in destination.parents: raise Error('Candidate must be outside every input directory')
    destination.mkdir(exist_ok=False)  # One final, exclusive directory; no renamed staging paths.
    result={'schema_version':1,'status':'failed','source_unchanged':False,'candidate':str(destination),'plan_sha256':expected['plan_sha256'],'commands':[],'errors':[],'accepted':False}
    try:
        board,schematic,_=closure.stage(destination)
        result['path_rebindings']=_rebind(closure,destination)
        _relocatable(destination/'inputs')
        staged={source:destination/'inputs'/source.relative_to(closure.anchor) for source in closure.files}
        immutable={path:native.sha256(path) for source,path in staged.items() if source!=closure.project.board}
        env=isolated_env(destination/'runtime'); cli=executable(kicad_cli)
        baseline,netlist=_checks(cli,board,schematic,destination/'baseline',env,result['commands'],False)
        result['baseline']=baseline
        _check_additions(expected['operations'],netlist)
        document=json.loads(canonical(expected['operations']))
        for op in document['operations']:
            if op['op']=='add_footprint': op['file']=str(staged[Path(op['file'])])
        native_result,log=probe('edit',board,document,python,env); result['commands'].append(log); result['changes']=native_result['changes']
        edited_headers,edited_items=_global_and_items(board)
        original_headers,_=_global_and_items(closure.project.board)
        if original_headers!=edited_headers: raise Error('Native save changed board settings/net declarations/global properties')
        checked,after_netlist=_checks(cli,board,schematic,destination/'checks',env,result['commands'],True)
        result['checks']=checked
        result['restored_materialized_variables']=_restore_materialized_variables(board,edited_headers,board.with_suffix('.kicad_pro'))
        final_headers,final_items=_global_and_items(board)
        if (edited_headers,edited_items)!=(final_headers,final_items): raise Error('Refill/save changed non-fill board geometry/properties')
        if not native.compare_netlists(netlist,after_netlist)['equal']: raise Error('Schematic native XML identities changed')
        # Reload the saved/refilled candidate, even if final findings reject it.
        final_view,log=probe('inspect',board,python=python,env=env); result['commands'].append(log)
        result['finding_delta']={kind:compare_findings(baseline['findings'][kind],checked['findings'][kind]) for kind in ('erc','drc')}
        result['inspection']=final_view
        for path,hash_value in immutable.items():
            if native.sha256(path)!=hash_value: raise Error(f'Candidate dependency modified by native process: {path}')
        _relocatable(destination/'inputs')
        all_findings=checked['findings']['erc']+checked['findings']['drc']
        opens=[v for v in checked['findings']['drc'] if v['severity'] in ('error','warning') and ((v['category']=='unconnected_items' and v['identity']['type']=='unconnected_items') or (v['category']=='violations' and v['identity']['type'] in ('track_dangling','via_dangling')))]
        other=[v for v in all_findings if v not in opens]
        if not checked['parity']['equal'] or other or (opens and not prec['policy']['allow_draft_opens']):
            result['status']='rejected'
        else:
            result['status']='draft' if opens else 'accepted'
            result['accepted']=not opens
        result['board']=str(board.relative_to(destination)); result['schematic']=str(schematic.relative_to(destination))
        result['relocatable']=True
    except Exception as error:
        result['errors'].append(str(error)); result['status']='failed'; result['accepted']=False
    finally:
        try:
            closure.verify_sources(before)
            for name,record in original_hashes.items():
                if native.sha256(name)!=record['sha256']: raise Error(f'Source input changed: {name}')
            result['source_unchanged']=True
        except Exception as error:
            result['errors'].append(str(error)); result['status']='failed'; result['accepted']=False
    save_json(destination/'result.json',result)
    if result['status'] in ('accepted','draft'):
        # Completion marker is exclusive and LAST, after native checks/save/reload/hash checks.
        save_json(destination/'completion.json',{'schema_version':1,'status':result['status'],'accepted':result['accepted'],'board':result['board'],'schematic':result['schematic'],'result_sha256':native.sha256(destination/'result.json')})
    return result
