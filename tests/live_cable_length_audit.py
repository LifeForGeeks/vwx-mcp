"""Read-only installed audit against the native chain and incomplete API probe."""
import asyncio
import json
import os
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
IDS=['9c27b811-8318-406c-bc1b-0c3dd22d7b19','c9fc829f-e0ae-433b-a9f2-123ba01c98d7']

async def main():
    path=ROOT/'evidence/live-qa/cable-length-audit-installed.json'
    report={'calls':[],'verified':False}
    def persist():path.write_text(json.dumps(report,indent=2),encoding='utf8')
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        surface=await client.list_tools();report['tool_count']=len(surface)
        assert next(t for t in surface if t.name=='get_cable_length_audit').annotations.readOnlyHint
        async def call(name,args):
            raw=await client.call_tool(name,args,timeout=45)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':result});persist()
            assert result.get('status')=='ok',result
            assert Path(result['document'])==DOC,result
            return result
        before=await call('get_cable_sections',{'object_ids':IDS})
        audit=await call('get_cable_length_audit',{'object_ids':IDS})
        rows={r['object_id']:r for r in audit['cables']}
        assert rows[IDS[0]]['result']=='consistent_in_scope'
        assert rows[IDS[1]]['result']=='mismatch'
        assert rows[IDS[1]]['pio_length_mm']==0
        assert rows[IDS[1]]['section_drawn_sum_mm']==6096
        assert rows[IDS[1]]['linear_path_local_mm']==6096
        assert audit['mismatch_count']==1
        inspection=await call('get_cable_inspection',{'object_ids':IDS,'geometry_detail':'summary'})
        assert inspection['objects'][1]['parts_length']==360
        after=await call('get_cable_sections',{'object_ids':IDS})
        assert before==after
        custom=after['cables'][1]
        assert custom['sections'][0]['parts']==['QA-T1-30']
        assert custom['sections'][0]['drawn_length_mm']+custom['sections'][0]['start_slack_mm']+custom['sections'][0]['end_slack_mm']==9144
        report.update(verified=True,read_only_section_state_unchanged=True,
            native_custom_part_selection_verified=True,cable_creation_complete=False,
            native_connections_verified=False,electrical_design_verified=False)
        persist();print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
