import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mcp-server'))


class CablePartsCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)/'CablePartsCache.xml'
        self.connectors = Path(self.tmp.name)/'CableConnectors.xml'
        self.cache.write_text('''<Libary>
<Entry Name="TRUE1 25ft" Symbol="TRUE1 Cable 25ft" ShortName="T1-25" SetName="VM" ConnectorStart="Legacy True1" ConnectorEnd="Legacy True1" Length="7620.000000" Use="true" RessourcePath="Jumper.vwx"/>
<Entry Name="TRUE1 25ft" Symbol="TRUE1 Cable 25ft" ShortName="T1-25" SetName="Rental" ConnectorStart="PowerTwistCBC" ConnectorEnd="PowerTwistCBC" Length="7620" Use="false" RessourcePath="Custom.vwx" UserBasedFolder="true"/>
<Entry Name="Data" Symbol="XLR" ShortName="DMX" Length="NaN" Use="unknown"/>
</Libary>''',encoding='utf8')
        self.connectors.write_text('<Entries><Entry UniversalName="PowerTwistCBC" LocalizedName="TRUE1"/></Entries>',encoding='utf8')

    def call(self, **kw):
        import cable_parts_catalog
        return cable_parts_catalog.inspect_catalog({'cache_path':str(self.cache), **kw})

    def test_scoped_search_preserves_duplicate_identity_and_disabled_parts(self):
        r=self.call(search='true1')
        self.assertEqual(r['status'],'ok')
        self.assertEqual(r['entry_count'],3)
        self.assertEqual(r['matched_count'],2)
        self.assertEqual([p['enabled_in_cache'] for p in r['parts']],[True,False])
        self.assertNotEqual(r['parts'][0]['entry_index'],r['parts'][1]['entry_index'])
        self.assertEqual(r['parts'][0]['length_raw'],'7620.000000')
        self.assertFalse(r['native_inventory_verified'])
        self.assertNotIn('fields',r['parts'][0])

    def test_exact_catalog_names_only_no_silent_alias(self):
        r=self.call(search='true1',connector_catalog_path=str(self.connectors))
        self.assertFalse(r['parts'][0]['connectors']['start']['in_catalog'])
        self.assertTrue(r['parts'][1]['connectors']['start']['in_catalog'])
        self.assertEqual(r['issue_counts']['connector_name_absent'],2)
        self.assertFalse(r['electrical_compatibility_verified'])

    def test_hash_guard_and_page_counts(self):
        r=self.call(limit=1)
        self.assertEqual(r['next_offset'],1)
        p=self.call(offset=1,limit=1,expected_sha256=r['source']['sha256'])
        self.assertEqual(p['parts'][0]['entry_index'],1)
        self.cache.write_text('<Libary/>',encoding='utf8')
        self.assertEqual(self.call(expected_sha256=r['source']['sha256'])['status'],'error')

    def test_unknown_flags_and_numbers_remain_unknown(self):
        p=self.call(search='Data')['parts'][0]
        self.assertIsNone(p['enabled_in_cache'])
        self.assertEqual(p['length_raw'],'NaN')
        self.assertIn('invalid_numeric_value',p['issues'])

    def test_bounds_and_xml_entities_are_rejected(self):
        for kw in ({'limit':0},{'limit':51},{'offset':-1},{'offset':True},
                   {'search':'x'*513},{'include_fields':'yes'},{'unexpected':True}):
            self.assertEqual(self.call(**kw)['status'],'error')
        self.cache.write_text('<!DOCTYPE Libary [<!ENTITY x "x">]><Libary/>',encoding='utf8')
        self.assertEqual(self.call()['status'],'error')

    def test_exact_symbols_reports_missing_and_preserves_all_sources(self):
        r=self.call(symbols=['TRUE1 Cable 25ft','Missing'])
        self.assertEqual(r['matched_count'],2)
        self.assertEqual(r['missing_symbols'],['Missing'])

    def test_long_field_is_explicitly_truncated(self):
        self.cache.write_text('<Libary><Entry Name="'+('x'*600)+'" Symbol="A"/></Libary>',encoding='utf8')
        p=self.call(include_fields=True)['parts'][0]
        self.assertEqual(len(p['name']),512)
        self.assertIn('Name',p['truncated_fields'])
        self.assertEqual(len(p['fields']['Name']),512)

    def test_generic_dispatch_does_not_require_running_bridge(self):
        import vwx_mcp_server as server
        with patch.object(server,'get_vwx_connection',side_effect=AssertionError('Bridge must not be contacted')):
            r=json.loads(server.cmd('get_cable_parts_catalog',{'cache_path':str(self.cache)}))
        self.assertEqual(r['status'],'ok')

