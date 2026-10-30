import unittest
from test_entertainment import e, vs, server


class DataSheetTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True, side_effect=True)
        vs.GetFPathName.return_value = 'QA.vwx'
        vs.IFC_GetDSCount.return_value = (True, 2)
        vs.IFC_GetDSNameAt.side_effect = lambda n, i: (True, ['Inventory', 'Review'][i])
        vs.IFC_GetDSFieldsCount.return_value = (True, 3)
        vs.IFC_GetDSFieldInfoAt.side_effect = lambda n, s, i: (True, ['Model', 'Supplier', 'Note'][i], i != 2, False)
        vs.GetObjectByUuid.side_effect = lambda oid: None if oid == 'missing' else oid
        vs.DSH_GetDSFieldsCount.return_value = (True, 3)
        vs.DSH_GetDSFieldValue.side_effect = lambda h, s, f: (True, {'Model': 'Chauvet Color Strike M', 'Supplier': '', 'Note': 'Review'}[f], 2, 0)

    def run_tool(self, **kw):
        return e.get_data_sheet_inspection({'mapping_name': 'Lighting Device', **kw})

    def test_lists_mapping_sheets_without_broken_object_index_enumerators(self):
        r = self.run_tool()
        self.assertEqual(r['sheet_names'], ['Inventory', 'Review'])
        self.assertFalse(r['sheets_truncated'])
        vs.DSH_GetDSNameAt.assert_not_called()
        vs.DSH_GetDSFieldInfoAt.assert_not_called()

    def test_field_page_and_native_values_preserve_blank_and_raw_status(self):
        r = self.run_tool(data_sheet='Inventory', object_ids=['a'], field_offset=1, field_limit=1)
        self.assertEqual(r['field_count'], 3)
        self.assertEqual(r['next_field_offset'], 2)
        self.assertEqual(r['fields'], [{'index': 1, 'label': 'Supplier', 'visible': True, 'by_formula': False}])
        v = r['objects'][0]['values'][0]
        self.assertTrue(v['native_ok'])
        self.assertEqual(v['value'], '')
        self.assertEqual(v['operation_status'], 2)
        self.assertEqual(v['source'], 'instance')

    def test_failed_native_read_is_not_reported_as_blank_data(self):
        vs.DSH_GetDSFieldValue.return_value = (False, '', 1, -1)
        vs.DSH_GetDSFieldValue.side_effect = None
        r = self.run_tool(data_sheet='Inventory', object_ids=['a'])
        self.assertFalse(r['objects'][0]['values'][0]['native_ok'])
        self.assertIsNone(r['objects'][0]['values'][0]['value'])
        self.assertEqual(r['failed_reads'], 3)

    def test_missing_object_and_unavailable_sheet_are_scoped_errors(self):
        vs.DSH_GetDSFieldsCount.return_value = (False, 0)
        r = self.run_tool(data_sheet='Inventory', object_ids=['missing', 'a'])
        self.assertEqual(r['object_errors'], 2)
        self.assertTrue(all('error' in o for o in r['objects']))
        vs.DSH_GetDSFieldValue.assert_not_called()

    def test_definition_failure_is_not_an_empty_sheet(self):
        vs.IFC_GetDSFieldsCount.return_value = (False, 0)
        r = self.run_tool(data_sheet='Invalid')
        self.assertEqual(r['status'], 'error')

    def test_invalid_bounds_and_duplicate_ids_rejected_before_reads(self):
        for kw in [{'field_offset': -1}, {'field_limit': 0}, {'field_limit': 51},
                   {'object_ids': ['a'] * 11}, {'object_ids': ['a', 'a']},
                   {'object_ids': ['a']}, {'field_offset': True}]:
            self.assertEqual(self.run_tool(**kw)['status'], 'error', kw)
        vs.IFC_GetDSCount.assert_not_called()

    def test_values_are_bounded_without_losing_source_codes(self):
        vs.DSH_GetDSFieldValue.side_effect = None
        vs.DSH_GetDSFieldValue.return_value = (True, 'x' * 600, 99, 42)
        r = self.run_tool(data_sheet='Inventory', object_ids=['a'], field_limit=1)
        v = r['objects'][0]['values'][0]
        self.assertEqual(len(v['value']), 512)
        self.assertTrue(v['truncated'])
        self.assertEqual(v['source'], 'unknown')
        self.assertEqual(v['source_code'], 42)
        self.assertEqual(v['operation_status'], 99)

    def test_readonly_requires_menu_context_and_does_not_write(self):
        self.assertTrue(server._is_readonly('get_data_sheet_inspection'))
        self.assertIn('get_data_sheet_inspection', server._MENU_CONTEXT_READS)
        self.run_tool(data_sheet='Inventory', object_ids=['a'])
        vs.DSH_SetDSFieldValue.assert_not_called()
        vs.SetRField.assert_not_called()
        vs.ResetObject.assert_not_called()


if __name__ == '__main__':
    unittest.main()
