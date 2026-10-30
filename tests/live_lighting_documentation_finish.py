"""Continue from retained numbering receipt after JSON tuple/list normalization fix."""
import asyncio, json, os, sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from live_lighting_documentation import ROOT, QA, DOC, IDS

async def main():
    old=json.loads((QA/'lighting-documentation-installed.json').read_text(encoding='utf8'))
    output=QA/'lighting-documentation-verified.json';assert not output.exists()
    before=old['calls'][0]['result'];report={'calls':[],'before':before,
        'correction':'Normalized snapshots through JSON before comparison; no hardware or attachment difference occurred.'}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args,allow_error=False):
            r=await client.call_tool(name,args,timeout=60);value=json.loads(next(c.text for c in r.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':value});output.write_text(json.dumps(report,indent=2),encoding='utf8')
            if not allow_error:assert not value.get('error'),{k:v for k,v in value.items() if k not in ('receipt','recovery_params')}
            return value
        def targets(devices):return [{'object_id':r['object_id'],'expected_fingerprint':r['fingerprint']} for r in devices]
        recovered=await call('vwx',{'command':'get_lighting_documentation_verification','params':old['calls'][-1]['result']['recovery_params']})
        numbered=await call('number_lighting_devices',{'expected_document':DOC,'items':targets(recovered['devices']),
            'field':'unit_number','start':10,'increment':2,'padding':3,'prefix':'QA-'})
        assert numbered['verification']['verified'] and numbered['rollback_items']
        stale=await call('set_lighting_documentation',{'expected_document':DOC,
            'items':[{**r,'values':{'purpose':'must not apply'}} for r in targets(before['devices'])]},True)
        assert stale.get('error') and 'Stale' in stale['error']
        edited=await call('set_lighting_documentation',{'expected_document':DOC,'items':[
            {**r,'values':{'channel':str(701+i),'purpose':'QA Front Wash','color':'L201'}}
            for i,r in enumerate(targets(numbered['verification']['devices']))]})
        assert edited['verification']['verified']
        restored=await call('set_lighting_documentation',{'expected_document':DOC,'items':[
            {**r,'values':b['values']} for r,b in zip(targets(edited['verification']['devices']),before['devices'])]})
        assert restored['verification']['devices']==before['devices']
        repeated=await call('get_lighting_documentation',{'object_ids':IDS});assert repeated==before
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,restored=True,numbering_verified=True,stale_edits_rejected=True,
            fields_and_worksheet_sources_verified=True,attachments_accessories_modes_patch_preserved=True,
            rendered_label_layout_verified=False)
        output.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('calls','before','correction')}))

if __name__=='__main__':asyncio.run(main())
