"""Opt-in installed MCP cable probes; edits only the separate Toolkit QA file."""
import asyncio, json, math, os, sys
from pathlib import Path
from datetime import datetime, timezone
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'; DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')


async def main():
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    evidence=QA/'live-cables.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    async with Client(transport) as client:
        catalog=await client.list_tools()
        assert len(catalog)==277
        assert next(t for t in catalog if t.name=='get_cable_inspection').annotations.readOnlyHint
        report['tool_count']=len(catalog)
        async def call(name,args,expect_error=False):
            raw=await client.call_tool(name,args,timeout=180)
            body=next(c.text for c in raw.content if c.type=='text'); result=json.loads(body)
            report['calls'].append({'tool':name,'arguments':args,'result':result,'payload_bytes':len(body.encode('utf8'))})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert bool(result.get('error'))==expect_error,result
            return result
        async def script(code):
            return (await call('execute_script',{'code':'assert vs.GetFPathName()=='+repr(DOC)+'\n'+code}))['result']
        capture="rows=[]\nvs.ForEachObject(lambda h:rows.append(vs.GetObjectUuid(h)),\"(PON='CablePathObject')\")\n__result__={'paths':sorted(rows),'active_layer':vs.GetLName(vs.ActLayer()),'active_class':vs.ActiveClass(),'probe_reset':vs.GetRField(vs.GetObjectByUuid('58a3beb4-ebaa-4d9f-bd75-b1e97a3b4306'),'CableObject','ResetCount')}"
        before=await script(capture)
        items=[{'name':'VM-QA-Tool-CablePath-A','layer':'VM-QA-Cable','class':'VM-QA-Cable-Path',
                'route_id':'QA-TOOL-PATH-A','location':'QA straight and riser',
                'vertices':[[100,100,12],[220,100,12],[220,100,132],[460,100,132]]},
               {'name':'VM-QA-Tool-CablePath-B','layer':'VM-QA-Cable','class':'VM-QA-Cable-Path',
                'route_id':'QA-TOOL-PATH-B','location':'QA diagonal',
                'vertices':[[100,300,0],[223.456,412.345,27.89],[325.456,400.345,147.89]]}]
        await call('create_cable_paths',{'expected_document':str(QA/'Wrong.vwx'),'items':items},True)
        bad=[items[0],{**items[1],'vertices':[[0,0,0],[0,0,0]]}]
        await call('create_cable_paths',{'expected_document':DOC,'items':bad},True)
        assert await script(capture)==before,'Preflight changed the QA document'
        created=await call('create_cable_paths',{'expected_document':DOC,'items':items})
        assert created['verification']['verified'] and not created['requires_verification']
        assert created['verification']['paths'][0]['length']==480
        expected=sum(math.dist(a,b) for a,b in zip(items[1]['vertices'],items[1]['vertices'][1:]))
        assert math.isclose(created['verification']['paths'][1]['length'],expected,abs_tol=1e-6)
        ids=[r['object_id'] for r in created['created']]
        inspected=await call('get_cable_inspection',{'object_ids':ids,'include_fields':True})
        assert inspected['issue_count']==0,inspected
        assert all(r['path_type']==111 for r in inspected['objects'])
        assert all(r['fields']['Class2DAttributes']=='VM-QA-Cable-Path' for r in inspected['objects'])
        incomplete=await call('get_cable_inspection',{'object_ids':['58a3beb4-ebaa-4d9f-bd75-b1e97a3b4306','b320a4d4-5659-4c95-95ed-f861977f1987'],'issue_limit':1})
        assert incomplete['issues_truncated'] and incomplete['issue_count']>1
        assert incomplete['issue_counts']['unsupported_path_geometry']==2
        assert incomplete['native_connections_verified'] is False
        after=await script(capture)
        assert len(after['paths'])==len(before['paths'])+2
        assert all(after[k]==before[k] for k in ['active_layer','active_class','probe_reset'])
        await call('create_cable_paths',{'expected_document':DOC,'items':items},True)
        assert await script(capture)==after,'Duplicate attempt changed native paths'
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,completed=datetime.now(timezone.utc).isoformat())
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'verified':True,'tools':len(catalog),'calls':len(report['calls']),'path_ids':ids}))


if __name__=='__main__':asyncio.run(main())
