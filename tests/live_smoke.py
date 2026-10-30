"""Explicit opt-in integration exercise against the separate Toolkit QA copy.
Never silently reruns a failed creation. Results are saved after each call.
"""
import argparse,asyncio,json,os,sys,shutil
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['objects','sheets','finish','save']);args=parser.parse_args()
    report={'phase':args.phase,'calls':[]}
    report_path=QA/('live-'+args.phase+'.json')
    transport=StdioTransport(command=sys.executable,args=[str(ROOT/'mcp-server/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CALL_TIMEOUT':'180','VWX_SOCKET_TIMEOUT':'170','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        tools=await client.list_tools();report['tool_count']=len(tools);report['tools']=[t.name for t in tools if t.name in ['create_native_objects','get_entertainment_state','create_truss_position']]
        async def call(name,params,expect_error=False):
            result=await client.call_tool(name,params,timeout=180,raise_on_error=False)
            data=json.loads(next(c.text for c in result.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':params,'result':data})
            report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
            error=bool(data.get('error')) or result.is_error
            print(name, 'EXPECTED ERROR' if error and expect_error else 'ERROR' if error else 'OK',flush=True)
            assert error==expect_error,(name,data)
            return data
        state=await call('get_entertainment_state',{'criteria':"((PON='Lighting Device') & (N='VM-LX-035'))",'limit':1,'detail':'full'})
        assert os.path.normcase(os.path.normpath(state['document']))==os.path.normcase(DOC),state.get('document')
        if args.phase=='objects':
            structure={'expected_document':DOC,'layers':[{'name':'Toolkit QA','kind':'design','scale':48},
                       {'name':'QA-101','kind':'sheet'},{'name':'QA-102','kind':'sheet'}],'classes':['TK-Lighting','TK-Rigging','TK-Staging','TK-Video']}
            await call('ensure_drawing_structure',structure);repeat=await call('ensure_drawing_structure',structure)
            assert all(not x['created'] for x in repeat['layers'])
            await call('ensure_drawing_structure',{**structure,'expected_document':str(QA/'Wrong.vwx')},True)
            library=r'C:\Program Files\Vectorworks 2026\Libraries\Entertainment\Video LED\Panels\ROE Visual\Carbon.vwx'
            resources=await call('list_native_library_resources',{'path':library})
            fresh=next(r['name'] for r in resources['resources'] if not r['already_in_document'])
            await call('import_native_resources',{'expected_document':DOC,'path':library,'names':[fresh]})
            await call('import_native_resources',{'expected_document':DOC,'path':library,'names':[fresh]},True)
            objects={'expected_document':DOC,'items':[
                {'name':'TK-Fixture-1','plugin':'Lighting Device','layer':'Toolkit QA','class':'TK-Lighting','position':[2030,0,100],
                 'symbol':'Robe Lighting Robin Pointe','fields':{'FixtureID':'TK-1'}},
                {'name':'TK-Fixture-2','plugin':'Lighting Device','layer':'Toolkit QA','class':'TK-Lighting','position':[2070,0,100],
                 'symbol':'Robe Lighting Robin Pointe','fields':{'FixtureID':'TK-2'}},
                {'name':'TK-Deck-1','plugin':'Stage Deck','layer':'Toolkit QA','class':'TK-Staging','position':[2000,100,0],
                 'fields':{'Width':'96"','Depth':'48"','Height':'24"'}}]}
            created=await call('create_native_objects',objects);ids=[x['object_id'] for x in created['created'][:2]]
            await call('create_native_objects',objects,True)
            await call('get_native_schema',{'object_id':ids[0]})
            accessory={'expected_document':DOC,'device_ids':ids,'accessories':[{'symbol':'VM Robe 2 Omegas - 2x T57011 - pitch TBC','position_mm':[0,0,85]}]}
            await call('set_lighting_accessories',accessory);again=await call('set_lighting_accessories',accessory)
            assert all(len(x['accessories'])==1 for x in again['devices'])
            await call('set_lighting_sources',{'expected_document':DOC,'assignments':[
                {'object_id':ids[0],'sources':{'Body Inventory':'Armory OWN - Crankdat - Stock Unverified'}},
                {'object_id':ids[1],'sources':{'Body Inventory':'Armory RENTAL - Supplier TBC - Stock Unverified'}}]})
            rig=await call('create_truss_position',{'expected_document':DOC,'name':'TK-Position-1','position_name':'TOOLKIT TEST POSITION',
                'layer':'Toolkit QA','class_name':'TK-Rigging','position':[2000,0,100],
                'members':[{'name':'TK-Truss-1','symbol':"Tyler Truss 12x12 Standard Bolt 10' Straight",'position':[0,0,0]}]})
            attach=await call('attach_loads_to_position',{'expected_document':DOC,'position_id':rig['position']['object_id'],'expected_device_ids':ids})
            assert attach['attached_expected'] and not attach['moved_device_ids'],attach
            (QA/'object-ids.json').write_text(json.dumps({'devices':ids,'position':rig['position']['object_id']}))
        elif args.phase=='sheets':
            ids=json.loads((QA/'object-ids.json').read_text())
            columns=[{'header':'Fixture','formula':"='Lighting Device'.'FixtureID'"},
                     {'header':'Body source','formula':"='Lighting Device'.'Body Inventory'",'width':350}]
            report_args={'expected_document':DOC,'name':'TK Live Fixture Inventory','criteria':"((PON='Lighting Device') & (L='Toolkit QA'))",'columns':columns}
            w=await call('upsert_database_worksheet',report_args);assert w['valid'] and w['database_rows']==2,w
            w2=await call('upsert_database_worksheet',{**report_args,'update':True});assert w2['object_id']==w['object_id']
            for sheet in ['QA-101','QA-102']:
                await call('place_shared_worksheet',{'expected_document':DOC,'worksheet':'TK Live Fixture Inventory','sheet':sheet,'name':'TK-Report-'+sheet,'position':[2,8]})
            await call('place_shared_worksheet',{'expected_document':DOC,'worksheet':'TK Live Fixture Inventory','sheet':'QA-101','name':'TK-Report-QA-101','position':[2,8]})
            await call('update_title_block_data',{'expected_document':DOC,'project':{'Project Name':'VELVET MIRROR / TOOLKIT QA'},
                       'sheets':[{'sheet':'G-001','fields':{'Status':'TOOLKIT TEST COPY'}}]})
            vp=await call('create_sheet_viewport',{'expected_document':DOC,'sheet':'QA-101','name':'TK-Viewport-1','scale':48,
                'bounds':[1980,180,2180,-100],'center':[-5,0],'layers':['Toolkit QA'],
                'hidden_classes':['Lighting-Input-2D','Lighting-Input-3D']})
            await call('annotate_viewport',{'expected_document':DOC,'viewport_id':vp['object_id'],'annotation_offset':vp['annotation_offset'],
                'items':[{'name':'TK-Dimension-1','kind':'dimension','position':[2000,100],'end':[2096,100],'direction':'horizontal','offset':30},
                         {'name':'TK-Text-1','kind':'text','position':[2000,-65],'text':'NATIVE TOOLKIT / 1:48','font_size':12}]})
            await call('add_vp_class_override',{'viewport_id':vp['object_id'],'class_name':'TK-Rigging','pen_fore_rgb':[128,128,128]})
            ov=await call('list_vp_class_overrides',{'viewport_id':vp['object_id']});assert ov['count']==len(ov['overrides'])==1,ov
        elif args.phase=='finish':
            await call('set_fixture_label_layout',{'expected_document':DOC,'legend':'VM Fixture ID - Plan',
                'devices':[{'object_id':state['devices'][0]['object_id'],'label_index':1,'offset_mm':[900,0]}]})
            await call('create_native_objects',{'expected_document':DOC,'items':[
                {'name':'TK-LEDWall-1','plugin':'LEDWall','layer':'Toolkit QA','class':'TK-Video','position':[2200,0,48],
                 'fields':{'MainSymbol':'ROE Carbon CB5 LED Panel','WallMode':'Builder','BuilderColumns':'2','BuilderRows':'1',
                           'HangingSupport':False,'GroundSupport':False,'WallID':'TK-VIDEO-1'}}]})
            await call('save_document_checked',{'expected_document':DOC})
            configured=ROOT.parent/'vectorworks-rebuild/armory/evidence/print-check.pdf'
            backup=QA/'previous-configured-pdf.pdf';shutil.copy2(configured,backup)
            try:
                await call('export_sheet_set_checked',{'expected_document':DOC,'sheets':['QA-101','QA-102'],
                    'configured_output':str(configured),'destination':str(QA/'Velvet-Mirror-Toolkit-QA.pdf')})
            finally:shutil.copy2(backup,configured)
        else:
            await call('save_document_checked',{'expected_document':DOC})
        report['passed']=True;report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':asyncio.run(main())
