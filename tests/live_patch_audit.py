"""Opt-in conflict tests on two known QA fixtures; preserve and restore patch data."""
import asyncio
import json
import os
from pathlib import Path
import sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')
NAMES=['TK-Fixture-1','TK-Fixture-2']
FIELDS=['System','Universe','Num Channels','DMX Address','Absolute Address','Channel','UniverseAddress']


async def main():
    report={'calls':[]}; uncertain=False
    path=QA/'live-patch-audit.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CALL_TIMEOUT':'180','VWX_SOCKET_TIMEOUT':'170','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,parameters):
            nonlocal uncertain
            try:result=await client.call_tool(name,parameters,timeout=180)
            except Exception:
                uncertain=True
                raise
            data=json.loads(next(c.text for c in result.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':parameters,'result':data})
            path.write_text(json.dumps(report,indent=2),encoding='utf-8')
            if data.get('cid') and data.get('retry_safe') is False:uncertain=True
            assert not data.get('error'),data
            return data
        async def script(code):
            return (await call('execute_script',{'code':'assert vs.GetFPathName() == '+repr(DOC)+'\n'+code}))['result']
        capture=(
            'out=[]\nfor n in '+repr(NAMES)+':\n'
            ' h=vs.GetObject(n);assert h\n'
            ' hp=vs.OLDGetHangingPos(h,0)\n'
            ' out.append({"name":n,"matrix":vs.GetEntityMatrix(h),"hp":vs.GetObjectUuid(hp) if hp else None,"fields":{f:vs.GetRField(h,"Lighting Device",f) for f in '+repr(FIELDS)+'}})\n'
            '__result__=out')
        before=await script(capture)
        report['before']=before
        (QA/'patch-restore-receipt.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
        async def configure(second_address=10,second_system='A',second_channel='2'):
            values=[{'System':'A','Universe':'1','Num Channels':'20','DMX Address':'1','Absolute Address':'1','Channel':'1','UniverseAddress':'1/1'},
                    {'System':second_system,'Universe':'1','Num Channels':'30','DMX Address':str(second_address),'Absolute Address':str(second_address),'Channel':second_channel,'UniverseAddress':'1/'+str(second_address)}]
            await script('for n,values in '+repr(list(zip(NAMES,values)))+':\n'
                         ' h=vs.GetObject(n)\n'
                         ' for k,v in values.items():\n'
                         '  if k in ["Num Channels","DMX Address","Absolute Address"]:vs.LDevice_SetParamLong(h,0,-2,k,int(v))\n'
                         '  else:vs.LDevice_SetParamStr(h,0,-2,k,v)\n'
                         ' vs.LDevice_Reset(h)\n__result__="configured QA fixtures"')
        async def audit():
            return await call('get_lighting_patch_audit',{'criteria':"((PON='Lighting Device') & (L='Toolkit QA'))",'include_parts':True})
        try:
            await configure()
            overlap=await audit()
            assert overlap['issue_counts'].get('address_overlap')==1,overlap
            assert overlap['non_control_accessories']==2 and overlap['control_parts']==2,overlap
            await configure(second_system='B')
            independent=await audit();assert not independent['has_errors'],independent
            await configure(second_address=1,second_channel='1')
            identical=await audit();assert identical['issue_counts'].get('identical_patch')==1 and not identical['has_errors'],identical
            await configure(second_address=510)
            overflow=await audit();assert overflow['issue_counts'].get('universe_overflow')==1,overflow
        finally:
            if not uncertain:
                await script('for row in '+repr(before)+':\n'
                             ' h=vs.GetObject(row["name"])\n'
                             ' for k,v in row["fields"].items():\n'
                             '  if k in ["Num Channels","DMX Address","Absolute Address"]:vs.LDevice_SetParamLong(h,0,-2,k,int(v))\n'
                             '  else:vs.LDevice_SetParamStr(h,0,-2,k,v)\n'
                             ' vs.LDevice_Reset(h)\n__result__="restored QA patch fields"')
                after=await script(capture)
                report['restored']=after==before
                path.write_text(json.dumps(report,indent=2),encoding='utf-8')
                assert after==before,(before,after)
            else:
                print('Uncertain native call: inspect its CID before restoring from patch-restore-receipt.json.',flush=True)
        baseline=await audit()
        assert baseline['unpatched_parts']==2 and not baseline['has_errors'],baseline
        report.update(passed=True,scenarios=['overlap','separate systems','identical patch review','universe overflow','restored unpatched'],read_path='cell >= 0, accessory -2 for parent, typed Long for address/footprint')
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('calls','before')},indent=2))


if __name__=='__main__':asyncio.run(main())
