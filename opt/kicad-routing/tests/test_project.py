"""Ordinary-flow unit tests: offline/no native or Java dependency."""
import sys
sys.dont_write_bytecode=True
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).absolute().parents[1]))
import general_flow as flow
import general_native as native
import project_contract as contract
import run as cli
import sandbox
import runtime
from safety import STATE, TOOL, GateError, digest, tree_hashes, run_process
from project_fixture import project


class ProjectTests(unittest.TestCase):
    def setUp(self):
        STATE.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='project-unit-',dir=STATE)
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.snapshot=self.root/'Input with spaces'; self.snapshot.mkdir()
        self.rel='Orchard.kicad_pcb'; self.pcb=self.snapshot/self.rel
        self.pcb.write_text('''(kicad_pcb (version 20260206) (layers (0 "F.Cu" signal) (2 "B.Cu" signal)) (setup)
          (footprint "Local:Term" (layer "F.Cu") (uuid "00000000-0000-0000-0000-000000000001")
            (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask") (net "A")))
          (gr_line (start 0 0) (end 40 0) (layer "Edge.Cuts"))
          (gr_line (start 40 0) (end 40 30) (layer "Edge.Cuts"))
          (gr_line (start 40 30) (end 0 30) (layer "Edge.Cuts"))
          (gr_line (start 0 30) (end 0 0) (layer "Edge.Cuts")))''')
        self.pro=self.pcb.with_suffix('.kicad_pro'); self.pro.write_text(json.dumps(project('Orchard')))
        self.pcb.with_suffix('.kicad_sch').write_text('(kicad_sch (lib_symbols (symbol "Local:Term")))')
        self.lib=self.snapshot/'Local.pretty'; self.lib.mkdir(); (self.lib/'Term.kicad_mod').write_text('(footprint "Term")')
        (self.snapshot/'fp-lib-table').write_text('(fp_lib_table (lib (name "Local") (type "KiCad") (uri "${KIPRJMOD}/Local.pretty")))')
        self.drc={'kicad_version':'10.0.6','$schema':'https://schemas.kicad.org/drc.v1.json','violations':[], 'schematic_parity':[],
                  'included_severities':['error','warning','exclusion'],'ignored_checks':[],
                  'unconnected_items':[{'type':'unconnected_items','severity':'error','items':[{'uuid':'u1'},{'uuid':'u2'}]}]}
        self.info={'item_nets':{'u1':'A','u2':'A','u3':'PROTECTED'}}
        self.admission=contract.admit(self.snapshot,self.rel)
        self.plan=contract.plan_for(self.admission,self.info,self.drc,self.rel,['A'])

    def rejected(self, code, fn, *args):
        with self.assertRaises(contract.ProjectError) as cm: fn(*args)
        self.assertEqual(cm.exception.code,code)
        self.assertTrue(cm.exception.record()['hint'])

    def edit_project(self, fn):
        p=json.loads(self.pro.read_text()); fn(p); self.pro.write_text(json.dumps(p))

    def test_plan_discovers_hashes_uuids_protection(self):
        self.assertEqual(self.plan['schema'],contract.SCHEMA)
        self.assertEqual(self.plan['protected_nets'],['PROTECTED'])
        self.assertEqual(self.plan['baseline_open_pairs'],[{'net':'A','uuids':['u1','u2']}])
        self.assertEqual(self.plan['source_digest'],contract.object_digest(self.admission['files']))

    def test_source_and_context_digests_distinct(self):
        self.pcb.write_text(self.pcb.read_text().replace('version 20260206','version 20260207'))
        changed=contract.admit(self.snapshot,self.rel)
        self.assertNotEqual(changed['source_digest'],self.admission['source_digest'])
        self.assertEqual(changed['context_digest'],self.admission['context_digest'])

    def test_plan_schema_unknown_version_extra_and_missing(self):
        for fn in [lambda p:p.update(schema='v2'),lambda p:p.update(best_effort=True),lambda p:p.pop('source_digest')]:
            p=copy.deepcopy(self.plan);fn(p)
            self.rejected('PLAN_SCHEMA',contract.validate_plan,p,self.plan)

    def test_stale_context_plan(self):
        p=copy.deepcopy(self.plan);p['context_digest']='bad'
        self.rejected('PLAN_STALE',contract.validate_plan,p,self.plan)

    def test_unplanned_and_protected_opens(self):
        d=copy.deepcopy(self.drc);d['unconnected_items'][0]['items'][1]['uuid']='u3'
        self.rejected('OPEN_UNAUTHORIZED',contract.open_pairs,d,self.info['item_nets'],['A'])
        d['unconnected_items'][0]['items'][1]['uuid']='unknown'
        self.rejected('OPEN_UNSUPPORTED',contract.open_pairs,d,self.info['item_nets'],['A'])

    def test_authorization_explicit_unique_and_known(self):
        for auth in [[],['A','A'],['']]: self.rejected('NET_AUTHORIZATION',contract.plan_for,self.admission,self.info,self.drc,self.rel,auth)
        self.rejected('NET_UNKNOWN',contract.plan_for,self.admission,self.info,self.drc,self.rel,['absent'])

    def test_drc_findings_warnings_parity_exclusions(self):
        for key in ['violations','schematic_parity']:
            d=copy.deepcopy(self.drc);d[key]=[{'severity':'warning'}]
            self.rejected('BASELINE_FINDINGS',contract.drc_base,d)
        d=copy.deepcopy(self.drc);d['included_severities']=['error']
        self.rejected('DRC_SEVERITIES',contract.drc_base,d)

    def test_differential_pair_intent_and_cli_version_fail_closed(self):
        info=copy.deepcopy(self.info);info['item_nets'].update(u4='CLOCK_P',u5='CLOCK_N')
        self.rejected('DIFFERENTIAL_UNSUPPORTED',contract.plan_for,self.admission,info,self.drc,self.rel,['A'])
        d=copy.deepcopy(self.drc);d['kicad_version']='10.0.7'
        self.rejected('DRC_VERSION',contract.drc_base,d)

    def test_duplicate_opens_rejected(self):
        d=copy.deepcopy(self.drc);d['unconnected_items']*=2
        self.rejected('OPEN_DUPLICATE',contract.open_pairs,d,self.info['item_nets'],['A'])

    def test_path_escape_absolute_noncanonical(self):
        for value in ['../a.kicad_pcb','/a.kicad_pcb','./Orchard.kicad_pcb','sub//a.kicad_pcb','a\\b.kicad_pcb']:
            self.rejected('PCB_PATH',contract.relative_pcb,value)

    def test_snapshot_symlink_rejected(self):
        (self.snapshot/'escape.kicad_mod').symlink_to(self.lib/'Term.kicad_mod')
        self.rejected('PATH_SYMLINK',contract.admit,self.snapshot,self.rel)

    def test_source_hardlink_alias_rejected(self):
        os.link(self.pcb,self.root/'alias.kicad_pcb')
        self.rejected('SOURCE_ALIAS',contract.admit,self.snapshot,self.rel)

    def test_missing_context_rejected(self):
        self.pcb.with_suffix('.kicad_sch').unlink()
        self.rejected('CONTEXT_MISSING',contract.admit,self.snapshot,self.rel)

    def test_context_file_and_output_alias_rejected(self):
        (self.snapshot/'unexpected.json').write_text('{}')
        self.rejected('CONTEXT_FILE',contract.admit,self.snapshot,self.rel)
        self.rejected('SOURCE_OUTPUT_ALIAS',contract.snapshot_manifest,contract.TOOL.parent,self.rel)

    def test_external_or_missing_local_lib(self):
        table=self.snapshot/'fp-lib-table';t=table.read_text();table.write_text(t.replace('${KIPRJMOD}/Local.pretty','/usr/share/kicad/footprints'))
        self.rejected('LIBRARY_EXTERNAL',contract.admit,self.snapshot,self.rel)
        table.write_text(t);(self.lib/'Term.kicad_mod').unlink()
        self.rejected('LIBRARY_MISSING',contract.admit,self.snapshot,self.rel)

    def test_same_symbol_and_footprint_nickname_do_not_shadow_fpid(self):
        symbol = self.snapshot/'Local.kicad_sym'
        symbol.write_text('(kicad_symbol_lib (version 20250114))')
        for prefix in ['', '${KIPRJMOD}/']:
            with self.subTest(prefix=prefix):
                (self.snapshot/'sym-lib-table').write_text(
                    '(sym_lib_table (lib (name "Local") (type "KiCad") (uri "'+prefix+'Local.kicad_sym")))')
                before = tree_hashes(self.snapshot)
                admission = contract.admit(self.snapshot, self.rel)
                self.assertIn('Local.kicad_sym', admission['files'])
                self.assertEqual(admission['rules'], self.admission['rules'])
                self.assertEqual(tree_hashes(self.snapshot), before)
        (self.lib/'Term.kicad_mod').unlink()
        self.rejected('LIBRARY_MISSING', contract.admit, self.snapshot, self.rel)

    def test_relative_local_library_uri_and_legacy_same_target(self):
        for uri in ['Local.pretty', '${KIPRJMOD}/Local.pretty']:
            with self.subTest(uri=uri):
                self.assertEqual(contract.local_uri(uri,self.snapshot,self.snapshot),self.lib)
                table=self.snapshot/'fp-lib-table'
                table.write_text('(fp_lib_table (lib (name "Local") (type "KiCad") (uri "'+uri+'")))')
                admission=contract.admit(self.snapshot,self.rel)
                self.assertEqual(admission['rules'],self.admission['rules'])
                self.assertEqual(admission['outline'],self.admission['outline'])

    def test_parent_relative_local_libraries_stay_in_snapshot(self):
        project_dir=self.snapshot/'Board A';project_dir.mkdir()
        libraries=self.snapshot/'Libraries';libraries.mkdir()
        self.lib.rename(libraries/self.lib.name)
        for path in list(self.snapshot.iterdir()):
            if path.is_file():path.rename(project_dir/path.name)
        (project_dir/'fp-lib-table').write_text('(fp_lib_table (lib (name "Local") (type "KiCad") (uri "../Libraries/Local.pretty")))')
        (libraries/'Local.kicad_sym').write_text('(kicad_symbol_lib (version 20250114))')
        (project_dir/'sym-lib-table').write_text('(sym_lib_table (lib (name "Symbols") (type "KiCad") (uri "../Libraries/Local.kicad_sym")))')
        admission=contract.admit(self.snapshot,'Board A/'+self.rel)
        self.assertEqual(admission['rules'],self.admission['rules'])
        for uri in ['../Libraries/Local.pretty','${KIPRJMOD}/../Libraries/Local.pretty']:
            self.assertEqual(contract.local_uri(uri,project_dir,self.snapshot),libraries/'Local.pretty')

    def test_relative_uri_rejects_external_variables_urls_noncanonical(self):
        for uri in ['', '.', '..', '/absolute/Local.pretty', 'C:/Local.pretty',
                    'https://example.invalid/Local.pretty', 'file:///Local.pretty',
                    '${HOME}/Local.pretty', '$HOME/Local.pretty', '%HOME%/Local.pretty',
                    '${KIPRJMOD}/${OTHER}/Local.pretty', '~/Local.pretty',
                    './Local.pretty', 'Local.pretty/', 'Libraries//Local.pretty',
                    'Local.pretty/../Local.pretty', 'Libraries\\Local.pretty']:
            with self.subTest(uri=uri):
                self.rejected('LIBRARY_EXTERNAL',contract.local_uri,uri,self.snapshot,self.snapshot)

    def test_relative_uri_rejects_escape_and_missing(self):
        outside=self.root/'Outside.pretty';outside.mkdir()
        for uri in ['../Outside.pretty','${KIPRJMOD}/../Outside.pretty','Missing.pretty']:
            with self.subTest(uri=uri):
                self.rejected('LIBRARY_MISSING',contract.local_uri,uri,self.snapshot,self.snapshot)

    def test_relative_uri_rejects_symlink_dest_and_ancestor(self):
        link=self.snapshot/'Linked.pretty';link.symlink_to(self.lib,target_is_directory=True)
        for uri in ['Linked.pretty','Linked.pretty/Term.kicad_mod']:
            with self.subTest(uri=uri):
                self.rejected('PATH_SYMLINK',contract.local_uri,uri,self.snapshot,self.snapshot)
        # A redundant parent path cannot conceal the symlink either.
        self.rejected('LIBRARY_EXTERNAL',contract.local_uri,'Linked.pretty/../Local.pretty',self.snapshot,self.snapshot)

    def test_relative_uri_rejects_hardlink_aliases(self):
        sym=self.snapshot/'Local.kicad_sym';sym.write_text('(kicad_symbol_lib)')
        alias=self.root/'alias.kicad_sym';os.link(sym,alias)
        self.rejected('SOURCE_ALIAS',contract.local_uri,'Local.kicad_sym',self.snapshot,self.snapshot)
        sym.unlink();alias.unlink()
        os.link(self.lib/'Term.kicad_mod',self.root/'alias.kicad_mod')
        table=self.snapshot/'fp-lib-table';table.write_text(table.read_text().replace('${KIPRJMOD}/',''))
        self.rejected('SOURCE_ALIAS',contract.admit,self.snapshot,self.rel)

    def test_board_groups_fail_closed_even_unlocked(self):
        original=self.pcb.read_text()
        for lock in ['', '(locked yes)']:
            with self.subTest(lock=lock):
                group='(group "critical" '+lock+' (uuid "00000000-0000-0000-0000-000000000002") (members "00000000-0000-0000-0000-000000000001"))'
                self.pcb.write_text(original[:-1]+' '+group+')')
                self.rejected('GROUP_UNSUPPORTED',contract.admit,self.snapshot,self.rel)

    def test_footprint_groups_fail_closed_even_unlocked(self):
        original=self.pcb.read_text()
        for lock in ['', '(locked yes)']:
            with self.subTest(lock=lock):
                group='(group "pads" '+lock+' (uuid "00000000-0000-0000-0000-000000000002") (members))'
                self.pcb.write_text(original.replace('(footprint "Local:Term"','(footprint "Local:Term" '+group,1))
                self.rejected('GROUP_UNSUPPORTED',contract.admit,self.snapshot,self.rel)

    def test_conditional_and_length_rules_fail_closed(self):
        rules=self.pcb.with_suffix('.kicad_dru')
        rules.write_text('(version 1)(rule "x" (condition "A.NetName == B.NetName") (constraint clearance (min 0.2mm)))')
        self.rejected('DRU_CONDITIONAL',contract.admit,self.snapshot,self.rel)
        rules.write_text('(version 1)(rule "x" (constraint length (min 1mm)))')
        self.rejected('DRU_CONSTRAINT',contract.admit,self.snapshot,self.rel)

    def test_unconditional_minimum_covered_or_rejected(self):
        rules=self.pcb.with_suffix('.kicad_dru')
        rules.write_text('(version 1)(rule "x" (constraint track_width (min 0.25mm)))')
        contract.admit(self.snapshot,self.rel)
        rules.write_text(rules.read_text().replace('0.25','0.99'))
        self.rejected('DRU_UNCOVERED',contract.admit,self.snapshot,self.rel)

    def test_extra_classes_and_assignments_never_rewritten(self):
        self.edit_project(lambda p:p['net_settings']['netclass_assignments'].update(A='Default'))
        self.rejected('NETCLASS_UNSUPPORTED',contract.admit,self.snapshot,self.rel)

    def test_unsupported_project_minimum_and_ignored_rule(self):
        self.edit_project(lambda p:p['board']['design_settings']['rules'].update(min_hole_clearance=0.3))
        self.rejected('RULE_UNTRANSLATED',contract.admit,self.snapshot,self.rel)
        self.pro.write_text(json.dumps(project('Orchard')))
        self.edit_project(lambda p:p['board']['design_settings']['rule_severities'].update(clearance='ignore'))
        self.rejected('RULE_IGNORED',contract.admit,self.snapshot,self.rel)

    def test_arc_custom_pad_and_override(self):
        original=self.pcb.read_text()
        for replacement,code in [('smd custom','PAD_SHAPE'),('smd rect (clearance 0.01)','PAD_OVERRIDE')]:
            self.pcb.write_text(original.replace('smd rect',replacement))
            self.rejected(code,contract.admit,self.snapshot,self.rel)
        self.pcb.write_text(original[:-1]+' (arc (net "A")))')
        self.rejected('TRACK_ARC',contract.admit,self.snapshot,self.rel)

    def test_zones_and_other_stackup_rejected(self):
        original=self.pcb.read_text();self.pcb.write_text(original[:-1]+' (zone (net "A")))')
        self.rejected('ZONES_UNVERIFIED',contract.admit,self.snapshot,self.rel)
        self.pcb.write_text(original.replace('(2 "B.Cu" signal)','(4 "In1.Cu" signal) (2 "B.Cu" signal)'))
        self.rejected('STACKUP_UNSUPPORTED',contract.admit,self.snapshot,self.rel)

    def test_mechanics_outline_not_best_effort(self):
        self.pcb.write_text(self.pcb.read_text().replace('(end 40 30)','(end 39 30)'))
        self.rejected('OUTLINE_UNSUPPORTED',contract.admit,self.snapshot,self.rel)

    def test_duplicate_json_and_nonfinite(self):
        self.rejected('JSON_DUPLICATE',contract.strict_json,'{"a":1,"a":2}')
        self.rejected('JSON_NUMBER',contract.strict_json,'{"a":NaN}')

    def test_invariant_rejects_add_delete_placement_pad_locked_mechanics(self):
        before={'all_protected_net_copper':['locked','unlocked'],'footprints_pads_nets':['placement/pad'],
                'locked_copper':['fixed'],'saved_nonrouting_definitions':['edge'],'native_rules':['rule']}
        for key in before:
            for replacement in [[],['changed'],before[key]+['added']]:
                after=copy.deepcopy(before);after[key]=replacement
                self.rejected('INVARIANT_CHANGED',native.compare,before,after)
        native.compare(before,copy.deepcopy(before))

    def test_native_version_and_missing_binding(self):
        self.rejected('NATIVE_MISSING',native.ProjectAdapter,SimpleNamespace())
        api=SimpleNamespace(**{n:MagicMock() for n in ['LoadBoard','SaveBoard','GetSettingsManager','ExportSpecctraDSN','ImportSpecctraSES','ZONE_FILLER']},GetBuildVersion=lambda:'10.0.7')
        self.rejected('NATIVE_VERSION',native.ProjectAdapter,api)

    def test_dry_run_no_runtime_run_or_files(self):
        path=self.root/'plan.json';path.write_text(json.dumps(self.plan));before=tree_hashes(self.root)
        with patch.object(flow,'preflight_plan',return_value=(self.admission,self.info,self.drc)),patch.object(flow.runtime,'validate_runtime') as runtime:
            result=flow.route_project(self.snapshot,self.rel,path,'dry-run')
            self.assertEqual(result['status'],'dry-run');runtime.assert_not_called()
        self.assertEqual(tree_hashes(self.root),before)

    def test_plan_inside_snapshot_and_timeout_refused(self):
        self.rejected('PLAN_SOURCE_ALIAS',flow.route_project,self.snapshot,self.rel,self.snapshot/'plan.json','x')
        self.rejected('ROUTE_TIMEOUT',flow.route_project,self.snapshot,self.rel,self.root/'plan.json','x',121)

    def test_cli_default_readonly_and_requires_explicit_apply(self):
        with patch.object(flow,'route_project',return_value={'status':'dry-run'}) as route,patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(cli.main(['route-project','--snapshot',str(self.snapshot),'--pcb',self.rel,'--plan','plan.json','--run-id','x']),0)
            self.assertFalse(route.call_args.args[-1])

    def test_no_selected_net_or_autoplacement_option(self):
        for option in ['--selected-net','--auto-place']:
            with patch('sys.stderr',new=io.StringIO()),self.assertRaises(SystemExit) as cm:
                cli.main(['route-project','--snapshot',str(self.snapshot),'--pcb',self.rel,'--plan','p','--run-id','x',option,'A'])
            self.assertEqual(cm.exception.code,2)

    def test_readonly_capture_timeout_without_logs(self):
        before=tree_hashes(self.root)
        self.rejected('PROCESS_TIMEOUT',flow.capture,['/usr/bin/python3','-c','import time;time.sleep(2)'],0.1)
        self.assertEqual(tree_hashes(self.root),before)

    def test_effective_router_flags_are_really_compared(self):
        expected={**sandbox.SETTINGS,'router.copperToEdgeClearanceUm':650}
        actual={}
        for key,value in expected.items():
            if not key.startswith('router.'):continue
            parts=key.split('.')[1:];target=actual
            for part in parts[:-1]:target=target.setdefault(part,{})
            target[{'copperToEdgeClearanceUm':'copper_to_edge_clearance_um'}.get(parts[-1],parts[-1])]=value
        actual['automatic_neckdown']=True
        result=self.root/'freerouting-result.json';result.write_text(json.dumps({'settings_snapshot':actual}))
        with patch.object(sandbox,'java_command',return_value=['mock']),patch.object(sandbox,'run_process',return_value={'failure':None,'returncode':0}),patch.object(sandbox,'validate_logs'):
            with self.assertRaisesRegex(GateError,'effective router flag mismatch'):
                sandbox.route(self.root,runtime.RUNTIME/'java',runtime.RUNTIME/'jar',1,expected)

    def test_readonly_native_cwd_is_project_relative_and_bounded(self):
        project_dir=self.snapshot/'Board A';project_dir.mkdir()
        args=flow.readonly_command(self.snapshot,['/usr/bin/true'],project_dir)
        self.assertEqual(args[args.index('--chdir')+1],str(project_dir))
        self.assertNotIn('--bind',args)
        self.rejected('LIBRARY_MISSING',flow.readonly_command,self.snapshot,['/usr/bin/true'],self.root)

    def test_bounded_runner_logs_project_cwd_and_keeps_default(self):
        project_dir=self.snapshot/'Board A';project_dir.mkdir()
        argv=['/usr/bin/python3','-B','-c','import os;print(os.getcwd())']
        for name,cwd,expected in [('explicit',project_dir,project_dir),('default',None,TOOL)]:
            with self.subTest(name=name):
                result=run_process(argv,self.root/'logs',name,10,cwd=cwd)
                self.assertEqual(result['returncode'],0);self.assertIsNone(result['failure'])
                self.assertEqual(result['cwd'],str(expected))
                self.assertEqual((self.root/'logs'/(name+'.stdout.log')).read_text().strip(),str(expected))
                recorded=json.loads((self.root/'logs'/(name+'.process.json')).read_text())
                self.assertEqual(recorded['cwd'],str(expected))

    def test_bounded_runner_rejects_invalid_cwd_before_logs(self):
        link=self.root/'cwd-link';link.symlink_to(self.snapshot,target_is_directory=True)
        for cwd in [TOOL.parent,self.root/'missing',self.pcb,link]:
            with self.subTest(cwd=cwd),patch('safety.subprocess.Popen') as process:
                with self.assertRaises(GateError):
                    run_process(['/usr/bin/true'],self.root/'rejected-logs','invalid',cwd=cwd)
                process.assert_not_called()
                self.assertFalse((self.root/'rejected-logs').exists())

    def test_readonly_mounts_no_writable_bind(self):
        args=flow.readonly_command(self.snapshot,['/usr/bin/true'])
        self.assertNotIn('--bind',args);self.assertNotIn('--tmpfs',args)
        self.assertIn('--unshare-net',args);self.assertIn('--remount-ro',args)


if __name__=='__main__': unittest.main()
