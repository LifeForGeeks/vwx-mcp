import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'vwx-plugin'),str(ROOT/'mcp-server')]
vs=MagicMock(name='vs'); sys.modules['vs']=vs
import entertainment as e
import commands
import entertainment_tools as surface
import vwx_mcp_server as server
import vwx_pump as pump


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.doc=str(ROOT/'tests'/'Scratch.vwx')
        vs.GetFPathName.return_value=self.doc
        vs.GetUnits.return_value=(25,3,2,1,'in','sq ft')

    def test_wrong_document_rejected_before_native_mutation(self):
        result=e.ensure_drawing_structure({'expected_document':str(ROOT/'Other.vwx'),'layers':[],'classes':[]})
        self.assertEqual(result['status'],'error'); vs.CreateLayer.assert_not_called(); vs.NameClass.assert_not_called()

    def setup_listing(self):
        vs.ForEachObject.side_effect=lambda callback,criteria:[callback(h) for h in ['C','B','A']]
        vs.GetParametricRecord.return_value='record'
        vs.GetName.side_effect=lambda h:'Lighting Device' if h=='record' else h
        vs.GetObjectUuid.side_effect=lambda h:h
        vs.GetLayer.return_value='layer';vs.GetLName.return_value='Lighting';vs.GetClass.return_value='LX'
        vs.GetRField.side_effect=lambda h,r,k:('Same Symbol' if k=='Symbol Name' else
            'Owned' if k=='Body Inventory' else h if k=='Lens Inventory' else 'same')
        vs.OLDGetHangingPos.side_effect=lambda h,c:None if h=='B' else 'position'
        vs.LDevice_GetAccCount.side_effect=lambda h,c:{'A':2,'B':0,'C':1}[h]
        vs.FLayer.return_value=None;vs.ClassNum.return_value=0;vs.Count.return_value=3

    def test_summary_counts_all_matches_and_keeps_source_groups_distinct(self):
        self.setup_listing()
        with patch.object(e,'light') as detailed:
            r=e.get_entertainment_state({'limit':1})
        self.assertEqual(r['matched_devices'],3)
        self.assertEqual(r['summary'],{'attached_devices':2,'unattached_devices':1,'accessories_cell_0':3})
        self.assertEqual(r['inventory']['distinct_groups'],3)
        self.assertEqual(sum(g['count'] for g in r['inventory']['groups']),3)
        self.assertNotIn('devices',r);self.assertNotIn('layers',r)
        detailed.assert_not_called();vs.GetEntityMatrix.assert_not_called();vs.LDevice_GetAccPos3D.assert_not_called()

    def test_device_pages_are_uuid_sorted_without_dropping_global_scope_counts(self):
        self.setup_listing()
        r=e.get_entertainment_state({'detail':'devices','limit':1,'offset':1})
        self.assertEqual([d['object_id'] for d in r['devices']],['B'])
        self.assertEqual(r['next_offset'],2);self.assertTrue(r['truncated'])
        self.assertEqual(r['matched_devices'],3);self.assertIsNone(r['devices'][0]['hanging_position_id'])
        last=e.get_entertainment_state({'detail':'devices','limit':2,'offset':2})
        self.assertEqual(last['returned'],1);self.assertIsNone(last['next_offset'])

    def test_full_inspection_only_expands_requested_page(self):
        self.setup_listing()
        with patch.object(e,'light',side_effect=lambda h:{'expanded':h}) as detailed:
            r=e.get_entertainment_state({'detail':'full','include_structure':False,'limit':1,'offset':2})
        self.assertEqual(r['devices'],[{'expanded':'C'}]);detailed.assert_called_once_with('C')

    def test_native_creation_rejected_before_any_single_event_batch_edits(self):
        with patch.object(commands,'draw_rectangle') as draw:
            result=commands._batch({'calls':[{'command':'draw_rectangle'}, {'command':'create_native_objects'}]})
        self.assertEqual(result['code'],'VM_EVENT_BOUNDARY_REQUIRED')
        draw.assert_not_called()

    def test_units_reject_nonfinite_and_wrong_dimension(self):
        for value in [float('nan'),float('inf'),True]:
            with self.assertRaises(ValueError):e.number(value)
        with self.assertRaises(ValueError):e.point([1,2])

    def test_rotation_basis_is_orthonormal(self):
        vs.SetEntityMatrixN.return_value=True
        e.set_matrix('fixture',(10,20,30),(30,-40,70))
        _,u,v,w,p=vs.SetEntityMatrixN.call_args.args
        for axis in [u,v,w]:self.assertAlmostEqual(sum(x*x for x in axis),1)
        for a,b in [(u,v),(u,w),(v,w)]:self.assertAlmostEqual(sum(x*y for x,y in zip(a,b)),0)
        self.assertEqual(p,(10,20,30))

    def test_accessory_reuse_and_mm_contract(self):
        vs.GetObjectByUuid.return_value='fixture'; vs.GetObject.return_value='symbol'; vs.GetTypeN.return_value=16
        vs.GetParametricRecord.return_value='rec'; vs.GetName.side_effect=lambda h:'Lighting Device' if h=='rec' else 'F1'
        vs.GetObjectUuid.side_effect=lambda h:h; vs.GetLayer.return_value='layer'; vs.GetLName.return_value='Fixtures'; vs.GetClass.return_value='LX'
        vs.GetEntityMatrix.return_value=(True,(10,20,30),0,0,0); vs.OLDGetHangingPos.return_value='hp'
        acc=[]
        vs.GetRField.return_value=''
        vs.LDevice_GetAccCount.side_effect=lambda *_:len(acc)
        vs.LDevice_GetParamStr.side_effect=lambda h,c,i,f:acc[i]['symbol']
        vs.LDevice_GetAccPos3D.side_effect=lambda h,c,i:acc[i]['pose']
        def add(*_):
            acc.append({'symbol':'Clamp pair','pose':((0,0,0),0,0,0)});return len(acc)-1
        vs.LDevice_AddAccessory.side_effect=add
        vs.LDevice_SetAccPos3D.side_effect=lambda h,c,i,p,rx,ry,rz:acc[i].update(pose=(tuple(x/25.4 for x in p),rx,ry,rz))
        params={'expected_document':self.doc,'device_ids':['fixture'],'accessories':[{'symbol':'Clamp pair','position_mm':[0,0,85]}]}
        self.assertEqual(e.set_lighting_accessories(params)['status'],'ok')
        self.assertEqual(e.set_lighting_accessories(params)['status'],'ok')
        self.assertEqual(len(acc),1);self.assertEqual(acc[0]['pose'][0],(0,0,85/25.4))
        vs.SetEntityMatrixN.assert_not_called()

    def test_shared_worksheet_duplicates_image_not_resource(self):
        vs.GetObject.side_effect=lambda n:{'Report':'ws','A101':'sheet'}.get(n)
        vs.GetTypeN.side_effect=lambda h:{'ws':18,'sheet':31}[h]
        vs.GetObjectVariableInt.return_value=2;vs.GetWSImage.return_value='canonical'
        vs.HDuplicate.return_value='copy';vs.SetParent.return_value=True;vs.GetWSFromImage.return_value='ws'
        vs.GetBBox.return_value=((0,0),(3,-2));vs.GetObjectUuid.side_effect=lambda h:h
        vs.GetLName.return_value='Prior';vs.ActiveClass.return_value='None'
        result=e.place_shared_worksheet({'expected_document':self.doc,'worksheet':'Report','sheet':'A101','name':'placed','position':[5,7]})
        self.assertEqual(result['status'],'ok');vs.HDuplicate.assert_called_once_with('canonical',0,0)
        vs.CreateWSImage.assert_not_called();vs.CreateWS.assert_not_called();vs.HMove.assert_called_once_with('copy',5,7)

    def test_native_dimension_enums_and_legacy_mapping(self):
        self.assertEqual([commands._linear_dim_type(x) for x in [0,1,4,771,772,773]],[0,1,4,4,0,1])
        with self.assertRaises(ValueError):commands._linear_dim_type(999)
        with patch.object(commands,'_with_layer_class',return_value=(None,None)),patch.object(commands,'_restore'),patch.object(commands,'_newobj_result',return_value={}):
            commands.create_linear_dimension({'x1':0,'y1':0,'x2':120,'y2':0,'offset':24,'dim_type':772})
        self.assertEqual(vs.LinearDim.call_args.args,((0.0,0.0),(120.0,0.0),24.0,0,769,1025,0.0))

    def test_plan_viewport_projects_native_2d_and_hides_helpers(self):
        vs.GetObject.side_effect=lambda n:{'Sheet':'sheet','Layer':'layer'}.get(n)
        vs.GetTypeN.return_value=31
        vs.GetObjectVariableInt.side_effect=lambda h,k:2 if h=='sheet' else 1
        vs.CreateVP.return_value='vp';vs.SetVPCropObject.return_value=True
        vs.FLayer.return_value='layer';vs.NextLayer.return_value=None
        vs.ClassNum.return_value=1;vs.ClassList.return_value='Lighting-Input-2D'
        vs.GetLName.return_value='Prior';vs.ActiveClass.return_value='None'
        result=e.create_sheet_viewport({'expected_document':self.doc,'sheet':'Sheet','name':'New VP','scale':48,
            'bounds':[1980,180,2180,-100],'center':[-5,0],'layers':['Layer'],'hidden_classes':[]})
        self.assertEqual(result['status'],'ok',result)
        self.assertIn(unittest.mock.call('vp',1005,True),vs.SetObjectVariableBoolean.call_args_list)
        vs.SetVPClassVisibility.assert_called_with('vp','Lighting-Input-2D',-1)
        self.assertEqual(result['annotation_offset'],[-2320.,-40.])
        self.assertGreaterEqual(vs.ResetBBox.call_count,2)

    def test_class_override_uses_viewport_class_not_fake_handle(self):
        vs.GetTypeN.return_value=122;vs.GetObject.return_value='class';vs.CreateVPClOvrd.return_value=None
        with patch.object(commands,'_h',return_value='vp'),patch.object(commands,'_vp_cl_props',return_value={'pen_fore':(257,514,771)}):
            r=commands.add_vp_class_override({'viewport_id':'uuid','class_name':'Rigging','pen_fore_rgb':[1,2,3]})
        self.assertEqual(r['status'],'ok');vs.SetVPClOvrdPenFore.assert_called_once_with('vp','Rigging',257,514,771)

    def test_annotation_font_is_sized_after_parent_change(self):
        vs.GetObjectByUuid.return_value='vp';vs.GetTypeN.return_value=122
        vs.GetLayer.return_value='sheet';vs.GetObjectVariableInt.return_value=2
        vs.GetObjectVariableReal.return_value=48;vs.GetObject.return_value=None
        vs.GetLName.return_value='Sheet';vs.ActiveClass.return_value='None'
        vs.LNewObj.return_value='dim';vs.AddVPAnnotationObject.return_value=True
        result=e.annotate_viewport({'expected_document':self.doc,'viewport_id':'vp','annotation_offset':[0,0],
            'items':[{'name':'Dimension','kind':'dimension','position':[0,0],'end':[96,0],'font_size':10}]})
        self.assertEqual(result['status'],'ok',result)
        calls=vs.mock_calls
        adopt=calls.index(unittest.mock.call.AddVPAnnotationObject('vp','dim'))
        size=calls.index(unittest.mock.call.SetObjectVariableReal('dim',17,10/72*25.4*48))
        self.assertLess(adopt,size)
        vs.SetLSByClass.assert_called_once_with('dim')
        vs.ResetObject.assert_called_once_with('dim')

    def test_wrapper_payload_serializable_and_no_dispatcher(self):
        exposed={};calls=[]
        def register(fn):exposed[fn.__name__]=fn;return fn
        def cmd(name,p):json.dumps(p);calls.append((name,p));return 'ok'
        surface.register(register,cmd)
        exposed['save_document_checked'](self.doc)
        exposed['create_sheet_viewport'](self.doc,'A','VP',48,(-10,10,10,-10),(0,0),['Layer'],[])
        exposed['get_lighting_patch_audit']()
        exposed['get_viewport_display'](['uuid'])
        exposed['get_viewport_documentation'](['uuid'])
        exposed['get_cable_connector_catalog'](names=['XLR5'],include_sockets=True)
        exposed['get_electrical_components'](object_ids=['id'],detail='components')
        self.assertTrue(all('cmd' not in p for _,p in calls));self.assertEqual(len(exposed),48)
        for name in exposed:self.assertIn(name,server.TOOL_TAGS)
        self.assertTrue(server._is_readonly('get_entertainment_state'))
        self.assertFalse(server._is_readonly('attach_loads_to_position'))
        self.assertIn('get_entertainment_state',server._MENU_CONTEXT_READS)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        with patch.object(server,'_plugin_dir',return_value=str(self.base)):
            self.transport=server.VwxFileTransport()
    def tearDown(self):self.tmp.cleanup()

    def test_native_pump_yields_before_finalization_can_share_creation_event(self):
        def claim(_):
            pump._yield_to_host=True
            return True
        with patch.object(pump,'_housekeep'),patch.object(pump,'_log'),patch.object(pump,'_list_jobs',return_value=['create','finalize']),patch.object(pump,'_claim_and_run',side_effect=claim) as run:
            pump.pump_all()
        run.assert_called_once_with('create')

    def test_creation_finalizes_in_separate_native_command(self):
        connection=MagicMock()
        created=[{'object_id':'uuid','name':'Deck'}]
        connection.send_command.side_effect=[{'status':'ok','created':created,'requires_finalization':True,'next_command':'finalize_native_objects'},
                                            {'status':'ok','finalized_ids':['uuid']}]
        with patch.object(server,'get_vwx_connection',return_value=connection):
            result=json.loads(server.cmd('create_native_objects',{'expected_document':'test.vwx','items':[]}))
        self.assertFalse(result['requires_finalization'])
        connection.send_command.assert_has_calls([
            unittest.mock.call('create_native_objects',{'expected_document':'test.vwx','items':[]}),
            unittest.mock.call('finalize_native_objects',{'expected_document':'test.vwx','created':created})])

    def test_failed_finalization_preserves_creation_for_targeted_recovery(self):
        connection=MagicMock()
        connection.send_command.side_effect=[{'status':'ok','created':[{'object_id':'uuid'}],'requires_finalization':True},
                                            {'error':'timeout','cid':'abc','retry_safe':False}]
        with patch.object(server,'get_vwx_connection',return_value=connection):
            result=json.loads(server.cmd('create_native_objects',{'expected_document':'test.vwx'}))
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['recovery_command'],'finalize_native_objects')
        self.assertEqual(result['finalization']['cid'],'abc')
        self.assertEqual(connection.send_command.call_count,2)

    def test_completed_result_can_be_polled_twice(self):
        (Path(self.transport.results)/'abc123.json').write_text(json.dumps({'status':'ok','count':2}))
        for _ in range(2):
            self.assertEqual(self.transport.send_command('get_bridge_job_status',{'cid':'abc123'})['result']['count'],2)
        self.assertTrue((Path(self.transport.results)/'abc123.json').exists())

    def test_status_rejects_path_traversal(self):
        r=self.transport.send_command('poll',{'cid':'../../config'})
        self.assertEqual(r['code'],'INVALID_CID')

    def test_claimed_long_job_survives_stale_heartbeat(self):
        done=threading.Event()
        def native():
            while not done.is_set():
                jobs=list(Path(self.transport.jobs).glob('*.json'))
                if jobs:
                    job=json.loads(jobs[0].read_text());jobs[0].unlink()
                    time.sleep(.10) # Native operation blocks UI heartbeat after claiming.
                    (Path(self.transport.results)/(job['_cid']+'.json')).write_text(json.dumps({'status':'ok','native_finished':True}))
                    return
                time.sleep(.001)
        worker=threading.Thread(target=native);worker.start()
        try:
            with patch.object(server,'VWX_SOCKET_TIMEOUT',1),patch.object(server,'VWX_ALIVE_GRACE',.03),patch.object(self.transport,'bridge_state',return_value=(False,False,1000)):
                result=self.transport.send_command('render',{})
            self.assertTrue(result.get('native_finished'),result)
        finally:done.set();worker.join(2)

    def test_unclaimed_and_claimed_timeouts_distinguishable(self):
        with patch.object(server,'VWX_SOCKET_TIMEOUT',0):
            unclaimed=self.transport.send_command('mutation',{})
        self.assertTrue(unclaimed['retry_safe']);self.assertEqual(unclaimed['code'],'VW_JOB_UNCLAIMED')
        with patch.object(server,'VWX_SOCKET_TIMEOUT',0),patch.object(self.transport,'_discard',return_value=False):
            claimed=self.transport.send_command('mutation',{})
        self.assertFalse(claimed['retry_safe']);self.assertEqual(claimed['code'],'VW_DISPATCH_STUCK')


if __name__=='__main__':unittest.main()
