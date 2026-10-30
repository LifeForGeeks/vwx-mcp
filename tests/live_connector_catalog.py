"""Read-only connector catalog integration through the installed MCP server."""
import asyncio, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]; QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')


async def main():
    evidence=QA/'live-connector-catalog.json'
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    async with Client(transport) as client:
        catalog=await client.list_tools(); assert len(catalog)==277
        report['tool_count']=len(catalog)
        assert next(t for t in catalog if t.name=='get_cable_connector_catalog').annotations.readOnlyHint
        async def call(name,args,error=False):
            raw=await client.call_tool(name,args,timeout=180)
            body=next(c.text for c in raw.content if c.type=='text'); result=json.loads(body)
            report['calls'].append({'tool':name,'arguments':args,'result':result,'payload_bytes':len(body.encode('utf8'))})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert bool(result.get('error'))==error,result
            return result
        capture='assert vs.GetFPathName()=='+repr(DOC)+'\n__result__={"document":vs.GetFPathName(),"layer":vs.GetLName(vs.ActLayer()),"class":vs.ActiveClass(),"path_count":vs.Count("(PON=\'CablePathObject\')")} '
        before=(await call('execute_script',{'code':capture}))['result']
        first=await call('get_cable_connector_catalog',{'search':'Socapex','limit':2})
        assert first['connector_count']==105 and first['matched_count']==6
        assert len(first['connectors'])==2 and first['next_offset']==2
        path=Path(first['source']['path']); digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==first['source']['sha256']
        second=await call('get_cable_connector_catalog',{'search':'Socapex','offset':2,'limit':50,'expected_sha256':digest})
        assert len(second['connectors'])==4 and second['next_offset'] is None
        assert len({r['universal_name'] for r in first['connectors']+second['connectors']})==6
        names=['Socapex-19 US Hot-N-Grnd 120v','Socapex-19 US Hot-Hot-Grnd 208v','Socapex-19 P+N+E 230v']
        detailed=await call('get_cable_connector_catalog',{'names':names,'include_sockets':True,'expected_sha256':digest})
        rows={r['universal_name']:r for r in detailed['connectors']}
        us120=rows[names[0]];us208=rows[names[1]]
        assert us120['listed_socket_count']==19
        assert [s['index'] for s in us120['sockets'] if s['universal_name']=='PE1']==[12,13,14]
        assert us208['declared_connections']==[{'universal_name':names[2],'target_in_catalog':True,'reciprocal_declaration':False}]
        assert detailed['electrical_compatibility_verified'] is False and detailed['physical_wiring_verified'] is False
        xlr=await call('get_cable_connector_catalog',{'names':['XLR5','5-pin XLR'],'include_sockets':True})
        assert xlr['missing_names']==['5-pin XLR']
        assert xlr['connectors'][0]['socket_definition_status']=='not_listed' and xlr['connectors'][0]['sockets']==[]
        await call('get_cable_connector_catalog',{'expected_sha256':'0'*64},True)
        explicit=await call('get_cable_connector_catalog',{'path':str(path),'names':['XLR5'],'include_sockets':True})
        assert explicit['source']['kind']=='explicit_file' and explicit['connectors']==xlr['connectors']
        after=(await call('execute_script',{'code':capture}))['result']
        assert after==before and hashlib.sha256(path.read_bytes()).hexdigest()==digest
        report.update(verified=True,document_unchanged=True,source_unchanged=True,completed=datetime.now(timezone.utc).isoformat())
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'verified':True,'calls':len(report['calls']),'tools':len(catalog),'connectors':first['connector_count']}))


if __name__=='__main__':asyncio.run(main())
