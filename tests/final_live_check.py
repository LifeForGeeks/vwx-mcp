"""Opt-in final QA against the installed fork and the named disposable drawing."""
import asyncio
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / 'evidence/live-qa'
DOC = str(QA / 'Velvet-Mirror-Toolkit-QA.vwx')


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--create-final-deck', action='store_true')
    arguments=parser.parse_args()
    installed = Path.home() / '.local/share/vwx-mcp/vwx_mcp_server.py'
    transport = StdioTransport(command=sys.executable, args=[str(installed)], env={
        **os.environ, 'VWX_TRANSPORT': 'file', 'VWX_VW_VERSION': '2026',
        'VWX_CALL_TIMEOUT': '180', 'VWX_SOCKET_TIMEOUT': '170', 'VWX_CACHE_TTL': '0'})
    report = {'server': str(installed), 'calls': []}
    report_path = QA / 'final-installed-check.json'
    async with Client(transport) as client:
        catalog = await client.list_tools()
        report['tool_count'] = len(catalog)
        assert len(catalog) == 277

        async def call(name, parameters):
            result = await client.call_tool(name, parameters, timeout=180)
            data = json.loads(next(c.text for c in result.content if c.type == 'text'))
            report['calls'].append({'tool': name, 'arguments': parameters, 'result': data})
            report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            assert not data.get('error'), data
            print(name, 'OK', flush=True)
            return data

        if arguments.create_final_deck:
            created = await call('create_native_objects', {'expected_document': DOC, 'items': [
                {'name': 'TK-Deck-Final', 'plugin': 'Stage Deck', 'layer': 'Toolkit QA', 'class': 'TK-Staging',
                 'position': [2000, 100, 0], 'fields': {'Width': '96"', 'Depth': '48"', 'Height': '24"'}}]})
            assert not created['requires_finalization'], created
            await call('execute_script', {'code': 'assert vs.GetFPathName() == ' + repr(DOC) + '\n'
                "assert vs.GetLSN(vs.FInGroup(vs.GetObject('TK-Deck-Final'))) == 2\n"
                "for name in ['TK-Deck-2','TK-Deck-3','TK-Deck-Probe']:\n"
                " h=vs.GetObject(name)\n"
                " if h:vs.DelObject(h)\n"
                "__result__={'fresh_deck_visible_line_style':2}"})
        state = await call('get_entertainment_state', {
            'criteria': "((PON='Lighting Device') & (L='Toolkit QA'))", 'limit': 10, 'detail': 'full'})
        assert os.path.normcase(state['document']) == os.path.normcase(DOC)
        assert len(state['devices']) == 2
        assert all(d['hanging_position_id'] and len(d['accessories']) == 1 for d in state['devices'])
        results = Path(os.environ['APPDATA']) / 'Nemetschek/Vectorworks/2026/Plug-ins/VWX-MCP/ipc/results'
        cid = max(results.glob('*.json'), key=lambda p: p.stat().st_mtime_ns).stem
        first = await call('get_bridge_job_status', {'cid': cid})
        second = await call('get_bridge_job_status', {'cid': cid})
        assert first == second and first['status'] == 'done', (first, second)
        check = await call('execute_script', {'code':
            'assert vs.GetFPathName() == ' + repr(DOC) + '\n'
            "for name in ['TK-Viewport-1','TK-Viewport-2']:vs.UpdateVP(vs.GetObject(name))\n"
            "__result__={'deck_bounds':vs.GetBBox(vs.GetObject('TK-Deck-Final')),'dimension_mm':vs.GetObjectVariableReal(vs.GetObject('TK-Dimension-2'),17),'scale':vs.GetObjectVariableReal(vs.GetObject('TK-Viewport-1'),1003)}"})
        assert check['result']['deck_bounds'] == [[2000., 148.], [2096., 100.]]
        assert check['result']['scale'] == 48
        assert abs(check['result']['dimension_mm'] - 10 / 72 * 25.4 * 48) < .001
        await call('save_document_checked', {'expected_document': DOC})
        configured = ROOT.parent / 'vectorworks-rebuild/armory/evidence/print-check.pdf'
        backup = QA / 'previous-configured-pdf.pdf'
        shutil.copy2(configured, backup)
        await call('export_sheet_set_checked', {'expected_document': DOC, 'sheets': ['QA-101', 'QA-102'],
            'configured_output': str(configured), 'destination': str(QA / 'Velvet-Mirror-Toolkit-QA.pdf')})
        # Restore only after a known completed export; never race an uncertain running job.
        shutil.copy2(backup, configured)
    report['passed'] = True
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    asyncio.run(main())
