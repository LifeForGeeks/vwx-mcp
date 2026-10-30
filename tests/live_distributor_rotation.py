"""Verify final installed rotation guard with a new isolated, deliberately tilted QA instance."""
import asyncio,json,os,sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
ROOT=Path(__file__).resolve().parents[1];QA=ROOT/'evidence/live-qa';DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')

async def main():
    report={'calls':[]}
    async with Client(StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
                      env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})) as client:
        async def call(name,args):
            raw=await client.call_tool(name,args,timeout=180)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':result})
            (QA/'live-distributor-rotation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            assert not result.get('error'),result
            return result
        r=await call('create_distributors',{'expected_document':DOC,'items':[dict(name='VM-QA-DISTRIBUTOR-ROTATION',
            device_id='QA-DIST-ROTATION',symbol='Edison Twofer',position=[240,480,24],rotation=[10,20,30],
            layer='QA Electrical Chain',**{'class':'VM-QA-Electrical-Devices'},description='QA rotation test only')]})
        assert r['verification']['verified'] and not r['requires_verification']
        pose=r['created'][0]['matrix']
        assert all(abs(a-b)<1e-6 for a,b in zip(pose[1],[240,480,24]))
        assert all(abs(a-b)<1e-6 for a,b in zip(pose[2:],[10,20,30]))
        previous=json.loads((QA/'live-distributors.json').read_text())
        receipts=next(c['result']['created'] for c in previous['calls'] if c['tool']=='create_distributors' and not c['result'].get('error'))
        check=await call('vwx',{'command':'get_distributor_verification','params':{'expected_document':DOC,'created':receipts}})
        assert check['verified']
        await call('save_document_checked',{'expected_document':DOC})
        report['verified']=True
        (QA/'live-distributor-rotation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'final_installed_rotation_verified':True,'previous_distributors_unchanged':True,'saved':True,'id':r['created'][0]['object_id']}))

if __name__=='__main__':asyncio.run(main())
