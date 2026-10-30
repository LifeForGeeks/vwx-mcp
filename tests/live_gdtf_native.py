"""Run ONCE after native-gdtf-exchange-deployment is installed and VW restarted.
Uses a dedicated test device with a deliberately generic GDTF to test the API contract.
This is not a manufacturer-correct Robe fixture or a production plot.
"""
import asyncio,json,os,sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from live_lighting_documentation import ROOT,QA,DOC,IDS

async def main():
    out=QA/'gdtf-native-installed.json';assert not out.exists(),'Existing one-shot receipt; inspect instead of rerunning'
    report={'calls':[]}
    source=r'C:\Program Files\Vectorworks 2026\Plug-Ins\VW_Spotlight\Data\GDTF\Generic@LED_RGB8.gdtf'
    exported=QA/'VM-QA-GDTF-Native-Export.gdtf';assert not exported.exists()
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args):
            r=await client.call_tool(name,args,timeout=60);value=json.loads(next(c.text for c in r.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':value});out.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert not value.get('error'),{k:v for k,v in value.items() if k not in ('receipt','recovery_params')}
            return value
        before=await call('get_lighting_documentation',{'object_ids':IDS})
        availability=await call('get_lighting_gdtf',{'object_ids':IDS})
        assert all(d['native_exchange_available'] for d in availability['devices'])
        info=await call('get_gdtf_file',{'path':source})
        await call('ensure_drawing_structure',{'expected_document':DOC,'layers':[{'name':'QA GDTF Exchange','kind':'design','scale':48}],
            'classes':['VM-QA-GDTF-Devices']})
        created=await call('create_native_objects',{'expected_document':DOC,'items':[{
            'name':'VM-QA-GDTF-GENERIC-CONTRACT','plugin':'Lighting Device','layer':'QA GDTF Exchange',
            'class':'VM-QA-GDTF-Devices','position':[0,0,0],'rotation':[0,0,0],
            'symbol':'Robe Lighting Robin Pointe','fields':{'Purpose':'QA API test only - generic RGB data, not a real fixture specification'}}]})
        oid=created['created'][0]['object_id'];report['probe_id']=oid
        current=await call('get_lighting_gdtf',{'object_ids':[oid]})
        assigned=await call('assign_gdtf_file',{'expected_document':DOC,'object_id':oid,
            'expected_fingerprint':current['devices'][0]['fingerprint'],'path':source,
            'expected_sha256':info['sha256'],'mode':'Default','use_gdtf_geometry':False})
        assert assigned['verification']['verified']
        result=await call('export_lighting_gdtf',{'expected_document':DOC,'object_id':oid,'path':str(exported)})
        actual=result['file']
        assert actual['fixture_type_id'].casefold()==info['fixture_type_id'].casefold()
        assert actual['modes']==info['modes']
        report['archive_hash_matches_source']=actual['sha256']==info['sha256']
        after=await call('get_lighting_documentation',{'object_ids':IDS});assert before==after
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,native_assignment_verified=True,native_export_identity_and_modes_verified=True,
            reference_fixtures_preserved=True,mvr_export_roundtrip_verified=False,visual_geometry_verified=False)
        out.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
