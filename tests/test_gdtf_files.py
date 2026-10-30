import io, json, tempfile, unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from test_entertainment import e, server
import gdtf_files as g

def archive(xml,name='description.xml',extra=None):
    out=io.BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr(name,xml)
        for k,v in (extra or {}).items():z.writestr(k,v)
    return out.getvalue()

def fixture(channels='<DMXChannel Offset="1,2"/><DMXChannel Offset="3"/><DMXChannel/>',geometries=''):
    return '<GDTF DataVersion="1.2"><FixtureType Name="QA" Manufacturer="Test" FixtureTypeID="abc"><Geometries>'+geometries+'</Geometries><DMXModes><DMXMode Name="Mode"><DMXChannels>'+channels+'</DMXChannels></DMXMode></DMXModes></FixtureType></GDTF>'

class GDTFFilesTests(unittest.TestCase):
    def test_simple_offsets_virtual_and_multibyte_channel(self):
        info=g.gdtf_metadata(archive(fixture()));m=info['modes'][0]
        self.assertEqual(m['simple_single_break_footprint'],3);self.assertEqual(m['virtual_channels'],1)
        self.assertEqual(m['channel_definitions'],3)

    def test_geometry_references_and_multiple_breaks_withhold_simple_footprint(self):
        for xml in [fixture(geometries='<GeometryReference/>'),fixture('<DMXChannel Offset="1" DMXBreak="Overwrite"/>'),
                    fixture('<DMXChannel Offset="1" DMXBreak="2"/>')]:
            self.assertIsNone(g.gdtf_metadata(archive(xml))['modes'][0]['simple_single_break_footprint'])

    def test_invalid_offsets_are_not_reported_as_valid_footprints(self):
        for offset in ('0','513','a','1,2,3,4,5'):
            m=g.gdtf_metadata(archive(fixture('<DMXChannel Offset="'+offset+'"/>')))['modes'][0]
            self.assertIsNone(m['simple_single_break_footprint']);self.assertEqual(m['unresolved_channels'],1)

    def test_dtd_rejected_in_utf8_and_utf16(self):
        xml='<!DOCTYPE GDTF [<!ENTITY x "unsafe">]>'+fixture()
        for enc in ('utf8','utf-16'):
            with self.assertRaises(ValueError):g.gdtf_metadata(archive(xml.encode(enc)))

    def test_hash_guard_and_server_read_needs_no_vectorworks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fixture.gdtf';p.write_bytes(archive(fixture()))
            info=g.inspect_gdtf(str(p))
            with self.assertRaises(ValueError):g.inspect_gdtf(str(p),'0'*64)
            with patch.object(server,'get_vwx_connection',side_effect=AssertionError('Should not connect')):
                result=json.loads(server.cmd('get_gdtf_file',{'path':str(p),'expected_sha256':info['sha256']}))
            self.assertEqual(result['status'],'ok')

    def test_mvr_checks_exact_embedded_modes_and_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'scene.mvr'
            xml='<GeneralSceneDescription verMajor="1" verMinor="6"><Scene><Fixture uuid="a"><GDTFSpec>qa.gdtf</GDTFSpec><GDTFMode>Mode</GDTFMode></Fixture><Fixture uuid="b"><GDTFSpec>qa.gdtf</GDTFSpec><GDTFMode>Wrong</GDTFMode></Fixture><Fixture uuid="c"><GDTFSpec>missing.gdtf</GDTFSpec></Fixture></Scene></GeneralSceneDescription>'
            p.write_bytes(archive(xml,'GeneralSceneDescription.xml',{'qa.gdtf':archive(fixture())}))
            r=g.audit_mvr(str(p),1)
            self.assertEqual(r['fixture_count'],3);self.assertEqual(r['checked_gdtf_count'],1)
            self.assertEqual(r['issue_counts'],{'mode_not_in_embedded_gdtf':1,'missing_or_duplicate_embedded_gdtf':1})
            self.assertTrue(r['issues_truncated']);self.assertFalse(r['gdtf_mode_references_consistent'])

    def test_empty_mvr_is_not_a_successful_fixture_exchange(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'empty.mvr';p.write_bytes(archive('<GeneralSceneDescription/>','GeneralSceneDescription.xml'))
            self.assertFalse(g.audit_mvr(str(p))['gdtf_mode_references_consistent'])

    def test_import_hash_and_mode_preflight_before_native(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'guard'),patch.object(e,'handle') as handle:
            p=Path(tmp)/'qa.gdtf';p.write_bytes(archive(fixture()))
            args={'expected_document':'QA.vwx','object_id':'id','expected_fingerprint':'x','path':str(p),
                  'expected_sha256':'0'*64,'mode':'Missing','use_gdtf_geometry':False}
            self.assertEqual(e.assign_gdtf_file(args)['status'],'error');handle.assert_not_called()
            args['expected_sha256']=g.inspect_gdtf(str(p))['sha256']
            self.assertIn('mode',e.assign_gdtf_file(args)['error']);handle.assert_not_called()

if __name__=='__main__':unittest.main()
