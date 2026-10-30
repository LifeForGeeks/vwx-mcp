"""Create a disposable QA device from a library symbol, verify footprint, then remove it."""
import asyncio,json,os,sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')


async def main():
    report={}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CALL_TIMEOUT':'180','VWX_SOCKET_TIMEOUT':'170','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,p):
            r=await client.call_tool(name,p,timeout=180)
            d=json.loads(next(c.text for c in r.content if c.type=='text'));assert not d.get('error'),d
            return d
        report['catalog_count']=len(await client.list_tools())
        assert report['catalog_count']==277
        created=await call('create_native_objects',{'expected_document':DOC,'items':[
            {'name':'TK-Footprint-Probe','plugin':'Lighting Device','layer':'Toolkit QA','class':'TK-Lighting',
             'position':[2350,0,100],'symbol':'Robe Lighting Robin Pointe','fields':{'FixtureID':'FOOTPRINT-PROBE'}}]})
        report['creation']=created
        (QA/'library-footprint-check.json').write_text(json.dumps(report,indent=2))
        audit=await call('get_lighting_patch_audit',{'criteria':"((PON='Lighting Device') & (N='TK-Footprint-Probe'))",'include_parts':True})
        report['audit']=audit
        assert audit['parts'][0]['footprint']==30,audit
        assert audit['unpatched_parts']==1 and not audit['has_errors'],audit
        deletion=await call('execute_script',{'code':'assert vs.GetFPathName() == '+repr(DOC)+'\n'
            'h=vs.GetObjectByUuid('+repr(created['created'][0]['object_id'])+');assert h and vs.GetName(h)=="TK-Footprint-Probe"\n'
            'vs.DelObject(h)\n__result__={"probe_removed":not bool(vs.GetObject("TK-Footprint-Probe"))}'})
        assert deletion['result']['probe_removed']
        report.update(passed=True,removed=True)
        (QA/'library-footprint-check.json').write_text(json.dumps(report,indent=2))
        print('PASS: 270 tools; fresh native library fixture retained 30-channel footprint; QA probe removed.')


if __name__=='__main__':asyncio.run(main())
