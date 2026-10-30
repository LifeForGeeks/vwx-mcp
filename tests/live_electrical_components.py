"""Read-only installed MCP contract check. Provider success requires the new native binary."""
import asyncio, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]; QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')


async def main():
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    evidence=QA/'live-electrical-components.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    async with Client(transport) as client:
        catalog=await client.list_tools(); assert len(catalog)==277
        assert next(t for t in catalog if t.name=='get_electrical_components').annotations.readOnlyHint
        report['tool_count']=len(catalog)
        async def call(name,args,error=False):
            raw=await client.call_tool(name,args,timeout=180)
            body=next(c.text for c in raw.content if c.type=='text'); result=json.loads(body)
            report['calls'].append({'tool':name,'arguments':args,'result':result,'payload_bytes':len(body.encode())})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert bool(result.get('error'))==error,result
            return result
        capture='assert vs.GetFPathName()=='+repr(DOC)+'''\nobjects=[]
def collect(h):
    objects.append({'id':vs.GetObjectUuid(h),'name':vs.GetName(h),'record':vs.GetName(vs.GetParametricRecord(h))})
vs.ForEachObject(collect,"((PON='Lighting Device') | (PON='CableObject') | (PON='CablePathObject'))")
objects.sort(key=lambda r:(r['record'],r['id']))
__result__={'document':vs.GetFPathName(),'layer':vs.GetLName(vs.ActLayer()),'class':vs.ActiveClass(),'objects':objects,'extension_loaded':callable(getattr(vs,'VMGetElectricalComponents',None))}
'''
        before=(await call('execute_script',{'code':capture}))['result']
        chosen=[]
        for kind in ('Lighting Device','CableObject','CablePathObject'):
            item=next((r for r in before['objects'] if r['record']==kind),None)
            if item: chosen.append(item['id'])
        assert chosen,'QA native examples missing'
        summary=await call('get_electrical_components',{'object_ids':chosen})
        details=await call('get_electrical_components',{'object_ids':chosen,'detail':'components','include_internal_connections':True,'limit':100})
        assert not details['external_connections_verified'] and not details['engineering_values_verified']
        for s,d in zip(summary['objects'],details['objects']):
            assert s['inspection_status']==d['inspection_status']
            if not before['extension_loaded']:
                assert s['inspection_status']=='extension_unavailable',s
            else:
                assert s['inspection_status'] in ('ok','provider_unavailable'),s
                if s['inspection_status']=='ok':
                    assert s['component_count']==d['component_count']
                    assert 'components' not in s
        missing=await call('get_electrical_components',{'object_ids':['00000000-0000-0000-0000-000000000000']})
        assert missing['objects'][0]['inspection_status']=='missing_object'
        await call('get_electrical_components',{'object_ids':[chosen[0],chosen[0]]},True)
        after=(await call('execute_script',{'code':capture}))['result']
        assert before==after
        report.update(contract_verified=True,captured_state_unchanged=True,
            extension_loaded=before['extension_loaded'],
            provider_runtime_observed=any(r.get('component_count',0)>0 for r in summary['objects']),
            completed=datetime.now(timezone.utc).isoformat())
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('contract_verified','extension_loaded','provider_runtime_observed','tool_count')}))


if __name__=='__main__': asyncio.run(main())
