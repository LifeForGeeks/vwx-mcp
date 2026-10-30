"""One-shot installed native export test. Keeps receipts before attempting export."""
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
DEST=Path(os.environ['APPDATA'])/'Nemetschek/Vectorworks/2026/Libraries/Entertainment/Power/Cable Tools/Velvet Mirror QA Cable Parts.vwx'
IDS=['feb7c1d2-a1bd-4e65-af35-54dda27510ac','ae31d689-3edd-4994-a868-4651905699ce']

async def main():
    evidence=ROOT/'evidence/live-qa/custom-cable-part-export-v3.json'
    if not DEST.is_file() or evidence.exists(): raise RuntimeError('Expected prepared empty library and no previous v2 attempt; inspect receipts')
    empty_hash=hashlib.sha256(DEST.read_bytes()).hexdigest()
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        catalog=await client.list_tools(); assert len(catalog)==283
        async def call(name,args,error=False):
            row={'tool':name,'arguments':args};report['calls'].append(row)
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            raw=await client.call_tool(name,args,timeout=50)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            row['result']=result;evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert (result.get('status')=='error')==error,result
            return result
        before=await call('get_cable_part_symbols',{'object_ids':IDS})
        assert before['symbols'][0]['fields']['Length']=='9144'
        assert before['symbols'][0]['metadata']['EndGender']=='female'
        exported=await call('export_cable_part_library',{'expected_document':str(DOC),'path':str(DEST),'object_ids':IDS,'empty_library_sha256':empty_hash})
        records=await call('list_native_library_resources',{'path':str(DEST),'resource_type':47,'limit':25})
        assert {'CablePart','VM Cable Part Detail'}<=set(x['name'] for x in records['resources'])
        await call('export_cable_part_library',{'expected_document':str(DOC),'path':str(DEST),'object_ids':IDS},True)
        after=await call('get_cable_part_symbols',{'object_ids':IDS});assert before==after
        report.update(verified=True,tool_count=len(catalog),native_catalog_registered=False,
                      reopened_qa_part_records_verified=True,exported_records_verified=False)
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'verified':True,'path':str(DEST),'bytes':exported['bytes'],'symbols':exported['symbol_names']}))

if __name__=='__main__':asyncio.run(main())
