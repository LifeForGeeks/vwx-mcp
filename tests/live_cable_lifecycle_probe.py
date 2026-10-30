"""One-shot QA experiment for the staged native lifecycle extension.

Run after installation/restart. Records failed initialization as an experimental
outcome, never as a completed creator. Refuses existing evidence to prevent repeats.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
PROBE='944ec808-fb71-48df-bd4c-5484b4ae964c'
REFERENCES=['9c27b811-8318-406c-bc1b-0c3dd22d7b19','ad1a00dd-d227-450c-a71f-df7279c8eba3']

async def main():
    out=ROOT/'evidence/live-qa/native-cable-lifecycle-probe.json'
    if out.exists(): raise RuntimeError('Existing lifecycle attempt; inspect receipt before continuing')
    report={'calls':[], 'complete_insertion_verified':False, 'native_connections_verified':False}
    def persist():out.write_text(json.dumps(report,indent=2),encoding='utf8')
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def execute(code):
            attempt={'code':code};report['calls'].append(attempt);persist()
            response=await client.call_tool('execute_script',{'code':code},timeout=45)
            raw=json.loads(next(c.text for c in response.content if c.type=='text'))
            attempt['response']=raw;persist()
            assert not raw.get('error'),raw
            return raw['result']
        prefix='import vs, entertainment as e, json\n'
        prefix+='qa='+repr(str(DOC))+'\ne.guard({"expected_document":qa})\n'
        baseline=await execute(prefix+"e.require(hasattr(vs,'VMCableLifecycleProbe'),'New native extension not loaded')\n"
            +"__result__={'references':[e.cable_sections_snapshot(e.handle(i,86)) for i in "+repr(REFERENCES)+"],"
            +"'probe':e.cable_sections_snapshot(e.handle("+repr(PROBE)+",86))}\n")
        report['baseline']=baseline;persist()
        async def native(request):
            return await execute(prefix+'request=json.loads('+repr(json.dumps(request))+')\n'
                +'__result__=json.loads(vs.VMCableLifecycleProbe(json.dumps(request)))\n')
        for request in (
            {'operation':'update_style','expected_document':str(DOC.with_name('Wrong-Document.vwx')),'object_id':PROBE},
            {'operation':'update_style','expected_document':str(DOC),'object_id':REFERENCES[0]},
            {'operation':'update_style','expected_document':str(DOC),'object_id':'missing-probe-uuid'},
        ):
            result=await native(request)
            assert result['status']=='error' and result['retry_safe'],result
        report['update']=await native({'operation':'update_style','expected_document':str(DOC),'object_id':PROBE})
        assert report['update']['object_id']==PROBE and not report['update']['retry_safe']
        report['update_after']=await execute(prefix+'__result__={"sections":e.cable_sections_snapshot(e.handle('+repr(PROBE)+',86)),"audit":e.get_cable_length_audit({"object_ids":['+repr(PROBE)+']})}\n')
        create_code=prefix+'''name='VM-QA-CABLE-DEFERRED-REGEN'
e.require(not vs.GetObject(name),'Deferred-regeneration probe already exists')
style=e.named('Jumper Powercon True1',16)
prior=e.context()
try:
    vs.Layer('QA Electrical Chain');vs.NameClass('VM-QA-Electrical-Cables')
    vs.BeginPoly3D();vs.Add3DPt(0,1440,0);vs.Add3DPt(240,1440,0);vs.EndPoly3D()
    path=vs.LNewObj();vs.SetPolyClosed(path,False);path=vs.ConvertToNURBS(path,False)
    vs.SetClass(path,'VM-QA-Electrical-Cables')
    request={'operation':'create_styled','expected_document':qa,'path_id':vs.GetObjectUuid(path),'style_id':vs.GetObjectUuid(style)}
    result=json.loads(vs.VMCableLifecycleProbe(json.dumps(request)))
    if result.get('status')=='ok' and result.get('object_id'):
        h=e.handle(result['object_id'],86);vs.SetName(h,name)
    __result__={'request':request,'native':result}
finally:e.restore(prior)
'''
        report['creation']=await execute(create_code);persist()
        created=report['creation']['native'].get('object_id')
        assert created,report['creation']
        inspected=await execute(prefix+'__result__={"sections":e.cable_sections_snapshot(e.handle('+repr(created)+',86)),"audit":e.get_cable_length_audit({"object_ids":['+repr(created)+']}),"configuration":e.get_cable_inspection({"object_ids":['+repr(created)+'],"include_connector_configuration":True}),"references":[e.cable_sections_snapshot(e.handle(i,86)) for i in '+repr(REFERENCES)+']}\n')
        report['creation_after']=inspected
        assert inspected['references']==baseline['references'],'Reference cables changed'
        report['references_unchanged']=True
        report['length_agreement']=inspected['audit']['cables'][0]['result']=='consistent_in_scope'
        report['native_contract_exercised']=True
        persist()
        print(json.dumps({k:v for k,v in report.items() if k not in ('calls','baseline','creation_after','update_after')}))

if __name__=='__main__':asyncio.run(main())
