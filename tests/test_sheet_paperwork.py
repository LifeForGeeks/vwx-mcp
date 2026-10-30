import unittest
from unittest.mock import patch
from test_entertainment import e, vs, server

class SheetPaperworkTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.addCleanup(patch.stopall);patch.object(e,'sheet',side_effect=lambda n:n).start()
        vs.GetFPathName.return_value='QA.vwx'
        vs.FInLayer.side_effect=lambda h:{'S1':'v1','S2':'v3'}.get(h)
        vs.NextObj.side_effect=lambda h:{'v1':'group','v2':'image1','image1':'border1','v3':'image2','image2':'border2'}.get(h)
        vs.FInGroup.side_effect=lambda h:'v2' if h=='group' else None
        self.types={'v1':122,'v2':122,'v3':122,'group':11,'image1':56,'image2':56,'ws':18,'border1':86,'border2':86}
        vs.GetTypeN.side_effect=lambda h:self.types[h]
        vs.GetObjectUuid.side_effect=lambda h:h;vs.GetName.side_effect=lambda h:h;vs.GetClass.return_value='None'
        patch.object(e,'plugin',return_value='Title Block Border').start()
        vs.GetObjectVariableReal.return_value=48.0;vs.GetObjectVariableInt.return_value=7
        vs.GetObjectVariableBoolean.return_value=False;vs.VPHasCropObject.return_value=True
        vs.GetObjectVariableString.side_effect=lambda h,k:'Plan' if k==1032 else '1'
        vs.GetWSFromImage.return_value='ws';vs.GetWSImageScaleF.return_value=1.0;vs.GetWSRowColumnCount.return_value=(2,4)

    def run_audit(self,**p):return e.get_sheet_paperwork_audit({'sheets':['S1','S2'],**p})

    def test_duplicate_numbers_only_within_each_sheet(self):
        r=self.run_audit();self.assertEqual(r['status'],'ok')
        self.assertEqual(r['issue_counts'],{'duplicate_drawing_number':1})
        self.assertEqual(r['issues'][0]['sheet'],'S1');self.assertEqual(r['issues'][0]['count'],2)
        self.assertEqual(r['sheets'][0]['viewport_count'],2)

    def test_images_share_one_resource_across_sheets(self):
        r=self.run_audit();self.assertEqual(r['worksheet_resource_count'],1)
        self.assertEqual(r['worksheet_resources'],[{'worksheet_id':'ws','worksheet':'ws','images':2,'sheets':['S1','S2']}])

    def test_detail_limits_preserve_counts_and_prioritize_errors(self):
        vs.GetObjectVariableBoolean.return_value=True
        r=self.run_audit(limit=1)
        self.assertEqual(r['issue_counts']['viewport_needs_update'],3)
        self.assertEqual(r['issues'][0]['severity'],'error');self.assertTrue(r['issues_truncated'])
        self.assertEqual(r['sheets'][0]['viewport_count'],2);self.assertTrue(r['sheets'][0]['details_truncated'])

    def test_invalid_scale_and_broken_worksheet_are_reported(self):
        vs.GetObjectVariableReal.return_value=float('nan');vs.GetWSFromImage.return_value=None
        r=self.run_audit();self.assertEqual(r['issue_counts']['invalid_viewport_scale'],3)
        self.assertEqual(r['issue_counts']['missing_worksheet_resource'],2)
        self.assertIsNone(r['sheets'][0]['viewports'][0]['scale'])

    def test_empty_sheet_is_a_review_not_a_clean_issued_drawing(self):
        vs.FInLayer.return_value=None;vs.FInLayer.side_effect=None
        r=self.run_audit();self.assertFalse(r['has_errors']);self.assertEqual(r['issue_counts']['no_title_block_review'],2)

    def test_cycle_and_duplicate_sheet_rejected(self):
        vs.NextObj.side_effect=lambda h:'v1'
        self.assertEqual(self.run_audit()['status'],'error')
        self.assertEqual(self.run_audit(sheets=['S1','S1'])['status'],'error')

    def test_does_not_activate_recalculate_or_regenerate(self):
        self.run_audit();vs.Layer.assert_not_called();vs.RecalculateWS.assert_not_called()
        vs.UpdateVP.assert_not_called();vs.ResetObject.assert_not_called();vs.SetRField.assert_not_called()
        self.assertTrue(server._is_readonly('get_sheet_paperwork_audit'))
        self.assertIn('get_sheet_paperwork_audit',server._MENU_CONTEXT_READS)

if __name__=='__main__':unittest.main()
