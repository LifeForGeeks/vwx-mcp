"""Read Vectorworks' on-disk parts cache; never edit the cache or infer live stock."""
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter


def require(test, message):
    if not test:
        raise ValueError(message)


def read_xml(path, root_name, byte_limit):
    require(isinstance(path,str) and Path(path).is_absolute(), 'An absolute XML path is required')
    source=Path(path)
    require(source.suffix.lower()=='.xml', 'Expected an XML file')
    with source.open('rb') as stream:
        raw=stream.read(byte_limit+1)
    require(len(raw)<=byte_limit, 'XML exceeds size limit')
    text=raw.decode('utf-8-sig')
    require('<!DOCTYPE' not in text.upper() and '<!ENTITY' not in text.upper(), 'XML declarations/entities are not supported')
    root=ET.fromstring(text)
    require(root.tag==root_name, 'Unexpected XML root: '+root.tag)
    require(len(root)<=20000, 'XML exceeds 20000 entries')
    require(all(e.tag=='Entry' for e in root), 'Unexpected XML entry type')
    return root, {'path':str(source.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def inspect_catalog(p):
    try:
        require(isinstance(p,dict), 'Parameters must be an object')
        require(set(p)<= {'cache_path','connector_catalog_path','search','symbols','cable_set','offset','limit','include_fields','expected_sha256'}, 'Unknown catalog parameter')
        query=p.get('search',''); symbols=p.get('symbols'); cable_set=p.get('cable_set')
        offset,limit,fields=p.get('offset',0),p.get('limit',25),p.get('include_fields',False)
        require(isinstance(query,str) and len(query)<=512, 'search must be text up to 512 characters')
        require(symbols is None or isinstance(symbols,list) and 1<=len(symbols)<=25 and all(isinstance(s,str) and 0<len(s)<=512 for s in symbols) and len(set(symbols))==len(symbols), 'symbols must contain 1..25 unique names')
        require(cable_set is None or isinstance(cable_set,str) and len(cable_set)<=512, 'cable_set must be text up to 512 characters')
        require(type(offset) is int and offset>=0, 'offset must be a nonnegative integer')
        require(type(limit) is int and 1<=limit<=50, 'limit must be 1..50')
        require(type(fields) is bool, 'include_fields must be boolean')
        expected=p.get('expected_sha256')
        require(expected is None or isinstance(expected,str) and len(expected)==64 and all(c in '0123456789abcdefABCDEF' for c in expected), 'Invalid expected_sha256')
        root,source=read_xml(p.get('cache_path'),'Libary',16*1024*1024)
        require(expected is None or expected.lower()==source['sha256'], 'Parts cache changed; restart paging')
        connector_source=None; connector_names=None
        if p.get('connector_catalog_path') is not None:
            connectors,connector_source=read_xml(p['connector_catalog_path'],'Entries',4*1024*1024)
            connector_names={e.get('UniversalName') for e in connectors if e.get('UniversalName')}
        selected=[]; all_symbols=set(); sets=Counter()
        for index,entry in enumerate(root):
            require(len(entry.attrib)<=100, 'Part entry exceeds 100 attributes')
            values=entry.attrib
            all_symbols.add(values.get('Symbol'))
            sets[values.get('SetName')]+=1
            if symbols is not None and values.get('Symbol') not in symbols: continue
            if cable_set is not None and values.get('SetName')!=cable_set: continue
            if query.casefold() not in ' '.join(values.get(k,'') for k in ('Name','ShortName','Symbol','ConnectorStart','ConnectorEnd','SetName')).casefold(): continue
            selected.append((index,values))
        parts=[]; issue_counts=Counter()
        for index,values in selected[offset:offset+limit]:
            issues=[]
            def clip(key):
                v=values.get(key)
                return v[:512] if v is not None else None
            def flag(key):
                v=values.get(key)
                return {'true':True,'false':False}.get(v.lower()) if isinstance(v,str) else None
            for key in ('Name','Symbol','RessourcePath'):
                if not values.get(key): issues.append('missing_identity_field')
            for key in ('Length','Diameter','WireGauge','Weight'):
                value=values.get(key)
                if value not in ('',None):
                    try: valid=math.isfinite(float(value)) and float(value)>=0
                    except (TypeError,ValueError): valid=False
                    if not valid: issues.append('invalid_numeric_value')
            truncated=[k[:512] for k,v in values.items() if len(v)>512 or len(k)>512]
            if truncated: issues.append('field_text_truncated')
            ends={}
            for end in ('start','end'):
                name=values.get('Connector'+end.title())
                present=(name in connector_names) if connector_names is not None and name else None
                ends[end]={'name':name[:512] if name is not None else None,'in_catalog':present}
                if present is False: issues.append('connector_name_absent')
            issue_counts.update(issues)
            part={'entry_index':index,'name':clip('Name'),'symbol':clip('Symbol'),'short_name':clip('ShortName'),
                  'cable_set':clip('SetName'),'enabled_in_cache':flag('Use'),'length_raw':clip('Length'),
                  'connectors':ends,'source_resource':clip('RessourcePath'),
                  'user_folder_flag':flag('UserBasedFolder'),'workgroup_flag':flag('WorkGroupPath'),
                  'issues':list(dict.fromkeys(issues)),'truncated_fields':truncated}
            if fields: part['fields']={k[:512]:v[:512] for k,v in values.items()}
            parts.append(part)
        end=offset+len(parts)
        return {'status':'ok','source':source,'connector_source':connector_source,
                'entry_count':len(root),'matched_count':len(selected),'offset':offset,
                'next_offset':end if end<len(selected) else None,'parts':parts,
                'missing_symbols':[s for s in symbols or [] if s not in all_symbols],
                'cable_sets':[{'name':k[:512] if k is not None else None,'entries':v} for k,v in sets.most_common(50)],
                'cable_sets_truncated':len(sets)>50,'issue_counts':dict(issue_counts),'issue_counts_scope':'returned_page',
                'native_inventory_verified':False,'electrical_compatibility_verified':False,
                'scope':'One on-disk cache snapshot, not live inventory, quantities, resource existence or current drawing settings. Numeric values retain raw cache units. Source flags/paths are reported without opening resources. Connector lookup uses exact names in one optional XML file; missing names may reflect version/alias/catalog differences. No connector equivalence, physical gender, wiring or ratings are inferred. Cache is never edited.'}
    except Exception as exc:
        return {'status':'error','error':str(exc),'code':'VM_CABLE_PARTS_CATALOG_ERROR'}
