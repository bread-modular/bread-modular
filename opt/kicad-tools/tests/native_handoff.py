#!/usr/bin/env python3
"""Explicit synthetic-only real facade edit→route and schematic CLI regressions.

Requires installed matching KiCad/pcbnew and an already explicitly prepared
pinned router runtime. Never downloads or loads a released design. Not discovered
by unittest: invoke with a NEW --run-id. Retains full command logs and hashes.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

TOOLS = Path(__file__).resolve().parents[1]
ROUTER = TOOLS.parent / 'kicad-routing'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def save(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True, help='NEW unique [a-z0-9-] ID, max 21 characters')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,20}', args.run_id):
        parser.error('invalid run ID')
    require((ROUTER/'run.py').is_file(), 'optional routing sibling unavailable')
    root = TOOLS/'integration.tmp'/args.run_id
    root.mkdir(parents=True, exist_ok=False)
    cwd = root/'Unrelated working directory with spaces'; cwd.mkdir()
    requests = root/'Requests'; requests.mkdir()
    plans = root/'Plans'; plans.mkdir()
    candidates = root/'Candidates'; candidates.mkdir()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', NO_COLOR='1')
    env.pop('PYTHONPATH', None)
    records = []
    summary = {'schema_version':1, 'synthetic_only':True, 'passed':False, 'commands':records}

    def run(script, *arguments, expected=0):
        command = [sys.executable, '-B', str(script), *map(str, arguments)]
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=240)
        logs = {}
        for name, text in (('stdout', result.stdout), ('stderr', result.stderr)):
            path = root/f'command-{len(records)+1}.{name}.log'; path.write_text(text)
            logs[name] = {'file':path.name, 'sha256':digest(path)}
        records.append({'command':command, 'cwd':str(cwd), 'returncode':result.returncode, 'logs':logs})
        require(result.returncode == expected, f'{command}: expected {expected}, got {result.returncode}\n{result.stdout}\n{result.stderr}')
        return result

    def facade(*arguments, expected=0):
        return json.loads(run(TOOLS/'kicad_tools.py', *arguments, expected=expected).stdout)

    try:
        source = root/'Independent routing source'/'Bench A'
        run(ROUTER/'tests/project_fixture.py', source)
        original = hashes(source)
        inspected = facade('pcb', 'inspect', '--project-dir', source)
        footprints = [r for r in inspected['items'] if r['kind']=='footprint']
        require(len(footprints)==4, 'independent generator footprint inventory')
        require(next(r['at'] for r in footprints if r['reference']=='J2')==[34.0,10.0], 'original J2 position')
        ops = {'schema_version':1, 'operations':[
            {'op':'move_footprint', 'target':{'ref':'J2'}, 'at':[33,11]},
            {'op':'add_text', 'uuid':str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://example.invalid/facade-handoff-text')),
             'text':'Facade placement candidate', 'layer':'User.Comments', 'at':[20,28],
             'rotation_deg':0, 'size_mm':1, 'thickness_mm':0.15}
        ]}
        ops_file = requests/'pcb-ops.json'; save(ops_file, ops)
        edit = facade('pcb', 'plan', '--project-dir', source, '--ops', ops_file, '--allow-draft-opens')
        require(hashes(source)==original, 'plan changed original source')
        edit_file = plans/'pcb-edit.json'; save(edit_file, edit)
        candidate = candidates/'NEW placement candidate'
        applied = facade('pcb', 'apply', '--plan', edit_file, '--output', candidate, expected=1)
        require(applied['status']=='draft' and not applied['accepted'], 'opens-only placement draft required')
        require(applied['source_unchanged'] and not applied['errors'], 'PCB source immutable; no hidden errors')
        completion = json.loads((candidate/'completion.json').read_text())
        require(completion['status']=='draft' and not completion['accepted'], 'real draft completion marker')
        require(completion['result_sha256']==digest(candidate/'result.json'), 'completion binds result')
        require(applied['checks']['parity']['equal'], 'PCB native ref/pin/net parity')
        require(not applied['checks']['findings']['erc'], 'generated fixture must be ERC-clean without waivers')
        require(next(r['at'] for r in applied['inspection']['items'] if r['kind']=='footprint' and r['reference']=='J2')==[33.0,11.0], 'real facade move did not apply')
        require(any(r.get('text')=='Facade placement candidate' for r in applied['inspection']['items']), 'real text edit did not apply')
        old_tracks = [r for r in inspected['items'] if r['kind'] in ('track','via')]
        new_tracks = [r for r in applied['inspection']['items'] if r['kind'] in ('track','via')]
        require(old_tracks==new_tracks, 'footprint move must not drag or change existing copper')
        board = Path(completion['board'])
        require(board.parts[0]=='inputs', 'completed board belongs to inputs subtree')
        snapshot = candidate/'inputs'; relative_pcb = Path(*board.parts[1:]).as_posix()
        snapshot_before = hashes(snapshot)
        facade('route', 'inspect-project', '--snapshot', snapshot, '--pcb', relative_pcb)
        route_plan = facade('route', 'plan-project', '--snapshot', snapshot, '--pcb', relative_pcb, '--reroute-net', 'DATA')
        require(hashes(snapshot)==snapshot_before, 'routing plan changed completed input subtree')
        route_file = plans/'route-plan.json'; save(route_file, route_plan)
        facade('route', 'route-project', '--snapshot', snapshot, '--pcb', relative_pcb,
               '--plan', route_file, '--run-id', args.run_id, '--dry-run')
        routed = facade('route', 'route-project', '--snapshot', snapshot, '--pcb', relative_pcb,
                       '--plan', route_file, '--run-id', args.run_id, '--route-timeout', '120', '--apply')
        require(routed['status']=='passed', 'routing apply failed')
        run_dir = ROUTER/'work.tmp/runs'/args.run_id
        report = json.loads((run_dir/'run.json').read_text())
        require(report['source_immutable'] and report['invariant_deltas']==[], 'routing source/placement/settings invariant violation')
        require(report['after_counts']=={'schematic_parity':0,'unconnected_items':0,'violations':0}, 'final DRC/parity/opens not zero')
        require(report['metrics']['after']['via_count']>=1, 'opposite-side fixture requires real routed via')
        before = json.loads((run_dir/'before-copper.json').read_text())
        after = json.loads((run_dir/'after-copper.json').read_text())
        protected = lambda rows: [r for r in rows if r['net']!='DATA' or r['locked']]
        require(protected(before)==protected(after), 'locked/non-authorized copper changed')
        require(any(r['locked'] for r in protected(before)) and any(not r['locked'] for r in protected(before)), 'fixture protects locked and unlocked non-authorized copper')
        require(any(r['kind']=='PCB_VIA' and r['net']=='DATA' for r in after), 'no real DATA via after SES import')
        require(hashes(source)==original and hashes(snapshot)==snapshot_before, 'original or handoff source changed')
        summary['pcb_route'] = {'draft_exit':1, 'authorized_nets':['DATA'], 'source_immutable':True,
            'move_did_not_drag_copper':True, 'protected_copper_unchanged':True,
            'invariant_deltas':report['invariant_deltas'], 'after_counts':report['after_counts'],
            'via_count':report['metrics']['after']['via_count'], 'source_hashes':original,
            'snapshot_hashes':snapshot_before, 'run_report_sha256':digest(run_dir/'run.json'),
            'no_hand_edits':True, 'route_plan_sha256':digest(route_file)}

        # Separate flat-sheet fixture; an unrelated PCB sentinel must be ignored.
        generated = run(TOOLS/'schematic/tests/synthetic.py', '--output-dir', root/'Separate schematic source')
        sheet = Path(generated.stdout.strip())
        sentinel = sheet.with_suffix('.kicad_pcb'); sentinel.write_text('Unrelated PCB sentinel: never load, copy or synchronize.\n')
        sheet_original = hashes(sheet.parent)
        facade('schematic', 'inspect', '--input', sheet)
        edits = {'schema_version':1, 'grid_mm':1.27,
                 'edits':[{'op':'add_wire','points':[[15.24,25.4],[35.56,25.4]]}]}
        edits_file = requests/'schematic-edits.json'; save(edits_file, edits)
        sheet_output = candidates/'NEW schematic draft'
        sheet_plan = facade('schematic', 'plan', '--input', sheet, '--edits', edits_file, '--output-dir', sheet_output)
        sheet_plan_file = plans/'schematic-plan.json'; save(sheet_plan_file, sheet_plan)
        changed = facade('schematic', 'apply', '--plan', sheet_plan_file, expected=1)
        require(changed['status']=='draft_erc_findings' and not changed['accepted'], 'schematic status not honest draft')
        require(changed['native_force_save_reload_verified'] and changed['source_unchanged'], 'schematic native/source gate failed')
        require(changed['connectivity_delta']['changed_pins'], 'wire edit did not change actual pin/net membership')
        require(hashes(sheet.parent)==sheet_original and not list(sheet_output.rglob('*.kicad_pcb')), 'silent PCB synchronization/copy or source mutation')
        # Both real APIs imported from this source/copy, in a fresh unrelated-cwd process.
        code = ('import sys,json; sys.path.insert(0,sys.argv[1]); '
                'from automation import inspect; from schematic import inspect_sheet; '
                'a=inspect(project_dir=sys.argv[2]); b=inspect_sheet(sys.argv[3]); '
                'print(json.dumps({"footprints":sum(r["kind"]=="footprint" for r in a["items"]),"symbols":len(b["symbols"])}))')
        api = json.loads(run('-c', code, TOOLS, source, sheet).stdout)
        require(api=={'footprints':4,'symbols':5}, 'independent Python APIs failed')
        summary['schematic'] = {'status':changed['status'], 'accepted':False, 'native_force_save_reload_verified':True,
            'source_immutable':True, 'pcb_synchronized':False, 'changed_pins':changed['connectivity_delta']['changed_pins'],
            'source_hashes':sheet_original, 'result_sha256':digest(sheet_output/'result.json')}
        summary['python_api'] = api
        summary['passed'] = True
    except Exception as error:
        summary['error'] = str(error)
    save(root/'summary.json', summary)
    print(json.dumps({'passed':summary['passed'], 'summary':str(root/'summary.json'),
                      'error':summary.get('error')}, indent=2))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
