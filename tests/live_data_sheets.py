"""Read-only installed-MCP verification; requires the prepared, separate QA file."""
import asyncio
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / 'evidence/live-qa'
DOC = str(QA / 'Velvet-Mirror-Toolkit-QA.vwx')
OID = '000dc7ba-46fc-4bb2-830f-47679d157927'


async def main():
    report = {'started': datetime.now(timezone.utc).isoformat(), 'calls': []}
    path = QA / 'live-data-sheets.json'
    transport = StdioTransport(command=sys.executable,
        args=[str(Path.home() / '.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ, 'VWX_TRANSPORT': 'file', 'VWX_VW_VERSION': '2026',
             'VWX_CALL_TIMEOUT': '180', 'VWX_SOCKET_TIMEOUT': '170', 'VWX_CACHE_TTL': '0'})
    async with Client(transport) as client:
        catalog = await client.list_tools()
        report['tool_count'] = len(catalog)
        assert len(catalog) == 277
        tool = next(t for t in catalog if t.name == 'get_data_sheet_inspection')
        assert tool.annotations.readOnlyHint

        async def call(name, args):
            response = await client.call_tool(name, args, timeout=180)
            raw = next(c.text for c in response.content if c.type == 'text')
            data = json.loads(raw)
            report['calls'].append({'tool': name, 'arguments': args, 'result': data,
                                    'payload_bytes': len(raw.encode('utf-8'))})
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            return data

        await call('execute_script', {'code': 'assert vs.GetFPathName() == ' + repr(DOC) + '\n__result__="QA path verified"'})
        base = {'mapping_name': 'Lighting Device'}
        listing = await call('get_data_sheet_inspection', base)
        assert 'VM QA Device' in listing['sheet_names'] and 'VM QA Empty' in listing['sheet_names']
        args = {**base, 'data_sheet': 'VM QA Device', 'object_ids': [OID]}
        data = await call('get_data_sheet_inspection', args)
        assert data['status'] == 'ok' and data['failed_reads'] == data['object_errors'] == 0
        fields = {f['label']: f for f in data['fields']}
        values = {f['label']: f for f in data['objects'][0]['values']}
        assert values['Fixture Model']['value'] == 'Chauvet Color Strike M'
        assert values['Fixture ID']['value'] == 'LX-160'
        assert values['Supplier']['value'] == '' and values['Supplier']['native_ok']
        assert fields['Supplier']['visible'] is False
        page = await call('get_data_sheet_inspection', {**args, 'field_offset': 2, 'field_limit': 1})
        assert len(page['fields']) == 1 and page['next_field_offset'] == 3
        empty = await call('get_data_sheet_inspection', {**base, 'data_sheet': 'VM QA Empty'})
        assert empty['field_count'] == 0 and empty['fields'] == []
        invalid = await call('get_data_sheet_inspection', {**base, 'data_sheet': 'VM QA NONEXISTENT'})
        assert invalid['status'] == 'error'
        missing = await call('get_data_sheet_inspection', {**args, 'object_ids': ['00000000-0000-0000-0000-000000000000']})
        assert missing['object_errors'] == 1
        report['verified'] = True
        report['completed'] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'verified': True, 'tool_count': len(catalog), 'calls': len(report['calls']), 'evidence': str(path)}))


if __name__ == '__main__':
    asyncio.run(main())
