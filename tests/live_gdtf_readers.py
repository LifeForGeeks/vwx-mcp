"""Read-only installed GDTF/MVR checks before native extension restart."""
import asyncio,json,os,sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from live_lighting_documentation import ROOT,QA,DOC,IDS

async def main():
    out=QA/'gdtf-readers-installed.json';assert not out.exists()
    report={'calls':[]}
    path=r'C:\Program Files\Vectorworks 2026\Plug-Ins\VW_Spotlight\Data\GDTF\Generic@LED_RGB8.gdtf'
    sources=json.loads((ROOT.parent/'vectorworks-research/evidence/fall-tour-mvr-metadata.json').read_text(encoding='utf8'))
    mvr=next(r['path'] for r in sources if 'path' in r and Path(r['path']).is_file())
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args,allow_error=False):
            r=await client.call_tool(name,args,timeout=60);v=json.loads(next(c.text for c in r.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':v});out.write_text(json.dumps(report,indent=2),encoding='utf8')
            if not allow_error:assert not v.get('error'),v
            return v
        gd=await call('get_gdtf_file',{'path':path})
        assert gd['fixture_name']=='LED RGB8' and gd['modes'][0]['name']=='Default'
        assert gd['modes'][0]['simple_single_break_footprint']==3
        audit=await call('get_mvr_gdtf_audit',{'path':mvr,'limit':10})
        assert audit['fixture_count']>0 and audit['checked_gdtf_count']>0
        before=await call('get_lighting_gdtf',{'object_ids':IDS})
        assert all(not d['native_exchange_available'] for d in before['devices'])
        unavailable=await call('assign_gdtf_file',{'expected_document':DOC,'object_id':IDS[0],
            'expected_fingerprint':before['devices'][0]['fingerprint'],'path':path,'expected_sha256':gd['sha256'],
            'mode':'Default','use_gdtf_geometry':False},True)
        assert unavailable.get('error') and 'restarted' in unavailable['error']
        after=await call('get_lighting_gdtf',{'object_ids':IDS});assert after==before
        report.update(verified=True,readers_verified=True,missing_extension_blocks_mutation=True,
            source_unchanged=True,native_assignment_verified=False,native_export_verified=False,
            mvr_fixtures=audit['fixture_count'],mvr_gdtf_issues=audit['issue_counts'])
        out.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
