import hashlib
import tempfile
import unittest
from pathlib import Path
from test_entertainment import e, vs, server


CATALOG = '''<?xml version="1.0" encoding="utf-8"?>
<Entries>
 <Entry UniversalName="Soca-A" LocalizedName="Multipin A" SocketPatchCount="3">
  <Socket UniversalName="L1" LocalizedName="Line"/>
  <Socket UniversalName="PE" LocalizedName="Earth"/>
  <Socket UniversalName="PE" LocalizedName="Earth"/>
  <ConnectableWith UniversalName="Soca-B"/>
  <ConnectableWith UniversalName="Unknown"/>
 </Entry>
 <Entry UniversalName="Soca-B" LocalizedName="Multipin B" SocketPatchCount="3">
  <Socket UniversalName="L1" LocalizedName="Line"/>
 </Entry>
 <Entry UniversalName="XLR5" LocalizedName="5-pin XLR" SocketPatchCount="5"/>
</Entries>'''


class ConnectorCatalogTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True, side_effect=True)
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/'Libraries/Entertainment/Power/Cable Tools/CableConnectors.xml'
        self.path.parent.mkdir(parents=True)
        self.path.write_text(CATALOG,encoding='utf8')
        vs.GetFolderPath.return_value=str(self.root)

    def query(self, **p):
        self.assertIn('get_cable_connector_catalog',e.COMMANDS,'Connector catalog tool not implemented')
        return e.COMMANDS['get_cable_connector_catalog'](p)

    def test_default_catalog_searches_labels_but_keeps_universal_identity(self):
        result=self.query(search='multipin',limit=1)
        self.assertEqual(result['status'],'ok',result)
        self.assertEqual(result['connector_count'],3)
        self.assertEqual(result['matched_count'],2)
        self.assertEqual(result['next_offset'],1)
        self.assertEqual(result['connectors'][0]['universal_name'],'Soca-A')
        self.assertNotIn('sockets',result['connectors'][0])
        self.assertEqual(result['source']['sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertFalse(result['active_catalog_precedence_verified'])
        self.assertFalse(result['physical_wiring_verified'])

    def test_socket_order_and_repeated_labels_are_preserved(self):
        row=self.query(names=['Soca-A'],include_sockets=True)['connectors'][0]
        self.assertEqual([s['index'] for s in row['sockets']],[0,1,2])
        self.assertEqual([s['universal_name'] for s in row['sockets']],['L1','PE','PE'])
        self.assertEqual(row['repeated_socket_names'],['PE'])
        self.assertEqual(row['socket_definition_status'],'count_matches')

    def test_declared_links_do_not_become_symmetric_or_invented_compatibility(self):
        row=self.query(names=['Soca-A'])['connectors'][0]
        self.assertEqual(row['declared_connections'],[
            {'universal_name':'Soca-B','target_in_catalog':True,'reciprocal_declaration':False},
            {'universal_name':'Unknown','target_in_catalog':False,'reciprocal_declaration':None}])
        other=self.query(names=['Soca-B'])['connectors'][0]
        self.assertEqual(other['declared_connections'],[])

    def test_unlisted_and_partial_socket_maps_stay_distinct(self):
        r=self.query(names=['XLR5','Soca-B'],include_sockets=True)
        rows={x['universal_name']:x for x in r['connectors']}
        self.assertEqual(rows['XLR5']['socket_patch_count'],5)
        self.assertEqual(rows['XLR5']['sockets'],[])
        self.assertEqual(rows['XLR5']['socket_definition_status'],'not_listed')
        self.assertEqual(rows['Soca-B']['socket_definition_status'],'count_differs')

    def test_exact_lookup_reports_missing_names_without_alias_substitution(self):
        r=self.query(names=['xlr5','5-pin XLR','XLR5'])
        self.assertEqual(r['missing_names'],['xlr5','5-pin XLR'])
        self.assertEqual([x['universal_name'] for x in r['connectors']],['XLR5'])

    def test_hash_guard_rejects_changed_catalog_without_stale_cache(self):
        first=self.query();digest=first['source']['sha256']
        self.path.write_text(CATALOG.replace('Multipin A','Updated label'),encoding='utf8')
        self.assertEqual(self.query(expected_sha256=digest)['status'],'error')
        fresh=self.query(names=['Soca-A'])
        self.assertEqual(fresh['connectors'][0]['localized_name'],'Updated label')
        self.assertNotEqual(fresh['source']['sha256'],digest)

    def test_explicit_missing_source_does_not_fall_back_to_application(self):
        r=self.query(path=str(self.root/'missing.xml'))
        self.assertEqual(r['status'],'error')
        vs.GetFolderPath.assert_not_called()

    def test_malformed_or_unsupported_catalogs_fail_explicitly(self):
        for xml in ['<Other/>','<Entries><Entry/></Entries>',
            '<!DOCTYPE Entries [<!ENTITY x "value">]><Entries/>',
            CATALOG.replace('UniversalName="Soca-B" LocalizedName','UniversalName="Soca-A" LocalizedName'),
            CATALOG.replace('SocketPatchCount="5"','SocketPatchCount="bad"'),
            CATALOG.replace('<Entries>','<Entries><HiddenSettings/>'),
            CATALOG.replace('SocketPatchCount="5"','SocketPatchCount="5" Unknown="x"')]:
            self.path.write_text(xml,encoding='utf8')
            self.assertEqual(self.query()['status'],'error',xml)
        self.path.write_bytes(b' '*(1024*1024+1))
        self.assertEqual(self.query()['status'],'error')

    def test_query_bounds_and_readonly_contract(self):
        for p in [{'limit':0},{'limit':51},{'offset':-1},{'include_sockets':'yes'},
                  {'names':['a','a']},{'names':[]},{'names':['a'],'search':'x'},
                  {'expected_sha256':'bad'},{'path':'relative.xml'}]:
            self.assertEqual(self.query(**p)['status'],'error',p)
        self.assertIn('get_cable_connector_catalog',server._MENU_CONTEXT_READS)
        self.assertTrue(server._is_readonly('get_cable_connector_catalog'))
        vs.SetRField.assert_not_called();vs.ResetObject.assert_not_called()


if __name__=='__main__':unittest.main()
