"""Stdlib-only schema, identity, path and transaction-precondition tests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import api
import schema
from fixtures import uid, operations, text_op


class SchemaTests(unittest.TestCase):
    def test_valid_operations_and_copy_isolation(self):
        doc=operations(text_op()); result=schema.validate(doc); result['operations'][0]['text']='changed'
        self.assertEqual(doc['operations'][0]['text'],'SYNTHETIC')

    def test_numeric_and_schema_types(self):
        for value in (True,float('nan'),float('inf'),'1',1001,0.0000001):
            with self.subTest(value=value):
                doc=operations(text_op()); doc['operations'][0]['at'][0]=value
                with self.assertRaises((api.Error,ValueError)): schema.validate(doc)
        for version in (True,1.0,2,'1'):
            doc=operations(text_op()); doc['schema_version']=version
            with self.assertRaises(api.Error): schema.validate(doc)

    def test_unknown_fields_everywhere(self):
        for op in ({**text_op(),'surprise':0},{'op':'move_footprint','target':{'ref':'R1','hidden':1},'at':[0,0]},
                   {'op':'add_polyline','uuid':uid('p'),'net':'N','layer':'F.Cu','width_mm':0.2,'start':{'pad':{'ref':'R1','number':'1','hidden':1}},'end':{'uuid':uid('e')}}):
            with self.assertRaises(api.Error): schema.validate(operations(op))
        doc=operations(text_op()); doc['more']=[]
        with self.assertRaises(api.Error): schema.validate(doc)

    def test_duplicate_json_keys_and_nonfinite(self):
        for text in ('{"schema_version":1,"schema_version":1,"operations":[]}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(api.Error): schema.loads(text)

    def test_uuid_refs_and_duplicates(self):
        for ident in ('bad','00000000-0000-0000-0000-000000000000',uid('upper').upper()):
            op=text_op(); op['uuid']=ident
            with self.assertRaises(api.Error): schema.validate(operations(op))
        with self.assertRaises(api.Error): schema.validate(operations(text_op(),text_op()))
        for ref in ('R?','R 1','../R1',''):
            with self.assertRaises(api.Error): schema.validate(operations({'op':'move_footprint','target':{'ref':ref},'at':[0,0]}))

    def test_geometry_and_bounds(self):
        for poly in ([[0,0],[1,1],[0,1],[1,0]], [[0,0],[1,0],[2,0]], [[0,0],[1,0],[1,1],[0,0]]):
            with self.assertRaises(api.Error): schema.validate(operations({'op':'add_outline','uuid':uid('edge'),'polygon':poly,'width_mm':0.05}))
        with self.assertRaises(api.Error): schema.validate(operations({'op':'add_via','uuid':uid('via'),'at':[0,0],'net':'N','diameter_mm':0.3,'drill_mm':0.3}))
        with self.assertRaises(api.Error): schema.validate({'schema_version':1,'operations':[text_op(str(i)) for i in range(257)]})
        schema.validate(operations({'op':'add_outline','uuid':uid('edge'),'polygon':[[0,0],[2,0],[2,2],[0,2]],'width_mm':0.05}))

    def test_no_deferred_operations(self):
        for op in ('add_arc','lock','unlock','eval','set','move_symbol','auto_place'):
            with self.assertRaises(api.Error): schema.validate(operations({'op':op}))

    def test_relative_footprint_and_strict_mechanical(self):
        op={'op':'add_footprint','uuid':uid('fp'),'file':'part.kicad_mod','mechanical_only':True,'at':[0,0],'rotation_deg':0,'side':'back'}
        with self.assertRaises(api.Error): schema.validate(operations(op))
        self.assertTrue(Path(schema.validate(operations(op),'/tmp')['operations'][0]['file']).is_absolute())
        op['file']='child/../part.kicad_mod'
        self.assertEqual(schema.validate(operations(op),'/tmp')['operations'][0]['file'],'/tmp/part.kicad_mod')
        for key,value in [('pad_nets',{}),('reference','M1')]:
            with self.assertRaises(api.Error): schema.validate(operations({**op,key:value}),'/tmp')

    def test_deterministic_uuid_generation(self):
        self.assertEqual(schema.child_uuid(uid('fp'),1),schema.child_uuid(uid('fp'),1))
        self.assertNotEqual(schema.child_uuid(uid('fp'),1),schema.child_uuid(uid('fp'),2))


class IdentityTests(unittest.TestCase):
    def test_compare_identities_not_totals(self):
        report=lambda ident:{'violations':[{'type':'shorting_items','severity':'error','description':'short','items':[{'uuid':ident}]}],'unconnected_items':[],'schematic_parity':[]}
        left=api._identities(report(uid('a')),'drc'); right=api._identities(report(uid('b')),'drc')
        delta=api.compare_findings(left,right)
        self.assertEqual(len(delta['added']),1); self.assertEqual(len(delta['removed']),1); self.assertEqual(delta['retained'],[])

    def test_unknown_report_never_passes(self):
        for report in ({},{'violations':[]}, {'violations':[{}],'unconnected_items':[],'schematic_parity':[]}):
            with self.assertRaises(api.Error): api._identities(report,'drc')

    def test_apply_tamper_fails_before_any_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'candidate'
            doc={'schema_version':1,'kind':'pcb_edit_plan','operations':operations(text_op()),'preconditions':{},'changes':{},'source_writes':False,'status':'planned_not_checked','caveats':[],'native_diagnostics':{},'plan_sha256':'bad'}
            with self.assertRaises(api.Error): api.apply(doc,output)
            self.assertFalse(output.exists())

    def test_new_output_rejects_collision_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); (path/'used').mkdir(); (path/'alias').symlink_to(path/'used',target_is_directory=True)
            for target in (path/'used',path/'alias'/'child'):
                with self.assertRaises(api.Error): api.project.new_output(target)


if __name__=='__main__': unittest.main()
