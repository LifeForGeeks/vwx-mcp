import copy
import json
import unittest
from unittest.mock import patch, Mock
from test_entertainment import e, vs, ROOT, server


class CableSectionTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.doc=str(ROOT/'tests'/'Scratch.vwx');vs.GetFPathName.return_value=self.doc
        vs.GetObjectByUuid.return_value='cable';vs.GetTypeN.return_value=86
        vs.GetObjectUuid.side_effect=lambda h:'layer-id' if h=='layer' else 'cable-id'
        vs.GetLayer.return_value='layer';vs.GetClass.return_value='Cable';vs.GetPluginStyle.return_value='Jumper Edison'
        vs.GetRField.return_value='unchanged';vs.GetCustomObjectPath.return_value='path'
        vs.GetCableSectionsCnt.return_value=1;vs.GetCableBreaksCnt.return_value=0;vs.GetCablePartsCnt.return_value=1
        vs.GetCableBreakData.return_value='Break'
        self.data={'Name':'1','Length':'6096.000000','Start Slack':'150.000000','End Slack':'150.000000',
                   'Swag':'0.000000','Total Vertical Drop':'0.000000','Parts Ordered':'E-25ft',
                   'Loom ID':'','Box ID':'','Tape':''}
        vs.GetCableSectionData.side_effect=lambda h,key,i,j:self.data[key]
        def write(h,key,i,value):
            if key!='Name':
                self.assertTrue(value.endswith('mm'),'Dimension setter must always include units')
                value=format(float(value[:-2]),'.6f')
            self.data[key]=value
        vs.SetCableSectionData.side_effect=write
        self.addCleanup(patch.stopall)
        patch.object(e,'plugin',return_value='CableObject').start()
        patch.object(e,'cable_geometry_snapshot',return_value={'status':'ok','sha256':'geometry'}).start()

    def snapshot(self): return e.cable_sections_snapshot('cable')

    def metadata_native(self, synchronize=True):
        self.run_fields={'Loom_ID':'','Box_ID':'','TapeColorCode':''}
        vs.GetRField.side_effect=lambda h,rec,key:self.run_fields.get(key,'unchanged')
        original=vs.SetCableSectionData.side_effect
        mapping={'Loom ID':'Loom_ID','Box ID':'Box_ID','Tape':'TapeColorCode'}
        def write(h,key,index,value):
            if key in mapping:
                self.data[key]=value
                if synchronize:self.run_fields[mapping[key]]=value
            else:original(h,key,index,value)
        vs.SetCableSectionData.side_effect=write

    def test_metadata_writes_native_selectors_and_verifies_run_sync(self):
        self.metadata_native()
        r=self.change([{'index':1,'loom_id':'L1','box_id':'B1','tape':'Blue'}])
        self.assertEqual(r['status'],'ok')
        for key,value in [('Loom ID','L1'),('Box ID','B1'),('Tape','Blue')]:
            vs.SetCableSectionData.assert_any_call('cable',key,1,value)
        v=e.get_cable_section_verification({'expected_document':self.doc,'receipt':r['receipt']})
        self.assertTrue(v['verified']);self.assertEqual(v['cable']['sections'][0]['loom_id'],'L1')
        self.assertEqual(v['cable']['protected']['fields']['TapeColorCode'],'Blue')
        vs.SetRField.assert_not_called();vs.ResetObject.assert_not_called()

    def test_metadata_missing_run_sync_is_not_success(self):
        self.metadata_native(synchronize=False)
        r=self.change([{'index':1,'loom_id':'L1'}])
        v=e.get_cable_section_verification({'expected_document':self.doc,'receipt':r['receipt']})
        self.assertEqual(v['status'],'error')

    def test_same_section_value_with_different_run_value_is_not_noop(self):
        self.metadata_native();self.data['Loom ID']='L1'
        r=self.change([{'index':1,'loom_id':'L1'}])
        self.assertEqual(r['changed_field_count'],1)
        self.assertTrue(e.get_cable_section_verification({'expected_document':self.doc,'receipt':r['receipt']})['verified'])

    def test_metadata_multi_section_break_and_bad_values_preflight(self):
        self.metadata_native()
        for key,value in [('GetCableSectionsCnt',2),('GetCableBreaksCnt',1)]:
            fn=getattr(vs,key);old=fn.return_value;fn.return_value=value
            self.assertEqual(self.change([{'index':1,'name':'Changed','loom_id':'L1'}])['status'],'error')
            fn.return_value=old
        for value in [True,1,' '*2,'a'*129]:
            self.assertEqual(self.change([{'index':1,'tape':value}])['status'],'error')
        vs.SetCableSectionData.assert_not_called()

    def test_metadata_fingerprint_clearing_and_noop(self):
        self.metadata_native();before=self.snapshot()['fingerprint']
        self.data['Tape']='Changed'
        self.assertEqual(self.change([{'index':1,'box_id':'B1'}],expected_fingerprint=before)['status'],'error')
        r=self.change([{'index':1,'tape':''}])
        self.assertEqual(r['changed_field_count'],1)
        self.assertTrue(e.get_cable_section_verification({'expected_document':self.doc,'receipt':r['receipt']})['verified'])
        r=self.change([{'index':1,'tape':''}]);self.assertEqual(r['changed_field_count'],0)

    def change(self,sections,**changes):
        p={'expected_document':self.doc,'object_id':'cable-id','expected_fingerprint':self.snapshot()['fingerprint'],'sections':sections}
        p.update(changes)
        return e.set_cable_sections(p)

    def test_native_count_indices_and_mm_readback(self):
        r=self.snapshot();self.assertEqual(r['sections'][0]['drawn_length_mm'],6096)
        self.assertEqual(r['sections'][0]['parts'],['E-25ft'])
        vs.GetCablePartsCnt.assert_any_call('cable',0)
        vs.GetCableSectionData.assert_any_call('cable','Parts Ordered',1,1)

    def test_unit_safe_edit_and_post_event_stock_change(self):
        r=self.change([{'index':1,'start_slack_mm':300,'name':'Test'}])
        self.assertEqual(r['status'],'ok');self.assertTrue(r['requires_verification'])
        vs.SetCableSectionData.assert_any_call('cable','Start Slack',1,'300mm')
        self.data['Parts Ordered']='E-50ft'  # native event can choose different stock
        v=e.get_cable_section_verification({'expected_document':self.doc,'receipt':r['receipt']})
        self.assertTrue(v['verified']);self.assertFalse(v['parts_sufficiency_verified'])
        self.assertEqual(v['cable']['sections'][0]['parts'],['E-50ft'])

    def test_bad_fields_indices_lengths_or_stale_document_do_not_write(self):
        for rows in [[],[{'index':0,'swag_mm':10}],[{'index':2,'swag_mm':10}],
                     [{'index':1,'swag_mm':-1}],[{'index':1,'swag_mm':float('nan')}],
                     [{'index':1,'swag_mm':True}],[{'index':1,'parts_ordered':'X'}],
                     [{'index':1,'name':' ' }],[{'index':1}],
                     [{'index':1,'name':'A'},{'index':1,'name':'B'}]]:
            with self.subTest(rows=rows):self.assertEqual(self.change(rows)['status'],'error')
        self.assertEqual(self.change([{'index':1,'swag_mm':10}],expected_fingerprint='0'*64)['status'],'error')
        self.assertEqual(self.change([{'index':1,'swag_mm':10}],expected_document='wrong')['status'],'error')
        vs.SetCableSectionData.assert_not_called()

    def test_entire_batch_preflight_and_noop(self):
        self.assertEqual(self.change([{'index':1,'name':'A'},{'index':2,'name':'B'}])['status'],'error')
        vs.SetCableSectionData.assert_not_called()
        r=self.change([{'index':1,'start_slack_mm':150}])
        self.assertEqual(r['changed_field_count'],0);vs.SetCableSectionData.assert_not_called()

    def test_partial_failure_retains_attempts(self):
        def write(h,key,index,value):
            if key=='Swag':raise RuntimeError('native failed')
            self.data[key]=value
        vs.SetCableSectionData.side_effect=write
        r=self.change([{'index':1,'name':'A','swag_mm':20}])
        self.assertEqual(r['status'],'error');self.assertFalse(r['retry_safe'])
        self.assertEqual(len(r['attempted']),2);self.assertEqual(self.data['Name'],'A')

    def test_verification_rejects_silent_failure_and_changed_geometry(self):
        r=self.change([{'index':1,'name':'A'}])
        self.data['Name']='ignored'
        args={'expected_document':self.doc,'receipt':r['receipt']}
        self.assertEqual(e.get_cable_section_verification(args)['status'],'error')
        self.data['Name']='A';e.cable_geometry_snapshot.return_value={'status':'ok','sha256':'changed'}
        self.assertEqual(e.get_cable_section_verification(args)['status'],'error')

    def test_snapshot_bounds_and_unavailable_geometry(self):
        for value in [0,101,True]:
            vs.GetCableSectionsCnt.return_value=value
            with self.assertRaises(ValueError):self.snapshot()
        vs.GetCableSectionsCnt.return_value=1;vs.GetCablePartsCnt.return_value=501
        with self.assertRaises(ValueError):self.snapshot()
        vs.GetCablePartsCnt.return_value=1;e.cable_geometry_snapshot.return_value={'status':'unavailable'}
        with self.assertRaises(ValueError):self.snapshot()

    def test_server_uses_second_read_event_and_reports_uncertain_verification(self):
        conn=Mock();receipt={'object_id':'id'}
        first={'status':'ok','requires_verification':True,'receipt':receipt,'next_command':'get_cable_section_verification'}
        for last in [{'status':'ok','verified':True},{'status':'error','error':'read failed'}]:
            conn.send_command.side_effect=[copy.deepcopy(first),last]
            with patch.object(server,'get_vwx_connection',return_value=conn):
                r=json.loads(server.cmd('set_cable_sections',{'expected_document':self.doc}))
            self.assertEqual(conn.send_command.call_args.args[0],'get_cable_section_verification')
            self.assertEqual(r['status'],'ok' if last.get('verified') else 'error')
            if last.get('error'):self.assertFalse(r['retry_safe']);self.assertIn('recovery_params',r)
        self.assertIn('get_cable_sections',server._MENU_CONTEXT_READS)
        self.assertIn('get_cable_section_verification',server._MENU_CONTEXT_READS)


if __name__=='__main__':unittest.main()
