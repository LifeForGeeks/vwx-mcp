"""Read-only installed surface validation, usable while native UI is busy."""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]

async def main():
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        tools=await client.list_tools();assert len(tools)==283
        names=['get_cable_part_symbols','create_cable_part_symbols','export_cable_part_library']
        selected={t.name:t for t in tools if t.name in names};assert set(selected)==set(names)
        assert selected['get_cable_part_symbols'].annotations.readOnlyHint
        assert not selected['create_cable_part_symbols'].annotations.readOnlyHint
        assert not selected['export_cable_part_library'].annotations.readOnlyHint
        cache=Path(os.environ['APPDATA'])/'Nemetschek/Vectorworks/2026/Libraries/Entertainment/Power/Cable Tools/CablePartsCache.xml'
        raw=await client.call_tool('get_cable_parts_catalog',{'cache_path':str(cache),'search':'VM-QA','limit':10},timeout=15)
        catalog=json.loads(next(c.text for c in raw.content if c.type=='text'))
        assert not catalog.get('error'),catalog
        deployment=ROOT/'evidence/deployment-20260913-022702/manifest.json'
        files=json.loads(deployment.read_text(encoding='utf-8-sig'))
        assert all(hashlib.sha256(Path(x['destination']).read_bytes()).hexdigest().lower()==x['sha256'].lower() for x in files)
        report={'verified':True,'tool_count':len(tools),'tools':names,'installed_hashes_verified':len(files),
                'deployment':str(deployment),'catalog_snapshot':catalog,'native_calls':0,
                'pending_native_command':'3237cd927f8e','full_cable_workflows_complete':False}
        (ROOT/'evidence/cable-part-installed-surface.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('verified','tool_count','installed_hashes_verified','native_calls')}))

if __name__=='__main__':asyncio.run(main())
