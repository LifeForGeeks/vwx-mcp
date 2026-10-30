"""Does a native Use flag edit affect stock selected at the next cable rebuild?"""
import asyncio,json,os,sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx'
CABLE='9c27b811-8318-406c-bc1b-0c3dd22d7b19'
PART='27838a28-3de7-4438-b761-9a233713125f'

async def main():
    force='--force-rebuild' in sys.argv
    path=ROOT/('evidence/live-qa/cable-availability-forced-rebuild.json' if force else 'evidence/live-qa/cable-availability-consumption.json')
    if path.exists():raise RuntimeError('Attempt exists. Inspect receipts before resuming.')
    report={'calls':[],'restored':False}
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf8')
    save()
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0'})
    async with Client(transport) as client:
        async def call(name,args):
            row={'tool':name,'arguments':args};report['calls'].append(row);save()
            raw=await client.call_tool(name,args,timeout=45)
            r=json.loads(next(c.text for c in raw.content if c.type=='text'));row['result']=r;save()
            assert r.get('status')=='ok',r
            return r
        p=(await call('get_cable_part_symbols',{'object_ids':[PART]}))['symbols'][0]
        orig=await call('get_cable_sections',{'object_ids':[CABLE]})
        assert Path(orig['document'])==DOC
        before=orig['cables'][0];section=before['sections'][0]
        assert p['fields']['Use'].lower()=='true' and p['fields']['ShortName']=='E-25ft'
        assert before['section_count']==1 and section['start_slack_mm']==150
        disabled=await call('set_cable_part_availability',{'expected_document':str(DOC),'items':[{'object_id':PART,'enabled':False,'expected_fingerprint':p['fingerprint']}]})
        current=before
        if force:
            long_run=await call('set_cable_sections',{'expected_document':str(DOC),'object_id':CABLE,'expected_fingerprint':before['fingerprint'],
                'sections':[{'index':1,'start_slack_mm':8000}]})
            current=long_run['verification']['cable']
            report['parts_after_forced_growth']=current['sections'][0]['parts'];save()
        result=await call('set_cable_sections',{'expected_document':str(DOC),'object_id':CABLE,'expected_fingerprint':current['fingerprint'],
            'sections':[{'index':1,'start_slack_mm':151}]})
        after=result['verification']['cable']
        report['native_selection_respected_use_flag']='E-25ft' not in after['sections'][0]['parts']
        report['selected_parts_while_disabled']=after['sections'][0]['parts'];save()
        await call('set_cable_part_availability',{'expected_document':str(DOC),'items':[{'object_id':PART,'enabled':True,'expected_fingerprint':disabled['parts'][0]['fingerprint']}]})
        restore=await call('set_cable_sections',{'expected_document':str(DOC),'object_id':CABLE,'expected_fingerprint':after['fingerprint'],
            'sections':[{'index':1,'start_slack_mm':150}]})
        assert restore['verification']['cable']==before
        final=(await call('get_cable_part_symbols',{'object_ids':[PART]}))['symbols'][0]
        assert final==p
        report['restored']=True;save();print(json.dumps({k:v for k,v in report.items() if k!='calls'}))

if __name__=='__main__':asyncio.run(main())
