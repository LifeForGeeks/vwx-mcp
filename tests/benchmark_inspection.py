"""Read-only live comparison of concise inspections against a captured full response."""
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'


async def main():
    before_raw=(QA/'inspection-before-0.2.json').read_text(encoding='utf-8').strip()
    before=json.loads(before_raw)
    assert not before['truncated'], 'Baseline must contain all matching devices'
    measurements=[]
    installed=Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py'
    transport=StdioTransport(command=sys.executable,args=[str(installed)],env={**os.environ,
        'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CALL_TIMEOUT':'180','VWX_SOCKET_TIMEOUT':'170','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        catalog=await client.list_tools()
        tool=next(t for t in catalog if t.name=='get_entertainment_state')
        assert tool.inputSchema['properties']['detail']['default']=='summary'

        async def read(label,parameters):
            started=time.perf_counter()
            result=await client.call_tool('get_entertainment_state',parameters,timeout=180)
            raw=next(c.text for c in result.content if c.type=='text')
            data=json.loads(raw)
            assert not data.get('error'),data
            assert data['document']==before['document'],'Document changed; capture a new matching baseline'
            measurements.append({'label':label,'utf8_bytes':len(raw.encode('utf-8')),
                                 'elapsed_seconds':round(time.perf_counter()-started,3)})
            (QA/('inspection-'+label+'.json')).write_text(raw,encoding='utf-8')
            return data

        summary=await read('summary',{})
        assert summary['native_counts']==before['native_counts']
        assert summary['matched_devices']==len(before['devices'])
        assert summary['summary']['attached_devices']==sum(bool(d['hanging_position_id']) for d in before['devices'])
        assert summary['summary']['accessories_cell_0']==sum(len(d['accessories']) for d in before['devices'])
        inventory=Counter((d['fields']['Symbol Name'],d['fields']['Body Inventory'],d['fields']['Lens Inventory'],d['fields']['Accessory Inventory']) for d in before['devices'])
        assert not summary['inventory']['truncated']
        actual={(r['symbol'],r['body_source'],r['lens_source'],r['accessory_source']):r['count'] for r in summary['inventory']['groups']}
        assert actual==inventory
        full=await read('full',{'detail':'full','limit':1000})
        assert sorted(full['devices'],key=lambda d:d['object_id'])==sorted(before['devices'],key=lambda d:d['object_id'])
        assert full['layers']==before['layers'] and full['classes']==before['classes']
        criteria="((PON='Lighting Device') & (L='Toolkit QA'))"
        page1=await read('page-1',{'detail':'devices','criteria':criteria,'limit':1})
        page2=await read('page-2',{'detail':'devices','criteria':criteria,'limit':1,'offset':page1['next_offset']})
        assert page1['matched_devices']==page2['matched_devices']==2
        assert page2['next_offset'] is None
        qa_ids={d['object_id'] for d in before['devices'] if d['layer']=='Toolkit QA'}
        assert {d['object_id'] for page in (page1,page2) for d in page['devices']}==qa_ids
    before_bytes=len(before_raw.encode('utf-8'))
    report={'version':'0.2.0','passed':True,'baseline_utf8_bytes':before_bytes,
            'summary_reduction_percent':round(100*(1-measurements[0]['utf8_bytes']/before_bytes),2),
            'measurements':measurements,'matches':len(before['devices']),
            'verification':'Summary attachment/accessory/source counts and full device/structure readback match captured baseline. Two compact pages cover both scoped QA devices without duplicates.',
            'measurement_limit':'Payload bytes are a token-use proxy, not measured model tokens. Timings are single live observations, not a controlled performance study.'}
    (QA/'inspection-benchmark.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':asyncio.run(main())
