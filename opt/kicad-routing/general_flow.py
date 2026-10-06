"""Bounded standalone project candidate flow; stdout-only inspection/planning."""
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import runtime
import sandbox
from general_native import compare
from project_contract import (ProjectError, admit, context_hashes, drc_base, gate, object_digest,
                              no_links, open_pairs, plan_for, read_text, snapshot_manifest, strict_json, validate_plan)
from safety import TOOL, checked, digest, run_process, tree_hashes, write_json

DRC_FLAGS = ['pcb','drc','--format','json','--severity-all','--all-track-errors',
             '--schematic-parity','--exit-code-violations']
LIMITATIONS = ['Bounded two-layer scalar subset only; not all-board support.',
               'No auto-placement algorithm; placements must already be supplied and are invariant.',
               'Native push/shove/critical tuning remain GUI operations.',
               'Authorization is an invariant boundary, not Freerouting selected-net CLI support.',
               'No electrical/manufacturing/release approval.']


def readonly_command(root, argv, project_dir=None):
    """No writable host mount or scratch filesystem; outputs are pipes only."""
    gate(Path('/usr/bin/bwrap').is_file(), 'SANDBOX_MISSING', 'Bubblewrap required even for read-only native planning.')
    working_dir = no_links(root if project_dir is None else project_dir)
    gate(working_dir.is_dir() and working_dir.is_relative_to(root), 'LIBRARY_MISSING',
         'Native working directory must remain inside the snapshot.')
    args=['/usr/bin/bwrap','--die-with-parent','--new-session','--unshare-net','--unshare-pid',
          '--unshare-ipc','--unshare-uts','--cap-drop','ALL','--ro-bind','/usr','/usr']
    for name in ['/lib','/lib64']:
        if Path(name).exists(): args+=['--ro-bind',name,name]
    args+=['--dir','/etc']
    if Path('/etc/ld.so.cache').exists(): args+=['--ro-bind','/etc/ld.so.cache','/etc/ld.so.cache']
    for path in ['/etc/fonts','/var/cache/fontconfig']:
        if Path(path).exists(): args+=['--ro-bind',path,path]
    for path in ['/home/.config/kicad/10.0/colors','/home/.cache','/home/.local/share/kicad/10.0','/tmp/org.kicad.kicad/instances']:
        args+=['--dir',path]
    for name in ['plugins','scripting','template','projects','symbols','footprints','3dmodels','3rdparty']:
        args+=['--dir','/home/.local/share/kicad/10.0/'+name]
    args+=['--dir','/home/.cache/kicad/10.0']
    args+=['--ro-bind',str(TOOL),str(TOOL),'--ro-bind',str(root),str(root),
           '--proc','/proc','--dev','/dev','--remount-ro','/proc',
           '--clearenv','--setenv','PATH','/usr/bin','--setenv','HOME','/home',
           '--setenv','TMPDIR','/tmp','--setenv','LANG','C.UTF-8','--setenv','PYTHONDONTWRITEBYTECODE','1',
           '--chdir',str(working_dir),'--remount-ro','/','--']
    return args+list(map(str,argv))


def capture(argv, timeout=60):
    """Bounded pipe capture, no logs/output/temp files on the read-only path."""
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    p=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       start_new_session=True,preexec_fn=limits)
    sel=selectors.DefaultSelector(); parts={'stdout':bytearray(),'stderr':bytearray()}
    for name in parts: sel.register(getattr(p,name),selectors.EVENT_READ,name)
    end=time.monotonic()+timeout; error=None
    try:
        while sel.get_map():
            if time.monotonic()>end: error='PROCESS_TIMEOUT'; break
            for key,_ in sel.select(0.1):
                block=os.read(key.fileobj.fileno(),65536)
                if not block: sel.unregister(key.fileobj); continue
                parts[key.data].extend(block)
                if len(parts[key.data])>4*1024*1024: error='PROCESS_OUTPUT_LIMIT'; break
            if error: break
        if error: os.killpg(p.pid,signal.SIGKILL)
        try: p.wait(timeout=max(0.1,end-time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL); p.wait(); error='PROCESS_TIMEOUT'
    finally:
        sel.close(); p.stdout.close(); p.stderr.close()
    stderr=parts['stderr'].decode('utf8',errors='replace'); sys.stderr.write(stderr)
    gate(not error,error or 'PROCESS_FAILURE','Read-only native process exceeded its budget.')
    return p.returncode,parts['stdout'].decode('utf8'),stderr


def native_args(action, root, rel, payload):
    return ['/usr/bin/python3','-B','-X','faulthandler',str(TOOL/'general_native.py'),
            action,str(root),rel,json.dumps(payload,separators=(',',':'))]


def decode_native(code, text):
    try: result=strict_json(text)
    except (ValueError,UnicodeError):
        gate(False,'NATIVE_OUTPUT','Native worker produced no structured result; inspect retained stderr.')
    if result.get('status')=='failed':
        error=result['error']; raise ProjectError(error['code'],error['message'],error['hint'])
    gate(code==0,'NATIVE_PROCESS','Native worker failed.')
    return result


def inspect_project(snapshot, rel, authorized):
    root=Path(os.path.abspath(snapshot)); admission=admit(root,rel)
    c,t,_=capture(readonly_command(root,native_args('inspect',root,rel,{'authorized':authorized}),(root/rel).parent))
    info=decode_native(c,t)
    c,t,_=capture(readonly_command(root,['/usr/bin/kicad-cli']+DRC_FLAGS+['-o','/dev/stdout',str(root/rel)],(root/rel).parent))
    gate(c in (0,5) and '{' in t, 'DRC_PROCESS', 'Read-only DRC failed or produced no JSON.')
    blob=t[t.index('{'):]
    _,end=json.JSONDecoder().raw_decode(blob)
    gate(blob[end:].strip()=='Saved DRC Report to /dev/stdout','DRC_OUTPUT','Unexpected native DRC pipe trailer.')
    drc=strict_json(blob[:end])
    drc_base(drc)
    # Native CLI already checks parity; XML adds exact physical-pad node evidence on apply.
    gate(snapshot_manifest(root,rel)[1]==admission['files'], 'SOURCE_CHANGED','Source changed during inspection.')
    return admission,info,drc


def plan_project(snapshot, rel, authorized):
    admission,info,drc=inspect_project(snapshot,rel,authorized)
    return plan_for(admission,info,drc,rel,authorized)


def preflight_plan(snapshot, rel, plan):
    gate(type(plan) is dict and isinstance(plan.get('authorized_reroute_nets'),list),
         'PLAN_SCHEMA','Plan must contain explicit reroute-net authorization.')
    admission,info,drc=inspect_project(snapshot,rel,plan['authorized_reroute_nets'])
    expected=plan_for(admission,info,drc,rel,plan['authorized_reroute_nets'])
    validate_plan(plan,expected)
    return admission,info,drc


def route_project(snapshot, rel, plan_path, run_id, route_timeout=120, apply=False):
    gate(type(route_timeout) is int and 1<=route_timeout<=120,'ROUTE_TIMEOUT','Routing timeout must be 1..120 seconds.')
    gate(isinstance(run_id,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}',run_id), 'RUN_ID','Run ID must be a new non-path label.')
    root=Path(os.path.abspath(snapshot)); plan_file=Path(os.path.abspath(plan_path))
    gate(not plan_file.is_relative_to(root),'PLAN_SOURCE_ALIAS','Approval plan must be outside the immutable snapshot.')
    plan=strict_json(read_text(plan_file)); raw_plan_hash=digest(plan_file)
    admission,source_info,inspection_drc=preflight_plan(root,rel,plan)
    if not apply:
        return {'operation':'route-project','status':'dry-run','writes':False,'plan_sha256':object_digest(plan),
                'approval_required':'Re-run with --apply and the reviewed --plan file.', 'plan':plan}
    # Validate runtime offline BEFORE creating a run. No prepare or fallback here.
    java,jar,provenance=runtime.validate_runtime()
    from run import new_run
    run=new_run(run_id); start=time.monotonic()
    report={'schema':'bread-local-route-run/v1','operation':'route-project','status':'failed',
            'run_directory':str(run),'session_id':run.name,'session_nonce':uuid.uuid4().hex,
            'plan_sha256':object_digest(plan),'plan_file_sha256':raw_plan_hash,
            'source_digest':admission['source_digest'],'context_digest':admission['context_digest'],
            'source_hashes':admission['files'],'commands':[], 'limitations':LIMITATIONS,
            'manufacturing_status':'NOT_ASSESSED', 'inspection_drc':inspection_drc,
            'budget':{'total_seconds':240,'route_timeout':route_timeout,'max_passes':10,'java_heap_mb':512}}
    for name in ['native-home','native-xdg','native-tmp']: (run/name).mkdir()
    env={'PATH':'/usr/bin','LANG':'C.UTF-8','HOME':str(run/'native-home'),
         'XDG_CONFIG_HOME':str(run/'native-xdg'),'XDG_DATA_HOME':str(run/'native-xdg'),
         'XDG_CACHE_HOME':str(run/'native-xdg'),'TMPDIR':str(run/'native-tmp'), 'PYTHONDONTWRITEBYTECODE':'1'}
    def remaining(seconds):
        available=240-(time.monotonic()-start)
        gate(available>0,'TOTAL_TIMEOUT','Project routing stage budget exceeded.')
        return min(seconds,available)
    def process(argv,name,timeout=30,accepted=(0,),cwd=None):
        if cwd is not None:
            gate(Path(cwd).is_relative_to(run), 'LIBRARY_MISSING', 'Native candidate working directory must be run-local.')
        rec=run_process(argv,run/'logs',name,remaining(timeout),env=env,cwd=cwd)
        report['commands'].append(rec)
        if name.startswith('native-'): sys.stderr.write((run/'logs'/f'{name}.stderr.log').read_text(errors='replace'))
        if name.startswith('native-') and not rec['failure'] and rec['returncode']!=0:
            decode_native(rec['returncode'],(run/'logs'/f'{name}.stdout.log').read_text())
        checked(rec,accepted)
        return (run/'logs'/f'{name}.stdout.log').read_text()
    def native(action,side,payload,name=None):
        text=process(native_args(action,run/side,rel,payload),name or 'native-'+action,
                     cwd=(run/side/rel).parent)
        return decode_native(0,text)
    def info(side):
        value=native('inspect',side,{'authorized':plan['authorized_reroute_nets']},'native-inspect-'+side)
        write_json(run/(side+'-invariants.json'),value['invariants'],exclusive=True)
        write_json(run/(side+'-copper.json'),value['copper'],exclusive=True)
        write_json(run/(side+'-metrics.json'),value['metrics'],exclusive=True)
        return value
    try:
        gate(digest(plan_file)==raw_plan_hash,'PLAN_CHANGED','Approval file changed during preflight.')
        write_json(run/'approved-plan.json',plan,exclusive=True)
        write_json(run/'source-invariants.json',source_info['invariants'],exclusive=True)
        report['runtime']={'pins':runtime.PINS,'provenance_sha256':digest(runtime.RUNTIME/'provenance.json'),
                           'metadata':provenance['metadata'],'notice_files':len(provenance['notices'])}
        report['tool_hashes']={n:digest(TOOL/n) for n in ['run.py','general_flow.py','general_native.py',
                         'project_contract.py','safety.py','sandbox.py','runtime.py','pcbnew_adapter.py']}
        shutil.copytree(root,run/'source'); shutil.copytree(run/'source',run/'before')
        gate(tree_hashes(run/'source')==admission['files'], 'SOURCE_CHANGED','Source changed while being frozen.')
        before_drc_path=run/'before-drc.json'
        process(['/usr/bin/kicad-cli']+DRC_FLAGS+['--refill-zones','--save-board','-o',str(before_drc_path),str(run/'before'/rel)],
                'drc-before',60,(0,5),cwd=(run/'before'/rel).parent)
        before_drc=strict_json(read_text(before_drc_path)); report['before_drc']=before_drc
        before=info('before')
        compare(source_info['invariants'],before['invariants'])
        pairs=open_pairs(before_drc,before['item_nets'],plan['authorized_reroute_nets'])
        gate(pairs==plan['baseline_open_pairs'] and before_drc['ignored_checks']==plan['ignored_checks'],
             'BASELINE_CHANGED','Refilled/saved native baseline differs from explicitly planned opens/ignored checks.')
        report['before_counts']={k:len(before_drc[k]) for k in ['violations','schematic_parity','unconnected_items']}
        xml=run/'schematic-nets.xml'
        process(['/usr/bin/kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(run/'before'/Path(rel).with_suffix('.kicad_sch'))], 'schematic-netlist',cwd=(run/'before'/rel).parent)
        from run import schematic_nodes
        report['schematic_nodes']=schematic_nodes(xml,before['invariants'])
        dsn=run/('input-'+run.name+'.dsn')
        exported=native('export','before',{'dsn':str(dsn),'plan':plan,'admission':admission})
        report['export']=exported; write_json(run/'export.json',exported,exclusive=True)
        frozen_before=tree_hashes(run/'before')
        association={**exported,'session_design':dsn.stem,'session_id':run.name,
                     'session_nonce':report['session_nonce'], 'plan_sha256':object_digest(plan),
                     'plan_file_sha256':raw_plan_hash,'pcb':rel,'pcb_sha256':digest(run/'before'/rel),
                     'source_digest':admission['source_digest'],'source_hashes':admission['files'],
                     'context_digest':admission['context_digest'],'context_hashes':context_hashes(frozen_before,rel)}
        settings={**sandbox.SETTINGS,'router.copperToEdgeClearanceUm':round(admission['rules']['edge_clearance']*1000)}
        report['sandbox'],rec=sandbox.setup(run,remaining(15),settings); report['commands'].append(rec)
        report['commands'].append(sandbox.preflight(run,java,jar,remaining(30),settings))
        gate(digest(dsn)==exported['dsn_sha256'],'DSN_CHANGED','DSN changed before routing.')
        rec,result=sandbox.route(run,java,jar,remaining(route_timeout),settings)
        report['commands'].append(rec); report['freerouting_result']=result
        association['ses_sha256']=digest(run/'result.ses')
        write_json(run/'association.json',association,exclusive=True)
        gate(tree_hashes(run/'before')==frozen_before,'SESSION_STALE','Exported project context changed during routing.')
        gate(tree_hashes(run/'source')==admission['files'] and snapshot_manifest(root,rel)[1]==admission['files'],
             'SOURCE_CHANGED','Source snapshot changed during routing.')
        gate(digest(plan_file)==raw_plan_hash,'PLAN_CHANGED','Approval file changed during routing.')
        shutil.copytree(run/'before',run/'after',ignore=shutil.ignore_patterns(Path(rel).name))
        candidate=run/'after'/rel
        native('import','before',{'dsn':str(dsn),'ses':str(run/'result.ses'),'candidate':str(candidate),
                                 'plan':plan,'association':association,'source_hashes':admission['files']})
        after_drc_path=run/'after-drc.json'
        process(['/usr/bin/kicad-cli']+DRC_FLAGS+['--refill-zones','--save-board','-o',str(after_drc_path),str(candidate)],
                'drc-after',60,(0,5),cwd=candidate.parent)
        after_drc=strict_json(read_text(after_drc_path)); report['after_drc']=after_drc
        drc_base(after_drc)
        gate(not after_drc['unconnected_items'],'CANDIDATE_OPEN','Candidate still has native opens.')
        gate(after_drc['ignored_checks']==before_drc['ignored_checks'],'IGNORED_CHANGED','Native ignored checks changed.')
        after=info('after')
        report['invariant_deltas']=compare(before['invariants'],after['invariants'])
        gate(context_hashes(tree_hashes(run/'after'),rel)==association['context_hashes'],
             'CONTEXT_CHANGED','Saved project/rules/local libraries changed.')
        report['after_counts']={k:len(after_drc[k]) for k in ['violations','schematic_parity','unconnected_items']}
        report.update(status='passed',candidate=str(candidate),association=association,
                      metrics={'before':before['metrics'],'after':after['metrics']})
    except Exception as exc:
        report['error']=exc.record() if isinstance(exc,ProjectError) else {
            'code':'PROCESS_TIMEOUT' if 'timeout' in str(exc).lower() else 'ROUTE_FAILED',
            'message':f'{type(exc).__name__}: {exc}','hint':'Inspect this unique run\'s retained logs; no automatic retry.'}
    finally:
        try:
            report['source_immutable']=snapshot_manifest(root,rel)[1]==admission['files'] and (
                not (run/'source').exists() or tree_hashes(run/'source')==admission['files'])
            if not report['source_immutable']: report.update(status='failed',error={'code':'SOURCE_CHANGED','message':'Source changed.'})
        except Exception as exc: report.update(status='failed',source_immutable=False,error={'code':'SOURCE_CHECK','message':str(exc)})
        report['duration_seconds']=round(time.monotonic()-start,3)
        report['artifact_hashes']={str(p.relative_to(run)):digest(p) for p in sorted(run.rglob('*')) if p.is_file() and not p.is_symlink()}
        write_json(run/'run.json',report,exclusive=True)
    return report
