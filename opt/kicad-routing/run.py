#!/usr/bin/env python3
"""Stdlib facade: read-only doctor, opt-in prepare-runtime, synthetic-only smoke."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import fixture
import runtime
import sandbox
from safety import (GateError, STATE, TOOL, assert_same, checked, digest, require,
                    run_process, safe_path, tree_hashes, write_json)

LIMITATIONS = [
    'Synthetic fixture only; no arbitrary board input or production approval.',
    'KiCad 10.0.6 native SWIG compatibility; binding PROPERTY_ENUM stderr assertions retained.',
    'No proof for arbitrary custom rules, differential pairs, tuning, pad overrides or other stackups.',
    'Native DRC/zone connectivity is not an electrical, return-path, thermal or manufacturing review.',
    'Pinned upstream checksums/metadata are reproducibility checks, not an independent security audit.',
]
DRC_FLAGS = ['pcb','drc','--format','json','--severity-all','--all-track-errors',
             '--schematic-parity','--refill-zones','--save-board','--exit-code-violations']


def doctor():
    """No downloads, Java launches, board loads or output-directory creation."""
    probe = '''import json,sys
import pcbnew as p
names=['LoadBoard','SaveBoard','GetSettingsManager','ExportSpecctraDSN','ImportSpecctraSES','ZONE_FILLER']
print(json.dumps({'python':sys.version,'module':p.__file__,'version':p.GetBuildVersion(),
  'capabilities':{n:callable(getattr(p,n,None)) for n in names},
  'dsn_api':getattr(p,'ExportSpecctraDSN',None).__doc__,
  'ses_api':getattr(p,'ImportSpecctraSES',None).__doc__}))'''
    result = {"operation":"doctor", "architecture":platform.machine(), "system":platform.system(),
              "paths": {n:shutil.which(n) for n in ['python3','kicad-cli','bwrap','java','freerouting']},
              "pins":runtime.PINS, "limitations":LIMITATIONS}
    try:
        rec = subprocess.run(['/usr/bin/python3','-B','-c',probe],capture_output=True,text=True,timeout=15)
        result['binding_stderr'] = rec.stderr
        sys.stderr.write(rec.stderr)
        result['native'] = json.loads(rec.stdout) if rec.returncode == 0 else {"error":rec.returncode}
        for name in ['kicad-cli','bwrap']:
            if result['paths'][name]:
                r = subprocess.run([result['paths'][name],'--version'],capture_output=True,text=True,timeout=10)
                result[name] = {"version":r.stdout.strip(),"returncode":r.returncode,"stderr":r.stderr}
        java,jar,manifest = runtime.validate_runtime()
        result['runtime'] = {"status":"verified-bytes-not-executed", "java":str(java), "jar":str(jar),
                             "notices":len(manifest['notices']), "provenance_sha256":digest(runtime.RUNTIME/'provenance.json')}
    except (GateError,OSError,ValueError,subprocess.TimeoutExpired) as exc:
        result['runtime'] = {"status":"unavailable", "reason":str(exc)}
    return result


def new_run(run_id=None):
    run_id = run_id or ('smoke-'+uuid.uuid4().hex[:12])
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}',run_id), 'invalid run-id (not a path)')
    run = safe_path(STATE/'runs'/run_id)
    run.parent.mkdir(parents=True,exist_ok=True)
    require(not run.exists(), 'existing run/output overwrite refused')
    run.mkdir(mode=0o700)
    return run


def drc_gate(report, before=False, initial=None):
    require(report.get('$schema') == 'https://schemas.kicad.org/drc.v1.json', 'unsupported DRC report schema')
    for key in ['violations','schematic_parity','unconnected_items','ignored_checks','included_severities']:
        require(isinstance(report.get(key),list), 'incomplete DRC report: '+key)
    require(set(report['included_severities']) == {'error','warning','exclusion'}, 'DRC did not include every severity/exclusion')
    require(not report['violations'] and not report['schematic_parity'], 'native DRC/parity findings block acceptance')
    if before:
        expect = sorted([sorted([fixture.uid('J1pad2'),fixture.uid('J2pad3')]),
                         sorted([fixture.uid('J1pad3'),fixture.uid('J2pad2')])])
        actual = sorted(sorted(x['uuid'] for x in item['items']) for item in report['unconnected_items'])
        require(actual == expect and all(x['type']=='unconnected_items' and x['severity']=='error'
                 for x in report['unconnected_items']), 'initial opens do not match planned ordinary nets')
    else:
        require(not report['unconnected_items'], 'unrouted candidate rejected')
        require(initial is not None and report['ignored_checks'] == initial['ignored_checks'], 'DRC ignored checks changed')
    return {"violations":len(report['violations']), "parity":len(report['schematic_parity']),
            "opens":len(report['unconnected_items']), "ignored_checks":report['ignored_checks']}


def schematic_nodes(path, invariants):
    root = ET.parse(path).getroot()
    actual = sorted([node.attrib['ref'],node.attrib['pin'],net.attrib['name']]
                    for net in root.findall('./nets/net') for node in net.findall('node'))
    expected = sorted([fp['ref'],pad['number'],pad['net']]
                     for fp in invariants['footprints_pads_nets'] for pad in fp['pads'])
    require(actual == expected, 'native schematic netlist/physical pad parity mismatch')
    return actual


def smoke(run_id=None, route_timeout=120):
    require(1 <= route_timeout <= 120, 'route-timeout must be 1..120 seconds')
    run = new_run(run_id)
    start = time.monotonic()
    report = {"schema":1,"operation":"synthetic-smoke", "status":"failed", "run_directory":str(run),
              "fixture":fixture.IDENTITY,"production_ready":False,"limitations":LIMITATIONS,
              "budget":{"total_seconds":240,"routing_timeout_seconds":route_timeout,
                        "max_passes":10,"java_heap_mb":512,"processors":2,"log_bytes_per_stream":4194304},
              "commands":[], "tool_hashes":{}, "invariant_deltas":None}
    source_hashes = None
    for name in ['native-home','native-tmp','native-xdg']:
        (run/name).mkdir()
    env = {"PATH":"/usr/bin", "LANG":"C.UTF-8", "HOME":str(run/'native-home'),
           "XDG_CONFIG_HOME":str(run/'native-xdg'),"XDG_CACHE_HOME":str(run/'native-xdg'),
           "XDG_DATA_HOME":str(run/'native-xdg'),"TMPDIR":str(run/'native-tmp'),
           "PYTHONDONTWRITEBYTECODE":"1"}

    def remaining(requested):
        seconds = 240 - (time.monotonic()-start)
        require(seconds > 0, 'total smoke time budget exceeded')
        return min(requested, seconds)

    def process(argv,name,timeout=30,accepted=(0,)):
        rec = run_process(argv,run/'logs',name,remaining(timeout),env=env)
        report['commands'].append(rec)
        if name.startswith('native-'):
            stderr = (run/'logs'/f'{name}.stderr.log').read_text(errors='replace')
            sys.stderr.write(stderr)  # assertions are visible AND retained verbatim
        checked(rec,accepted)
        return rec

    def native(action):
        return process(['/usr/bin/python3','-B','-X','faulthandler',str(TOOL/'pcbnew_adapter.py'),action,str(run)],
                       'native-'+action)

    try:
        java,jar,provenance = runtime.validate_runtime()  # offline; never acquire here
        report['runtime'] = {"pins":runtime.PINS,"provenance_sha256":digest(runtime.RUNTIME/'provenance.json'),
                             "metadata":provenance['metadata'],"downloads":provenance['downloads'],
                             "notice_files":len(provenance['notices'])}
        for name in ['run.py','runtime.py','sandbox.py','fixture.py','pcbnew_adapter.py','safety.py']:
            report['tool_hashes'][name] = digest(TOOL/name)
        for name in ['/usr/bin/python3','/usr/bin/kicad-cli','/usr/bin/bwrap']:
            require(Path(name).is_file(), 'installed tool missing: '+name)
            report['tool_hashes'][name] = digest(name)
        native('create')
        source_hashes = tree_hashes(run/'source')
        report['source_hashes'] = source_hashes
        native('snapshot-source')
        source = json.loads((run/'source-invariants.json').read_text())
        shutil.copytree(run/'source',safe_path(run/'before'))
        drc_file = run/'before-drc.json'
        process(['/usr/bin/kicad-cli']+DRC_FLAGS+['-o',str(drc_file),str(run/'before/synthetic.kicad_pcb')],
                'drc-before',60,(0,5))
        before_drc = json.loads(drc_file.read_text())
        report['before_drc'] = before_drc  # retain all findings even when gate rejects
        report['before_drc_counts'] = drc_gate(before_drc,True)
        native('snapshot-before')
        before = json.loads((run/'before-invariants.json').read_text())
        assert_same(source,before)
        process(['/usr/bin/kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(run/'schematic-nets.xml'),
                 str(run/'before/synthetic.kicad_sch')],'schematic-netlist')
        report['schematic_nodes'] = schematic_nodes(run/'schematic-nets.xml',before)
        native('export')
        export = json.loads((run/'export.json').read_text())
        dsn = run/('input-'+run.name+'.dsn')
        association = {**export,"session_design":dsn.stem,"pcb_sha256":digest(run/'before/synthetic.kicad_pcb'),
                       "source_hashes":source_hashes,"companions":before['companions']}
        report['export'] = export
        report['sandbox'],rec = sandbox.setup(run,remaining(15))
        report['commands'].append(rec)
        report['commands'].append(sandbox.preflight(run,java,jar,remaining(30)))
        # Pin exported snapshot BEFORE job, and recheck it AFTER the sandbox.
        require(digest(dsn)==association['dsn_sha256'], 'DSN changed before routing')
        rec,router_result = sandbox.route(run,java,jar,remaining(route_timeout))
        report['commands'].append(rec)
        report['freerouting_result'] = router_result
        association['ses_sha256'] = digest(safe_path(run/'result.ses'))
        write_json(run/'association.json',association,exclusive=True)
        assert_same(source_hashes,tree_hashes(run/'source'))
        # Copy same-stem project/rules/library/schematic, not router-owned planes.
        (run/'after').mkdir()
        for path in (run/'before').iterdir():
            require(not path.is_symlink(), 'before symlink rejected')
            if path.name != 'synthetic.kicad_pcb':
                if path.is_dir():
                    shutil.copytree(path,run/'after'/path.name)
                else:
                    shutil.copy2(path,run/'after'/path.name)
        native('import')
        after_drc_file = run/'after-drc.json'
        process(['/usr/bin/kicad-cli']+DRC_FLAGS+['-o',str(after_drc_file),str(run/'after/synthetic.kicad_pcb')],
                'drc-after',60,(0,5))
        after_drc = json.loads(after_drc_file.read_text())
        report['after_drc'] = after_drc
        report['after_drc_counts'] = drc_gate(after_drc,False,before_drc)
        native('snapshot-after')  # saved/CLI-refilled disk state, not transient memory
        after = json.loads((run/'after-invariants.json').read_text())
        differences = sorted(key for key in before if before[key] != after.get(key))
        report['invariant_deltas'] = differences
        assert_same(before,after)
        report['metrics'] = {side:json.loads((run/(side+'-metrics.json')).read_text()) for side in ['before','after']}
        report['association'] = association
        report['status'] = 'passed'
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        if source_hashes is not None:
            try:
                report['source_immutable'] = tree_hashes(run/'source') == source_hashes
                require(report['source_immutable'], 'source fixture changed')
            except Exception as exc:
                report.update(status='failed',error=str(exc),source_immutable=False)
        report['duration_seconds'] = round(time.monotonic()-start,3)
        # Include failed sandbox subprocesses too (they may raise before returning).
        report['process_evidence'] = [str(p.relative_to(run)) for p in sorted((run/'logs').glob('*.process.json'))]
        report['artifact_hashes'] = {str(p.relative_to(run)):digest(p) for p in run.rglob('*')
            if p.is_file() and not p.is_symlink() and p.suffix in ['.dsn','.ses','.kicad_pcb','.kicad_pro','.kicad_dru','.kicad_sch','.xml','.json']}
        write_json(run/'run.json',report,exclusive=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Read-only capabilities and pinned byte checks; no execution/download')
    prep = sub.add_parser('prepare-runtime',help='Explicit trusted pinned downloads; never executes Java')
    prep.add_argument('--allow-downloads',action='store_true',help='Required explicit network opt-in')
    smoke_parser = sub.add_parser('smoke',help='Offline synthetic-only native DSN/SES + saved-board DRC; NO board input')
    smoke_parser.add_argument('--run-id',help='New evidence directory label (not a path); never reuse an existing label')
    smoke_parser.add_argument('--route-timeout',type=int,default=120,help='Java job deadline seconds (1..120), default 120; max 10 passes')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            result = doctor()
        elif args.command == 'prepare-runtime':
            data = runtime.prepare(args.allow_downloads)
            result = {'status':data['status'],'directory':str(runtime.RUNTIME), 'pins':runtime.PINS,
                      'downloads':data['downloads'],'notice_files':len(data['notices']),'execution':'NONE'}
        else:
            data = smoke(args.run_id,args.route_timeout)
            result = {key:data.get(key) for key in ['status','error','run_directory','duration_seconds',
                'source_immutable','before_drc_counts','after_drc_counts','invariant_deltas','metrics','production_ready']}
        print(json.dumps(result,indent=2,sort_keys=True))
        return 1 if result.get('status') == 'failed' else 0
    except (GateError,OSError,ValueError) as exc:
        print(json.dumps({'status':'failed','error':f'{type(exc).__name__}: {exc}'}),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
