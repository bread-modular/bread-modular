#!/usr/bin/env python3
"""Explicit installed-native + pinned offline runtime regressions; never downloads."""
import sys
sys.dont_write_bytecode=True
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).absolute().parents[1]))
import general_flow as flow
from project_contract import object_digest
from safety import STATE, TOOL, digest, sexpr, child, children, tree_hashes, write_json
from project_fixture import NAME, uid

PREFIX=''; ROOT=None; RECORDS=[]


def cmd(args, expected=0):
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    c=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=240,preexec_fn=limits,
                     env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','NO_COLOR':'1'})
    number=len(RECORDS)+1
    paths={}
    for name,text in [('stdout',c.stdout),('stderr',c.stderr)]:
        p=ROOT/f'command-{number}.{name}.log'; p.write_text(text)
        paths[name]={'file':p.name,'sha256':digest(p)}
    RECORDS.append({'command':list(map(str,args)),'exit_code':c.returncode,'logs':paths})
    if c.returncode!=expected:
        raise AssertionError(f'expected {expected}, got {c.returncode}: {c.stdout}\n{c.stderr}')
    return c


def cli(*args, expected=0):
    return cmd(['/usr/bin/python3','-B',TOOL/'run.py',*args],expected)


def structured(c):
    return json.loads(c.stdout if c.stdout.strip() else c.stderr.strip().splitlines()[-1])


class NativeProjectChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=ROOT/'Input snapshots'; cls.rel='Bench A/'+NAME+'.kicad_pcb'
        cmd(['/usr/bin/python3','-B','-X','faulthandler',TOOL/'tests/project_fixture.py',cls.snapshot/'Bench A'])
        cls.source_hashes=tree_hashes(cls.snapshot)
        cls.plan=structured(cli('plan-project','--snapshot',cls.snapshot,'--pcb',cls.rel,'--reroute-net','DATA'))
        cls.plan_path=ROOT/'approved-plan.json'; write_json(cls.plan_path,cls.plan,exclusive=True)
        cls.base_id=PREFIX+'-via'
        cls.result=structured(cli('route-project','--snapshot',cls.snapshot,'--pcb',cls.rel,'--plan',cls.plan_path,
                                  '--run-id',cls.base_id,'--route-timeout','120','--apply'))
        cls.run_dir=STATE/'runs'/cls.base_id
        cls.report=json.loads((cls.run_dir/'run.json').read_text())
        if cls.result['status']!='passed': raise AssertionError(cls.result)

    def clone(self,name):
        d=ROOT/name;shutil.copytree(self.snapshot,d);return d

    def plan_clone(self,snapshot,auth=('DATA',)):
        args=['plan-project','--snapshot',snapshot,'--pcb',self.rel]
        for n in auth: args+=['--reroute-net',n]
        plan=structured(cli(*args));p=ROOT/(snapshot.name+'-plan.json');write_json(p,plan,exclusive=True)
        return p

    def assert_error(self,c,code):
        data=structured(c);self.assertEqual(data['error']['code'],code,data)
        return data

    def import_probe(self,tag,*,ses_text=None,assoc_change=None,plan_change=None,candidate_exists=False):
        association=copy.deepcopy(self.report['association']);plan=copy.deepcopy(self.plan)
        ses=self.run_dir/'result.ses'
        if ses_text is not None:
            ses=ROOT/(tag+'.ses');ses.write_text(ses_text)
            association['ses_sha256']=digest(ses)
        if assoc_change: assoc_change(association)
        if plan_change: plan_change(plan)
        candidate=ROOT/(tag+'.kicad_pcb')
        if candidate_exists: candidate.write_text('existing')
        payload={'dsn':str(self.run_dir/('input-'+self.base_id+'.dsn')),'ses':str(ses),'candidate':str(candidate),
                 'plan':plan,'association':association,'source_hashes':self.source_hashes}
        c=cmd(flow.native_args('import',self.run_dir/'before',self.rel,payload),1)
        if not candidate_exists:self.assertFalse(candidate.exists())
        return c

    def test_01_forced_via_layers_and_all_native_gates(self):
        self.assertEqual(self.report['before_counts'],{'schematic_parity':0,'unconnected_items':1,'violations':0})
        self.assertEqual(self.report['after_counts'],{'schematic_parity':0,'unconnected_items':0,'violations':0})
        self.assertEqual(self.report['metrics']['after']['via_count'],1)
        self.assertTrue(self.report['source_immutable']);self.assertEqual(self.report['invariant_deltas'],[])
        rows=json.loads((self.run_dir/'after-copper.json').read_text())
        via=[r for r in rows if r['kind']=='PCB_VIA'];self.assertEqual(len(via),1)
        self.assertEqual((via[0]['width'],via[0]['drill'],via[0]['layers']),(700000,350000,[0,2]))
        self.assertEqual({r['layer'] for r in rows if r['net']=='DATA' and r['kind']=='PCB_TRACK'},{0,2})
        self.assertEqual(tree_hashes(self.snapshot),self.source_hashes)
        for record in self.report['commands']:
            command=record['command']
            if str(TOOL/'general_native.py') in command:
                pos=command.index(str(TOOL/'general_native.py'))
                expected=(Path(command[pos+2])/command[pos+3]).parent
            elif command[0]=='/usr/bin/kicad-cli':
                expected=Path(command[-1]).parent
            else:continue
            self.assertEqual(record['cwd'],str(expected))
        effective=json.loads((self.run_dir/'effective-settings.json').read_text())
        self.assertEqual(effective['requested']['router.copperToEdgeClearanceUm'],650)
        self.assertEqual(effective['actual_router']['copper_to_edge_clearance_um'],650)
        self.assertFalse(effective['actual_router']['automatic_neckdown'])

    def test_02_protect_locked_and_unlocked_critical_copper(self):
        before=json.loads((self.run_dir/'before-copper.json').read_text());after=json.loads((self.run_dir/'after-copper.json').read_text())
        self.assertEqual([r for r in before if r['net']=='SENSITIVE'],[r for r in after if r['net']=='SENSITIVE'])
        self.assertEqual([r['locked'] for r in after if r['net']=='SENSITIVE'],[r['locked'] for r in before if r['net']=='SENSITIVE'])
        self.assertEqual(self.report['export']['fixed_copper_count'],2)
        self.assertEqual(self.report['export']['removed_authorized_unlocked_count'],1)
        self.assertNotIn(uid('track2'),[r['uuid'] for r in after])

    def test_03_plan_and_dryrun_no_filesystem_writes(self):
        before=tree_hashes(STATE,allow_links=True)
        # cmd's test-harness logs are written AFTER the CLI returns; exclude them in comparison.
        n=len(RECORDS)
        c=cli('route-project','--snapshot',self.snapshot,'--pcb',self.rel,'--plan',self.plan_path,
              '--run-id',PREFIX+'-no-write','--dry-run')
        after=tree_hashes(STATE,allow_links=True)
        changed={k for k in set(before)|set(after) if before.get(k)!=after.get(k)}
        new_logs={str((ROOT/f'command-{n+1}.{s}.log').relative_to(STATE)) for s in ['stdout','stderr']}
        self.assertEqual(changed,new_logs)
        self.assertEqual(structured(c)['writes'],False)
        self.assertFalse((STATE/'runs'/(PREFIX+'-no-write')).exists())
        self.assertEqual(tree_hashes(self.snapshot),self.source_hashes)

    def test_04_authorized_completed_net_reroute_keeps_locked_segment(self):
        plan=structured(cli('plan-project','--snapshot',self.snapshot,'--pcb',self.rel,
                            '--reroute-net','DATA','--reroute-net','SENSITIVE'))
        path=ROOT/'reroute-plan.json';write_json(path,plan,exclusive=True)
        result=structured(cli('route-project','--snapshot',self.snapshot,'--pcb',self.rel,'--plan',path,
                              '--run-id',PREFIX+'-reroute','--apply'))
        self.assertEqual(result['status'],'passed')
        report=json.loads((STATE/'runs'/(PREFIX+'-reroute')/'run.json').read_text())
        self.assertEqual(report['export']['removed_authorized_unlocked_count'],2)
        rows=json.loads((STATE/'runs'/(PREFIX+'-reroute')/'after-copper.json').read_text())
        self.assertIn(uid('track0'),[r['uuid'] for r in rows])
        self.assertNotIn(uid('track1'),[r['uuid'] for r in rows])

    def test_05_native_placement_handoff_new_plan(self):
        snap=ROOT/'Handoff snapshot';pcb=snap/'Bench A'/Path(self.rel).name
        cmd(['/usr/bin/python3','-B',TOOL/'tests/project_fixture.py',pcb.parent])
        # Simulate a standalone editing-API/native placement candidate BEFORE snapshot approval.
        text=pcb.read_text();pcb.write_text(text.replace('(at 6 10)','(at 6.4 10)').replace('(start 6 10)','(start 6.4 10)').replace('(end 6.3 10)','(end 6.7 10)'))
        path=self.plan_clone(snap)
        result=structured(cli('route-project','--snapshot',snap,'--pcb',self.rel,'--plan',path,
                              '--run-id',PREFIX+'-handoff','--apply'))
        self.assertEqual(result['status'],'passed');self.assertEqual(result['invariant_deltas'],[])
        self.assert_error(cli('route-project','--snapshot',snap,'--pcb',self.rel,'--plan',self.plan_path,
                              '--run-id',PREFIX+'-stale-placement','--dry-run',expected=1),'PLAN_STALE')

    def test_06_conditional_rule_rejected_before_run(self):
        snap=self.clone('Conditional rule');dru=snap/Path(self.rel).with_suffix('.kicad_dru')
        dru.write_text('(version 1)(rule "Conditional" (condition "A.NetName == \'DATA\'") (constraint track_width (min 0.25mm)))')
        self.assert_error(cli('route-project','--snapshot',snap,'--pcb',self.rel,'--plan',self.plan_path,
                              '--run-id',PREFIX+'-bad-rule','--apply',expected=1),'DRU_CONDITIONAL')
        self.assertFalse((STATE/'runs'/(PREFIX+'-bad-rule')).exists())

    def test_07_protected_open_rejected(self):
        snap=self.clone('Protected open');pcb=snap/self.rel
        # Structural edit of ONLY generated test input, no product/module boards.
        text=pcb.read_text()
        pcb.write_text(re.sub(r'\t\(segment\n.*?\n\t\)',
                             lambda m:'' if '(net "SENSITIVE")' in m.group() else m.group(), text, flags=re.S))
        self.assert_error(cli('plan-project','--snapshot',snap,'--pcb',self.rel,'--reroute-net','DATA',expected=1),'OPEN_UNAUTHORIZED')

    def test_08_stale_rule_context_and_unplanned_open(self):
        snap=self.clone('Stale context');pro=snap/Path(self.rel).with_suffix('.kicad_pro')
        p=json.loads(pro.read_text());p['meta']['filename']='stale-but-same-rules.kicad_pro';pro.write_text(json.dumps(p))
        self.assert_error(cli('route-project','--snapshot',snap,'--pcb',self.rel,'--plan',self.plan_path,
                              '--run-id',PREFIX+'-stale','--dry-run',expected=1),'PLAN_STALE')
        p=copy.deepcopy(self.plan);p['baseline_open_pairs'][0]['uuids'][0]=uid('J3pad')
        path=ROOT/'wrong-open-plan.json';write_json(path,p,exclusive=True)
        self.assert_error(cli('route-project','--snapshot',self.snapshot,'--pcb',self.rel,'--plan',path,
                              '--run-id',PREFIX+'-wrong-open','--dry-run',expected=1),'PLAN_STALE')

    def test_09_real_route_timeout_group_killed_source_unchanged(self):
        result=structured(cli('route-project','--snapshot',self.snapshot,'--pcb',self.rel,'--plan',self.plan_path,
                              '--run-id',PREFIX+'-timeout','--route-timeout','1','--apply',expected=1))
        self.assertEqual(result['error']['code'],'PROCESS_TIMEOUT');self.assertTrue(result['source_immutable'])
        process=json.loads((STATE/'runs'/(PREFIX+'-timeout')/'logs/freerouting-route.process.json').read_text())
        self.assertEqual(process['failure'],'timeout');self.assertLess(process['returncode'],0)
        self.assertFalse((STATE/'runs'/(PREFIX+'-timeout')/'after').exists())

    def test_10_session_hash_base_design_plan_and_output_rejected(self):
        text=(self.run_dir/'result.ses').read_text()
        c=self.import_probe('ses-hash',ses_text=text+'\n',assoc_change=lambda a:a.update(ses_sha256=self.report['association']['ses_sha256']))
        self.assert_error(c,'SESSION_STALE')
        c=self.import_probe('ses-header',ses_text=text.replace('base_design "input-'+self.base_id+'"','base_design "foreign-session"'))
        self.assert_error(c,'SESSION_STALE')
        self.assert_error(self.import_probe('dsn-hash',assoc_change=lambda a:a.update(dsn_sha256='0'*64)),'SESSION_STALE')
        self.assert_error(self.import_probe('ses-plan',plan_change=lambda p:p.update(source_digest='0'*64)),'SESSION_PLAN')
        self.assert_error(self.import_probe('ses-output',candidate_exists=True),'OUTPUT_EXISTS')

    def test_11_native_import_protected_addition_and_placement_rejected(self):
        text=(self.run_dir/'result.ses').read_text()
        self.assert_error(self.import_probe('moved-placement',ses_text=text.replace('place J1 60000','place J1 61000')),'INVARIANT_CHANGED')
        injected=text.replace('(network_out','(network_out (net SENSITIVE (wire (path F.Cu 3200 100000 -220000 100000 -230000)))',1)
        self.assert_error(self.import_probe('protected-addition',ses_text=injected),'INVARIANT_CHANGED')

    def test_12_same_run_overwrite_and_path_rejected(self):
        self.assert_error(cli('route-project','--snapshot',self.snapshot,'--pcb',self.rel,'--plan',self.plan_path,
                              '--run-id',self.base_id,'--apply',expected=1),'INPUT_OR_RUNTIME')
        self.assert_error(cli('plan-project','--snapshot',self.snapshot,'--pcb','../foreign.kicad_pcb',
                              '--reroute-net','DATA',expected=1),'PCB_PATH')
        snap=self.clone('Symlink snapshot');(snap/'escape.kicad_mod').symlink_to(self.snapshot/'Bench A/Orchard.pretty/Rect.kicad_mod')
        self.assert_error(cli('plan-project','--snapshot',snap,'--pcb',self.rel,'--reroute-net','DATA',expected=1),'PATH_SYMLINK')

    def test_13_existing_through_via_protected_roundtrip(self):
        snap=ROOT/'Existing via snapshot';shutil.copytree(self.run_dir/'after',snap)
        path=self.plan_clone(snap,('SENSITIVE',))
        result=structured(cli('route-project','--snapshot',snap,'--pcb',self.rel,'--plan',path,
                              '--run-id',PREFIX+'-fixed-via','--apply'))
        self.assertEqual(result['status'],'passed');self.assertEqual(result['invariant_deltas'],[])
        self.assertEqual(result['metrics']['before']['via_count'],1)
        self.assertEqual(result['metrics']['after']['via_count'],1)


    def test_14_relative_fp_sym_table_inspect_and_plan_parity(self):
        control=self.clone('Relative URI control');project_dir=control/Path(self.rel).parent
        # Freeze the existing embedded symbol into a real local symbol library on
        # this COPY only; no editing worker or live project is invoked.
        text=(control/Path(self.rel).with_suffix('.kicad_sch')).read_text()
        start=text.index('(symbol "Orchard:Terminal"');depth=0
        for end in range(start,len(text)):
            if text[end]=='(':depth+=1
            elif text[end]==')':depth-=1
            if depth==0:break
        symbol=text[start:end+1].replace('"Orchard:Terminal"','"Terminal"',1)
        (project_dir/'Orchard.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") '+symbol+')\n')
        (project_dir/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "OrchardSymbols") (type "KiCad") (uri "${KIPRJMOD}/Orchard.kicad_sym") (options "") (descr "Frozen test copy")))\n')
        def inspect(snap):
            return structured(cli('inspect-project','--snapshot',snap,'--pcb',self.rel,'--reroute-net','DATA'))
        def plan(snap):
            return structured(cli('plan-project','--snapshot',snap,'--pcb',self.rel,'--reroute-net','DATA'))
        baseline_hashes=tree_hashes(control);baseline=inspect(control);base_plan=plan(control)
        parity_keys=['violations','schematic_parity','unconnected_items','ignored_checks','included_severities']
        for parent_relative in [False,True]:
            with self.subTest(parent_relative=parent_relative):
                snap=ROOT/('Relative sibling libraries' if parent_relative else 'Relative adjacent libraries')
                shutil.copytree(control,snap);directory=snap/Path(self.rel).parent
                prefix='../Libraries/' if parent_relative else ''
                if parent_relative:
                    libraries=snap/'Libraries';libraries.mkdir()
                    for name in ['Orchard.pretty','Orchard.kicad_sym']:
                        shutil.move(str(directory/name),str(libraries/name))
                for name in ['fp-lib-table','sym-lib-table']:
                    table=directory/name;table.write_text(table.read_text().replace('${KIPRJMOD}/',prefix))
                before=tree_hashes(snap);result=inspect(snap);approved=plan(snap)
                self.assertEqual(result['status'],'inspected')
                self.assertEqual(result['native']['invariants'],baseline['native']['invariants'])
                self.assertEqual(result['native']['item_nets'],baseline['native']['item_nets'])
                self.assertEqual(result['admission']['rules'],baseline['admission']['rules'])
                self.assertEqual(result['admission']['outline'],baseline['admission']['outline'])
                for key in parity_keys:self.assertEqual(result['drc'][key],baseline['drc'][key])
                for key in base_plan:
                    if key not in ['source_digest','context_digest']:
                        self.assertEqual(approved[key],base_plan[key])
                for key in ['source_digest','context_digest']:
                    self.assertNotEqual(approved[key],base_plan[key])
                if parent_relative:
                    path=ROOT/'relative-approved-plan.json';write_json(path,approved,exclusive=True)
                    routed=structured(cli('route-project','--snapshot',snap,'--pcb',self.rel,'--plan',path,
                                          '--run-id',PREFIX+'-relative','--apply'))
                    self.assertEqual(routed['status'],'passed');self.assertEqual(routed['invariant_deltas'],[])
                    self.assertEqual(routed['after_counts'],{'violations':0,'schematic_parity':0,'unconnected_items':0})
                    self.assertTrue(routed['source_immutable'])
                self.assertEqual(tree_hashes(snap),before)
        self.assertEqual(tree_hashes(control),baseline_hashes)
        self.assertEqual(tree_hashes(self.snapshot),self.source_hashes)

    def test_15_group_admission_rejected_before_native_or_routing(self):
        for footprint in [False,True]:
            for locked in [False,True]:
                with self.subTest(footprint=footprint,locked=locked):
                    tag=f'Group fp-{footprint} locked-{locked}'
                    snap=self.clone(tag);pcb=snap/self.rel;text=pcb.read_text()
                    member=uid('J1pad') if footprint else uid('track2')
                    lock='(locked yes)' if locked else ''
                    group=f'(group "critical" {lock} (uuid "{uid(tag)}") (members "{member}"))'
                    if footprint:
                        anchor='(footprint "Orchard:Rect"';self.assertIn(anchor,text)
                        text=text.replace(anchor,anchor+' '+group,1)
                    else:text=text.rstrip()[:-1]+' '+group+')\n'
                    pcb.write_text(text);before=tree_hashes(snap)
                    for action in ['inspect-project','plan-project']:
                        self.assert_error(cli(action,'--snapshot',snap,'--pcb',self.rel,
                                              '--reroute-net','DATA',expected=1),'GROUP_UNSUPPORTED')
                    self.assertEqual(tree_hashes(snap),before)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-prefix',required=True,help='New unique bounded prefix; creates only ignored test/evidence outputs')
    args=parser.parse_args();PREFIX=args.run_prefix
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,20}',PREFIX):parser.error('invalid prefix')
    ROOT=STATE/('native-tests-'+PREFIX);ROOT.mkdir(parents=True,exist_ok=False)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeProjectChecks))
    write_json(ROOT/'summary.json',{'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
               'commands':RECORDS,'source_immutable':hasattr(NativeProjectChecks,'source_hashes') and tree_hashes(NativeProjectChecks.snapshot)==NativeProjectChecks.source_hashes,
               'run_ids':[PREFIX+s for s in ['-via','-reroute','-handoff','-timeout','-fixed-via','-relative']]},exclusive=True)
    sys.exit(0 if result.wasSuccessful() else 1)
