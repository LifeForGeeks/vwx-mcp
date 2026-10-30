"""Native route plan/elevation and PDF QA; no production show edits."""
import asyncio, json, os, shutil, sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT=Path(__file__).resolve().parents[1]; QA=ROOT/'evidence/live-qa'
DOC=str(QA/'Velvet-Mirror-Toolkit-QA.vwx')


async def main():
    report={'calls':[]}; evidence=QA/'live-cable-documentation.json'
    transport=StdioTransport(command=sys.executable,args=[str(Path.home()/'.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ,'VWX_TRANSPORT':'file','VWX_VW_VERSION':'2026','VWX_CACHE_TTL':'0','VWX_CALL_TIMEOUT':'180'})
    async with Client(transport) as client:
        async def call(name,args):
            raw=await client.call_tool(name,args,timeout=180)
            result=json.loads(next(c.text for c in raw.content if c.type=='text'))
            report['calls'].append({'tool':name,'arguments':args,'result':result})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert not result.get('error'),result
            return result
        await call('ensure_drawing_structure',{'expected_document':DOC,'layers':[{'name':'QA-CABLE','kind':'sheet','paper_size':[24,18]}],'classes':[]})
        for key,view,center,bounds,title in [
            ('Plan','plan',[-5.5,0],[40,470,520,40],'CABLE ROUTES - TOP PLAN'),
            ('Front','front',[5.5,0],[40,220,520,-50],'CABLE ROUTES - FRONT ELEVATION')]:
            vp=await call('create_sheet_viewport',{'expected_document':DOC,'sheet':'QA-CABLE','name':'VM-QA-Cable-'+key,
                'scale':48,'bounds':bounds,'center':center,'layers':['VM-QA-Cable'],'hidden_classes':[],'view':view})
            notes=[{'name':'VM-QA-Cable-'+key+'-Title','kind':'text','position':[40,bounds[1]+65],
                    'text':title,'font_size':14},
                   {'name':'VM-QA-Cable-'+key+'-Scale','kind':'text','position':[40,bounds[1]+42],
                    'text':'SCALE 1:48 | 1/4 inch = 1 foot | Print at 100%','font_size':10},
                   {'name':'VM-QA-Cable-'+key+'-Note','kind':'text','position':[40,bounds[3]-55],
                    'text':'QA geometry only. Route A = 40 ft.\rConnections, cable stock and loads are not assigned.','font_size':10}]
            if key=='Plan':
                notes.append({'name':'VM-QA-Cable-Plan-Dim','kind':'dimension','position':[100,100],'end':[460,100],
                              'direction':'horizontal','offset':-30,'font_size':10})
            else:
                notes.append({'name':'VM-QA-Cable-Front-Dim','kind':'dimension','position':[220,12],'end':[220,132],
                              'direction':'vertical','offset':-35,'font_size':10})
            await call('annotate_viewport',{'expected_document':DOC,'viewport_id':vp['object_id'],'annotation_offset':vp['annotation_offset'],'items':notes})
        await call('save_document_checked',{'expected_document':DOC})
        configured=ROOT.parent/'vectorworks-rebuild/armory/evidence/print-check.pdf'
        backup=QA/'cable-before-configured-pdf.pdf'
        shutil.copy2(configured,backup)
        exported=await call('export_sheet_set_checked',{'expected_document':DOC,'sheets':['QA-CABLE'],
            'configured_output':str(configured),'destination':str(QA/'Cable-Route-QA.pdf')})
        # Restore the configured destination only after a completed checked export.
        shutil.copy2(backup,configured)
        report['export_complete']=True
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'export_complete':True,'calls':len(report['calls']),'destination':exported}))


if __name__=='__main__':asyncio.run(main())
