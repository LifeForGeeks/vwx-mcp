"""One-shot verification of retained decks and corrected tuple-based creation."""
import asyncio, json, os, sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from live_stage_grid import ROOT, QA, DOC

async def main():
    old=json.loads((QA/'stage-grid-installed.json').read_text(encoding='utf8'))
    output=QA/'stage-grid-verified.json';assert not output.exists(), 'Existing one-shot receipt'
    report={'calls':[],'original_creation_evidence':'stage-grid-installed.json',
            'correction':'SetEntityMatrixN offset must be a tuple; existing four QA objects repositioned, not recreated.'}
    original=old['calls'][-1]['result']; args=old['calls'][-1]['arguments']
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args,allow_error=False):
            response=await client.call_tool(name,args,timeout=60)
            value=json.loads(next(c.text for c in response.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':value})
            output.write_text(json.dumps(report,indent=2),encoding='utf8')
            if not allow_error:assert not value.get('error'), {k:v for k,v in value.items() if k not in ('created','recovery_params')}
            return value
        verified=await call('vwx',{'command':'get_stage_deck_verification','params':original['recovery_params']})
        assert verified['verified']
        fresh=await call('create_stage_deck_grid',{**args,'name':'VM-QA-MODULAR-STAGE-B','columns':2,'rows':1,
            'rotation':90,'origin_mm':[5000,0,100],'rail_edges':['front'],'structure':'Legs-Basic'})
        assert fresh['verification']['verified']
        ids=[r['object_id'] for r in original['created']+fresh['created']]
        first=await call('get_stage_deck_inspection',{'object_ids':ids})
        again=await call('get_stage_deck_inspection',{'object_ids':ids});assert first==again
        dup=await call('create_stage_deck_grid',args,allow_error=True);assert dup.get('error')
        after=(await call('execute_script',old['calls'][0]['arguments']))['result']
        assert after==old['calls'][0]['result']['result'], 'Existing objects/context changed'
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,created_ids=ids,existing_objects_and_context_unchanged=True,
                      fresh_creation_verified=True,repeated_inspection_stable=True,duplicate_rejected=True,
                      visual_comparison=False,manufacturer_specific_geometry=False)
        output.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
