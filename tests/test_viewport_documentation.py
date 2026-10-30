import unittest
from test_entertainment import e,vs,server


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.fields={'old':{'Title':'Front Elevation','Drawing':'1','Sheet':'QA','fScale Config':'Scale Label','Custom Scale':''},
                     'new':{'Title':'Top Plan','Drawing':'1','Sheet':'QA','ScaleDisplay':'Custom','Custom Scale':'NOT TO SCALE'}}
        vs.GetObjectByUuid.side_effect=lambda h:h
        vs.GetObjectUuid.side_effect=lambda h:h
        vs.GetTypeN.side_effect=lambda h:122 if h=='vp' else 11 if h=='nested' else 86
        vs.GetName.side_effect=lambda h:{'old-record':'Drawing Label','new-record':'Drawing Label2'}.get(h,h)
        vs.GetLayer.return_value='sheet';vs.GetLName.return_value='QA';vs.GetClass.return_value='Labels'
        vs.GetObjectVariableString.side_effect=lambda h,k:'Top Plan' if k==1032 else '1'
        vs.GetObjectVariableInt.return_value=7
        vs.GetObjectVariableReal.return_value=48
        vs.GetObjectVariableBoolean.return_value=False
        vs.GetPref.return_value=True
        vs.GetVPGroup.return_value='annotations'
        vs.FInGroup.side_effect=lambda h:{'annotations':'old','nested':'new'}.get(h)
        vs.NextObj.side_effect=lambda h:'nested' if h=='old' else None
        vs.GetParametricRecord.side_effect=lambda h:h+'-record' if h in self.fields else None
        vs.NumFields.side_effect=lambda r:len(self.fields[r.removesuffix('-record')])
        vs.GetFldName.side_effect=lambda r,i:list(self.fields[r.removesuffix('-record')])[i-1]
        vs.GetRField.side_effect=lambda h,r,k:self.fields[h][k]
        vs.GetPluginStyle.return_value=''

    def run_tool(self,**kw):
        self.assertIn('get_viewport_documentation',e.COMMANDS)
        return e.COMMANDS['get_viewport_documentation']({'viewport_ids':['vp'],**kw})

    def test_two_label_generations_and_nested_groups(self):
        r=self.run_tool(include_labels=True)
        self.assertEqual(r['status'],'ok')
        self.assertEqual(r['viewports'][0]['label_count'],2)
        self.assertEqual({x['plugin'] for x in r['viewports'][0]['labels']},{'Drawing Label','Drawing Label2'})
        codes={x['code'] for x in r['issues']}
        self.assertTrue({'label_title_differs','title_view_review','custom_scale_review'} <= codes)
        self.assertFalse(r['physical_scale_verified'])

    def test_compact_output_does_not_reduce_issue_counts(self):
        r=self.run_tool(limit=1)
        self.assertEqual(len(r['issues']),1)
        self.assertGreater(r['issue_count'],1)
        self.assertTrue(r['issues_truncated'])
        self.assertNotIn('labels',r['viewports'][0])

    def test_missing_fields_are_unknown_not_blank_matches(self):
        del self.fields['new']['Title']
        r=self.run_tool(include_labels=True)
        label=next(x for x in r['viewports'][0]['labels'] if x['id']=='new')
        self.assertIsNone(label['fields']['Title'])
        self.assertIn('label_fields_missing',{x['code'] for x in r['issues']})

    def test_custom_views_and_sections_do_not_get_axis_guess(self):
        vs.GetObjectVariableInt.return_value=0
        r=self.run_tool()
        self.assertNotIn('title_view_review',{x['code'] for x in r['issues']})
        vs.GetObjectVariableInt.return_value=7
        vs.GetObjectVariableBoolean.return_value=True
        self.assertNotIn('title_view_review',{x['code'] for x in self.run_tool()['issues']})

    def test_empty_annotations_and_arbitrary_titles_are_not_errors(self):
        vs.GetVPGroup.return_value=None
        vs.GetObjectVariableString.side_effect=lambda h,k:'Stage world' if k==1032 else ''
        r=self.run_tool()
        self.assertEqual(r['issue_count'],0)
        self.assertEqual(r['viewports'][0]['label_count'],0)

    def test_invalid_scope_and_failed_native_reads_do_not_report_success(self):
        for kw in [{'viewport_ids':[]},{'viewport_ids':['vp']*2},{'limit':0},{'limit':101},{'include_labels':'yes'}]:
            self.assertEqual(self.run_tool(**kw)['status'],'error')
        vs.GetVPGroup.assert_not_called()
        vs.GetRField.side_effect=RuntimeError('native failed')
        self.assertEqual(self.run_tool()['status'],'error')

    def test_readonly_menu_context_and_no_label_reset(self):
        self.assertIn('get_viewport_documentation',server._MENU_CONTEXT_READS)
        self.assertTrue(server._is_readonly('get_viewport_documentation'))
        self.run_tool()
        vs.SetRField.assert_not_called();vs.ResetObject.assert_not_called();vs.UpdateVP.assert_not_called()


if __name__=='__main__':unittest.main()
