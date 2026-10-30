import copy
import hashlib
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from test_entertainment import e, vs, ROOT


class CablePartSymbolTests(unittest.TestCase):
    def setUp(self):
        vs.reset_mock(return_value=True,side_effect=True)
        self.doc=str(ROOT/'tests'/'Scratch.vwx');vs.GetFPathName.return_value=self.doc
        self.fields=json.loads((ROOT/'evidence/live-qa/native-cable-part-schema.json').read_text(encoding='utf8'))['result'][0]['records'][0]['fields']
        self.values={'base':{'CablePart':{f['name']:f['value'] for f in self.fields}}}
        self.names={'base':'Library TRUE1'};self.types={'base':16,'root':54,'text-base':10,'line-base':3}
        self.texts={'text-base':"25'"};self.children={'base':['line-base','text-base']}
        vs.GetObject.side_effect=lambda n:next((h for h,v in self.names.items() if v==n),None)
        vs.GetObjectByUuid.side_effect=lambda u:u if u in self.types else None
        vs.GetTypeN.side_effect=lambda h:self.types[h]
        vs.GetName.side_effect=lambda h:'CablePart' if h=='rec' else self.names.get(h,'')
        vs.GetObjectUuid.side_effect=lambda h:h
        vs.GetParent.return_value='root'
        vs.NumRecords.return_value=1;vs.GetRecord.return_value='rec'
        vs.NumFields.return_value=len(self.fields)
        vs.GetFldName.side_effect=lambda r,i:self.fields[i-1]['name']
        vs.GetFldType.side_effect=lambda r,i:self.fields[i-1]['type']
        vs.GetRField.side_effect=lambda h,r,k:self.values[h].get(r,{}).get(k,'')
        vs.FInSymDef.side_effect=lambda h:self.children[h][0]
        def next_obj(h):
            for children in self.children.values():
                if h in children:
                    i=children.index(h)+1
                    return children[i] if i<len(children) else None
            return None
        vs.NextObj.side_effect=next_obj;vs.GetText.side_effect=lambda h:self.texts[h]
        vs.SetText.side_effect=lambda h,v:self.texts.__setitem__(h,v)
        vs.SetName.side_effect=lambda h,n:self.names.__setitem__(h,n)
        vs.SetRField.side_effect=lambda h,r,k,v:self.values[h].setdefault(r,{}).__setitem__(k,v)
        def duplicate(h,parent):
            self.types.update(new=16,**{'line-new':3,'text-new':10});self.names['new']='copy'
            self.values['new']=copy.deepcopy(self.values[h]);self.children['new']=['line-new','text-new'];self.texts['text-new']=self.texts['text-base']
            return 'new'
        vs.CreateDuplicateObject.side_effect=duplicate

    def call(self,name,**p):
        self.assertIn(name,e.COMMANDS)
        return e.COMMANDS[name](p)

    def item(self,**change):
        fields={f['name']:f['value'] for f in self.fields}
        fields.update(Name='QA TRUE1 30ft',ShortName='QA-T1-30',Length=9144,Weight=2300,Use=False,SetName='QA')
        return {'template_symbol':'Library TRUE1','symbol_name':'VM Test','fields':fields,
                'text_replacements':{"25'":"30'"},**change}

    def test_wrong_document_and_incomplete_spec_fail_without_edits(self):
        for p in [{'expected_document':self.doc+'x','items':[self.item()]},
                  {'expected_document':self.doc,'items':[self.item(fields={'Name':'Bad'})]}]:
            self.assertEqual(self.call('create_cable_part_symbols',**p)['status'],'error')
        vs.CreateDuplicateObject.assert_not_called();vs.NewField.assert_not_called()

    def test_entire_batch_is_preflighted_before_creation(self):
        for item in [self.item(symbol_name='Library TRUE1'),self.item(symbol_name='Other',text_replacements={}),
                     self.item(symbol_name='Other',fields={**self.item()['fields'],'Length':float('nan')}),
                     self.item(symbol_name='vm test')]:
            r=self.call('create_cable_part_symbols',expected_document=self.doc,items=[self.item(),item])
            self.assertEqual(r['status'],'error')
        vs.CreateDuplicateObject.assert_not_called()

    def test_creation_updates_native_values_and_visible_text_without_changing_template(self):
        original=copy.deepcopy(self.values['base'])
        r=self.call('create_cable_part_symbols',expected_document=self.doc,items=[self.item()])
        self.assertEqual(r['status'],'ok',r)
        self.assertEqual(self.values['base'],original)
        self.assertEqual(self.values['new']['CablePart']['Length'],'9144')
        self.assertEqual(self.texts['text-new'],"30'")
        self.assertEqual(self.texts['text-base'],"25'")
        self.assertFalse(r['native_catalog_registered'])
        self.assertTrue(r['created'][0]['verified'])

    def test_mismatched_native_schema_and_nested_geometry_are_rejected(self):
        vs.GetFldType.side_effect=lambda r,i:4
        r=self.call('create_cable_part_symbols',expected_document=self.doc,items=[self.item()])
        self.assertEqual(r['status'],'error')
        vs.GetFldType.side_effect=lambda r,i:self.fields[i-1]['type']
        self.types['line-base']=11
        r=self.call('create_cable_part_symbols',expected_document=self.doc,items=[self.item()])
        self.assertEqual(r['status'],'error')
        vs.CreateDuplicateObject.assert_not_called()

    def test_partial_failure_keeps_created_uuid_for_recovery(self):
        vs.SetRField.side_effect=RuntimeError('native failure')
        r=self.call('create_cable_part_symbols',expected_document=self.doc,items=[self.item()])
        self.assertEqual(r['status'],'error')
        self.assertFalse(r['retry_safe'])
        self.assertEqual(r['created'][0]['object_id'],'new')
        vs.DelObject.assert_not_called()

    def test_symbol_readback_is_read_only_and_preserves_raw_units(self):
        r=self.call('get_cable_part_symbols',object_ids=['base'])
        self.assertEqual(r['status'],'ok',r)
        self.assertEqual(r['symbols'][0]['fields']['Length'],'7620')
        self.assertEqual(r['symbols'][0]['texts'],["25'"])
        self.assertFalse(r['native_catalog_registered'])
        vs.SetRField.assert_not_called();vs.ResetObject.assert_not_called()

    def test_export_refuses_wrong_document_existing_path_or_nonpart_without_native_call(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'Existing.vwx';dest.write_bytes(b'original')
            for changes in ({'expected_document':self.doc+'x'},{'path':str(dest)},{'object_ids':['root']}):
                args={'expected_document':self.doc,'path':str(Path(folder)/'New.vwx'),'object_ids':['base'],**changes}
                self.assertEqual(self.call('export_cable_part_library',**args)['status'],'error')
            self.assertEqual(dest.read_bytes(),b'original');vs.VMExportSymbolLibrary.assert_not_called()

    def test_export_requires_compiled_extension(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(vs,'VMExportSymbolLibrary',None):
            result=self.call('export_cable_part_library',expected_document=self.doc,path=str(Path(folder)/'New.vwx'),object_ids=['base'])
            self.assertEqual(result['status'],'error');self.assertIn('extension',result['error'])

    def test_export_verifies_resource_names_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'New.vwx'
            def export(payload):
                request=json.loads(payload);dest.write_bytes(b'fake native file')
                return json.dumps({'contract_version':1,'status':'ok','path':str(dest),'symbol_names':['Library TRUE1'],'object_ids':['base']})
            vs.VMExportSymbolLibrary.side_effect=export
            vs.BuildResourceListN.return_value=(1,1);vs.GetNameFromResourceList.return_value='Library TRUE1'
            result=self.call('export_cable_part_library',expected_document=self.doc,path=str(dest),object_ids=['base'])
            self.assertEqual(result['status'],'ok',result);self.assertTrue(result['resource_names_verified'])
            self.assertFalse(result['native_catalog_registered']);self.assertEqual(len(result['sha256']),64)

    def test_export_failure_retains_file_and_marks_retry_unsafe(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'New.vwx'
            def export(payload):
                dest.write_bytes(b'partial')
                return json.dumps({'contract_version':1,'status':'error','error':'Native failure'})
            vs.VMExportSymbolLibrary.side_effect=export
            result=self.call('export_cable_part_library',expected_document=self.doc,path=str(dest),object_ids=['base'])
            self.assertEqual(result['status'],'error');self.assertFalse(result['retry_safe']);self.assertTrue(result['file_exists'])
            self.assertEqual(dest.read_bytes(),b'partial')

    def test_export_does_not_claim_success_for_missing_resource(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'New.vwx'
            def export(payload):
                dest.write_bytes(b'native file')
                return json.dumps({'contract_version':1,'status':'ok','path':str(dest),'symbol_names':['Library TRUE1'],'object_ids':['base']})
            vs.VMExportSymbolLibrary.side_effect=export;vs.BuildResourceListN.return_value=(1,0)
            result=self.call('export_cable_part_library',expected_document=self.doc,path=str(dest),object_ids=['base'])
            self.assertEqual(result['status'],'error');self.assertFalse(result['retry_safe'])

    def test_existing_empty_library_requires_current_hash_and_preserves_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'Empty.vwx';dest.write_bytes(b'empty library');digest=hashlib.sha256(dest.read_bytes()).hexdigest()
            args={'expected_document':self.doc,'path':str(dest),'object_ids':['base'],'empty_library_sha256':digest}
            bad=self.call('export_cable_part_library',**{**args,'empty_library_sha256':'0'*64})
            self.assertEqual(bad['status'],'error');vs.VMExportSymbolLibrary.assert_not_called()
            def export(payload):
                self.assertTrue(json.loads(payload)['allow_empty_existing']);dest.write_bytes(b'populated library')
                return json.dumps({'contract_version':1,'status':'ok','path':str(dest),'symbol_names':['Library TRUE1'],'object_ids':['base']})
            vs.VMExportSymbolLibrary.side_effect=export
            vs.BuildResourceListN.side_effect=[(1,0),(2,0),(3,1)];vs.GetNameFromResourceList.return_value='Library TRUE1'
            result=self.call('export_cable_part_library',**args)
            self.assertEqual(result['status'],'ok',result)
            self.assertEqual(Path(result['backup_path']).read_bytes(),b'empty library')

    def test_existing_nonempty_library_is_never_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'Populated.vwx';dest.write_bytes(b'existing resources')
            vs.BuildResourceListN.return_value=(1,3)
            result=self.call('export_cable_part_library',expected_document=self.doc,path=str(dest),object_ids=['base'],empty_library_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
            self.assertEqual(result['status'],'error');vs.VMExportSymbolLibrary.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()),[dest])

    def test_overlong_names_and_numeric_strings_are_rejected_before_mutation(self):
        for item in (self.item(symbol_name='Test'+' '*200),self.item(fields={**self.item()['fields'],'Weight':'0'*5000})):
            self.assertEqual(self.call('create_cable_part_symbols',expected_document=self.doc,items=[item])['status'],'error')
        vs.CreateDuplicateObject.assert_not_called();vs.NewField.assert_not_called()
