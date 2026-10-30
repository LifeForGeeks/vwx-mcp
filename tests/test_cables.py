import json
import unittest
from unittest.mock import patch, MagicMock
from test_entertainment import e, vs, server, ROOT


class CableTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True, side_effect=True)
        self.doc = str(ROOT/'tests'/'Scratch.vwx')
        vs.GetFPathName.return_value = self.doc

    def invoke(self, name, **p):
        self.assertIn(name, e.COMMANDS, 'Cable workflow is not implemented')
        return e.COMMANDS[name](p)

    def test_invalid_route_batch_never_starts_geometry(self):
        base = {'name':'A','layer':'Rig','class':'Paths','route_id':'P1',
                'vertices':[[0,0,0],[120,0,0],[120,0,120],[360,0,120]]}
        for change in [{'vertices':[[0,0,0]]}, {'vertices':[[0,0,0],[0,0,0]]},
                       {'vertices':[[0,0,0],[float('nan'),1,1]]}, {'route_id':''}]:
            rows = [base, {**base, 'name':'B', 'route_id':'P2', **change}]
            result = self.invoke('create_cable_paths', expected_document=self.doc, items=rows)
            self.assertEqual(result['status'], 'error')
        vs.BeginPoly3D.assert_not_called()
        vs.DefineCustomObj.assert_not_called()

    def setup_inspector(self):
        raw = json.loads((ROOT/'evidence/live-qa/cable-default-schemas.json').read_text())['result']
        self.fields = {r['plugin']:{f['name']:f['default'] for f in r['fields']} for r in raw}
        self.fields['CableObject'].update(CableRun_ID='D1', Loom_ID='L1',
            StartObjectName='Looks connected', StartObjectUUID='gone', EndObjectUUID='device',
            Length='0', LengthPartsTotal='0', StartObjectPort='1', EndObjectPort='2')
        self.fields['CablePathObject'].update(ID='P1', Length='40ft')
        self.plugins = {'run':'CableObject', 'path':'CablePathObject'}
        vs.GetObjectByUuid.side_effect = lambda h: None if h=='gone' else h
        vs.GetObjectUuid.side_effect = lambda h:h
        vs.GetTypeN.side_effect = lambda h: 25 if h=='run-geo' else 111 if h=='path-geo' else 86
        vs.GetParametricRecord.side_effect = lambda h:self.plugins.get(h)
        vs.GetName.side_effect = lambda h:h
        vs.NumFields.side_effect = lambda r:len(self.fields[r])
        vs.GetFldName.side_effect = lambda r,i:list(self.fields[r])[i-1]
        vs.GetRField.side_effect = lambda h,r,f:self.fields[r][f]
        vs.GetPluginStyle.return_value='Data style'
        vs.GetLayer.return_value='Rig'; vs.GetLName.return_value='Rig'
        vs.GetClass.return_value='Cables'; vs.GetLayerElevation.return_value=(0,0)
        vs.GetCustomObjectPath.side_effect=lambda h:h+'-geo'
        vs.GetEntityMatrix.return_value=(True,(0,0,0),0,0,0)
        vs.ValidNumStr.side_effect=lambda v:(True,480) if v=='40ft' else (True,0)
        vs.GetUnits.return_value=(25,3,2,1,'in','sq ft')

    def test_reports_stale_endpoint_and_bad_path_without_certifying_connections(self):
        self.setup_inspector()
        result=self.invoke('get_cable_inspection', object_ids=['run','path'])
        self.assertEqual(result['status'],'ok')
        self.assertFalse(result['native_connections_verified'])
        run=result['objects'][0]
        self.assertFalse(run['endpoints']['start']['resolves'])
        self.assertTrue(run['endpoints']['end']['resolves'])
        self.assertEqual(run['loom_id'],'L1')
        self.assertEqual(result['objects'][1]['drawn_length'],480)
        self.assertTrue({'unsupported_path_geometry','nonpositive_drawn_length','endpoint_uuid_missing_object','cable_style_data_incomplete'} <= {i['code'] for i in result['issues']})
        self.assertNotIn('fields',run)
        vs.ResetObject.assert_not_called();vs.SetRField.assert_not_called()

    def test_unknown_and_truncated_values_are_explicit(self):
        self.setup_inspector()
        del self.fields['CableObject']['StartObjectUUID']
        self.fields['CableObject']['UsedPartsOrdered']='x'*800
        result=self.invoke('get_cable_inspection',object_ids=['run'],include_fields=True,issue_limit=1)
        row=result['objects'][0]
        self.assertIsNone(row['endpoints']['start']['stored_uuid'])
        self.assertIsNone(row['endpoints']['start']['resolves'])
        self.assertIn('StartObjectUUID',row['missing_fields'])
        self.assertIn('UsedPartsOrdered',row['truncated_fields'])
        self.assertEqual(len(row['fields']['UsedPartsOrdered']),512)
        self.assertTrue(result['issues_truncated'])
        self.assertGreater(result['issue_count'],len(result['issues']))

    def test_native_connector_references_are_distinct_from_unspecified_numeric_ports(self):
        self.setup_inspector()
        self.fields['CableObject'].update(StartObjectPort='-1', EndObjectPort='-1',
            __StartConnectorUUID='111eb5fe-2a27-4fb0-9c4e-12d819cdc78a',
            __EndConnectorUUID='00000000-0000-0000-0000-000000000000')
        result=self.invoke('get_cable_inspection',object_ids=['run'])
        ends=result['objects'][0]['endpoints']
        self.assertEqual(ends['start'].get('stored_component_uuid'),'111eb5fe-2a27-4fb0-9c4e-12d819cdc78a')
        self.assertEqual(ends['end'].get('stored_component_uuid'),'00000000-0000-0000-0000-000000000000')
        self.assertEqual(ends['end'].get('component_reference_state'),'zero_uuid')
        self.assertNotIn('endpoint_port_unassigned',result['issue_counts'])
        self.assertFalse(result['native_connections_verified'])
        vs.SetRField.assert_not_called();vs.ResetObject.assert_not_called()

    def test_connector_reference_absence_and_truncation_do_not_become_valid_links(self):
        self.setup_inspector()
        self.fields['CableObject'].pop('__StartConnectorUUID',None)
        self.fields['CableObject']['__EndConnectorUUID']='x'*800
        row=self.invoke('get_cable_inspection',object_ids=['run'])['objects'][0]
        self.assertEqual(row['endpoints']['start'].get('component_reference_state'),'field_unavailable')
        self.assertIsNone(row['endpoints']['start'].get('stored_component_uuid'))
        self.assertEqual(len(row['endpoints']['end'].get('stored_component_uuid','')),512)
        self.assertIn('__EndConnectorUUID',row['truncated_fields'])

    def test_summary_endpoint_text_is_bounded_too(self):
        self.setup_inspector()
        self.fields['CableObject']['StartObjectUUID']='u'*800
        self.fields['CableObject']['StartObjectPort']='p'*800
        result=self.invoke('get_cable_inspection',object_ids=['run'])
        endpoint=result['objects'][0]['endpoints']['start']
        self.assertEqual(len(endpoint['stored_uuid']),512)
        self.assertEqual(len(endpoint['stored_port']),512)
        self.assertIn('StartObjectUUID',result['objects'][0]['truncated_fields'])

    def test_unknown_route_settings_are_not_silently_ignored(self):
        row={'name':'A','layer':'Rig','class':'Paths','route_id':'P1',
             'vertices':[[0,0,0],[120,0,0]],'connect_to':'unsupported'}
        result=self.invoke('create_cable_paths',expected_document=self.doc,items=[row])
        self.assertEqual(result['status'],'error')
        vs.ForEachObject.assert_not_called()

    def test_inspection_rejects_duplicate_ids_and_foreign_plugins(self):
        self.setup_inspector()
        for ids in [[],['run','run'],['run']*51,['device']]:
            self.assertEqual(self.invoke('get_cable_inspection',object_ids=ids)['status'],'error')

    def test_followup_failure_preserves_creation_receipt_and_blocks_recreation(self):
        connection=MagicMock()
        created={'status':'ok','created':[{'object_id':'path'}],'requires_verification':True}
        connection.send_command.side_effect=[created,{'status':'error','error':'native length mismatch'}]
        with patch.object(server,'get_vwx_connection',return_value=connection):
            result=json.loads(server.cmd('create_cable_paths',{'expected_document':self.doc}))
        self.assertEqual(result['status'],'error')
        self.assertFalse(result['retry_safe'])
        self.assertEqual(result['created'][0]['object_id'],'path')
        self.assertEqual(result['recovery_command'],'get_cable_path_verification')

    def test_inspector_uses_menu_context_and_readonly_hint(self):
        self.assertIn('get_cable_inspection',server._MENU_CONTEXT_READS)
        self.assertTrue(server._is_readonly('get_cable_inspection'))

    def test_verification_catches_route_shape_change_even_with_correct_length(self):
        self.setup_inspector()
        self.fields['CablePathObject'].update(Set2DAttributes='Class',Class2DAttributes='Cables',Location='')
        vs.GetEntityMatrix.return_value=(True,(2000,2600,0),0,0,0)
        vs.GetTypeN.side_effect=lambda h:111 if h=='path-geo' else 86
        vs.NurbsCurveGetNumPieces.return_value=3
        vs.NurbsGetNumPts.return_value=2;vs.NurbsDegree.return_value=1
        points=[(0,0,0),(120,0,0),(120,0,120),(360,0,120)]
        vs.NurbsGetPt3D.side_effect=lambda h,s,i:points[s+i]
        receipt={'object_id':'path','name':'path','class':'Cables','layer':'Rig','route_id':'P1',
                 'location':'','vertices':[[2000+x,2600+y,z] for x,y,z in points],'expected_length':480}
        p={'expected_document':self.doc,'created':[receipt]}
        good=self.invoke('get_cable_path_verification',**p)
        self.assertEqual(good['status'],'ok',good)
        self.assertTrue(good['verified'])
        points[1]=(0,120,0)
        bad=self.invoke('get_cable_path_verification',**p)
        self.assertEqual(bad['status'],'error')
        vs.ResetObject.assert_not_called()


if __name__=='__main__':unittest.main()
