import copy
import json
import unittest
from test_entertainment import e, vs, server


def component(device='device-a', identity='input'):
    return dict(device_id=device, component_id=identity, type_code=0, name='Input',
                connector='XLR5', average_consumption_w=0.0, maximum_consumption_w=120.0,
                is_virtual=True, is_link_through=False, internal_connections=[])


class ElectricalComponentTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True, side_effect=True)
        vs.GetObjectByUuid.return_value='handle'
        vs.GetTypeN.return_value=86
        vs.GetObjectUuid.return_value='object'
        vs.GetName.return_value='Fixture'
        vs.GetClass.return_value='LX'
        vs.GetLName.return_value='Lighting'
        vs.GetFPathName.return_value='QA.vwx'
        self.payload=dict(contract_version=1,status='ok',object_id='object',
                          provider_available=True,components=[component()])
        vs.VMGetElectricalComponents=lambda h: json.dumps(self.payload)

    def query(self, **kwargs):
        self.assertIn('get_electrical_components',e.COMMANDS)
        return e.COMMANDS['get_electrical_components']({'object_ids':['object'],**kwargs})

    def test_summary_has_counts_without_claiming_a_connected_circuit(self):
        result=self.query()
        row=result['objects'][0]
        self.assertEqual(row['component_count'],1)
        self.assertEqual(row['type_counts'],{'input':1})
        self.assertNotIn('components',row)
        self.assertFalse(result['external_connections_verified'])
        self.assertFalse(result['engineering_values_verified'])

    def test_identity_is_pair_and_links_resolve_within_device_only(self):
        a=component(); b=component('device-b'); c=component(identity='out')
        c['internal_connections']=[dict(own_socket=1,other_socket=2,other_component_id='input',name='link')]
        self.payload['components']=[a,b,c]
        row=self.query(detail='components',include_internal_connections=True)['objects'][0]
        self.assertEqual(row['identity_issues'],[])
        link=row['components'][2]['internal_connections'][0]
        self.assertEqual(link['target_match_count'],1)
        self.assertEqual(link['target_device_id'],'device-a')

    def test_duplicate_pair_is_ambiguous_not_arbitrarily_resolved(self):
        self.payload['components']=[component(),component(),component(identity='out')]
        self.payload['components'][2]['internal_connections']=[dict(own_socket=0,other_socket=0,other_component_id='input',name='')]
        row=self.query(detail='components',include_internal_connections=True)['objects'][0]
        self.assertTrue(row['identity_issues'])
        self.assertEqual(row['components'][2]['internal_connections'][0]['target_match_count'],2)

    def test_missing_target_and_empty_identity_remain_explicit(self):
        self.payload['components'][0]['device_id']=''
        self.payload['components'][0]['internal_connections']=[dict(own_socket=0,other_socket=5,other_component_id='absent',name='')]
        row=self.query(detail='components',include_internal_connections=True)['objects'][0]
        self.assertTrue(row['identity_issues'])
        self.assertIsNone(row['components'][0]['internal_connections'][0]['target_match_count'])

    def test_unavailable_extension_provider_and_empty_provider_differ(self):
        vs.VMGetElectricalComponents=None
        self.assertEqual(self.query()['objects'][0]['inspection_status'],'extension_unavailable')
        vs.VMGetElectricalComponents=lambda h: json.dumps(self.payload)
        self.payload.update(provider_available=False,components=[])
        self.assertEqual(self.query()['objects'][0]['inspection_status'],'provider_unavailable')
        self.payload['provider_available']=True
        row=self.query()['objects'][0]
        self.assertEqual(row['inspection_status'],'ok')
        self.assertEqual(row['component_count'],0)

    def test_failure_wrong_version_and_identity_do_not_become_empty_success(self):
        original=copy.deepcopy(self.payload)
        for changes in [dict(status='error',error='Provider returned failure'),dict(contract_version=99),dict(object_id='other'),dict(provider_available='yes')]:
            self.payload={**original,**changes}
            row=self.query()['objects'][0]
            self.assertEqual(row['inspection_status'],'error',row)
            self.assertNotIn('component_count',row)

    def test_invalid_numeric_fields_and_oversized_payload_rejected(self):
        for value in [float('nan'),float('inf'),True,'120']:
            self.payload['components'][0]['maximum_consumption_w']=value
            self.assertEqual(self.query()['objects'][0]['inspection_status'],'error')
        vs.VMGetElectricalComponents=lambda h:' '*1000001
        self.assertEqual(self.query()['objects'][0]['inspection_status'],'error')

    def test_unknown_type_is_preserved_and_no_consumption_sum_is_invented(self):
        self.payload['components'][0]['type_code']=99
        row=self.query(detail='components')['objects'][0]
        self.assertEqual(row['type_counts'],{'unknown:99':1})
        self.assertEqual(row['components'][0]['maximum_consumption_w'],120.0)
        self.assertNotIn('total_power_w',row)

    def test_detail_limit_does_not_reduce_whole_object_counts(self):
        self.payload['components']=[component(identity=str(i)) for i in range(3)]
        row=self.query(detail='components',limit=1)['objects'][0]
        self.assertEqual(row['component_count'],3)
        self.assertEqual(len(row['components']),1)
        self.assertTrue(row['components_truncated'])
        self.assertNotIn('internal_connections',row['components'][0])

    def test_invalid_request_fails_before_native_lookup(self):
        for kwargs in [dict(object_ids=[]),dict(object_ids=['object']*11),dict(object_ids=['object','object']),dict(limit=0),dict(limit=True),dict(detail='full'),dict(include_internal_connections='yes'),dict(include_internal_connections=True)]:
            self.assertEqual(self.query(**kwargs)['status'],'error',kwargs)
        vs.GetObjectByUuid.assert_not_called()

    def test_missing_or_nonparametric_object_is_reported_without_provider(self):
        vs.GetObjectByUuid.return_value=None
        self.assertEqual(self.query()['objects'][0]['inspection_status'],'missing_object')
        vs.GetObjectByUuid.return_value='handle'; vs.GetTypeN.return_value=3
        self.assertEqual(self.query()['objects'][0]['inspection_status'],'unsupported_object_type')

    def test_readonly_menu_contract(self):
        self.assertIn('get_electrical_components',server._MENU_CONTEXT_READS)
        self.assertTrue(server._is_readonly('get_electrical_components'))
        self.query()
        vs.SetRField.assert_not_called(); vs.ResetObject.assert_not_called()


if __name__=='__main__': unittest.main()
