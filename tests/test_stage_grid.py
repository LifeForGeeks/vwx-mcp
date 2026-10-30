"""Guard, geometry planning and deferred-regeneration contracts for stage grids."""
import json
import unittest
from unittest.mock import patch
from test_entertainment import e, vs, server, commands, ROOT


class StageGridTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.doc=str(ROOT/'tests'/'Scratch.vwx'); vs.GetFPathName.return_value=self.doc
        vs.GetUnits.return_value=(25,3,2,1,'in','sq ft')
        vs.GetObject.return_value=None; vs.GetObjectVariableInt.return_value=1
        self.p={'expected_document':self.doc,'name':'Deck','layer':'Stage','class':'STG',
                'origin_mm':[254,508,0],'columns':2,'rows':2,'deck_size_mm':[1219.2,2438.4,609.6],
                'rotation':90,'rail_edges':['back','left','right']}

    def test_rotation_unit_conversion_and_only_perimeter_rails(self):
        plans=e.stage_grid_plan(self.p)
        self.assertTrue(e.same(plans[1]['position'],[10,68,0]))
        self.assertTrue(e.same(plans[2]['position'],[-86,20,0]))
        self.assertEqual(plans[0]['fields']['RailRight'],'None')
        self.assertEqual(plans[1]['fields']['RailLeft'],'None')
        self.assertEqual(plans[2]['fields']['RailBack'],'Straight')
        self.assertEqual(plans[0]['fields']['RailBack'],'None')
        self.assertEqual(plans[3]['fields']['Unit'],'Deck-R02-C02')
        # A metric drawing describes the same physical grid.
        vs.GetUnits.return_value=(25,3,2,25.4,'mm','sq m')
        metric=e.stage_grid_plan(self.p)
        self.assertTrue(e.same(metric[1]['position'],[254,1727.2,0]))

    def test_invalid_grid_rejected_before_any_creation(self):
        for edit in [{'columns':True},{'rows':26},{'deck_size_mm':[1,2,-1]},
                     {'rotation':float('nan')},{'rail_edges':['left','left']},
                     {'deck_size_mm':[1200,2400,20]},{'hidden_private_setting':True}]:
            with self.subTest(edit=edit):
                r=e.create_stage_deck_grid({**self.p,**edit});self.assertEqual(r['status'],'error')
        vs.CreateCustomObjectN.assert_not_called(); vs.DefineCustomObj.assert_not_called()

    def test_dry_run_creates_no_native_resources(self):
        with patch.object(e,'named',return_value='resource'):
            result=e.create_stage_deck_grid({**self.p,'dry_run':True})
        self.assertEqual(result['status'],'ok');self.assertEqual(result['count'],4)
        vs.DefineCustomObj.assert_not_called();vs.CreateCustomObjectN.assert_not_called()

    def test_existing_unit_rejected_even_if_object_name_differs(self):
        vs.ForEachObject.side_effect=lambda cb,criteria:cb('existing')
        vs.GetRField.return_value='deck-r02-c02'
        with patch.object(e,'named',return_value='resource'):
            result=e.create_stage_deck_grid(self.p)
        self.assertEqual(result['status'],'error');vs.CreateCustomObjectN.assert_not_called()

    def test_native_failure_retains_created_uuid(self):
        plans=e.stage_grid_plan(self.p)
        keys=list(plans[0]['fields'])
        vs.DefineCustomObj.return_value='definition';vs.NumFields.return_value=len(keys)
        vs.GetFldName.side_effect=lambda h,i:keys[i-1]
        vs.NumCustomObjectChoices.return_value=3
        vs.GetCustomObjectChoice.side_effect=lambda pn,key,i: (
            ['None','Straight','Straight'][i-1] if key.startswith('Rail') and key!='RailProfile'
            else plans[0]['fields'][key])
        vs.CreateCustomObjectN.side_effect=['deck',None];vs.GetObjectUuid.return_value='retained-uuid'
        vs.GetEntityMatrix.return_value=[True,plans[0]['position'],0,0,90]
        with patch.object(e,'named',return_value='resource'),patch.object(e,'context'),patch.object(e,'restore'),patch.object(e,'set_matrix') as place:
            result=e.create_stage_deck_grid(self.p)
        self.assertEqual(result['status'],'error');self.assertFalse(result['retry_safe'])
        self.assertEqual(result['created'][0]['object_id'],'retained-uuid')
        self.assertIsInstance(place.call_args.args[1],tuple)

    def test_post_event_verification_detects_changed_dimensions_and_layer(self):
        receipt={**e.stage_grid_plan(self.p)[0],'object_id':'deck'}
        actual={k:receipt[k] for k in ('name','layer','class')}
        actual.update(native_geometry_present=True,matrix=[True,receipt['position'],0,0,90],
                      lengths_mm=receipt['lengths_mm'],fields={'LegTotal':'4'})
        vs.GetRField.side_effect=lambda h,pn,k:e.scalar(receipt['fields'][k])
        with patch.object(e,'handle',return_value='deck'),patch.object(e,'stage_deck_snapshot',return_value=actual):
            p={'expected_document':self.doc,'created':[receipt]}
            self.assertTrue(e.get_stage_deck_verification(p)['verified'])
            actual['lengths_mm']={**receipt['lengths_mm'],'Width':1000}
            self.assertEqual(e.get_stage_deck_verification(p)['status'],'error')
            actual['lengths_mm']=receipt['lengths_mm'];actual['layer']='Wrong layer'
            self.assertEqual(e.get_stage_deck_verification(p)['status'],'error')

    def test_failed_post_event_read_never_recreates(self):
        connection=unittest.mock.MagicMock()
        connection.send_command.side_effect=[{'created':[{'object_id':'deck'}],'requires_verification':True},
                                             {'error':'Deck dimensions differ'}]
        with patch.object(server,'get_vwx_connection',return_value=connection):
            result=json.loads(server.cmd('create_stage_deck_grid',{'expected_document':self.doc}))
        self.assertFalse(result['retry_safe']);self.assertEqual(connection.send_command.call_count,2)
        self.assertEqual(result['recovery_command'],'get_stage_deck_verification')

    def test_stage_creation_rejects_single_event_batch(self):
        r=commands._batch({'calls':[{'command':'create_stage_deck_grid'}]})
        self.assertEqual(r['code'],'VM_EVENT_BOUNDARY_REQUIRED')


if __name__=='__main__':unittest.main()
