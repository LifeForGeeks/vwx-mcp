import copy, json, unittest
from unittest.mock import patch, MagicMock
from test_entertainment import e, vs, ROOT, server, commands


class LightingDocumentationTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.doc=str(ROOT/'tests/Scratch.vwx');vs.GetFPathName.return_value=self.doc
        vs.GetObjectByUuid.side_effect=lambda uid:uid;vs.GetTypeN.return_value=86
        vs.IsLDSchematicViewObj.return_value=False;vs.LDevice_GetCellCount.return_value=1;vs.LDevice_GetAccCount.return_value=0
        self.values={uid:{field:'' for field in e.LIGHTING_DOCUMENTATION.values()} for uid in ('A','B')}
        vs.GetRField.side_effect=lambda h,pn,k:self.values[h].get(k,'protected')
        vs.LDevice_GetParamStr.side_effect=lambda h,c,a,k:self.values[h].get(k,'protected')
        vs.LDevice_GetParamLong.return_value=0
        vs.LDevice_SetParamStr.side_effect=lambda h,c,a,k,v:self.values[h].__setitem__(k,v)
        self.addCleanup(patch.stopall)
        patch.object(e,'plugin',return_value='Lighting Device').start()
        patch.object(e,'validate_fields').start()
        self.base={uid:{'object_id':uid,'name':uid,'layer':'Lighting','class':'LX',
            'matrix':[True,[1,2,3],0,0,0],'hanging_position_id':'truss','fields':{},'accessories':[]} for uid in ('A','B')}
        patch.object(e,'light',side_effect=lambda h:copy.deepcopy(self.base[h])).start()

    def target(self,uid):
        s=e.lighting_documentation_snapshot(uid)
        return {'object_id':uid,'expected_fingerprint':s['fingerprint']}

    def edit(self,items,**kwargs):
        return e.set_lighting_documentation({'expected_document':self.doc,'items':items,**kwargs})

    def test_stale_last_device_prevents_entire_batch(self):
        a=self.target('A'); b=self.target('B');self.values['B']['Channel']='changed'
        r=self.edit([{**a,'values':{'channel':'10'}},{**b,'values':{'channel':'11'}}])
        self.assertEqual(r['status'],'error');vs.LDevice_SetParamStr.assert_not_called()

    def test_parent_only_setters_and_post_event_verification(self):
        r=self.edit([{**self.target('A'),'values':{'channel':'001','color':'L201','purpose':'Wash'}}])
        self.assertTrue(r['requires_verification'])
        for call in vs.LDevice_SetParamStr.call_args_list:self.assertEqual(call.args[1:3],(0,-2))
        verified=e.get_lighting_documentation_verification(json.loads(json.dumps({'expected_document':self.doc,'receipt':r['receipt']})))
        self.assertTrue(verified['verified']);self.assertNotIn('protected',verified['devices'][0])
        self.base['A']['hanging_position_id']='wrong'
        failed=e.get_lighting_documentation_verification({'expected_document':self.doc,'receipt':r['receipt']})
        self.assertEqual(failed['status'],'error')

    def test_raw_worksheet_value_mismatch_is_reported(self):
        r=self.edit([{**self.target('A'),'values':{'channel':'20'}}])
        vs.GetRField.side_effect=lambda h,pn,k:'old' if k=='Channel' else self.values[h].get(k,'protected')
        v=e.get_lighting_documentation_verification({'expected_document':self.doc,'receipt':r['receipt']})
        self.assertIn('Worksheet source record',v['error'])

    def test_numbering_order_padding_increment_and_dry_run(self):
        r=e.number_lighting_devices({'expected_document':self.doc,'items':[self.target('B'),self.target('A')],
            'field':'unit_number','start':7,'increment':2,'prefix':'LX-','padding':3,'dry_run':True})
        self.assertEqual([x['changes']['unit_number'] for x in r['planned']],['LX-007','LX-009'])
        vs.LDevice_SetParamStr.assert_not_called();vs.LDevice_Reset.assert_not_called()

    def test_empty_clearing_and_noop(self):
        self.values['A']['Purpose']='old'
        r=self.edit([{**self.target('A'),'values':{'purpose':''}}]);self.assertEqual(r['changed_field_count'],1)
        vs.LDevice_SetParamStr.reset_mock();vs.LDevice_Reset.reset_mock()
        r=self.edit([{**self.target('A'),'values':{'purpose':''}}]);self.assertEqual(r['changed_field_count'],0)
        vs.LDevice_SetParamStr.assert_not_called();vs.LDevice_Reset.assert_not_called()

    def test_position_patch_and_unknown_fields_cannot_be_written(self):
        for values in ({'Position':'X'},{'dmx_address':'10'},{'channel':2},{'color':'a\x00b'}):
            r=self.edit([{**self.target('A'),'values':values}]);self.assertEqual(r['status'],'error')
        vs.LDevice_SetParamStr.assert_not_called()

    def test_multicell_and_schematic_rejected(self):
        vs.LDevice_GetCellCount.return_value=2
        self.assertEqual(e.get_lighting_documentation({'object_ids':['A']})['status'],'error')
        vs.LDevice_GetCellCount.return_value=1;vs.IsLDSchematicViewObj.return_value=True
        self.assertEqual(e.get_lighting_documentation({'object_ids':['A']})['status'],'error')

    def test_mutation_failure_retains_receipt_without_retry(self):
        a=self.target('A');vs.LDevice_Reset.side_effect=RuntimeError('native failure')
        r=self.edit([{**a,'values':{'channel':'10'}}])
        self.assertFalse(r['retry_safe']);self.assertEqual(r['attempted_ids'],['A']);self.assertEqual(len(r['receipt']),1)

    def test_server_compacts_success_and_returns_guarded_rollback(self):
        native=self.edit([{**self.target('A'),'values':{'channel':'001'}}])
        final=e.get_lighting_documentation_verification({'expected_document':self.doc,'receipt':native['receipt']})
        conn=MagicMock();conn.send_command.side_effect=[native,final]
        with patch.object(server,'get_vwx_connection',return_value=conn):
            result=json.loads(server.cmd('set_lighting_documentation',{'expected_document':self.doc}))
        self.assertNotIn('receipt',result);self.assertEqual(result['rollback_items'][0]['values'],{'channel':''})
        self.assertEqual(result['rollback_items'][0]['expected_fingerprint'],final['devices'][0]['fingerprint'])

    def test_single_event_batch_rejected(self):
        r=commands._batch({'calls':[{'command':'number_lighting_devices'}]})
        self.assertEqual(r['code'],'VM_EVENT_BOUNDARY_REQUIRED')


if __name__=='__main__':unittest.main()
