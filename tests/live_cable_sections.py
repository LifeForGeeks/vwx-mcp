"""One-shot native section edit, stock rebuild and restoration in Toolkit QA."""
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
ID='9c27b811-8318-406c-bc1b-0c3dd22d7b19'

async def main():
    evidence=ROOT/'evidence/live-qa/cable-section-native-roundtrip.json'
    if evidence.exists():raise RuntimeError('Attempt exists; inspect receipts before any further mutation.')
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[],'verified':False}
    def persist():evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
    persist()
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        tools=await client.list_tools();report['tool_count']=len(tools)
        for name,readonly in [('get_cable_sections',True),('set_cable_sections',False)]:
            assert next(t for t in tools if t.name==name).annotations.readOnlyHint==readonly
        async def call(name,args,ok=True):
            row={'tool':name,'arguments':args};report['calls'].append(row);persist()
            raw=await client.call_tool(name,args,timeout=45)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            row['result']=result;persist()
            assert (result.get('status')=='ok')==ok,result
            return result
        original=await call('get_cable_sections',{'object_ids':[ID]})
        assert Path(original['document'])==DOC
        before=original['cables'][0];assert before['section_count']==1 and before['break_count']==0
        section=before['sections'][0]
        assert section['start_slack_mm']==150 and section['end_slack_mm']==150 and section['swag_mm']==0
        params={'expected_document':str(DOC),'object_id':ID,'expected_fingerprint':before['fingerprint'],
                'sections':[{'index':1,'name':'VM QA Native Section','start_slack_mm':8000,'end_slack_mm':200,'swag_mm':100}]}
        changed=await call('set_cable_sections',params)
        assert changed['verification']['verified'] and not changed['requires_verification']
        after=changed['verification']['cable']
        assert after['sections'][0]['start_slack_mm']==8000
        assert after['sections'][0]['parts']!=section['parts'], 'Native stock did not rebuild'
        check=await call('get_cable_inspection',{'object_ids':[ID],'geometry_detail':'summary'})
        assert check['units'][3]==1.0 and check['units'][4]=='"','QA is expected in inches'
        total=check['objects'][0]['parts_length']*25.4
        needed=sum(after['sections'][0][k] for k in ['drawn_length_mm','start_slack_mm','end_slack_mm','swag_mm'])
        assert total>=needed,{'stock_mm':total,'needed_mm':needed}
        report['changed_stock_length_mm']=total;report['changed_needed_length_mm']=needed
        await call('set_cable_sections',params,ok=False)  # stale fingerprint must reject
        restore={k:section[k] for k in ['index','name','start_slack_mm','end_slack_mm','swag_mm']}
        restored=await call('set_cable_sections',{'expected_document':str(DOC),'object_id':ID,
            'expected_fingerprint':after['fingerprint'],'sections':[restore]})
        assert restored['verification']['cable']==before
        final=await call('get_cable_sections',{'object_ids':[ID]})
        assert final['cables'][0]==before
        report.update(verified=True,restored=True,native_stock_rebuild_verified=True,
                      electrical_design_verified=False,multi_section_and_break_mutations_verified=False)
        persist();print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
