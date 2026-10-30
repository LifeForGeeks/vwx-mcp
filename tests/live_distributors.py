"""Installed-server QA exercise; new names are intentional, never rerun creation blindly."""
import asyncio,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1];QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')

async def main():
    report={'started':datetime.now(timezone.utc).isoformat(),'calls':[]}
    evidence=QA/'live-distributors.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    async with Client(transport) as client:
        catalog=await client.list_tools();report['tool_count']=len(catalog)
        assert len(catalog)==279
        assert next(t for t in catalog if t.name=='get_distributor_inspection').annotations.readOnlyHint
        async def call(name,args,error=False):
            raw=await client.call_tool(name,args,timeout=180)
            body=next(c.text for c in raw.content if c.type=='text');r=json.loads(body)
            report['calls'].append({'tool':name,'arguments':args,'result':r,'payload_bytes':len(body.encode())})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert bool(r.get('error'))==error,r
            return r
        names=['Edison Twofer','100A Cube 001 Edison','VM-QA-SIMULATED-120V-15A-SOURCE']
        script='assert vs.GetFPathName()=='+repr(DOC)+'\n__result__={n:vs.GetObjectUuid(vs.GetObject(n)) for n in '+repr(names)+'}'
        symbols=(await call('execute_script',{'code':script}))['result']
        read=await call('get_distributor_inspection',{'object_ids':list(symbols.values()),'detail':'components','limit':100})
        assert [o['component_count'] for o in read['objects']]==[3,38,1],read
        assert not any(o['identity_issues'] for o in read['objects'][:2])
        assert read['objects'][2]['identity_issues'][0]['issue']=='missing_internal_id'
        specs=[dict(name='VM-QA-CHAIN-TWOFER',device_id='QA-CHAIN-D1',symbol=names[0],position=[240,0,0],rotation=[0,0,90]),
               dict(name='VM-QA-CHAIN-CUBE',device_id='QA-CHAIN-D2',symbol=names[1],position=[240,240,24],rotation=[0,0,30]),
               dict(name='VM-QA-CHAIN-SOURCE',device_id='QA-CHAIN-S1',symbol=names[2],position=[0,0,0])]
        for s in specs:s.update(layer='QA Electrical Chain',**{'class':'VM-QA-Electrical-Devices'},location='QA Electrical Chain')
        await call('create_distributors',{'expected_document':DOC+'.wrong','items':specs},True)
        created=await call('create_distributors',{'expected_document':DOC,'items':specs})
        assert not created['requires_verification'] and created['verification']['verified'],created
        ids=[r['object_id'] for r in created['created']]
        details=await call('get_distributor_inspection',{'object_ids':ids,'detail':'components','limit':100})
        summary=await call('get_distributor_inspection',{'object_ids':ids})
        for a,b in zip(details['objects'],summary['objects']):
            assert a['component_count']==b['component_count'] and a['symbol_fingerprint']==b['symbol_fingerprint']
            assert 'components' not in b
        await call('create_distributors',{'expected_document':DOC,'items':specs},True)
        repeat=await call('vwx',{'command':'get_distributor_verification','params':{'expected_document':DOC,'created':created['created']}})
        assert repeat['verified']
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,created_ids=ids,external_connections_verified=False,
                      visual_verification=False,completed=datetime.now(timezone.utc).isoformat())
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('verified','tool_count','created_ids','external_connections_verified')}))

if __name__=='__main__':asyncio.run(main())
