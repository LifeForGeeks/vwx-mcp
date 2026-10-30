"""One-shot QA edits and explicit restoration on two existing test fixtures."""
import asyncio, json, os, sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1];QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx');OUTPUT=QA/'lighting-documentation-installed.json'
IDS=['dc42604d-3fd8-4d0e-9b75-be2c7c2d3560','da1b8ed0-4bd7-452f-9179-8f78538a27fd']

async def main():
    assert not OUTPUT.exists(),'Existing one-shot receipt; inspect instead of rerunning mutations'
    report={'calls':[]}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args,allow_error=False):
            r=await client.call_tool(name,args,timeout=60)
            value=json.loads(next(c.text for c in r.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':value})
            OUTPUT.write_text(json.dumps(report,indent=2),encoding='utf8')
            if not allow_error:assert not value.get('error'),{k:v for k,v in value.items() if k not in ('receipt','recovery_params')}
            return value
        def targets(devices):return [{'object_id':r['object_id'],'expected_fingerprint':r['fingerprint']} for r in devices]
        before=await call('get_lighting_documentation',{'object_ids':IDS});report['before']=before
        assert all(r['accessory_count']==1 and r['hanging_position_id'] for r in before['devices'])
        items=targets(before['devices'])
        dry=await call('number_lighting_devices',{'expected_document':DOC,'items':items,'field':'unit_number','prefix':'QA-','start':7,'increment':2,'padding':3,'dry_run':True})
        assert [r['changes']['unit_number'] for r in dry['planned']]==['QA-007','QA-009']
        numbered=await call('number_lighting_devices',{'expected_document':DOC,'items':items,'field':'unit_number','prefix':'QA-','start':7,'increment':2,'padding':3})
        assert numbered['verification']['verified']
        stale=await call('set_lighting_documentation',{'expected_document':DOC,'items':[{**r,'values':{'purpose':'must not apply'}} for r in items]},True)
        assert stale.get('error') and 'Stale' in stale['error']
        edited=await call('set_lighting_documentation',{'expected_document':DOC,
            'items':[{**r,'values':{'channel':str(701+i),'purpose':'QA Front Wash','color':'L201'}} for i,r in enumerate(targets(numbered['verification']['devices']))]})
        assert edited['verification']['verified']
        restore=[{**r,'values':b['values']} for r,b in zip(targets(edited['verification']['devices']),before['devices'])]
        restored=await call('set_lighting_documentation',{'expected_document':DOC,'items':restore})
        assert restored['verification']['devices']==before['devices']
        repeated=await call('get_lighting_documentation',{'object_ids':IDS});assert repeated==before
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,restored=True,numbering_verified=True,stale_edits_rejected=True,
                      fields_and_worksheet_sources_verified=True,attachments_accessories_modes_patch_preserved=True,
                      rendered_label_layout_verified=False)
        OUTPUT.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('calls','before')}))

if __name__=='__main__':asyncio.run(main())
