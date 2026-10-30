"""Read-only installed-MCP checks against existing named Toolkit QA fixtures."""
import asyncio
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / 'evidence/live-qa'
DOC = str(QA / 'Velvet-Mirror-Toolkit-QA.vwx')
IDS = ['9c27b811-8318-406c-bc1b-0c3dd22d7b19',
       '432701ff-5aa1-4afa-8e19-05fb62ab7f8c', '359ac935-b807-498d-968d-288b3e830d01']


async def main():
    evidence = QA / 'live-cable-geometry.json'
    report = {'started': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'calls': []}
    transport = StdioTransport(command=sys.executable,
        args=[str(Path.home() / '.local/share/vwx-mcp/vwx_mcp_server.py')],
        env={**os.environ, 'VWX_TRANSPORT':'file', 'VWX_VW_VERSION':'2026',
             'VWX_CACHE_TTL':'0', 'VWX_CALL_TIMEOUT':'60'})
    async with Client(transport) as client:
        catalog = await client.list_tools()
        tool = next(t for t in catalog if t.name == 'get_cable_inspection')
        assert tool.annotations.readOnlyHint
        assert 'geometry_detail' in tool.inputSchema['properties']
        report['tool_count'] = len(catalog)
        async def call(name, args):
            raw = await client.call_tool(name, args, timeout=60)
            body = next(c.text for c in raw.content if c.type == 'text')
            result = json.loads(body)
            report['calls'].append({'tool': name, 'arguments': args, 'result': result,
                                    'payload_bytes': len(body.encode('utf8'))})
            evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
            assert not result.get('error'), result
            return result
        capture = """import vs
assert vs.GetFPathName() == %r
ids = %r
objects = []
for oid in ids:
    h = vs.GetObjectByUuid(oid)
    assert h
    rec = vs.GetParametricRecord(h)
    kind = vs.GetName(rec)
    fields = {vs.GetFldName(rec,i):vs.GetRField(h,kind,vs.GetFldName(rec,i)) for i in range(1,vs.NumFields(rec)+1)}
    p = vs.GetCustomObjectPath(h)
    pieces = []
    for s in range(vs.NurbsCurveGetNumPieces(p)):
        pieces.append({'degree':vs.NurbsDegree(p,s),
          'control_points_local':[vs.NurbsGetPt3D(p,s,i) for i in range(vs.NurbsGetNumPts(p,s))],
          'weights':[vs.NurbsGetWeight(p,s,i) for i in range(vs.NurbsGetNumPts(p,s))],
          'knots':[vs.NurbsKnot(p,s,i) for i in range(vs.NurbsNumKnots(p,s))]})
    objects.append({'id':oid,'matrix':vs.GetEntityMatrix(h),'pieces':pieces,'fields':fields,
                    'class':vs.GetClass(h),'layer':vs.GetLName(vs.GetLayer(h))})
selected=[]
vs.ForEachObject(lambda h:selected.append(vs.GetObjectUuid(h)), '(SEL=TRUE)')
__result__={'objects':objects,'layer':vs.GetLName(vs.ActLayer()),'class':vs.ActiveClass(),'selection':sorted(selected)}
""" % (DOC, IDS)
        before = (await call('execute_script', {'code':capture}))['result']
        summary = await call('get_cable_inspection', {'object_ids':IDS,'geometry_detail':'summary'})
        points = await call('get_cable_inspection', {'object_ids':IDS,'geometry_detail':'points'})
        repeat = await call('get_cable_inspection', {'object_ids':IDS,'geometry_detail':'summary'})
        assert summary == repeat, 'Read-only repeated snapshot changed'
        expected_lengths = [240,480,math.dist((0,0,0),(123.456,112.345,27.89)) + math.dist((123.456,112.345,27.89),(225.456,100.345,147.89))]
        for native, short, full, expected in zip(before['objects'], summary['objects'], points['objects'], expected_lengths):
            geo = full['geometry']
            assert geo['status']=='ok' and geo['corner_polyline']
            assert geo['pieces'] == native['pieces']
            assert geo['object_transform']['origin_parent'] == native['matrix'][1]
            assert geo['object_transform']['rotation_degrees'] == native['matrix'][2:]
            assert geo['sha256'] == short['geometry']['sha256']
            assert 'pieces' not in short['geometry']
            assert math.isclose(geo['linear_length_local'],expected,abs_tol=1e-6)
            assert not geo['world_coordinates_verified']
        assert points['objects'][0]['geometry']['endpoints_local']==[[0,0,0],[240,0,0]]
        limited = await call('get_cable_inspection', {'object_ids':[IDS[1]],'geometry_detail':'summary','geometry_point_limit':2})
        assert limited['objects'][0]['geometry']['status']=='unavailable'
        assert limited['objects'][0]['drawn_length']==480
        assert 'geometry_unavailable' in limited['issue_counts']
        plain = await call('get_cable_inspection', {'object_ids':IDS})
        assert all('geometry' not in row for row in plain['objects'])
        after = (await call('execute_script', {'code':capture}))['result']
        assert before == after, 'Inspector altered geometry, records or drawing context'
        report.update(verified=True, completed=datetime.now(timezone.utc).isoformat(),
            offline_tests=108, native_movement_propagation_verified=False,
            full_electrical_chain_verified=False,
            default_payload_bytes=report['calls'][-2]['payload_bytes'],
            summary_payload_bytes=report['calls'][1]['payload_bytes'],
            points_payload_bytes=report['calls'][2]['payload_bytes'])
        evidence.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('verified','tool_count','read_only','default_payload_bytes','summary_payload_bytes','points_payload_bytes')}))
        print('Calls:',len(report['calls']))


if __name__ == '__main__':
    asyncio.run(main())
