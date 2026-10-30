"""Read-only native-reader validation after bridge installation; separate QA only."""
import asyncio, json, os, sys
from pathlib import Path
from datetime import datetime, timezone
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]; QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')
VPS=['6f5066f2-3b7b-4b09-9395-98b4fddb5e68','175e5451-f435-4fe6-ba2a-b0457a8c1f3b']


async def main():
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    path=QA/'live-native-readers.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    async with Client(transport) as client:
        async def call(name,args):
            result=await client.call_tool(name,args,timeout=180)
            text=next(c.text for c in result.content if c.type=='text'); value=json.loads(text)
            report['calls'].append({'tool':name,'arguments':args,'result':value,'payload_bytes':len(text.encode())})
            path.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert not value.get('error'),value
            return value
        capture='assert vs.GetFPathName()=='+repr(DOC)+'''\nrows=[]
def read(h):
    if vs.GetRField(h,'Lighting Device','Symbol Name')=='Chauvet Color Strike M':
        rows.append({'id':vs.GetObjectUuid(h),'name':vs.GetName(h),'wattage':vs.GetRField(h,'Lighting Device','Wattage'),'symbol':vs.GetRField(h,'Lighting Device','Symbol Name')})
vs.ForEachObject(read,"(PON='Lighting Device')")
rows.sort(key=lambda r:r['id'])
__result__={'document':vs.GetFPathName(),'layer':vs.GetLName(vs.ActLayer()),'class':vs.ActiveClass(),'fixture_count':vs.Count("(PON='Lighting Device')"),'matching_fixtures':rows}
'''
        before=(await call('execute_script',{'code':capture}))['result']
        selected=before['matching_fixtures'][:2]; assert len(selected)==2
        args={'object_ids':[r['id'] for r in selected],'detail':'components','include_internal_connections':True,'limit':100}
        electrical=await call('get_electrical_components',args)
        outputs=[]
        for source,row in zip(selected,electrical['objects']):
            assert row['inspection_status']=='ok' and not row['components_truncated'],row
            consumers=[c for c in row['components'] if c['type']=='consumer']
            through=[c for c in row['components'] if c['is_link_through']]
            assert len(consumers)==1 and len(through)==1,row
            consumer=consumers[0]; output=through[0]
            # Stored field comparison only; no claim about actual fixture specification.
            assert source['wattage']=='870 W' and consumer['maximum_consumption_w']==870
            assert consumer['average_consumption_w']==870
            assert consumer['device_id'].lower()==source['id'].lower()
            assert output['device_id'].lower()==source['id'].lower()
            link=consumer['internal_connections'][0]
            assert link['other_component_id']==output['component_id'] and link['target_match_count']==1
            assert link['target_device_id'].lower()==source['id'].lower()
            outputs.append(output)
        assert outputs[0]['component_id']==outputs[1]['component_id']
        assert outputs[0]['device_id']!=outputs[1]['device_id']
        repeated=await call('get_electrical_components',args); assert repeated==electrical
        vp=await call('get_viewport_display',{'viewport_ids':VPS})
        for row in vp['viewports']:
            context=row['native_context']
            assert context['available'] and context['style']['native_ok']
            assert context['style']['resource_index']==0
            assert context['data_visualization']['available']
            assert not context['data_visualization']['enabled'] and not context['data_visualization']['paused']
        vp_again=await call('get_viewport_display',{'viewport_ids':VPS}); assert vp_again==vp
        # Known extension signature from our compiled SFunctionDef, not an inferred SDK call.
        invalid=(await call('execute_script',{'code':'assert vs.GetFPathName()=='+repr(DOC)+'\n__result__={"electrical":vs.VMGetElectricalComponents(None),"viewport":vs.VMGetViewportContext(None)}'}))['result']
        for raw in invalid.values():
            assert isinstance(raw,str) and json.loads(raw)['status']=='error'
        after=(await call('execute_script',{'code':capture}))['result']; assert before==after
        report.update(verified=True,paired_identity_verified=True,stored_wattage_agreement=True,
                      repeated_reads_stable=True,unstyled_viewport_context_verified=True,
                      captured_state_unchanged=True,external_connections_verified=False,
                      hardware_specifications_verified=False,visual_oip_schematic_comparison=False,
                      completed=datetime.now(timezone.utc).isoformat())
        path.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'verified':True,'calls':len(report['calls']),'fixtures':len(selected),'viewports':len(VPS)}))


if __name__=='__main__': asyncio.run(main())
