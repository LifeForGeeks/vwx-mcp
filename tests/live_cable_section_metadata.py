"""One-shot native section metadata + run synchronization + worksheet roundtrip."""
import asyncio
import json
import os
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
IDS=['c9fc829f-e0ae-433b-a9f2-123ba01c98d7','ad1a00dd-d227-450c-a71f-df7279c8eba3']

async def main():
    out=ROOT/'evidence/live-qa/cable-section-metadata-installed.json'
    if out.exists():raise RuntimeError('Existing mutation receipt: inspect before retry')
    report={'calls':[],'verified':False}
    def persist():out.write_text(json.dumps(report,indent=2),encoding='utf8')
    persist()
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        surface=await client.list_tools();report['tool_count']=len(surface)
        assert not next(t for t in surface if t.name=='set_cable_sections').annotations.readOnlyHint
        async def call(name,args,ok=True):
            row={'tool':name,'arguments':args};report['calls'].append(row);persist()
            raw=await client.call_tool(name,args,timeout=45)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            row['result']=result;persist()
            assert (result.get('status')=='ok')==ok,result
            return result
        before=await call('get_cable_sections',{'object_ids':IDS})
        assert Path(before['document'])==DOC
        for index,cable in enumerate(before['cables']):
            assert cable['section_count']==1 and cable['break_count']==0
            marker='VM-QA-META-'+str(index)
            args={'expected_document':str(DOC),'object_id':cable['object_id'],'expected_fingerprint':cable['fingerprint'],
                'sections':[{'index':1,'loom_id':marker,'box_id':marker+'-BOX','tape':marker+'-TAPE'}]}
            changed=await call('set_cable_sections',args)
            assert changed['verification']['verified'] and not changed['requires_verification']
            after=changed['verification']['cable']
            assert after['protected']['fields']['Loom_ID']==marker
            assert after['protected']['fields']['Box_ID']==marker+'-BOX'
            assert after['protected']['fields']['TapeColorCode']==marker+'-TAPE'
            assert after['sections'][0]['parts']==cable['sections'][0]['parts']
            # Native worksheet must show the metadata, not just record readback.
            code="""import vs, entertainment as e
e.guard({'expected_document':DOC})
ws=e.named('VM QA Cable Native Data Comparison',18);vs.RecalculateWS(ws)
__result__={'status':'ok','values':[[vs.GetWSSubrowCellString(ws,2,c,r) for c in (7,8,9)] for r in range(1,vs.GetWSSubrowCount(ws,2)+1)]}
""".replace('DOC',repr(str(DOC)))
            raw=await client.call_tool('execute_script',{'code':code},timeout=45)
            ws=json.loads(next(c.text for c in raw.content if c.type=='text'))
            report.setdefault('worksheet_reads',[]).append(ws);persist()
            assert not ws.get('error') and [marker,marker+'-BOX',marker+'-TAPE'] in ws['result']['values']
            await call('set_cable_sections',args,ok=False)
            args['expected_fingerprint']=after['fingerprint']
            args['sections']=[{'index':1,**{k:cable['sections'][0][k] for k in ('loom_id','box_id','tape')}}]
            restored=await call('set_cable_sections',args)
            assert restored['verification']['cable']==cable
        final=await call('get_cable_sections',{'object_ids':IDS});assert before==final
        report.update(verified=True,restored=True,worksheet_verified=True,multi_section_sync_verified=False)
        persist();print(json.dumps({k:v for k,v in report.items() if k not in ('calls','worksheet_reads')}))

if __name__=='__main__':asyncio.run(main())
