"""Native API is unavailable offline; fake only that boundary, exercise workflow logic."""
import copy
import json
import unittest
from unittest.mock import patch
from test_entertainment import e, vs, server, commands, ROOT


class DistributorTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.doc=str(ROOT/'tests'/'Scratch.vwx')
        vs.GetFPathName.return_value=self.doc
        self.objects={'sym':16,'d':86,'a':86,'b':86,'layer':31,'class':94}
        self.names={'sym':'Library Twofer','d':'D1','layer':'Power','class':'Power-Devices'}
        self.pios={'d':'DistributorObject','a':'ElectricComponent_Input','b':'ElectricComponent_Output'}
        self.values={'d':{'Symbol':'Library Twofer','ID':'D1','Name':'Twofer','Location':'Power'},
                     'a':{'Name':'Input','Connector':'NEMA 5-15','Internal_ID':'internal-a','Connections':'[]'},
                     'b':{'Name':'Output','Connector':'NEMA 5-15','Internal_ID':'internal-b','Connections':'[]'}}
        vs.GetObjectByUuid.side_effect=lambda x:x if x in self.objects else None
        vs.GetObject.side_effect=lambda n:next((h for h,v in self.names.items() if v==n),None)
        vs.GetTypeN.side_effect=lambda h:self.objects[h]
        vs.GetName.side_effect=lambda h:self.pios[h[2:]] if str(h).startswith('r:') else self.names.get(h,h)
        vs.GetParametricRecord.side_effect=lambda h:'r:'+h if h in self.pios else None
        vs.GetRField.side_effect=lambda h,p,k:self.values.get(h,{}).get(k,'')
        vs.GetObjectUuid.side_effect=lambda h:h
        vs.FInSymDef.side_effect=lambda h:'a' if h=='sym' else None
        vs.NextObj.side_effect=lambda h:'b' if h=='a' else None
        vs.FInGroup.return_value=None
        vs.GetLayer.return_value='layer';vs.GetLName.return_value='Power';vs.GetClass.return_value='Power-Devices'
        vs.GetObjectVariableInt.return_value=1
        vs.GetEntityMatrix.return_value=(True,(0,0,0),0,0,0)

    def invoke(self, name, params):
        self.assertIn(name,e.COMMANDS,'New distributor workflow must be registered')
        return e.COMMANDS[name](params)

    def item(self,**changes):
        return dict(name='new',layer='Power',**{'class':'Power-Devices'},position=[0,0,0],
                    symbol='Library Twofer',device_id='QA-D2',**changes)

    def test_library_definition_and_instance_keep_geometry_and_internal_ids_separate(self):
        r=self.invoke('get_distributor_inspection',{'object_ids':['sym','d'],'detail':'components'})
        self.assertEqual(r['status'],'ok',r)
        for obj in r['objects']:
            self.assertEqual(obj['component_count'],2)
            self.assertEqual(obj['type_counts'],{'input':1,'output':1})
            self.assertEqual(obj['components'][0]['geometry_id'],'a')
            self.assertEqual(obj['components'][0]['stored_internal_id'],'internal-a')
        self.assertFalse(r['external_connections_verified'])
        vs.ResetObject.assert_not_called();vs.SetRField.assert_not_called()

    def test_limit_preserves_total_and_changed_library_invalidates_fingerprint(self):
        p={'object_ids':['d'],'detail':'components','limit':1}
        first=self.invoke('get_distributor_inspection',p)['objects'][0]
        self.assertEqual(first['component_count'],2);self.assertTrue(first['components_truncated'])
        self.values['b']['Connector']='other'
        second=self.invoke('get_distributor_inspection',p)['objects'][0]
        self.assertNotEqual(first['symbol_fingerprint'],second['symbol_fingerprint'])

    def test_repeated_internal_ids_are_reported_not_repaired(self):
        self.values['b']['Internal_ID']='internal-a'
        row=self.invoke('get_distributor_inspection',{'object_ids':['sym']})['objects'][0]
        self.assertEqual(row['identity_issues'][0]['issue'],'duplicate_internal_id')
        vs.SetRField.assert_not_called()

    def test_cycle_and_missing_symbol_are_explicit_failures(self):
        vs.NextObj.side_effect=lambda h:'a'
        row=self.invoke('get_distributor_inspection',{'object_ids':['d']})['objects'][0]
        self.assertEqual(row['inspection_status'],'error')
        self.values['d']['Symbol']='missing'
        row=self.invoke('get_distributor_inspection',{'object_ids':['d']})['objects'][0]
        self.assertEqual(row['inspection_status'],'error')

    def test_creation_wrong_document_and_private_fields_fail_before_mutation(self):
        for p in [dict(expected_document=self.doc+'x',items=[self.item()]),
                  dict(expected_document=self.doc,items=[self.item(fields={'InputUUID':'bad'})])]:
            self.assertEqual(self.invoke('create_distributors',p)['status'],'error')
        vs.CreateCustomObjectN.assert_not_called()

    def test_second_invalid_item_rejects_entire_creation_batch(self):
        p=dict(expected_document=self.doc,items=[self.item(),dict(self.item(),name='second',symbol='missing')])
        self.assertEqual(self.invoke('create_distributors',p)['status'],'error')
        vs.CreateCustomObjectN.assert_not_called()

    def test_creation_receipt_survives_native_failure_and_restores_context(self):
        vs.CreateCustomObjectN.side_effect=RuntimeError('native insertion failed')
        r=self.invoke('create_distributors',dict(expected_document=self.doc,items=[self.item()]))
        self.assertEqual(r['status'],'error');self.assertIn('created',r)
        self.assertFalse(r['retry_safe']);vs.PopAttrs.assert_called_once()

    def test_success_requires_separate_readback_of_native_symbol_geometry(self):
        self.names.pop('d')
        vs.CreateCustomObjectN.return_value='d'
        vs.SetEntityMatrixN.return_value=True
        vs.SetName.side_effect=lambda h,n:self.names.update({h:n})
        vs.SetRField.side_effect=lambda h,p,k,v:self.values.setdefault(h,{}).update({k:v})
        r=self.invoke('create_distributors',dict(expected_document=self.doc,items=[self.item()]))
        self.assertEqual(r['status'],'ok',r);self.assertTrue(r['requires_verification'])
        check=dict(expected_document=self.doc,created=r['created'])
        self.assertFalse(self.invoke('get_distributor_verification',check)['verified'])
        self.objects['generated']=15
        vs.FInGroup.side_effect=lambda h:'generated' if h=='d' else None
        vs.GetSymName.return_value='Library Twofer'
        self.assertTrue(self.invoke('get_distributor_verification',check)['verified'])
        self.assertEqual(vs.CreateCustomObjectN.call_count,1)

    def test_existing_device_id_collision_is_case_insensitive(self):
        vs.ForEachObject.side_effect=lambda f,c:f('d')
        item=self.item();item['device_id']='d1'
        r=self.invoke('create_distributors',dict(expected_document=self.doc,items=[item]))
        self.assertEqual(r['status'],'error');vs.CreateCustomObjectN.assert_not_called()

    def test_missing_internal_id_is_preserved_as_review_issue_not_rewritten(self):
        self.values['a']['Internal_ID']=''
        self.names.pop('d');vs.CreateCustomObjectN.return_value='d';vs.SetEntityMatrixN.return_value=True
        r=self.invoke('create_distributors',dict(expected_document=self.doc,items=[self.item()]))
        self.assertEqual(r['status'],'ok',r)
        self.assertEqual(r['created'][0]['identity_issues'][0]['issue'],'missing_internal_id')
        self.assertFalse(any(c.args[2]=='Internal_ID' for c in vs.SetRField.call_args_list))

    def test_native_insertion_cannot_silently_change_requested_rotation(self):
        self.names.pop('d');vs.CreateCustomObjectN.return_value='d';vs.SetEntityMatrixN.return_value=True
        vs.GetEntityMatrix.return_value=(True,(0,0,0),0,0,45)
        r=self.invoke('create_distributors',dict(expected_document=self.doc,items=[self.item()]))
        self.assertEqual(r['status'],'error',r);self.assertEqual(r['created'][0]['object_id'],'d')

    def test_stale_verification_is_readonly_and_does_not_recreate(self):
        receipt=dict(object_id='d',name='D1',layer='Power',**{'class':'Power-Devices'},
                     matrix=[True,[0,0,0],0,0,0],symbol='Library Twofer',symbol_fingerprint='old',
                     fields=copy.deepcopy(self.values['d']))
        r=self.invoke('get_distributor_verification',dict(expected_document=self.doc,created=[receipt]))
        self.assertFalse(r['verified']);vs.ResetObject.assert_not_called();vs.CreateCustomObjectN.assert_not_called()

    def test_event_boundary_rejects_batch_before_prior_mutation(self):
        with patch.object(commands,'draw_rectangle') as draw:
            r=commands._batch({'calls':[{'command':'draw_rectangle'},{'command':'create_distributors'}]})
        self.assertEqual(r.get('code'),'VM_EVENT_BOUNDARY_REQUIRED');draw.assert_not_called()

    def test_server_preserves_creation_receipt_when_verification_times_out(self):
        connection=type('Connection',(),{})()
        from unittest.mock import Mock
        connection.send_command=Mock(side_effect=[{'status':'ok','created':[{'object_id':'new'}],'requires_verification':True},TimeoutError('pending')])
        with patch.object(server,'get_vwx_connection',return_value=connection):
            r=json.loads(server.cmd('create_distributors',{'expected_document':self.doc}))
        self.assertEqual(r['status'],'error');self.assertEqual(r['created'][0]['object_id'],'new')
        self.assertEqual(r['recovery_command'],'get_distributor_verification');self.assertFalse(r['retry_safe'])
