"""Installed server checks; requires cached XML, not an active native bridge."""
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
CACHE=Path(os.environ['APPDATA'])/'Nemetschek/Vectorworks/2026/Libraries/Entertainment/Power/Cable Tools/CablePartsCache.xml'
CONNECTORS=Path(os.environ['ProgramFiles'])/'Vectorworks 2026/Libraries/Entertainment/Power/Cable Tools/CableConnectors.xml'


async def main():
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[], 'native_bridge_required':False}
    evidence=ROOT/'evidence/installed-cable-parts-catalog.json'
    digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before=[digest(CACHE),digest(CONNECTORS)]
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        catalog=await client.list_tools()
        tool=next(t for t in catalog if t.name=='get_cable_parts_catalog')
        assert tool.annotations.readOnlyHint
        assert len(catalog)>=280
        async def call(name,args,error=False):
            raw=await client.call_tool(name,args,timeout=30)
            body=next(c.text for c in raw.content if c.type=='text')
            r=json.loads(body)
            report['calls'].append({'tool':name,'arguments':args,'result':r,'payload_bytes':len(body.encode('utf8'))})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert bool(r.get('error'))==error, r
            return r
        base={'cache_path':str(CACHE),'connector_catalog_path':str(CONNECTORS)}
        page=await call('get_cable_parts_catalog',{**base,'limit':1})
        assert page['entry_count']>0 and page['source']['sha256']==before[0]
        await call('get_cable_parts_catalog',{**base,'offset':1,'limit':1,'expected_sha256':before[0]})
        true1=await call('get_cable_parts_catalog',{**base,'search':'TRUE1','limit':50})
        assert true1['matched_count']>0
        details=await call('get_cable_parts_catalog',{**base,'search':'TRUE1','limit':50,'include_fields':True})
        assert len(details['parts'])==len(true1['parts'])
        assert 'fields' in details['parts'][0] and 'fields' not in true1['parts'][0]
        generic=await call('vwx',{'command':'get_cable_parts_catalog','params':{**base,'search':'TRUE1','limit':50}})
        assert generic==true1
        await call('get_cable_parts_catalog',{**base,'expected_sha256':'0'*64},True)
        assert before==[digest(CACHE),digest(CONNECTORS)], 'Source XML changed during read-only tests'
        report.update(verified=True,completed=datetime.now(timezone.utc).isoformat(),tool_count=len(catalog),
                      source_xml_unchanged=True,entry_count=page['entry_count'],true1_entries=true1['matched_count'],
                      true1_issue_counts=true1['issue_counts'],native_part_creation_verified=False)
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('verified','tool_count','entry_count','true1_entries','source_xml_unchanged')}))


if __name__=='__main__':asyncio.run(main())
