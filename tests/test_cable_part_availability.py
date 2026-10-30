import copy
import unittest
import test_cable_part_symbols as fixtures
from test_entertainment import e, vs


class CablePartAvailabilityTests(unittest.TestCase):
    setUp = fixtures.CablePartSymbolTests.setUp
    call = fixtures.CablePartSymbolTests.call

    def spec(self, oid='base', enabled=False):
        return {'object_id':oid,'enabled':enabled,
                'expected_fingerprint':e.cable_part_symbol_snapshot(oid)['fingerprint']}

    def run_change(self, items, **extra):
        return self.call('set_cable_part_availability', expected_document=self.doc, items=items, **extra)

    def test_toggle_and_noop_preserve_other_data_without_reset(self):
        before=e.cable_part_symbol_snapshot('base')
        result=self.run_change([self.spec()])
        self.assertEqual(result['status'],'ok'); self.assertEqual(result['changed_count'],1)
        self.assertTrue(result['parts'][0]['verified'])
        after=e.cable_part_symbol_snapshot('base')
        self.assertEqual(after['fields'],{**before['fields'],'Use':'False'})
        self.assertEqual(after['texts'],before['texts'])
        vs.SetRField.reset_mock()
        result=self.run_change([self.spec()])
        self.assertEqual(result['changed_count'],0); vs.SetRField.assert_not_called()
        vs.ResetObject.assert_not_called()

    def test_entire_batch_preflight_rejects_stale_later_item(self):
        self.types['alt']=16; self.names['alt']='Other Part'
        self.values['alt']=copy.deepcopy(self.values['base']); self.children['alt']=self.children['base']
        stale=self.spec('alt'); stale['expected_fingerprint']='0'*64
        result=self.run_change([self.spec(),stale])
        self.assertEqual(result['status'],'error'); vs.SetRField.assert_not_called()

    def test_strict_bounds_and_types_reject_before_writing(self):
        for items in [[],[self.spec()]*26,[self.spec(),self.spec()],
                      [{**self.spec(),'enabled':'false'}],
                      [{**self.spec(),'expected_fingerprint':'bad'}],
                      [{**self.spec(),'rebuild':True}]]:
            with self.subTest(items=items[:1]):
                self.assertEqual(self.run_change(items)['status'],'error')
                vs.SetRField.assert_not_called()
        self.assertEqual(self.run_change([self.spec()],rebuild=True)['status'],'error')
        result=self.call('set_cable_part_availability',expected_document=self.doc+'wrong',items=[self.spec()])
        self.assertEqual(result['status'],'error'); vs.SetRField.assert_not_called()

    def test_silent_write_failure_has_recovery_receipt(self):
        vs.SetRField.side_effect=None
        result=self.run_change([self.spec()])
        self.assertEqual(result['status'],'error'); self.assertFalse(result['retry_safe'])
        self.assertEqual(result['parts'][0]['object_id'],'base')
        self.assertTrue(result['parts'][0]['write_attempted'])
        self.assertFalse(result['parts'][0]['verified'])

    def test_partial_failure_preserves_success_and_reports_failed_attempt(self):
        self.types['alt']=16; self.names['alt']='Other Part'
        self.values['alt']=copy.deepcopy(self.values['base']); self.children['alt']=self.children['base']
        def setter(h,r,k,v):
            if h=='alt': raise RuntimeError('native failure')
            self.values[h][r][k]=v
        vs.SetRField.side_effect=setter
        result=self.run_change([self.spec(),self.spec('alt')])
        self.assertEqual(result['status'],'error'); self.assertEqual(len(result['parts']),2)
        self.assertTrue(result['parts'][0]['verified']); self.assertFalse(result['parts'][1]['verified'])
        self.assertEqual(self.values['base']['CablePart']['Use'],'False')

    def test_incidental_field_change_is_detected(self):
        def setter(h,r,k,v):
            self.values[h][r][k]=v; self.values[h][r]['Length']='999'
        vs.SetRField.side_effect=setter
        result=self.run_change([self.spec()])
        self.assertEqual(result['status'],'error')
        self.assertIn('Other cable-part data changed',result['error'])

    def test_native_flat_polyline_supported_but_nested_group_rejected(self):
        self.types['poly']=21;self.children['base'].append('poly')
        result=self.run_change([self.spec()])
        self.assertEqual(result['status'],'ok')
        self.assertEqual(e.cable_part_symbol_snapshot('base')['graphic_types'],[3,10,21])
        self.types['poly']=11
        with self.assertRaises(ValueError):e.cable_part_symbol_snapshot('base')


if __name__=='__main__': unittest.main()
