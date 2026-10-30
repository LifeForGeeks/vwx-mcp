"""One-shot native stage assembly QA. Never rerun after a creation receipt exists."""
import asyncio, json, os, sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]; QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx'); OUTPUT=QA/'stage-grid-installed.json'

async def main():
    assert not OUTPUT.exists(), 'Existing one-shot receipt; inspect it instead of recreating'
    report={'calls':[]}
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args,allow_error=False):
            result=await client.call_tool(name,args,timeout=60)
            value=json.loads(next(c.text for c in result.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':value})
            OUTPUT.write_text(json.dumps(report,indent=2),encoding='utf8')
            if not allow_error:assert not value.get('error'),value
            return value
        capture='assert vs.GetFPathName()=='+repr(DOC)+'''\nitems=[]
def read(h):
    if not vs.GetName(h).startswith('VM-QA-MODULAR-STAGE-'):
        items.append([vs.GetObjectUuid(h),vs.GetEntityMatrix(h),vs.GetClass(h),vs.GetLName(vs.GetLayer(h))])
vs.ForEachObject(read,"((PON='Stage Deck') | (PON='Lighting Device') | (PON='TrussItem'))")
__result__={'items':sorted(items,key=lambda x:x[0]),'layer':vs.GetLName(vs.ActLayer()),'class':vs.ActiveClass()}
'''
        before=(await call('execute_script',{'code':capture}))['result']
        await call('ensure_drawing_structure',{'expected_document':DOC,
            'layers':[{'name':'QA Modular Staging','kind':'design','scale':48}],
            'classes':['VM-QA-Staging-Decks']})
        args={'expected_document':DOC,'name':'VM-QA-MODULAR-STAGE','layer':'QA Modular Staging',
              'class_name':'VM-QA-Staging-Decks','origin_mm':[0,0,0],'columns':2,'rows':2,
              'deck_size_mm':[1219.2,2438.4,609.6],'rotation':30,
              'structure':'Legs-Braced','rail_edges':['back','left','right'],
              'rail_type':'Straight+Toe','vendor':'QA Rental Supplier','location':'QA Modular Stage',
              'brand':'Unconfirmed','model':'Generic native deck'}
        dry=await call('create_stage_deck_grid',{**args,'dry_run':True});assert dry['count']==4 and not dry['created']
        created=await call('create_stage_deck_grid',args)
        assert created['verification']['verified'] and not created['requires_verification'],created
        ids=[r['object_id'] for r in created['created']]
        first=await call('get_stage_deck_inspection',{'object_ids':ids})
        assert len(first['decks'])==4
        repeated=await call('get_stage_deck_inspection',{'object_ids':ids});assert first==repeated
        duplicate=await call('create_stage_deck_grid',args,allow_error=True);assert duplicate.get('error')
        after=(await call('execute_script',{'code':capture}))['result'];assert before==after
        await call('save_document_checked',{'expected_document':DOC})
        report.update(verified=True,created_ids=ids,existing_objects_and_context_unchanged=True,
                      repeated_inspection_stable=True,duplicate_rejected=True,
                      visual_comparison=False,manufacturer_specific_geometry=False)
        OUTPUT.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
