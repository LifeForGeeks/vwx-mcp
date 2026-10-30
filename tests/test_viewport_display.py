import json
import unittest
from test_entertainment import e, vs, server


class ViewportDisplayTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True, side_effect=True)
        vs.GetObjectByUuid.return_value = 'vp'
        vs.GetTypeN.return_value = 122
        vs.GetFPathName.return_value = 'QA.vwx'
        vs.GetName.return_value = 'Viewport'
        vs.GetLayer.return_value = 'sheet'
        vs.GetLName.side_effect = lambda h: {'model': 'Model', 'sheet': 'Sheet'}[h]
        vs.GetObjectVariableInt.side_effect = lambda h, s: (1 if h == 'model' else 2) if s == 154 else 0
        vs.GetObjectVariableReal.return_value = 48.0
        vs.GetObjectVariableBoolean.return_value = False
        vs.FLayer.return_value = 'model'
        vs.NextLayer.side_effect = lambda h: 'sheet' if h == 'model' else None
        vs.GetLVis.return_value = 0
        vs.GetLScale.return_value = 48.0
        vs.ClassNum.return_value = 3
        vs.ClassList.side_effect = lambda i: ['Visible', 'Hidden', 'Gray'][i-1]
        vs.GetCVis.return_value = 0
        vs.GetVPClassVisibility.side_effect = lambda h, n: (True, {'Visible': 0, 'Hidden': -1, 'Gray': 2}[n])
        vs.GetVPLayerVisibility.return_value = (True, 0)
        vs.GetVPClOvrdCount.return_value = 1
        vs.GetVPClOvrdName.return_value = 'Gray'
        vs.GetVPLrOvrdCount.return_value = 0
        vs.VPHasCropObject.return_value = True
        vs.VMGetViewportContext = None

    def run_tool(self, **kw):
        return e.get_viewport_display({'viewport_ids': ['uuid'], **kw})

    def test_summary_covers_every_class_and_design_layer_without_detail_arrays(self):
        r = self.run_tool()['viewports'][0]
        self.assertEqual(r['class_visibility_counts'], {'visible': 1, 'hidden': 1, 'gray': 1})
        self.assertEqual(r['layer_visibility_counts'], {'visible': 1})
        self.assertEqual(r['scale'], 48)
        self.assertNotIn('classes', r)
        self.assertEqual(r['native_context']['available'], False)
        vs.GetPluginStyle.assert_not_called()

    def test_detail_bounds_do_not_reduce_counts_or_hide_overrides(self):
        r = self.run_tool(detail='visibility', limit=1)['viewports'][0]
        self.assertEqual(r['class_count'], 3)
        self.assertTrue(r['classes_truncated'])
        self.assertEqual(r['classes'][0]['name'], 'Gray')
        self.assertTrue(r['classes'][0]['has_attribute_override'])
        self.assertEqual(r['classes'][0]['document_visibility'], 0)

    def test_failed_visibility_is_unknown_not_visible(self):
        vs.GetVPClassVisibility.side_effect = lambda *a: (False, 0)
        r = self.run_tool(detail='visibility')['viewports'][0]
        self.assertEqual(r['class_visibility_counts'], {'unknown': 3})
        self.assertIsNone(r['classes'][0]['visibility'])

    def test_empty_scopes_do_not_claim_truncation_at_later_offset(self):
        r = self.run_tool(detail='visibility', class_names=[], layer_names=[], offset=9)['viewports'][0]
        self.assertFalse(r['classes_truncated'])
        self.assertFalse(r['layers_truncated'])

    def test_explicit_scopes_and_paging(self):
        r = self.run_tool(detail='visibility', class_names=['Visible', 'Gray'], layer_names=['Model'], offset=1, limit=1)['viewports'][0]
        self.assertEqual(r['class_count'], 2)
        self.assertEqual(r['classes'][0]['name'], 'Visible')
        self.assertEqual(r['layers'], [])
        self.assertEqual(self.run_tool(class_names=['Misspelled'])['status'], 'error')

    def test_native_contract_version_and_uuid_are_checked(self):
        vs.VMGetViewportContext = lambda h: json.dumps({'status': 'ok', 'contract_version': 1, 'viewport_id': 'uuid', 'style': {'native_ok': True, 'resource_index': 0}})
        r = self.run_tool()['viewports'][0]
        self.assertTrue(r['native_context']['available'])
        self.assertEqual(r['native_context']['style']['resource_index'], 0)
        vs.VMGetViewportContext = lambda h: json.dumps({'status': 'ok', 'contract_version': 99, 'viewport_id': 'other'})
        self.assertFalse(self.run_tool()['viewports'][0]['native_context']['available'])

    def test_invalid_scope_rejected_before_scanning(self):
        for kw in [{'limit': 0}, {'offset': -1}, {'detail': 'pretend'}, {'viewport_ids': ['uuid'] * 11}]:
            self.assertEqual(self.run_tool(**kw)['status'], 'error')
        vs.FLayer.assert_not_called()

    def test_readonly_menu_context_and_no_mutations(self):
        self.assertIn('get_viewport_display', server._MENU_CONTEXT_READS)
        self.assertTrue(server._is_readonly('get_viewport_display'))
        self.run_tool()
        vs.SetVPClassVisibility.assert_not_called()
        vs.SetVPLayerVisibility.assert_not_called()
        vs.UpdateVP.assert_not_called()


if __name__ == '__main__': unittest.main()
