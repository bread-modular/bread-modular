"""Offline stdlib tests. Native/process doubles; NEVER download or route a real board."""
import sys
sys.dont_write_bytecode = True
import copy
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).absolute().parents[1]))
import fixture
import pcbnew_adapter as native
import run as cli
import runtime
import sandbox
from safety import (GateError, STATE, assert_same, digest, run_process, safe_path,
                    sexpr, validate_session)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        STATE.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='unit-',dir=STATE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = self.root/'before'; self.before.mkdir()
        self.pcb = self.before/'synthetic.kicad_pcb'
        self.pcb.write_text('(kicad_pcb (version 20260206))')
        self.pcb.with_suffix('.kicad_pro').write_text(json.dumps(fixture.project()))
        self.pcb.with_suffix('.kicad_dru').write_text(fixture.RULES)
        self.dsn = self.root/'input-unit.dsn'
        self.dsn.write_text(f'(pcb "{self.dsn}" (wiring))')
        self.ses = self.root/'result.ses'
        self.ses.write_text('(session input-unit (base_design input-unit) (routes (network_out)))')
        self.candidate = self.root/'after/synthetic.kicad_pcb'
        self.source = {'synthetic.kicad_pcb':'source-hash'}
        self.association = {'source_hashes':self.source.copy(), 'dsn_sha256':digest(self.dsn),
            'ses_sha256':digest(self.ses),'dsn_header':str(self.dsn),'session_design':'input-unit',
            'pcb_sha256':digest(self.pcb),'companions':native.companions(self.pcb)}
        self.api = SimpleNamespace(**{n:MagicMock() for n in ['LoadBoard','SaveBoard','GetSettingsManager',
            'ExportSpecctraDSN','ImportSpecctraSES','ZONE_FILLER']}, GetBuildVersion=lambda:'10.0.6-test')
        self.adapter = native.NativeAdapter(self.api)
        self.board = MagicMock()
        self.adapter.load = MagicMock(return_value=self.board)

    def imported(self):
        return self.adapter.import_session(self.pcb,self.dsn,self.ses,self.candidate,self.association,self.source)

    def test_missing_runtime(self):
        with patch.object(runtime,'RUNTIME',self.root/'absent.tmp'):
            with self.assertRaisesRegex(GateError,'runtime missing'):
                runtime.validate_runtime()

    def test_download_requires_explicit_opt_in(self):
        with patch.object(runtime,'download') as download:
            with self.assertRaisesRegex(GateError,'--allow-downloads'):
                runtime.prepare(False)
            download.assert_not_called()

    def test_prepare_never_overwrites_runtime(self):
        existing = self.root/'runtime.tmp'; existing.mkdir()
        with patch.object(runtime,'RUNTIME',existing), patch.object(runtime,'download') as download:
            with self.assertRaisesRegex(GateError,'already exists'):
                runtime.prepare(True)
            download.assert_not_called()

    def test_wrong_hardware_rejected(self):
        with patch.object(runtime.platform,'machine',return_value='aarch64'):
            with self.assertRaisesRegex(GateError,'x86_64'):
                runtime.architecture()

    def test_pin_metadata_mismatch(self):
        p = runtime.PINS['freerouting']
        data = {'tag_name':p['tag'],'assets':[{'name':p['name'],'digest':'sha256:bad',
                'size':p['size'],'browser_download_url':p['url']}]}
        with self.assertRaisesRegex(GateError,'metadata mismatch'):
            runtime.verify_metadata(data,p)

    def test_untrusted_download_urls_rejected(self):
        for url in ['http://github.com/a','https://evil.example/a','https://user:pass@github.com/a',
                    'https://github.com:444/a']:
            with self.subTest(url=url), self.assertRaises(GateError):
                runtime.trusted_url(url)

    def test_archive_paths_symlinks_and_special_files(self):
        cases = [('root/../escape',None,'file'),('/absolute',None,'file'),
                 (runtime.JRE_DIR+'/legal/escape','../../../outside','link'),
                 (runtime.JRE_DIR+'/bin/tool',None,'hardlink')]
        for i,(name,target,kind) in enumerate(cases):
            archive = self.root/f'bad-{i}.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                member = tarfile.TarInfo(name)
                if kind=='link':
                    member.type=tarfile.SYMTYPE; member.linkname=target
                elif kind=='hardlink':
                    member.type=tarfile.LNKTYPE; member.linkname=runtime.JRE_DIR+'/x'
                else:
                    member.size=1
                tar.addfile(member,io.BytesIO(b'x') if kind=='file' else None)
            dest = self.root/f'extract-{i}'
            with self.subTest(name=name), self.assertRaises(GateError):
                runtime.safe_extract(archive,dest)
            self.assertFalse(dest.exists())

    def test_archive_symlink_ancestor_rejected(self):
        archive = self.root/'ancestor.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,kind,target in [(runtime.JRE_DIR,'dir',None),(runtime.JRE_DIR+'/real','dir',None),
                    (runtime.JRE_DIR+'/link','link','real'),(runtime.JRE_DIR+'/link/file','file',None)]:
                member=tarfile.TarInfo(name)
                if kind=='dir':member.type=tarfile.DIRTYPE
                elif kind=='link':member.type=tarfile.SYMTYPE;member.linkname=target
                else:member.size=1
                tar.addfile(member,io.BytesIO(b'x') if kind=='file' else None)
        with self.assertRaisesRegex(GateError,'symlink ancestor'):
            runtime.safe_extract(archive,self.root/'extracted')

    def test_archive_safe_relative_notice_link(self):
        archive=self.root/'safe.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            member=tarfile.TarInfo(runtime.JRE_DIR+'/legal/LICENSE'); member.size=7
            tar.addfile(member,io.BytesIO(b'license'))
            member=tarfile.TarInfo(runtime.JRE_DIR+'/legal/alias');member.type=tarfile.SYMTYPE;member.linkname='LICENSE'
            tar.addfile(member)
        dest=runtime.safe_extract(archive,self.root/'safe-extraction')
        self.assertEqual((dest/'legal/alias').read_text(),'license')

    def test_path_and_symlink_escape(self):
        with self.assertRaises(GateError):safe_path(self.root/'../escape',self.root)
        link=self.root/'link';link.symlink_to(self.before,target_is_directory=True)
        with self.assertRaisesRegex(GateError,'symlink'):safe_path(link/'synthetic.kicad_pcb')

    def test_no_run_overwrite_or_path_ids(self):
        with patch.object(cli,'STATE',self.root):
            cli.new_run('existing')
            with self.assertRaisesRegex(GateError,'overwrite'):cli.new_run('existing')
            for value in ['../outside','/absolute','modules/base']:
                with self.subTest(value=value),self.assertRaises(GateError):cli.new_run(value)

    def test_missing_native_api(self):
        with self.assertRaisesRegex(GateError,'API unavailable'):
            native.NativeAdapter(SimpleNamespace())

    def test_failed_native_export_uses_two_argument_binding(self):
        self.api.ExportSpecctraDSN.return_value=False
        output=self.root/'new.dsn'
        with self.assertRaisesRegex(GateError,'export failed'):self.adapter.export(self.pcb,output)
        self.api.ExportSpecctraDSN.assert_called_once_with(self.board,str(output))
        self.assertFalse(output.exists())

    def test_export_never_overwrites(self):
        with self.assertRaisesRegex(GateError,'overwrite'):self.adapter.export(self.pcb,self.dsn)
        self.api.ExportSpecctraDSN.assert_not_called()

    def test_failed_native_import_never_saves(self):
        self.api.ImportSpecctraSES.return_value=False
        with patch.object(native,'live_snapshot',return_value={'placement':'unchanged'}):
            with self.assertRaisesRegex(GateError,'import failed'):self.imported()
        self.api.ImportSpecctraSES.assert_called_once_with(self.board,str(self.ses))
        self.api.SaveBoard.assert_not_called();self.assertFalse(self.candidate.exists())

    def test_candidate_never_overwrites(self):
        self.candidate.parent.mkdir();self.candidate.write_text('existing')
        with self.assertRaisesRegex(GateError,'overwrite'):self.imported()
        self.api.ImportSpecctraSES.assert_not_called()

    def test_malformed_empty_and_unclosed_ses(self):
        for data in ['', '(session input-unit', '(session "unterminated)', '(pcb not-a-session)']:
            self.ses.write_text(data);self.association['ses_sha256']=digest(self.ses)
            with self.subTest(data=data),self.assertRaises(GateError):
                validate_session(self.dsn,self.ses,self.association,self.source)

    def test_stale_source_and_session_bytes(self):
        with self.assertRaisesRegex(GateError,'stale source'):
            validate_session(self.dsn,self.ses,self.association,{'changed':'source'})
        self.ses.write_text(self.ses.read_text()+'\n')
        with self.assertRaisesRegex(GateError,'stale SES'):
            validate_session(self.dsn,self.ses,self.association,self.source)

    def test_stale_dsn_and_headers(self):
        self.dsn.write_text(self.dsn.read_text()+'\n')
        with self.assertRaisesRegex(GateError,'stale DSN'):
            validate_session(self.dsn,self.ses,self.association,self.source)
        self.association['dsn_sha256']=digest(self.dsn)
        self.ses.write_text('(session other (base_design other) (routes))')
        self.association['ses_sha256']=digest(self.ses)
        with self.assertRaisesRegex(GateError,'header mismatch'):
            validate_session(self.dsn,self.ses,self.association,self.source)
        self.ses.write_text('(session input-unit (base_design input-unit) (routes))')
        self.association['ses_sha256']=digest(self.ses)
        self.dsn.write_text('(pcb "stale-header" (wiring))');self.association['dsn_sha256']=digest(self.dsn)
        with self.assertRaisesRegex(GateError,'stale DSN header'):
            validate_session(self.dsn,self.ses,self.association,self.source)

    def test_stale_exported_board(self):
        self.pcb.write_text('changed')
        with self.assertRaisesRegex(GateError,'stale exported PCB'):self.imported()
        self.api.ImportSpecctraSES.assert_not_called()

    def test_changed_project_rules_rejected_before_import(self):
        self.pcb.with_suffix('.kicad_dru').write_text('(version 1)')
        with self.assertRaisesRegex(GateError,'stale project/rules'):self.imported()
        self.api.ImportSpecctraSES.assert_not_called()

    def test_unsupported_rule_or_weakened_project_rejected_at_load(self):
        adapter=native.NativeAdapter(self.api)
        self.pcb.with_suffix('.kicad_dru').write_text('(version 1)')
        with self.assertRaisesRegex(GateError,'custom rules'):adapter.load(self.pcb)
        self.pcb.with_suffix('.kicad_dru').write_text(fixture.RULES)
        data=fixture.project();data['board']['design_settings']['rules']['min_clearance']=0.01
        self.pcb.with_suffix('.kicad_pro').write_text(json.dumps(data))
        with self.assertRaisesRegex(GateError,'project constraints'):adapter.load(self.pcb)

    def test_import_changed_placement_nets_rules_locked_and_branches(self):
        before={'footprints_pads_nets':['fixed-placement/netmap'], 'native_rules':{'width':250000},
                'locked_copper':['uuid/width/layer/drill'], 'all_protected_net_copper':['locked']}
        self.api.ImportSpecctraSES.return_value=True
        for key in before:
            after=copy.deepcopy(before);after[key]=['changed']
            with self.subTest(key=key),patch.object(native,'live_snapshot',side_effect=[before,after]):
                with self.assertRaisesRegex(GateError,'invariant changed'):self.imported()
        self.api.SaveBoard.assert_not_called()

    def test_zone_fills_can_change_but_definitions_cannot(self):
        a=self.root/'a.kicad_pcb';b=self.root/'b.kicad_pcb'
        a.write_text('(kicad_pcb (setup (aux_axis_origin 1 2)) (zone (net GND) (thermal_gap 0.3) (filled_polygon old)))')
        b.write_text(a.read_text().replace('old','new'))
        assert_same(native.saved_definitions(a),native.saved_definitions(b))
        b.write_text(b.read_text().replace('0.3','0.1'))
        with self.assertRaisesRegex(GateError,'zone_keepout'):assert_same(native.saved_definitions(a),native.saved_definitions(b))

    def report(self):
        pairs=[['J1pad2','J2pad3'],['J1pad3','J2pad2']]
        return {'$schema':'https://schemas.kicad.org/drc.v1.json','ignored_checks':[],
                'included_severities':['error','warning','exclusion'],'violations':[], 'schematic_parity':[],
                'unconnected_items':[{'type':'unconnected_items','severity':'error',
                    'items':[{'uuid':fixture.uid(n)} for n in pair]} for pair in pairs]}

    def test_drc_planned_opens_only(self):
        data=self.report();self.assertEqual(cli.drc_gate(data,True)['opens'],2)
        data['unconnected_items'][0]['items'][0]['uuid']='not-a-planned-pad'
        with self.assertRaisesRegex(GateError,'planned ordinary'):cli.drc_gate(data,True)

    def test_drc_warnings_parity_opens_exclusions_and_ignored_checks(self):
        initial=self.report()
        for key in ['violations','schematic_parity','unconnected_items','ignored_checks']:
            data=self.report();data['unconnected_items']=[];data[key]=[{'severity':'warning'}]
            with self.subTest(key=key),self.assertRaises(GateError):cli.drc_gate(data,False,initial)
        data=self.report();data['included_severities']=['error']
        with self.assertRaisesRegex(GateError,'every severity'):cli.drc_gate(data,True)

    def test_mocked_process_timeout_blocks_routing(self):
        self.ses.unlink()
        rec={'failure':'timeout','returncode':-9}
        with patch.object(sandbox,'java_command',return_value=['mock-java']),patch.object(sandbox,'run_process',return_value=rec) as process:
            with self.assertRaisesRegex(GateError,'timeout'):
                sandbox.route(self.root,runtime.RUNTIME/'java',runtime.RUNTIME/'jar',1)
            self.assertEqual(process.call_args.args[-1],1)

    def test_unknown_flags_fail_even_with_zero_exit(self):
        logs=self.root/'logs';logs.mkdir()
        (logs/'mock.stdout.log').write_text('Freerouting v2.5.0\nAnalytics are disabled\nUnknown settings property: router.wrong\n')
        (logs/'mock.stderr.log').write_text('')
        with self.assertRaisesRegex(GateError,'ignored a setting'):sandbox.validate_logs(self.root,'mock')

    def test_real_bounded_process_preserves_stderr_and_kills_timeout(self):
        rec=run_process(['/usr/bin/python3','-u','-c',
            'import sys,time;print("started");print("binding warning",file=sys.stderr);time.sleep(2)'],
            self.root/'logs','timeout',0.15)
        self.assertEqual(rec['failure'],'timeout')
        self.assertIn('binding warning',(self.root/'logs/timeout.stderr.log').read_text())
        self.assertTrue((self.root/'logs/timeout.process.json').is_file())

    def test_no_log_overwrite(self):
        logs=self.root/'logs';logs.mkdir();(logs/'existing.stdout.log').write_text('evidence')
        with patch('safety.subprocess.Popen') as process:
            with self.assertRaisesRegex(GateError,'overwrite'):run_process(['mock'],logs,'existing')
            process.assert_not_called()

    def test_smoke_missing_runtime_keeps_honest_evidence_without_network(self):
        with patch.object(cli,'STATE',self.root),patch.object(runtime,'validate_runtime',side_effect=GateError('runtime missing')),patch.object(runtime,'download') as download:
            result=cli.smoke('no-runtime',1)
            self.assertEqual(result['status'],'failed');self.assertFalse(result['production_ready'])
            self.assertTrue((self.root/'runs/no-runtime/run.json').is_file());download.assert_not_called()

    def test_smoke_cli_refuses_arbitrary_board_inputs(self):
        with patch.object(cli,'smoke') as smoke,patch('sys.stderr',new=io.StringIO()):
            with self.assertRaises(SystemExit) as exc:cli.main(['smoke','--board','modules/base/real.kicad_pcb'])
            self.assertEqual(exc.exception.code,2);smoke.assert_not_called()


if __name__=='__main__':
    unittest.main()
