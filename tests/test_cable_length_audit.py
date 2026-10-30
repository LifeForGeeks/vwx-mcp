import copy
import unittest
from unittest.mock import patch
from test_entertainment import e, vs, server


class CableLengthAuditTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True, side_effect=True)
        vs.GetFPathName.return_value='QA.vwx'
        vs.GetRField.return_value='20ft'
        vs.GetName.return_value='QA'
        self.one_mm=1/25.4
        self.pio=240.0
        vs.ValidNumStr.side_effect=lambda text: (True,self.one_mm if text=='1mm' else self.pio)
        self.snapshot={'section_count':1,'break_count':0,'part_count':1,
            'sections':[{'drawn_length_mm':6096.0,'vertical_drop_mm':0,'part_count':1}]}
        self.geometry={'status':'ok','linear_length_local':240.0}
        self.addCleanup(patch.stopall)
        patch.object(e,'handle',return_value='cable').start()
        patch.object(e,'cable_sections_snapshot',side_effect=lambda h:copy.deepcopy(self.snapshot)).start()
        patch.object(e,'cable_geometry_snapshot',side_effect=lambda *a:copy.deepcopy(self.geometry)).start()

    def audit(self,**kwargs):
        return e.get_cable_length_audit({'object_ids':['id'],**kwargs})

    def test_detects_observed_zero_pio_despite_valid_native_section_and_stock(self):
        self.pio=0
        result=self.audit(); row=result['cables'][0]
        self.assertEqual(row['result'],'mismatch')
        self.assertEqual(row['section_drawn_sum_mm'],6096)
        self.assertEqual(row['issues'],['pio_length_positive','pio_matches_section'])
        self.assertTrue(row['checks']['local_path_matches_section'])
        vs.ResetObject.assert_not_called();vs.SetRField.assert_not_called()

    def test_document_units_and_tolerance_are_explicit(self):
        for one_mm,pio in [(1/25.4,240),(1,6096),(1/304.8,20)]:
            self.one_mm=one_mm;self.pio=pio;self.geometry['linear_length_local']=pio
            row=self.audit()['cables'][0]
            self.assertEqual(row['result'],'consistent_in_scope')
            self.assertAlmostEqual(row['pio_length_mm'],6096)
        self.pio+=0.5/304.8
        self.assertEqual(self.audit(tolerance_mm=1)['cables'][0]['result'],'consistent_in_scope')
        self.assertEqual(self.audit(tolerance_mm=0.1)['cables'][0]['result'],'mismatch')

    def test_unvalidated_geometry_and_section_topology_cannot_pass(self):
        self.geometry['linear_length_local']=None
        self.assertEqual(self.audit()['cables'][0]['result'],'incomplete')
        self.geometry['linear_length_local']=240
        for field,value in [('section_count',2),('break_count',1)]:
            old=self.snapshot[field];self.snapshot[field]=value
            row=self.audit()['cables'][0]
            self.assertEqual(row['result'],'incomplete');self.assertFalse(row['comparison_supported'])
            self.snapshot[field]=old
        self.snapshot['sections'][0]['vertical_drop_mm']=100
        self.assertEqual(self.audit()['cables'][0]['result'],'incomplete')

    def test_unreadable_negative_and_nonfinite_pio_lengths_are_not_zero(self):
        for value in [float('nan'),float('inf'),-1]:
            self.pio=value;row=self.audit()['cables'][0]
            self.assertIsNone(row['pio_length_mm']);self.assertIn('pio_length_unreadable',row['issues'])
        vs.GetRField.return_value=''
        self.assertIsNone(self.audit()['cables'][0]['pio_length_mm'])

    def test_count_mismatch_and_read_only_scope(self):
        self.snapshot['part_count']=2
        result=self.audit()
        self.assertIn('section_part_counts_match',result['cables'][0]['issues'])
        self.assertFalse(result['world_geometry_verified']);self.assertFalse(result['electrical_design_verified'])
        self.assertIn('get_cable_length_audit',server._MENU_CONTEXT_READS)

    def test_rejects_invalid_bounds_and_units(self):
        for kwargs in [{'object_ids':[]},{'object_ids':['A','a']},{'object_ids':['x']*11},
                       {'tolerance_mm':True},{'tolerance_mm':-1},{'tolerance_mm':101},
                       {'tolerance_mm':float('nan')},{'unexpected':True}]:
            self.assertEqual(self.audit(**kwargs)['status'],'error')
        vs.ValidNumStr.assert_not_called()
        self.one_mm=0
        self.assertEqual(self.audit()['status'],'error')


if __name__=='__main__':unittest.main()
