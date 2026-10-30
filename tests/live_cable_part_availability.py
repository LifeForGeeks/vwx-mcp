"""One-shot QA Use-flag round trip. Retains receipts before every native call."""
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
IDS=['feb7c1d2-a1bd-4e65-af35-54dda27510ac','ae31d689-3edd-4994-a868-4651905699ce']
CABLE='9c27b811-8318-406c-bc1b-0c3dd22d7b19'

async def main():
    evidence=ROOT/'evidence/live-qa/cable-part-availability-roundtrip.json'
    if evidence.exists(): raise RuntimeError('Attempt already exists. Inspect receipts instead of rerunning.')
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[],'verified':False}
    def persist(): evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
    persist()
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        tools=await client.list_tools(); report['tool_count']=len(tools)
        setter=next(t for t in tools if t.name=='set_cable_part_availability')
        assert not setter.annotations.readOnlyHint
        async def call(name,args,ok=True):
            row={'tool':name,'arguments':args}; report['calls'].append(row);persist()
            raw=await client.call_tool(name,args,timeout=45)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            row['result']=result;persist()
            assert (result.get('status')=='ok')==ok,result
            return result
        before=await call('get_cable_part_symbols',{'object_ids':IDS})
        assert Path(before['document'])==DOC
        assert all(x['fields']['Use'].lower()=='true' for x in before['symbols'])
        cable_before=await call('get_cable_inspection',{'object_ids':[CABLE],'geometry_detail':'summary'})
        def items(parts,enabled):
            return [{'object_id':x['object_id'],'enabled':enabled,'expected_fingerprint':x['fingerprint']} for x in parts]
        await call('set_cable_part_availability',{'expected_document':str(DOC)+'wrong','items':items(before['symbols'],False)},ok=False)
        disabled=await call('set_cable_part_availability',{'expected_document':str(DOC),'items':items(before['symbols'],False)})
        assert disabled['changed_count']==2 and all(x['verified'] for x in disabled['parts'])
        off=await call('get_cable_part_symbols',{'object_ids':IDS})
        assert all(x['fields']['Use'].lower()=='false' for x in off['symbols'])
        await call('set_cable_part_availability',{'expected_document':str(DOC),'items':items(before['symbols'],True)},ok=False)
        restored=await call('set_cable_part_availability',{'expected_document':str(DOC),'items':items(off['symbols'],True)})
        assert restored['changed_count']==2
        after=await call('get_cable_part_symbols',{'object_ids':IDS})
        assert after['symbols']==before['symbols']
        noop=await call('set_cable_part_availability',{'expected_document':str(DOC),'items':items(after['symbols'],True)})
        assert noop['changed_count']==0
        cable_after=await call('get_cable_inspection',{'object_ids':[CABLE],'geometry_detail':'summary'})
        assert cable_after['objects']==cable_before['objects']
        report.update(verified=True,restored_user_enabled_state=True,other_part_data_preserved=True,
                      cable_inspection_unchanged=True,native_run_part_consumption_verified=False)
        persist();print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__': asyncio.run(main())
