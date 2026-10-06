"""Opt-in KiCad 10.0 synthetic fixtures, generated exclusively under TemporaryDirectory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import api
from fixtures import fixture, hashes, operations, text_op, uid


@unittest.skipUnless(os.environ.get('KICAD_AUTOMATION_INTEGRATION')=='1', 'set KICAD_AUTOMATION_INTEGRATION=1 with matching pcbnew/CLI 10.0')
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='PCB API synthetic '); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        env=patch.dict(os.environ,HOME=str(self.root/'home'),XDG_CONFIG_HOME=str(self.root/'config'),XDG_CACHE_HOME=str(self.root/'cache')); env.start(); self.addCleanup(env.stop)

    def build(self,**kwargs):
        self.source,self.pretty=fixture(self.root,**kwargs); self.before=hashes(self.source)
        return self.source

    def execute(self,doc,draft=False,name='Candidate'):
        planned=api.plan(doc,project_dir=self.source,allow_draft_opens=draft)
        self.assertEqual(hashes(self.source),self.before)
        self.assertEqual(planned['plan_sha256'],api.plan(doc,project_dir=self.source,allow_draft_opens=draft)['plan_sha256'])
        result=api.apply(planned,self.root/name)
        self.assertTrue(result['source_unchanged']); self.assertEqual(hashes(self.source),self.before)
        if result['status'] in ('accepted','draft'): self.assertTrue((self.root/name/'completion.json').is_file())
        else: self.assertFalse((self.root/name/'completion.json').exists())
        return result

    def assert_status(self,result,status):
        self.assertEqual(result['status'],status,json.dumps({'status':result['status'],'errors':result['errors'],'findings':[(kind,[(v['category'],v['identity']['type'],v['identity'].get('description')) for v in values]) for kind,values in result.get('checks',{}).get('findings',{}).items()]},indent=2))

    def test_text_clean_candidate_and_relocation(self):
        self.build(external=True)
        before=hashes(self.root); result=self.execute(operations(text_op()))
        self.assert_status(result,'accepted'); self.assertTrue(result['checks']['parity']['equal'])
        self.assertIn('assert',next(c['stderr'] for c in result['commands'] if '_worker.py' in ' '.join(c['command'])))
        candidate=self.root/'Candidate'; relocated=self.root/'Moved with spaces'; shutil.move(candidate,relocated)
        # Remove input dependencies to prove bindings do not reach the source.
        shutil.rmtree(self.source); shutil.rmtree(self.pretty); shutil.rmtree(self.root/'External symbol library')
        info=api.inspect(project_dir=(relocated/result['board']).parent)
        self.assertTrue(any(i.get('text')=='SYNTHETIC' for i in info['items']))
        logs=[]; checked,_=api._checks(api.executable('kicad-cli'),relocated/result['board'],relocated/result['schematic'],self.root/'relocated checks',api.isolated_env(self.root/'verify runtime'),logs,False)
        self.assertEqual(checked['findings'],{'erc':[],'drc':[]}); self.assertTrue(checked['parity']['equal'])

    def test_transform_both_sides_pad_identity_and_copper_unchanged(self):
        self.build()
        initial=api.inspect(project_dir=self.source)['items']
        for side in ('back','front'):
            ops=operations({'op':'flip_footprint','target':{'ref':'R1'},'side':'back'}, {'op':'move_footprint','target':{'uuid':uid('R1item')},'at':[20,23]}, {'op':'rotate_footprint','target':{'ref':'R1'},'rotation_deg':90}, {'op':'flip_footprint','target':{'ref':'R1'},'side':side})
            result=self.execute(ops,True,name='transform '+side); self.assert_status(result,'draft')
            after=result['inspection']['items']; fp=next(i for i in after if i['kind']=='footprint' and i['reference']=='R1')
            self.assertEqual(fp['side'],side); self.assertEqual(fp['at'],[20,23])
            self.assertEqual({i['uuid']:(i['number'],i['net']) for i in initial if i['kind']=='pad'}, {i['uuid']:(i['number'],i['net']) for i in after if i['kind']=='pad'})
            self.assertEqual([i for i in initial if i['kind']=='track'],[i for i in after if i['kind']=='track'])

    def test_route_branch_and_unknown_net_endpoint(self):
        self.build(extra=True)
        route={'op':'add_polyline','uuid':uid('branch'),'net':'SIGNAL','layer':'F.Cu','width_mm':0.25,'start':{'track':uid('route'),'at':[25,20]},'end':{'pad':{'ref':'R3','number':'1'}},'waypoints':[]}
        result=self.execute(operations(route)); self.assert_status(result,'accepted')
        self.assertEqual(len(result['finding_delta']['drc']['removed']),1)
        for bad in ({**route,'net':'MISSING'},{**route,'start':{'track':uid('route'),'at':[25,21]}}):
            with self.assertRaises(api.Error): api.plan(operations(bad),project_dir=self.source)

    def test_via_layer_transition(self):
        self.build(routed=False)
        doc=operations({'op':'add_via','uuid':uid('v1'),'net':'SIGNAL','at':[22,20],'diameter_mm':0.6,'drill_mm':0.3}, {'op':'add_via','uuid':uid('v2'),'net':'SIGNAL','at':[28,20],'diameter_mm':0.6,'drill_mm':0.3},
            {'op':'add_polyline','uuid':uid('to v1'),'net':'SIGNAL','layer':'F.Cu','width_mm':0.25,'start':{'pad':{'ref':'R1','number':'1'}},'end':{'uuid':uid('v1')}},
            {'op':'add_polyline','uuid':uid('bottom'),'net':'SIGNAL','layer':'B.Cu','width_mm':0.25,'start':{'uuid':uid('v1')},'end':{'uuid':uid('v2')}},
            {'op':'add_polyline','uuid':uid('to R2'),'net':'SIGNAL','layer':'F.Cu','width_mm':0.25,'start':{'uuid':uid('v2')},'end':{'pad':{'ref':'R2','number':'1'}}})
        result=self.execute(doc); self.assert_status(result,'accepted')
        self.assertEqual(len([i for i in result['inspection']['items'] if i['kind']=='via']),2)

    def test_zone_fill_and_outline_lines(self):
        self.build(routed=False)
        doc=operations({'op':'add_zone','uuid':uid('z'),'net':'SIGNAL','layer':'F.Cu','polygon':[[15,15],[35,15],[35,30],[15,30]],'clearance_mm':0.2,'min_thickness_mm':0.25})
        result=self.execute(doc); self.assert_status(result,'accepted')
        self.assertIn('(filled_polygon',(self.root/'Candidate'/result['board']).read_text())
        # Add outline on a fixture with its original rectangle removed synthetically.
        import pcbnew as p
        board=p.LoadBoard(str(self.source/'synthetic.kicad_pcb'))
        for item in list(board.GetDrawings()): board.Remove(item)
        p.SaveBoard(str(self.source/'synthetic.kicad_pcb'),board,True); self.before=hashes(self.source)
        shape={'op':'add_outline','uuid':uid('new outline'),'polygon':[[10,10],[40,10],[40,35],[10,35]],'width_mm':0.05}
        result=self.execute(operations(shape),True,name='Outline'); self.assert_status(result,'draft')
        self.assertEqual(len([i for i in result['inspection']['items'] if i['kind']=='edge_line']),4)

    def test_electrical_addition_and_mechanical_only(self):
        self.build(missing=True)
        op={'op':'add_footprint','uuid':uid('add R2'),'file':str(self.pretty/'R.kicad_mod'),'mechanical_only':False,'reference':'R2','value':'synthetic','footprint_id':'Auto:R','symbol_path':'/'+uid('schematic')+'/'+uid('R2'),'pad_nets':{'1':'SIGNAL'},'at':[30,20],'rotation_deg':0,'side':'front'}
        route={'op':'add_polyline','uuid':uid('new route'),'net':'SIGNAL','layer':'F.Cu','width_mm':0.25,'start':{'pad':{'ref':'R1','number':'1'}},'end':{'pad':{'ref':'R2','number':'1'}}}
        result=self.execute(operations(op,route)); self.assert_status(result,'accepted')
        # A board-only empty mechanical template is explicitly non-electrical.
        mech=self.pretty/'Mechanic.kicad_mod'; mech.write_text('(footprint "Mechanic" (version 20241229) (generator "pcbnew") (layer "F.Cu") (attr board_only))'); self.before=hashes(self.source)
        op={'op':'add_footprint','uuid':uid('mechanic'),'file':str(mech),'mechanical_only':True,'at':[15,15],'rotation_deg':20,'side':'back'}
        result=self.execute(operations(op),True,name='Mechanical'); self.assert_status(result,'rejected')  # original missing R2 parity must NEVER be waived
        bad={**op,'file':str(self.pretty/'R.kicad_mod')}
        with self.assertRaises(api.Error): api.plan(operations(bad),project_dir=self.source)

    def test_cli_config_operations_hashes_and_draft_exit(self):
        self.build()
        requests=self.root/'Requests'; requests.mkdir(); profiles=self.root/'Profiles'; profiles.mkdir(); plans=self.root/'Plans'; plans.mkdir()
        config=profiles/'project.json'; config.write_text(json.dumps({'schema_version':1,'project_dir':'../Synthetic source','board':'../Synthetic source/synthetic.kicad_pcb','root_schematic':'../Synthetic source/synthetic.kicad_sch'}))
        ops=requests/'ops.json'; ops.write_text(json.dumps(operations({'op':'delete_item','uuid':uid('route'),'expected_kind':'track'})))
        script=Path(api.HERE)/'run.py'
        def cli(*args):
            return subprocess.run([sys.executable,'-B',str(script),*map(str,args)],cwd=self.root,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=180)
        inspected=cli('inspect','--config',config); self.assertEqual(inspected.returncode,0,inspected.stdout+inspected.stderr)
        planned=cli('plan','--config',config,'--ops',ops,'--allow-draft-opens'); self.assertEqual(planned.returncode,0,planned.stdout+planned.stderr)
        plan_file=plans/'edit.json'; plan_file.write_text(planned.stdout)
        applied=cli('apply','--plan',plan_file,'--output',self.root/'CLI candidate'); self.assertEqual(applied.returncode,1,applied.stdout+applied.stderr)
        self.assertEqual(json.loads(applied.stdout)['status'],'draft'); self.assertEqual(hashes(self.source),self.before)
        ops.write_text(ops.read_text()+' ')
        stale=cli('apply','--plan',plan_file,'--output',self.root/'CLI stale'); self.assertEqual(stale.returncode,2)
        self.assertIn('Stale input hash',stale.stdout); self.assertFalse((self.root/'CLI stale').exists())

    def test_hierarchical_schematic_rebinding_and_native_parity(self):
        self.build(hierarchical=True)
        result=self.execute(operations(text_op())); self.assert_status(result,'accepted')
        self.assertEqual(len(result['path_rebindings']),3)
        candidate=self.root/'Candidate'; relocated=self.root/'Hierarchy moved'; shutil.move(candidate,relocated)
        shutil.rmtree(self.source); shutil.rmtree(self.root/'External sheets')
        logs=[]; checked,_=api._checks(api.executable('kicad-cli'),relocated/result['board'],relocated/result['schematic'],self.root/'Hierarchy checks',api.isolated_env(self.root/'Hierarchy runtime'),logs,False)
        self.assertTrue(checked['parity']['equal']); self.assertEqual(checked['findings'],{'erc':[],'drc':[]})

    def test_mechanical_and_single_edge_line_additions(self):
        self.build()
        mech=self.pretty/'Mechanic.kicad_mod'; mech.write_text('(footprint "Mechanic" (version 20241229) (generator "pcbnew") (layer "F.Cu") (attr board_only))'); self.before=hashes(self.source)
        op={'op':'add_footprint','uuid':uid('mech clean'),'file':str(mech),'mechanical_only':True,'at':[15,15],'rotation_deg':20,'side':'back'}
        result=self.execute(operations(op)); self.assert_status(result,'accepted')
        self.assertTrue(any(i['uuid']==op['uuid'] and i['side']=='back' and i['reference']=='' for i in result['inspection']['items']))
        # A single detached edge cannot form a valid outline; native shape gate rejects it.
        line={'op':'add_edge_line','uuid':uid('stray edge'),'start':[12,12],'end':[13,12],'width_mm':0.05}
        result=self.execute(operations(line),True,name='Edge rejection'); self.assert_status(result,'rejected')

    def test_uuid_collisions_duplicate_additions_and_parity_mismatch(self):
        self.build(different_net=True)
        self.before=hashes(self.source)
        collide=text_op(); collide['uuid']=uid('R1item')
        with self.assertRaises(api.Error): api.plan(operations(collide),project_dir=self.source)
        op={'op':'add_footprint','uuid':uid('duplicate'),'file':str(self.pretty/'R.kicad_mod'),'mechanical_only':False,'reference':'R1','value':'synthetic','footprint_id':'Auto:R','symbol_path':'/'+uid('schematic')+'/'+uid('R1'),'pad_nets':{'1':'SIGNAL'},'at':[20,20],'rotation_deg':0,'side':'front'}
        with self.assertRaises(api.Error): api.plan(operations(op),project_dir=self.source)
        # Allowed named board net, but absent schematic reference: no inference/waiver.
        op.update(reference='R9',uuid=uid('mismatch'),pad_nets={'1':'OTHER'},at=[15,25])
        result=self.execute(operations(op),True,name='Parity failure'); self.assert_status(result,'failed')
        self.assertIn('not in on-board schematic',result['errors'][0])

    def test_locks_nested_groups_and_duplicate_refs(self):
        self.build()
        import pcbnew as p
        path=self.source/'synthetic.kicad_pcb'
        for protection in ('self','child','ancestor'):
            board=p.LoadBoard(str(path)); fp=next(fp for fp in board.GetFootprints() if fp.GetReference()=='R1')
            if protection=='self': fp.SetLocked(True)
            if protection=='child': next(iter(fp.GraphicalItems())).SetLocked(True)
            if protection=='ancestor':
                parent=p.PCB_GROUP(board); parent.SetName('parent'); parent.SetUuid(p.KIID(uid('parent'))); parent.SetLocked(True); board.Add(parent)
                child=p.PCB_GROUP(board); child.SetName('child'); child.SetUuid(p.KIID(uid('group'))); board.Add(child); parent.AddItem(child); child.AddItem(fp)
            p.SaveBoard(str(path),board,True)
            with self.assertRaisesRegex(api.Error,'Locked item or ancestor'): api.plan(operations({'op':'move_footprint','target':{'ref':'R1'},'at':[20,23]}),project_dir=self.source)
            # Generate the next variant without touching any released project.
            shutil.rmtree(self.source); self.source,self.pretty=fixture(self.root)
        # Individual PAD.SetLocked flags are not serialized by this native version.
        # Validate the guard itself in memory, without pretending these are GUI locks.
        import importlib.util
        spec=importlib.util.spec_from_file_location('_synthetic_guard',api.HERE/'_worker.py'); worker=importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
        memory=p.LoadBoard(str(path)); fp=next(fp for fp in memory.GetFootprints() if fp.GetReference()=='R1'); next(iter(fp.Pads())).SetLocked(True)
        with self.assertRaisesRegex(api.Error,'Locked item or ancestor'): worker.perform(memory,operations({'op':'move_footprint','target':{'ref':'R1'},'at':[20,23]}))
        board=p.LoadBoard(str(path)); zone=p.ZONE(board); zone.SetLayer(p.F_Cu); zone.SetNet(board.FindNet('SIGNAL')); zone.SetLocked(True)
        zone.Outline().NewOutline()
        for pt in ([15,15],[35,15],[35,30],[15,30]): zone.Outline().Append(p.VECTOR2I(*(x*1000000 for x in pt)))
        board.Add(zone); p.SaveBoard(str(path),board,True)
        with self.assertRaises(api.Error): api.plan(operations(text_op()),project_dir=self.source)
        board=p.LoadBoard(str(path)); next(fp for fp in board.GetFootprints() if fp.GetReference()=='R2').SetReference('R1'); p.SaveBoard(str(path),board,True)
        with self.assertRaises(api.Error): api.inspect(project_dir=self.source)

    def test_stale_collision_failure_rollback(self):
        self.build(); planned=api.plan(operations(text_op()),project_dir=self.source)
        used=self.root/'used'; used.mkdir()
        with self.assertRaises(api.Error): api.apply(planned,used)
        linked=self.root/'alias'; linked.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(api.Error): api.apply(planned,linked/'output')
        # Inject a native failure AFTER exclusive candidate creation; source unchanged,
        # no success marker, and forensic failure result retained.
        original=api.probe
        def fail_edit(action,*args,**kwargs):
            if action=='edit': raise api.Error('synthetic native failure stderr: assertion preserved')
            return original(action,*args,**kwargs)
        with patch.object(api,'probe',side_effect=fail_edit): result=api.apply(planned,self.root/'Failure')
        self.assert_status(result,'failed'); self.assertFalse((self.root/'Failure'/'completion.json').exists()); self.assertEqual(hashes(self.source),self.before)
        rebind=api._rebind
        def source_link(closure,directory):
            result=rebind(closure,directory)
            target=directory/'inputs'/closure.project.board.relative_to(closure.anchor)
            target.unlink(); os.link(closure.project.board,target)
            return result
        with patch.object(api,'_rebind',side_effect=source_link): linked_result=api.apply(planned,self.root/'Source linked')
        self.assert_status(linked_result,'failed'); self.assertIn('linked/aliased',linked_result['errors'][0]); self.assertEqual(hashes(self.source),self.before)
        # Real failed subprocess (not a mocked status): version probe delegates to
        # the installed CLI, while actual native commands return nonzero + stderr.
        wrapper=self.root/'failing-cli'; native_cli=api.executable('kicad-cli')
        wrapper.write_text('#!'+sys.executable+'\nimport os,sys\nif sys.argv[1:]==["version"]: os.execv('+repr(native_cli)+', ['+repr(native_cli)+',"version"])\nsys.stderr.write("synthetic native command failure\\n")\nsys.exit(42)\n'); wrapper.chmod(0o755)
        failing_plan=api.plan(operations(text_op()),project_dir=self.source,kicad_cli=str(wrapper))
        real_failure=api.apply(failing_plan,self.root/'Real native failure',kicad_cli=str(wrapper))
        self.assert_status(real_failure,'failed'); self.assertEqual(real_failure['commands'][0]['returncode'],42)
        self.assertIn('synthetic native command failure',real_failure['commands'][0]['stderr']); self.assertFalse((self.root/'Real native failure'/'completion.json').exists()); self.assertEqual(hashes(self.source),self.before)
        (self.source/'synthetic.kicad_dru').write_text('(version 1)\n')
        with self.assertRaises(api.Error): api.apply(planned,self.root/'Stale')
        self.assertFalse((self.root/'Stale').exists())

    def test_opens_shorts_and_selected_delete_gates(self):
        self.build()
        delete=operations({'op':'delete_item','uuid':uid('route'),'expected_kind':'track'})
        result=self.execute(delete); self.assert_status(result,'rejected')
        result=self.execute(delete,True,name='Draft'); self.assert_status(result,'draft')
        # An intentional same-net route traversing a foreign-net pad must fail even
        # with draft opens permitted. Same-net endpoints alone are not a clearance gate.
        shutil.rmtree(self.source); self.source,self.pretty=fixture(self.root,different_net=True); self.before=hashes(self.source)
        route={'op':'add_polyline','uuid':uid('short'),'net':'SIGNAL','layer':'F.Cu','width_mm':0.25,'start':{'pad':{'ref':'R1','number':'1'}},'end':{'pad':{'ref':'R2','number':'1'}},'waypoints':[[25,25]]}
        result=self.execute(operations(route),True,name='Short'); self.assert_status(result,'rejected')
        self.assertTrue(any(v['identity']['type'] in ('shorting_items','clearance') for v in result['checks']['findings']['drc']))


if __name__=='__main__': unittest.main()
