"""Opt-in label inspection/coordination test, guarded to the separate QA document."""
import asyncio,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'; DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')
VP='6f5066f2-3b7b-4b09-9395-98b4fddb5e68'
OTHER='175e5451-f435-4fe6-ba2a-b0457a8c1f3b'
LABEL='dbb9ce43-996d-485d-88b8-90f674a7ddc9'


async def main():
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    evidence=QA/'live-viewport-documentation.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    uncertain=False
    async with Client(transport) as client:
        catalog=await client.list_tools()
        assert len(catalog)==277
        assert next(t for t in catalog if t.name=='get_viewport_documentation').annotations.readOnlyHint
        report['tool_count']=len(catalog)
        async def call(name,args):
            nonlocal uncertain
            try:
                raw=await client.call_tool(name,args,timeout=180)
                body=next(c.text for c in raw.content if c.type=='text')
                result=json.loads(body)
            except Exception:
                uncertain=True
                raise
            report['calls'].append({'tool':name,'arguments':args,'result':result,'payload_bytes':len(body.encode('utf8'))})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            if result.get('cid') and result.get('retry_safe') is False: uncertain=True
            assert not result.get('error'),result
            return result
        async def script(code):
            return (await call('execute_script',{'code':'assert vs.GetFPathName() == '+repr(DOC)+'\n'+code}))['result']
        capture='v=vs.GetObjectByUuid('+repr(VP)+');h=vs.GetObjectByUuid('+repr(LABEL)+');c=vs.GetObjectByUuid('+repr(OTHER)+')\nassert v and h and c\n__result__={"title":vs.GetObjectVariableString(v,1032),"number":vs.GetObjectVariableString(v,1033),"coordination":vs.GetPref(544),"custom":vs.GetRField(h,"Drawing Label2","Custom Scale"),"display":vs.GetRField(h,"Drawing Label2","ScaleDisplay"),"other_title":vs.GetObjectVariableString(c,1032),"other_view":vs.GetObjectVariableInt(c,1007)}'
        before=await script(capture)
        report['before']=before
        try:
            baseline=await call('get_viewport_documentation',{'viewport_ids':[VP,OTHER],'include_labels':True})
            assert baseline['viewports'][0]['label_count']==2
            assert {'Drawing Label','Drawing Label2'}=={r['plugin'] for r in baseline['viewports'][0]['labels']}
            assert any(i['code']=='custom_scale_review' for i in baseline['issues'])
            assert before==await script(capture), 'Read-only inspection changed native state'
            # Real native coordination: edit one label, then inspect after its reset event.
            await script('h=vs.GetObjectByUuid('+repr(LABEL)+')\nvs.SetRField(h,"Drawing Label2","Title","Front Elevation")\nvs.ResetObject(h)\n__result__="QA label reset"')
            changed=await call('get_viewport_documentation',{'viewport_ids':[VP,OTHER],'include_labels':True})
            assert changed['viewports'][0]['drawing_title']=='Front Elevation'
            assert all(r['fields']['Title']=='Front Elevation' for r in changed['viewports'][0]['labels'])
            assert any(i['code']=='title_view_review' for i in changed['issues'])
            assert changed['viewports'][1]==baseline['viewports'][1]
            compact=await call('get_viewport_documentation',{'viewport_ids':[VP],'limit':1})
            assert compact['issue_count']>len(compact['issues']) and compact['issues_truncated']
            assert 'labels' not in compact['viewports'][0]
        finally:
            if not uncertain:
                await script('h=vs.GetObjectByUuid('+repr(LABEL)+')\nvs.SetRField(h,"Drawing Label2","Title",'+repr(before['title'])+')\nvs.ResetObject(h)\n__result__="restored QA title"')
                assert before==await script(capture)
                report['restored']=True
        report['verified']=True
        report['completed']=datetime.now(timezone.utc).isoformat()
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'verified':True,'restored':report['restored'],'tools':len(catalog),'calls':len(report['calls'])}))


if __name__=='__main__':asyncio.run(main())
