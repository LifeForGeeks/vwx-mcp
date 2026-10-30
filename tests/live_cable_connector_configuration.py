"""Read-only installed connector/style and asymmetric custom-part verification."""
import asyncio
import json
import os
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
IDS=['9c27b811-8318-406c-bc1b-0c3dd22d7b19',
     'ad1a00dd-d227-450c-a71f-df7279c8eba3',
     '944ec808-fb71-48df-bd4c-5484b4ae964c']

async def main():
    out=ROOT/'evidence/live-qa/cable-connector-configuration-installed.json'
    if out.exists(): raise RuntimeError('Evidence exists; inspect before repeating')
    report={'calls':[], 'read_only':True, 'verified':False}
    def persist(): out.write_text(json.dumps(report,indent=2),encoding='utf8')
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        surface=await client.list_tools(); report['tool_count']=len(surface)
        tool=next(t for t in surface if t.name=='get_cable_inspection')
        assert tool.annotations.readOnlyHint
        assert 'include_connector_configuration' in tool.inputSchema['properties']
        async def call(name, args):
            raw=await client.call_tool(name,args,timeout=45)
            data=json.loads(next(c.text for c in raw.content if c.type=='text'))
            report['calls'].append({'tool':name, 'arguments':args, 'result':data});persist()
            assert data.get('status')=='ok',data
            return data
        before=await call('get_cable_sections',{'object_ids':IDS})
        assert Path(before['document'])==DOC
        plain=await call('get_cable_inspection',{'object_ids':IDS})
        detailed=await call('get_cable_inspection',{'object_ids':IDS,'include_connector_configuration':True})
        for basic,row in zip(plain['objects'],detailed['objects']):
            assert basic=={k:v for k,v in row.items() if k!='connector_configuration'}
            config=row['connector_configuration'];assert config['status']=='ok'
            assert not config['style_mismatches'] and not config['native_connections_verified']
            assert all(v['matches_style'] for v in config['parameters'].values())
            assert not config['physical_gender_verified'] and not config['pin_wiring_verified']
        parts=await call('get_cable_part_symbols',{'object_ids':['ae31d689-3edd-4994-a868-4651905699ce']})
        part=parts['symbols'][0];probe=before['cables'][2]
        config=detailed['objects'][2]['connector_configuration']['parameters']
        assert part['fields']['ConnectorStart']==config['start']['value']=='NEMA 5-15'
        assert part['fields']['ConnectorEnd']==config['end']['value']=='NAC3FX-W and NAC3MX-W'
        assert probe['sections'][0]['parts']==[part['fields']['ShortName']]
        assert float(part['fields']['Length'])==1524
        section=probe['sections'][0]
        needed=sum(section[k] for k in ('drawn_length_mm','start_slack_mm','end_slack_mm','swag_mm'))
        assert abs(needed-1519.2)<0.001 and needed<=1524
        after=await call('get_cable_sections',{'object_ids':IDS});assert after==before
        report.update(verified=True,unchanged_sections=True,asymmetric_part_selection_verified=True,
            native_connection_verification=False,complete_insertion_verified=False)
        report['detail_extra_bytes']=len(json.dumps(detailed))-len(json.dumps(plain))
        persist();print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__': asyncio.run(main())
