"""Opt-in native visibility exercise on the separate QA file, restoring each setting."""
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
IDS = ['6f5066f2-3b7b-4b09-9395-98b4fddb5e68', '175e5451-f435-4fe6-ba2a-b0457a8c1f3b']


async def main():
    report = {'started': datetime.now(timezone.utc).isoformat(), 'calls': []}
    path = QA / 'live-viewport-display.json'
    uncertain = False
    transport = StdioTransport(command=sys.executable,
        args=[str(Path.home() / '.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ, 'VWX_TRANSPORT': 'file', 'VWX_VW_VERSION': '2026',
             'VWX_CALL_TIMEOUT': '180', 'VWX_SOCKET_TIMEOUT': '170', 'VWX_CACHE_TTL': '0'})
    async with Client(transport) as client:
        catalog = await client.list_tools()
        report['tool_count'] = len(catalog)
        assert len(catalog) == 277
        assert next(t for t in catalog if t.name == 'get_viewport_display').annotations.readOnlyHint

        async def call(name, args):
            nonlocal uncertain
            try:
                response = await client.call_tool(name, args, timeout=180)
                raw = next(c.text for c in response.content if c.type == 'text')
                value = json.loads(raw)
            except Exception:
                uncertain = True
                raise
            report['calls'].append({'tool': name, 'arguments': args, 'result': value,
                                    'payload_bytes': len(raw.encode('utf8'))})
            path.write_text(json.dumps(report, indent=2), encoding='utf8')
            if value.get('cid') and value.get('retry_safe') is False: uncertain = True
            assert not value.get('error'), value
            return value

        async def script(code):
            return (await call('execute_script', {'code': 'assert vs.GetFPathName() == ' + repr(DOC) + '\n' + code}))['result']

        capture = ('v=vs.GetObjectByUuid(' + repr(IDS[0]) + ');l=vs.GetObject("Toolkit QA")\n'
                   'c=vs.GetObjectByUuid(' + repr(IDS[1]) + ')\n'
                   '__result__={"class":vs.GetVPClassVisibility(v,"TK-Staging"),"layer":vs.GetVPLayerVisibility(v,l),'
                   '"other_class":vs.GetVPClassVisibility(c,"TK-Staging"),"other_layer":vs.GetVPLayerVisibility(c,l),'
                   '"document_class":vs.GetCVis("TK-Staging"),"document_layer":vs.GetLVis(l),"scale":vs.GetObjectVariableReal(v,1003)}')
        before = await script(capture)
        assert before['class'][0] and before['layer'][0]
        (QA / 'viewport-visibility-restore.json').write_text(json.dumps(before, indent=2))
        args = {'viewport_ids': IDS, 'detail': 'visibility', 'class_names': ['TK-Staging'], 'layer_names': ['Toolkit QA']}
        try:
            for kind, setter, target in [('class', 'SetVPClassVisibility', '"TK-Staging"'), ('layer', 'SetVPLayerVisibility', 'l')]:
                for value, state in [(2, 'gray'), (-1, 'hidden'), (0, 'visible')]:
                    await script('v=vs.GetObjectByUuid(' + repr(IDS[0]) + ');l=vs.GetObject("Toolkit QA")\n'
                                 'assert vs.' + setter + '(v,' + target + ',' + str(value) + ')\n__result__="setting applied in QA"')
                    result = await call('get_viewport_display', args)
                    changed, control = result['viewports']
                    key = 'classes' if kind == 'class' else 'layers'
                    assert changed[key][0]['state'] == state
                    original = before['other_class' if kind == 'class' else 'other_layer'][1]
                    assert control[key][0]['visibility'] == original
                    assert changed[key][0]['document_visibility'] == before['document_class' if kind == 'class' else 'document_layer']
            summary = await call('get_viewport_display', {'viewport_ids': [IDS[0]]})
            detail = await call('get_viewport_display', {'viewport_ids': [IDS[0]], 'detail': 'visibility', 'limit': 1})
            assert summary['viewports'][0]['class_count'] == detail['viewports'][0]['class_count']
            assert detail['viewports'][0]['classes_truncated']
            report['native_context_available'] = summary['viewports'][0]['native_context']['available']
        finally:
            if not uncertain:
                await script('v=vs.GetObjectByUuid(' + repr(IDS[0]) + ');l=vs.GetObject("Toolkit QA")\n'
                             'assert vs.SetVPClassVisibility(v,"TK-Staging",' + str(before['class'][1]) + ')\n'
                             'assert vs.SetVPLayerVisibility(v,l,' + str(before['layer'][1]) + ')\nvs.UpdateVP(v)\n__result__="restored"')
                after = await script(capture)
                assert before == after
                report['restored'] = True
        report['verified'] = True
        report['completed'] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps({k: report[k] for k in ['verified', 'restored', 'tool_count', 'native_context_available']}))


if __name__ == '__main__': asyncio.run(main())
