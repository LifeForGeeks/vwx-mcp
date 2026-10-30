"""Explicit QA mutation: creates two uniquely named disabled native cable parts once."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
IDS=['38da5dcb-2dcd-4785-879a-16c109bf5b15','476adf9c-10b1-4c32-bbbf-9f0cb224a52f']

async def main():
    evidence=ROOT/'evidence/live-qa/custom-cable-parts-live.json'
    if evidence.exists() and 'create_cable_part_symbols' in evidence.read_text(encoding='utf8'):
        raise RuntimeError('Creation already attempted. Inspect stored receipts; do not rerun automatically.')
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        catalog=await client.list_tools(); assert len(catalog)>=282
        async def call(name,args):
            row={'tool':name,'arguments':args};report['calls'].append(row)
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            raw=await client.call_tool(name,args,timeout=45)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            row['result']=result;evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert result.get('status')=='ok',result
            return result
        before=await call('get_cable_part_symbols',{'object_ids':IDS})
        items=[]
        for i,part in enumerate(before['symbols']):
            fields=dict(part['fields'])
            fields.update(Use=False,SetName='VM-QA-Unverified')
            if i==0:
                fields.update(Name='VM QA TRUE1 M-F 30ft',ShortName='QA-T1-30',Length=9144,Weight=0)
                name='VM-QA-Custom-TRUE1-MF-30ft';texts={"25'":"30' QA"}
                meta={'StartManufacturer':'Neutrik','StartModel':'NAC3MX-W','StartGender':'male',
                      'EndManufacturer':'Neutrik','EndModel':'NAC3FX-W','EndGender':'female'}
            else:
                fields.update(Name='VM QA Edison-TRUE1 5ft',ShortName='QA-E-T1-5')
                name='VM-QA-Custom-Edison-TRUE1-5ft';texts={"5'":"5' QA",'Edison':'Edison'}
                meta={'StartGender':'male','EndManufacturer':'Neutrik','EndModel':'NAC3FX-W','EndGender':'female'}
            meta['Notes']='QA ONLY. Cable body values copied from official template, not verified against actual inventory. Zero weight means unspecified in this QA example. Connector model identities are test specifications, not user inventory claims.'
            items.append({'template_symbol':part['symbol_name'],'symbol_name':name,'fields':fields,'text_replacements':texts,'metadata':meta})
        made=await call('create_cable_part_symbols',{'expected_document':str(DOC),'items':items})
        assert len(made['created'])==2 and all(x['verified'] for x in made['created'])
        newids=[x['object_id'] for x in made['created']]
        after=await call('get_cable_part_symbols',{'object_ids':IDS+newids})
        assert [x['fingerprint'] for x in before['symbols']]==[x['fingerprint'] for x in after['symbols'][:2]]
        assert after['symbols'][2]['fields']['Length']=='9144'
        assert after['symbols'][2]['metadata']['StartGender']=='male'
        assert after['symbols'][2]['metadata']['EndGender']=='female'
        assert all(x['fields']['Use'].lower()=='false' for x in after['symbols'][2:])
        report.update(verified=True,tool_count=len(catalog),created_ids=newids,library_exported=False,native_catalog_registered=False)
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('verified','tool_count','created_ids')}))

if __name__=='__main__': asyncio.run(main())
