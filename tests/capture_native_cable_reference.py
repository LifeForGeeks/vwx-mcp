"""Read a user-drawn QA reference after native-cable-manual-reference-baseline.json.

No drawing writes or resets. Refuses an existing receipt to preserve observations.
Run only after the user finishes the native Cable tool and returns to Selection.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'evidence/live-qa/native-cable-manual-reference-baseline.json'
OUT=ROOT/'evidence/live-qa/native-cable-manual-reference.json'

async def main():
    if OUT.exists(): raise RuntimeError('Reference receipt exists; inspect it before another capture')
    baseline=json.loads(BASE.read_text(encoding='utf8'))
    # JSON appears only inside Python source as a repr-quoted literal, never as shell text.
    code='''import vs, entertainment as e, json
baseline=json.loads(BASELINE)
e.guard({'expected_document':baseline['document']})
ids=[];vs.ForEachObject(lambda h:ids.append(vs.GetObjectUuid(h)),"(PON='CableObject')")
new=sorted(set(ids)-set(baseline['cable_ids']))
e.require(1<=len(new)<=5,'Expected 1..5 new user-drawn reference cables; found '+str(len(new)))
def inspect(oid):
    h=e.handle(oid,86);rec=vs.GetParametricRecord(h)
    e.require(e.plugin(h)=='CableObject','Expected CableObject')
    count=vs.NumFields(rec);e.require(0<count<=512,'Unexpected record schema')
    fields={vs.GetFldName(rec,i):vs.GetRField(h,'CableObject',vs.GetFldName(rec,i)) for i in range(1,count+1)}
    row={'identity':e.identity(h),'fields':{k:v[:1024] for k,v in fields.items()},
         'truncated_fields':[k for k,v in fields.items() if len(v)>1024],
         'style':vs.GetPluginStyle(h),'sections':e.cable_sections_snapshot(h),
         'geometry':e.cable_geometry_snapshot(h,vs.GetCustomObjectPath(h),'points',2000)}
    return row
probe=inspect(baseline['selected_probe_id']);references=[inspect(oid) for oid in new]
diffs=[{'object_id':row['identity']['object_id'],'fields':{
    key:{'api_probe':probe['fields'].get(key),'native_reference':row['fields'].get(key)}
    for key in sorted(set(probe['fields'])|set(row['fields']))
    if probe['fields'].get(key)!=row['fields'].get(key)}} for row in references]
__result__={'document':vs.GetFPathName(),'new_reference_ids':new,'probe':probe,'references':references,
    'field_differences':diffs,'audit':e.get_cable_length_audit({'object_ids':[baseline['selected_probe_id']]+new}),
    'read_only':True,'causal_explanation_verified':False}
'''.replace('BASELINE',repr(json.dumps(baseline)))
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        raw=await client.call_tool('execute_script',{'code':code},timeout=45)
        result=json.loads(next(c.text for c in raw.content if c.type=='text'))
        if result.get('error'):raise RuntimeError(result)
        data=result['result'];OUT.write_text(json.dumps(data,indent=2),encoding='utf8')
        print(json.dumps({'new_reference_ids':data['new_reference_ids'],'audit':data['audit'],
                          'field_differences':data['field_differences']}))

if __name__=='__main__':asyncio.run(main())
