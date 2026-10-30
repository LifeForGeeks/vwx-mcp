import unittest
import test_cables
from test_entertainment import e, vs


class ConnectorConfigurationTests(unittest.TestCase):
    setUp = test_cables.CableTests.setUp
    setup_inspector = test_cables.CableTests.setup_inspector
    invoke = test_cables.CableTests.invoke

    def setup_config(self):
        self.setup_inspector()
        self.fields['CableObject'].update(StartConector='Combined TRUE1', EndConnector='Combined TRUE1', CableType='JumperCable')
        self.style_fields = dict(self.fields['CableObject'])
        self.plugins['definition'] = 'CableObject'
        vs.GetObject.return_value = 'style'
        vs.GetTypeN.side_effect = lambda h: 16 if h == 'style' else 111 if h.endswith('-geo') else 86
        vs.FInSymDef.return_value = 'definition'; vs.NextObj.return_value = None
        vs.GetParamStyleType.return_value = 1
        vs.GetRField.side_effect = lambda h,r,f: (self.style_fields if h == 'definition' else self.fields[r]).get(f, '')

    def inspect(self, **kwargs):
        return self.invoke('get_cable_inspection', object_ids=['run'], include_connector_configuration=True, **kwargs)

    def test_matching_family_does_not_certify_gender_or_wiring(self):
        self.setup_config()
        row = self.inspect()['objects'][0]['connector_configuration']
        self.assertEqual(row['status'], 'ok')
        self.assertTrue(row['parameters']['start']['matches_style'])
        self.assertEqual(row['parameters']['end']['control'], 'by_style')
        for flag in ('physical_gender_verified','pin_wiring_verified','native_connections_verified'):
            self.assertFalse(row[flag])
        vs.SetRField.assert_not_called(); vs.ResetObject.assert_not_called()

    def test_each_end_style_mismatch_is_reported(self):
        self.setup_config()
        self.fields['CableObject']['EndConnector'] = 'NEMA 5-15'
        result = self.inspect()
        config = result['objects'][0]['connector_configuration']
        self.assertEqual(config['style_mismatches'], ['EndConnector'])
        self.assertEqual(result['issue_counts']['connector_style_mismatch'], 1)
        self.assertTrue(config['parameters']['start']['matches_style'])

    def test_by_instance_difference_is_not_a_style_mismatch(self):
        self.setup_config()
        self.fields['CableObject']['StartConector'] = 'Other'
        for mode, label in ((0,'by_instance'),(2,'always_by_instance'),(-1,'unknown')):
            vs.GetParamStyleType.return_value = mode
            config = self.inspect()['objects'][0]['connector_configuration']
            self.assertEqual(config['style_mismatches'], [])
            self.assertEqual(config['parameters']['start']['control'], label)
            self.assertIsNone(config['parameters']['start']['matches_style'])

    def test_unstyled_and_default_skip_style_reads(self):
        self.setup_config()
        self.invoke('get_cable_inspection', object_ids=['run'])
        vs.FInSymDef.assert_not_called()
        vs.GetPluginStyle.return_value = ''
        config = self.inspect()['objects'][0]['connector_configuration']
        self.assertEqual(config['parameters']['start']['control'], 'by_instance')
        self.assertIsNone(config['parameters']['start']['style_value'])
        vs.FInSymDef.assert_not_called(); vs.GetParamStyleType.assert_not_called()

    def test_missing_resource_or_ambiguous_definition_does_not_claim_success(self):
        self.setup_config()
        vs.GetObject.return_value = None
        result = self.inspect()
        self.assertEqual(result['objects'][0]['connector_configuration']['status'], 'unavailable')
        self.assertIn('connector_configuration_unavailable', result['issue_counts'])
        vs.GetObject.return_value = 'style'
        self.plugins['definition2'] = 'CableObject'
        vs.NextObj.side_effect = lambda h: 'definition2' if h == 'definition' else None
        self.assertEqual(self.inspect()['objects'][0]['connector_configuration']['status'], 'unavailable')

    def test_truncated_or_absent_values_are_not_equal_by_accident(self):
        self.setup_config()
        self.fields['CableObject']['StartConector'] = 'x'*600
        self.style_fields['StartConector'] = 'x'*600
        self.fields['CableObject']['AdapterStart'] = 'a'*600
        del self.fields['CableObject']['EndConnector']
        config = self.inspect()['objects'][0]['connector_configuration']
        start, end = config['parameters']['start'], config['parameters']['end']
        self.assertEqual(len(start['value']), 512)
        self.assertEqual(len(start['adapter']), 512)
        self.assertTrue(start['truncated'])
        self.assertIsNone(start['matches_style']); self.assertIsNone(end['matches_style'])

    def test_bounds_and_bad_switch_reject_before_native_reads(self):
        self.setup_config()
        for params in ({'object_ids':['run'], 'include_connector_configuration':1},
                       {'object_ids':[str(i) for i in range(11)], 'include_connector_configuration':True}):
            self.assertEqual(self.invoke('get_cable_inspection', **params)['status'], 'error')
        vs.GetObjectByUuid.assert_not_called()


if __name__ == '__main__': unittest.main()
