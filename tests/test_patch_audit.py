import unittest
from unittest.mock import patch
from test_entertainment import e, vs


def part(key,address=1,footprint=10,system='A',universe='1',channel='1',**extra):
    return {'part_id':key,'address':address,'footprint':footprint,'system':system,'universe':universe,
            'channel':channel,'accessory_index':-2,'fixture_mode':'Known Mode','gdtf_mode':'',**extra}


class PatchAuditTests(unittest.TestCase):
    def test_adjacent_ranges_and_different_systems_do_not_conflict(self):
        r=e.audit_patch_parts([part('a'),part('b',11),part('c',system='B'),part('d',universe='2')])
        self.assertFalse(r['needs_review']);self.assertEqual(r['patched_parts'],4)

    def test_overlap_same_start_and_identical_patch_have_different_meanings(self):
        r=e.audit_patch_parts([part('a'),part('b',5),part('c',channel='2'),part('d')])
        self.assertEqual(r['issue_counts']['identical_patch'],1)
        self.assertEqual(r['issue_counts']['same_address_different_channel'],2)
        self.assertEqual(r['issue_counts']['address_overlap'],3)
        identical=next(i for i in r['issues'] if i['code']=='identical_patch')
        self.assertEqual(identical['severity'],'review')

    def test_boundary_512_is_inclusive_and_overflow_is_reported(self):
        r=e.audit_patch_parts([part('a',503),part('b',504,system='B')])
        self.assertEqual(r['issue_counts'],{'universe_overflow':1})

    def test_unpatched_clamp_excluded_but_patched_accessory_audited(self):
        r=e.audit_patch_parts([part('a'),part('clamp',0,0,accessory_index=0),part('scroller',1,8,accessory_index=1)])
        self.assertEqual(r['non_control_accessories'],1)
        self.assertEqual(r['issue_counts']['identical_patch'],1)

    def test_missing_data_is_not_filled_from_assumptions(self):
        r=e.audit_patch_parts([part('a',0,0,fixture_mode=''),part('b',system='',universe='')])
        for code in ['unpatched','zero_footprint_unpatched','mode_unspecified','invalid_system','missing_universe']:
            self.assertEqual(r['issue_counts'][code],1)

    def test_errors_survive_review_output_cap_and_totals_cover_all_parts(self):
        r=e.audit_patch_parts([part(str(i),0,fixture_mode='') for i in range(100)]+[part('bad',513)],1)
        self.assertEqual(r['issues'][0]['code'],'invalid_address')
        self.assertEqual(r['issue_count'],201);self.assertTrue(r['issues_truncated'])

    def test_native_adapter_uses_minus_two_and_typed_numeric_getters(self):
        vs.reset_mock(return_value=True,side_effect=True)
        vs.ForEachObject.side_effect=lambda cb,criteria:cb('device')
        vs.GetObjectUuid.return_value='uuid';vs.GetName.return_value='Fixture'
        vs.GetFPathName.return_value='test.vwx';vs.LDevice_GetCellCount.return_value=2
        vs.IsLDSchematicViewObj.return_value=False
        vs.LDevice_GetAccCount.return_value=0
        vs.LDevice_GetParamStr.side_effect=lambda h,c,a,n:{'System':'A','Universe':'1','Fixture Mode':'Known'}.get(n,'')
        vs.LDevice_GetParamLong.side_effect=lambda h,c,a,n:1+c*10 if n=='DMX Address' else 10
        with patch.object(e,'plugin',return_value='Lighting Device'):
            r=e.get_lighting_patch_audit({'include_parts':True})
        self.assertEqual(r['parts_scanned'],2);self.assertFalse(r['has_errors'])
        self.assertTrue(all(c.args[2]==-2 for c in vs.LDevice_GetParamLong.call_args_list))
        vs.SetRField.assert_not_called();vs.ResetObject.assert_not_called()

    def test_schematic_representations_do_not_double_count_fixture_patch(self):
        vs.reset_mock(return_value=True,side_effect=True)
        vs.ForEachObject.side_effect=lambda cb,criteria:cb('schematic')
        vs.IsLDSchematicViewObj.return_value=True;vs.GetFPathName.return_value='test.vwx'
        with patch.object(e,'plugin',return_value='Lighting Device'):
            r=e.get_lighting_patch_audit({})
        self.assertEqual(r['excluded_schematic_views'],1);self.assertEqual(r['matched_devices'],0)
        vs.LDevice_GetCellCount.assert_not_called()

    def test_audit_is_readonly_but_needs_native_menu_context(self):
        from test_entertainment import server,pump
        self.assertTrue(server._is_readonly('get_lighting_patch_audit'))
        self.assertIn('get_lighting_patch_audit',server._MENU_CONTEXT_READS)


if __name__=='__main__':unittest.main()
