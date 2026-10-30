"""Velvet Mirror native workflows. Runs only on the Vectorworks main thread.

Design-layer coordinates and paper coordinates use document units. Native accessory
offsets use millimetres. No project-specific names, paths or equipment ratings.
"""
import functools
import hashlib
import json
import math
import os
import shutil
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
import vs

VERSION = '0.15.1'
COMMANDS = {}
NATIVE_TYPES = ('Lighting Device', 'Stage Deck', 'Stage Steps', 'Side Arm', 'LEDWall')
HELPER_CLASSES = ('NonPlot', 'Chord Snapping', 'Insert Points', 'Rigging-Truss-Magnet',
                  'Lighting-Input-', 'Lighting-Movement Radius', 'Lighting-Beam-Angle',
                  'Power-Components', 'Video-Signal-Input', 'Video-Signal-Output', 'Video-Power-Input', 'Video-Power-Output')


def command(fn):
    @functools.wraps(fn)
    def checked(p):
        try:
            return {'status': 'ok', **fn(p)}
        except Exception as exc:
            return {'status': 'error', 'error': str(exc), 'code': 'VM_WORKFLOW_ERROR',
                    'command': fn.__name__,
                    'recovery': 'Inspect named objects before retrying; a native API failure can leave partial work.'}
    COMMANDS[fn.__name__] = checked
    return checked


def require(condition, message):
    if not condition:
        raise ValueError(message)


ELECTRICAL_COMPONENT_FIELDS = {
    'ElectricComponent_Input': ('input', ('Input', 'Connections')),
    'ElectricComponent_Output': ('output', ('Output', 'Connections')),
    'ElectricComponent_Fuse': ('fuse', ('Rating', 'Ampere', 'In', 'Out', 'Connections')),
    'ElectricComponent_Generator': ('generator', ('Voltage', 'MaximumPower')),
    'ElectricComponent_Consumer': ('consumer', ('Power', 'PowerFactor', 'MinimumVoltage', 'MaximumVoltage')),
}


def distributor_symbol_snapshot(symbol):
    """Read definition components, not a runtime electrical network. Never reset resources."""
    require(vs.GetTypeN(symbol) == 16, 'Expected a symbol definition')
    components=[]; seen=set(); child=vs.FInSymDef(symbol); nodes=0
    while child:
        nodes+=1; require(nodes<=4096, 'Symbol traversal exceeds 4096 objects')
        uid=vs.GetObjectUuid(child)
        require(uid and uid not in seen, 'Repeated symbol child identity or traversal cycle')
        seen.add(uid)
        pn=plugin(child) if vs.GetTypeN(child)==86 else ''
        if pn in ELECTRICAL_COMPONENT_FIELDS:
            require(len(components)<512, 'Symbol exceeds 512 electrical components')
            kind, extra=ELECTRICAL_COMPONENT_FIELDS[pn]
            keys=('Name','Connector','Internal_ID','ScaleX','ScaleY','ScaleZ')+extra
            values={k:vs.GetRField(child,pn,k) for k in keys}
            require(all(isinstance(v,str) and len(v)<=65536 for v in values.values()), 'Oversized/invalid component field')
            components.append({'geometry_id':uid, 'stored_internal_id':values['Internal_ID'],
                'plugin':pn, 'type':kind, 'name':values['Name'], 'connector':values['Connector'],
                'definition_local_matrix':matrix(child), 'stored_fields':values})
        child=vs.NextObj(child)
    counts=Counter(c['stored_internal_id'].lower() for c in components)
    issues=[{'stored_internal_id':key,'count':count,
             'issue':'missing_internal_id' if not key else 'duplicate_internal_id'}
            for key,count in counts.items() if not key or count>1]
    encoded=json.dumps(components,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    require(len(encoded)<=1000000, 'Symbol electrical data exceeds 1 MB')
    return {'symbol':vs.GetName(symbol), 'symbol_id':vs.GetObjectUuid(symbol),
            'symbol_fingerprint':hashlib.sha256(encoded).hexdigest(), 'component_count':len(components),
            'type_counts':dict(Counter(c['type'] for c in components)), 'identity_issues':issues,
            'components':components, 'scan_scope':'Immediate symbol-definition children; nested geometry is not expanded.'}


@command
def get_distributor_inspection(p):
    ids=p.get('object_ids'); batch(ids,10)
    require(all(isinstance(x,str) and 0<len(x)<=128 for x in ids),'Invalid object_ids')
    require(len(set(x.lower() for x in ids))==len(ids),'Duplicate object_ids')
    detail=p.get('detail','summary'); limit=p.get('limit',25)
    require(detail in ('summary','components'),'detail must be summary or components')
    require(type(limit) is int and 1<=limit<=100,'limit must be 1..100')
    out=[]
    for oid in ids:
        row={'object_id':oid};out.append(row)
        try:
            h=handle(oid); kind=vs.GetTypeN(h)
            if kind==16:
                symbol=h; row['object_kind']='symbol_definition'
            else:
                require(kind==86 and plugin(h)=='DistributorObject','Expected native DistributorObject or symbol definition')
                row.update(identity(h)); row['object_kind']='distributor'
                row['fields']={k:vs.GetRField(h,'DistributorObject',k) for k in ('ID','Name','Location','Symbol','Weight','NameInventory')}
                row['matrix']=matrix(h); symbol=named(row['fields']['Symbol'],16)
            snapshot=distributor_symbol_snapshot(symbol)
            components=snapshot.pop('components'); row.update(snapshot)
            if detail=='components':
                # Connections remain unparsed stored data. Internal_ID is not an object UUID.
                row['components']=[{**c,'stored_fields':{k:v[:512] for k,v in c['stored_fields'].items()},
                    'truncated_fields':[k for k,v in c['stored_fields'].items() if len(v)>512]}
                    for c in components[:limit]]
                row['components_truncated']=len(components)>limit
            row['inspection_status']='ok'
        except Exception as exc: row.update(inspection_status='error',reason=str(exc))
    return {'document':vs.GetFPathName(),'objects':out,'external_connections_verified':False,
            'engineering_values_verified':False,
            'scope':'Symbol-definition components and raw stored settings; not runtime device connections. Component matrices are definition-local, not world placement. Ratings and internal connection strings are not certified wiring or circuit calculations.'}


@command
def create_distributors(p):
    """Insert library-backed native distributors; verify after the native event finishes."""
    guard(p); require(set(p)<= {'expected_document','items'},'Unsupported creation setting')
    items=batch(p.get('items'),25); plans=[]; names=set(); device_ids=set()
    existing=[]
    vs.ForEachObject(lambda h:existing.append(vs.GetRField(h,'DistributorObject','ID')), "(PON='DistributorObject')")
    allowed={'name','layer','class','symbol','device_id','position','rotation','description','location'}
    for row in items:
        require(isinstance(row,dict) and set(row)<=allowed,'Unsupported distributor setting; connection/private fields are not writable')
        for key in ('name','layer','class','symbol','device_id'):
            require(isinstance(row.get(key),str) and 0<len(row[key].strip())<=128,'Missing/invalid '+key)
        for key in ('description','location'):
            require(isinstance(row.get(key,''),str) and len(row.get(key,''))<=512,'Invalid '+key)
        require(row['name'].casefold() not in names and not vs.GetObject(row['name']),'Duplicate/existing object name')
        require(row['device_id'].casefold() not in device_ids and row['device_id'].casefold() not in {x.casefold() for x in existing},'Duplicate/existing distributor ID')
        names.add(row['name'].casefold()); device_ids.add(row['device_id'].casefold())
        layer=named(row['layer'],31); require(vs.GetObjectVariableInt(layer,154)==1,'Use a design layer')
        named(row['class'],94); xyz=point(row['position']); angles=point(row.get('rotation',[0,0,0]))
        symbol=named(row['symbol'],16); snapshot=distributor_symbol_snapshot(symbol)
        require(snapshot['component_count'],'Library symbol requires native electrical components')
        require(snapshot['type_counts'].get('input',0) or snapshot['type_counts'].get('generator',0),'Symbol requires an input or source component')
        values={'ID':row['device_id'],'Name':row.get('description',row['symbol']),
                'Symbol':row['symbol'],'Location':row.get('location','')}
        plans.append((row,xyz,angles,snapshot,values))
    prior=context(); created=[]
    try:
        for row,xyz,angles,snapshot,values in plans:
            vs.Layer(row['layer']);vs.NameClass(row['class']);defaults_by_class()
            h=vs.CreateCustomObjectN('DistributorObject',xyz[:2],angles[2],False)
            require(h,'Native distributor creation failed')
            receipt={'object_id':vs.GetObjectUuid(h),'name':row['name'],'layer':row['layer'],'class':row['class'],
                     'symbol':row['symbol'],'symbol_fingerprint':snapshot['symbol_fingerprint'],'fields':values,
                     'identity_issues':snapshot['identity_issues'],
                     'matrix':[True,list(xyz),*angles]}
            created.append(receipt)
            vs.SetName(h,row['name']);vs.SetClass(h,row['class']);attributes_by_class(h)
            put(h,'DistributorObject',values);set_matrix(h,xyz,angles);vs.ResetObject(h)
            actual=matrix(h);require(same(actual[1],xyz),'Native insertion moved distributor')
            require(same(rotation_axes(actual[2:5]),rotation_axes(angles)), 'Native insertion changed distributor rotation')
            receipt['matrix']=actual
    except Exception as exc:
        return {'status':'error','error':str(exc),'created':created,'retry_safe':False,
                'recovery':'Inspect the returned UUIDs and requested names; never repeat uncertain creation.'}
    finally: restore(prior)
    return {'created':created,'count':len(created),'requires_verification':True,
            'next_command':'get_distributor_verification','external_connections_verified':False}


@command
def get_distributor_verification(p):
    guard(p); rows=batch(p.get('created'),25); results=[]
    for receipt in rows:
        row={'object_id':receipt.get('object_id')};results.append(row)
        try:
            h=handle(receipt['object_id'],86); require(plugin(h)=='DistributorObject','Distributor type changed')
            actual=identity(h)
            require(all(actual[k]==receipt[k] for k in ('name','layer','class')),'Distributor identity/organization changed')
            require(same(matrix(h),receipt['matrix']),'Distributor pose changed')
            require(all(vs.GetRField(h,'DistributorObject',k)==v for k,v in receipt['fields'].items()),'Distributor settings changed')
            snapshot=distributor_symbol_snapshot(named(receipt['symbol'],16))
            require(snapshot['symbol_fingerprint']==receipt['symbol_fingerprint'],'Symbol electrical definition changed')
            child=vs.FInGroup(h); found=[]; seen=set()
            while child:
                uid=vs.GetObjectUuid(child)
                require(uid not in seen and len(seen)<4096,'Generated geometry traversal invalid')
                seen.add(uid)
                if vs.GetTypeN(child)==15: found.append(vs.GetSymName(child))
                child=vs.NextObj(child)
            require(receipt['symbol'] in found,'Native symbol geometry not regenerated; retry verification only')
            row.update(verified=True,component_count=snapshot['component_count'],type_counts=snapshot['type_counts'])
        except Exception as exc: row.update(verified=False,reason=str(exc))
    return {'verified':all(r['verified'] for r in results),'objects':results,'external_connections_verified':False,
            'scope':'Native distributor type, settings, pose, layer/class, generated symbol reference and electrical definition snapshot.'}


@command
def get_electrical_components(p):
    """Read SDK electrical components; never infer external connections or sum shared power."""
    ids = p.get('object_ids')
    require(isinstance(ids, list) and 1 <= len(ids) <= 10 and
            all(isinstance(x, str) and 0 < len(x) <= 128 for x in ids), 'object_ids requires 1..10 identifiers')
    require(len({x.lower() for x in ids}) == len(ids), 'Duplicate object_ids')
    detail = p.get('detail', 'summary'); limit = p.get('limit', 25)
    links = p.get('include_internal_connections', False)
    require(detail in ('summary', 'components'), 'detail must be summary or components')
    require(type(limit) is int and 1 <= limit <= 100, 'limit must be 1..100')
    require(type(links) is bool and (not links or detail == 'components'),
            'include_internal_connections requires boolean and components detail')
    kinds = {0: 'input', 1: 'output', 2: 'fuse', 3: 'generator', 4: 'consumer'}
    objects = []
    fn = getattr(vs, 'VMGetElectricalComponents', None)
    for oid in ids:
        row = {'object_id': oid}; objects.append(row)
        h = vs.GetObjectByUuid(oid)
        if not h:
            row['inspection_status'] = 'missing_object'; continue
        if vs.GetTypeN(h) != 86:
            row['inspection_status'] = 'unsupported_object_type'; continue
        row.update(name=vs.GetName(h), layer=vs.GetLName(vs.GetLayer(h)), class_name=vs.GetClass(h))
        if not callable(fn):
            row.update(inspection_status='extension_unavailable', reason='VMGetElectricalComponents is not loaded; install the staged native bridge after a normal Vectorworks close')
            continue
        try:
            raw = fn(h)
            require(isinstance(raw, str) and len(raw) <= 1000000, 'Unexpected native electrical payload')
            data = json.loads(raw)
            require(isinstance(data, dict) and type(data.get('contract_version')) is int and data['contract_version'] == 1,
                    'Unsupported native electrical contract')
            require(data.get('status') == 'ok', 'Native provider failed: ' + str(data.get('error', 'unknown error')))
            require(isinstance(data.get('object_id'), str) and data['object_id'].lower() == oid.lower(), 'Native object identity mismatch')
            require(type(data.get('provider_available')) is bool, 'Invalid provider availability')
            components = data.get('components')
            require(isinstance(components, list) and len(components) <= 512, 'Invalid component array')
            if not data['provider_available']:
                require(not components, 'Unavailable provider returned components')
                row['inspection_status'] = 'provider_unavailable'; continue
            pair_counts = Counter(); link_count = 0
            for c in components:
                require(isinstance(c, dict), 'Invalid component')
                for key in ('device_id', 'component_id', 'name', 'connector'):
                    require(isinstance(c.get(key), str) and len(c[key]) <= 2048, 'Invalid component ' + key)
                require(type(c.get('type_code')) is int, 'Invalid component type code')
                for key in ('average_consumption_w', 'maximum_consumption_w'):
                    require(type(c.get(key)) in (int, float) and math.isfinite(c[key]), 'Invalid component ' + key)
                for key in ('is_virtual', 'is_link_through'):
                    require(type(c.get(key)) is bool, 'Invalid component ' + key)
                conn = c.get('internal_connections')
                require(isinstance(conn, list), 'Invalid internal connections')
                link_count += len(conn); require(link_count <= 2048, 'Internal connection limit exceeded')
                for link in conn:
                    require(isinstance(link, dict), 'Invalid internal connection')
                    for key in ('own_socket', 'other_socket'):
                        require(type(link.get(key)) is int and link[key] >= 0, 'Invalid socket index')
                    for key in ('name', 'other_component_id'):
                        require(isinstance(link.get(key), str) and len(link[key]) <= 2048, 'Invalid internal connection ' + key)
                pair_counts[(c['device_id'].lower(), c['component_id'].lower())] += 1
            issues = []
            for (device, component), count in pair_counts.items():
                if not device or not component or count > 1:
                    issues.append({'device_id': device, 'component_id': component, 'count': count,
                                   'issue': 'missing_identity' if not device or not component else 'duplicate_pair'})
            row.update(inspection_status='ok', component_count=len(components),
                       type_counts=dict(Counter(kinds.get(c['type_code'], 'unknown:' + str(c['type_code'])) for c in components)),
                       internal_connection_count=link_count, identity_issues=issues[:100], identity_issues_truncated=len(issues) > 100)
            if detail == 'components':
                output = []
                for c in components[:limit]:
                    item = {k: c[k] for k in ('device_id', 'component_id', 'type_code', 'name', 'connector',
                            'average_consumption_w', 'maximum_consumption_w', 'is_virtual', 'is_link_through')}
                    item['type'] = kinds.get(c['type_code'], 'unknown:' + str(c['type_code']))
                    item['internal_connection_count'] = len(c['internal_connections'])
                    if links:
                        item['internal_connections'] = [{**link, 'target_device_id': c['device_id'],
                            'target_match_count': pair_counts[(c['device_id'].lower(), link['other_component_id'].lower())]
                            if c['device_id'] and link['other_component_id'] else None}
                            for link in c['internal_connections']]
                    output.append(item)
                row.update(components=output, components_truncated=len(components) > limit)
        except Exception as exc:
            row.update(inspection_status='error', reason=str(exc))
    return {'document': vs.GetFPathName(), 'objects': objects, 'external_connections_verified': False,
            'engineering_values_verified': False,
            'scope': 'Native provider components and internal links within each device. Pair device/component UUIDs; preserve provider order. Consumption is raw provider data, not a circuit total, rating or calculation. Target matches are identity matches only, not verified wiring. No connection setters or object resets.'}


@command
def get_cable_connector_catalog(p):
    """Inspect one on-disk connector catalog without inferring wiring or live precedence."""
    query, names = p.get('search', ''), p.get('names')
    offset, limit = p.get('offset', 0), p.get('limit', 25)
    include, expected = p.get('include_sockets', False), p.get('expected_sha256')
    require(isinstance(query, str) and len(query) <= 256, 'search must be text up to 256 characters')
    require(type(offset) is int and offset >= 0, 'offset must be a nonnegative integer')
    require(type(limit) is int and 1 <= limit <= 50, 'limit must be 1..50')
    require(type(include) is bool, 'include_sockets must be boolean')
    if names is not None:
        batch(names, 25)
        require(all(isinstance(n, str) and n and len(n) <= 256 for n in names), 'Exact universal names require 1..256 characters')
        require(len(set(names)) == len(names), 'Duplicate lookup names')
        require(not query, 'Use search or exact names, not both')
    if expected is not None:
        require(isinstance(expected, str) and len(expected) == 64 and all(c in '0123456789abcdefABCDEF' for c in expected), 'expected_sha256 must be 64 hexadecimal characters')
    explicit = p.get('path')
    require(explicit is None or (isinstance(explicit, str) and explicit and os.path.isabs(explicit)), 'path must be an absolute XML file path')
    if explicit is None:
        app = vs.GetFolderPath(1)
        require(app and os.path.isabs(app), 'Native application folder unavailable')
        source = Path(app) / 'Libraries/Entertainment/Power/Cable Tools/CableConnectors.xml'
    else:
        source = Path(explicit)
    require(source.is_file() and source.suffix.lower() == '.xml', 'Connector XML file not found: '+str(source))
    with source.open('rb') as stream:
        raw = stream.read(1024*1024+1)
    require(len(raw) <= 1024*1024, 'Connector XML exceeds 1 MiB')
    digest = hashlib.sha256(raw).hexdigest()
    require(expected is None or digest == expected.lower(), 'Connector catalog changed; obtain a fresh hash before continuing this page sequence')
    text = raw.decode('utf-8-sig')
    require('<!doctype' not in text.casefold() and '<!entity' not in text.casefold(), 'DTD and entity declarations are unsupported')
    root = ET.fromstring(text)
    require(root.tag == 'Entries' and not root.attrib and not (root.text or '').strip(), 'Unsupported connector catalog root')
    require(len(root) <= 2048, 'Connector catalog exceeds 2048 entries')
    entries = []
    def clean_element(element, tag, allowed, required):
        require(element.tag == tag and set(element.attrib) <= allowed and required <= set(element.attrib), 'Unsupported '+tag+' schema')
        require(not (element.text or '').strip() and not (element.tail or '').strip(), 'Unexpected text in '+tag)
        for key, value in element.attrib.items():
            require(bool(value) and len(value) <= 256, tag+' attribute must have 1..256 characters: '+key)
    for entry in root:
        clean_element(entry, 'Entry', {'UniversalName','LocalizedName','SocketPatchCount'}, {'UniversalName','SocketPatchCount'})
        count_raw = entry.get('SocketPatchCount')
        require(count_raw.isascii() and count_raw.isdecimal(), 'SocketPatchCount must be a nonnegative integer')
        count = int(count_raw)
        require(count <= 65535 and len(entry) <= 256, 'Connector definition exceeds supported bounds')
        sockets, targets = [], []
        for child in entry:
            require(not len(child), 'Nested connector elements are unsupported')
            if child.tag == 'Socket':
                clean_element(child, 'Socket', {'UniversalName','LocalizedName'}, {'UniversalName'})
                sockets.append({'index': len(sockets), 'universal_name': child.get('UniversalName'), 'localized_name': child.get('LocalizedName')})
            else:
                clean_element(child, 'ConnectableWith', {'UniversalName'}, {'UniversalName'})
                targets.append(child.get('UniversalName'))
        socket_names = Counter(s['universal_name'] for s in sockets)
        entries.append({'universal_name': entry.get('UniversalName'), 'localized_name': entry.get('LocalizedName'),
            'socket_patch_count': count, 'listed_socket_count': len(sockets), 'sockets': sockets,
            'socket_definition_status': 'not_listed' if not sockets and count else 'count_matches' if len(sockets) == count else 'count_differs',
            'repeated_socket_names': [n for n, ncount in socket_names.items() if ncount > 1],
            'targets': targets})
    index = {row['universal_name']: row for row in entries}
    require(len(index) == len(entries), 'Duplicate connector universal names are ambiguous')
    missing = [n for n in names if n not in index] if names is not None else []
    matched = [r for r in entries if (r['universal_name'] in names if names is not None else
        query.casefold() in (r['universal_name']+' '+(r['localized_name'] or '')).casefold())]
    matched.sort(key=lambda r: (r['universal_name'].casefold(), r['universal_name']))
    page = matched[offset:offset+limit]
    require(sum(len(r['targets']) + (len(r['sockets']) if include else 0) for r in page) <= 1000, 'Detail exceeds 1000 socket/link rows; reduce limit')
    output = []
    for row in page:
        value = {k: v for k, v in row.items() if k not in ('targets','sockets')}
        value['declared_connections'] = [{'universal_name': target, 'target_in_catalog': target in index,
            'reciprocal_declaration': row['universal_name'] in index[target]['targets'] if target in index else None} for target in row['targets']]
        if include: value['sockets'] = row['sockets']
        output.append(value)
    end = offset + len(page)
    return {'source': {'path': str(source.resolve()), 'kind': 'explicit_file' if explicit is not None else 'application_file',
                       'sha256': digest, 'bytes': len(raw)},
            'connector_count': len(entries), 'matched_count': len(matched), 'offset': offset,
            'next_offset': end if end < len(matched) else None, 'missing_names': missing, 'connectors': output,
            'active_catalog_precedence_verified': False, 'electrical_compatibility_verified': False, 'physical_wiring_verified': False,
            'scope': 'One UTF-8 catalog snapshot. Socket indices are zero-based XML order, not certified physical pin numbers. ConnectableWith declarations are reported directionally; absent or reciprocal entries do not prove electrical compatibility. User/workgroup overrides and native in-memory catalog state are not resolved.'}


CABLE_PART_TYPES = {'Use':2, 'Name':4, 'ShortName':4, 'Length':3, 'Diameter':3,
    'ConnectorStart':4, 'ConnectorEnd':4, 'MaterialRating':4, 'SetName':4,
    'Weight':3, 'AwgPreset':4, 'WireGauge':3}
CABLE_PART_META = 'VM Cable Part Detail'
CABLE_PART_META_FIELDS = ('StartManufacturer','StartModel','StartGender','EndManufacturer',
    'EndModel','EndGender','PartNumber','Notes','TemplateSymbol','TemplateFingerprint')


def cable_part_symbol_snapshot(h):
    require(vs.GetTypeN(h)==16, 'Expected symbol definition')
    count=vs.NumRecords(h); require(0<=count<=64, 'Record count exceeds bound')
    records={vs.GetName(vs.GetRecord(h,i)):vs.GetRecord(h,i) for i in range(1,count+1)}
    require('CablePart' in records, 'Symbol has no native CablePart record')
    r=records['CablePart']; require(vs.NumFields(r)==len(CABLE_PART_TYPES), 'Unsupported CablePart schema')
    schema={vs.GetFldName(r,i):vs.GetFldType(r,i) for i in range(1,vs.NumFields(r)+1)}
    require(schema==CABLE_PART_TYPES, 'Unsupported native CablePart field types')
    fields={k:vs.GetRField(h,'CablePart',k) for k in CABLE_PART_TYPES}
    require(all(isinstance(v,str) and len(v)<=512 for v in fields.values()), 'Oversized CablePart fields')
    child=vs.FInSymDef(h); seen=set(); texts=[]; kinds=[]
    while child:
        uid=vs.GetObjectUuid(child)
        require(uid and uid not in seen and len(seen)<100, 'Invalid or oversized part graphics')
        seen.add(uid); kind=vs.GetTypeN(child)
        require(kind in (3,10,21), 'Only flat native line/text/polyline part graphics supported')
        kinds.append(kind)
        if kind==10:
            value=vs.GetText(child); require(len(value)<=512, 'Oversized part label'); texts.append(value)
        child=vs.NextObj(child)
    fingerprint=hashlib.sha256(json.dumps([fields,texts,kinds],sort_keys=True).encode('utf8')).hexdigest()
    metadata={k:vs.GetRField(h,CABLE_PART_META,k) for k in CABLE_PART_META_FIELDS} if CABLE_PART_META in records else {}
    return {'object_id':vs.GetObjectUuid(h),'symbol_name':vs.GetName(h),'fields':fields,
            'texts':texts,'graphic_types':kinds,'fingerprint':fingerprint,'metadata':metadata}


@command
def get_cable_part_symbols(p):
    ids=batch(p.get('object_ids'),25)
    require(all(isinstance(x,str) and 0<len(x)<=128 for x in ids), 'Invalid UUID')
    require(len({x.lower() for x in ids})==len(ids), 'Duplicate UUIDs')
    return {'document':vs.GetFPathName(),'symbols':[cable_part_symbol_snapshot(handle(x)) for x in ids],
            'native_catalog_registered':None,
            'scope':'Native resource records and flat line/text/polyline graphics. Length is raw millimetres; other numeric units remain unverified. Fingerprint covers fields, labels and graphic types, not geometric coordinates. Library registration is not checked.'}


@command
def set_cable_part_availability(p):
    """Change the current document's native Use flags; do not rebuild cable runs."""
    guard(p); require(set(p)<= {'expected_document','items'}, 'Unsupported availability setting')
    plans=[]; seen=set()
    for item in batch(p.get('items'),25):
        require(isinstance(item,dict) and set(item)=={'object_id','enabled','expected_fingerprint'}, 'Supply UUID, enabled and expected_fingerprint')
        oid=item['object_id']; enabled=item['enabled']; expected=item['expected_fingerprint']
        require(isinstance(oid,str) and 0<len(oid)<=128 and oid.lower() not in seen, 'Invalid or duplicate UUID')
        seen.add(oid.lower()); require(type(enabled) is bool, 'enabled must be boolean')
        require(isinstance(expected,str) and len(expected)==64 and all(c in '0123456789abcdefABCDEF' for c in expected), 'Invalid expected_fingerprint')
        h=handle(oid); before=cable_part_symbol_snapshot(h)
        require(before['fingerprint']==expected.lower(), 'Cable part changed since inspection: '+oid)
        require(before['fields']['Use'].lower() in ('true','false'), 'Unrecognized native Use value')
        plans.append((h,enabled,before))
    receipts=[]
    try:
        for h,enabled,before in plans:
            change=(before['fields']['Use'].lower()=='true')!=enabled
            row={'object_id':before['object_id'],'symbol_name':before['symbol_name'],
                 'before_enabled':before['fields']['Use'].lower()=='true','enabled':enabled,
                 'write_attempted':change,'verified':False}
            receipts.append(row)
            if change: vs.SetRField(h,'CablePart','Use','True' if enabled else 'False')
            after=cable_part_symbol_snapshot(h)
            require(after['fields']['Use'].lower()==str(enabled).lower(), 'Native Use readback mismatch')
            expected_fields=dict(before['fields']); expected_fields['Use']=after['fields']['Use']
            require(after['fields']==expected_fields and all(after[k]==before[k] for k in ('object_id','symbol_name','texts','graphic_types','metadata')), 'Other cable-part data changed')
            row.update(verified=True,fingerprint=after['fingerprint'])
    except Exception as exc:
        return {'status':'error','error':str(exc),'parts':receipts,'retry_safe':False,
                'recovery':'Read all requested UUIDs before retrying. Partial writes may remain; no automatic rollback or cable rebuild.'}
    return {'document':vs.GetFPathName(),'parts':receipts,'changed_count':sum(r['write_attempted'] for r in receipts),
            'cable_runs_rebuilt':False,'scope':'Native CablePart.Use flags in this document only. No external library/cache edit, cable reset or compatibility check. An already-open dialog or cached native configuration may need reopening; consuming these parts in a run requires separate verification.'}


@command
def create_cable_part_symbols(p):
    guard(p); require(set(p)<= {'expected_document','items'}, 'Unsupported creation setting')
    plans=[]; names=set()
    for item in batch(p.get('items'),25):
        require(isinstance(item,dict) and set(item)<= {'template_symbol','symbol_name','fields','text_replacements','metadata'}, 'Unsupported part setting')
        name=item.get('symbol_name'); template=item.get('template_symbol')
        require(all(isinstance(x,str) and 0<len(x)<=128 and x.strip()==x for x in (name,template)), 'Invalid symbol name')
        require(name.casefold() not in names and not vs.GetObject(name), 'Symbol name already exists or is duplicated')
        names.add(name.casefold()); h=named(template,16); before=cable_part_symbol_snapshot(h)
        fields=item.get('fields'); require(isinstance(fields,dict) and set(fields)==set(CABLE_PART_TYPES), 'Supply all 12 native CablePart fields explicitly')
        normalized={}
        for key,kind in CABLE_PART_TYPES.items():
            value=fields[key]
            if kind==2:
                require(type(value) is bool or (isinstance(value,str) and value.lower() in ('true','false')), 'Use must be boolean')
                normalized[key]='True' if value is True or (isinstance(value,str) and value.lower()=='true') else 'False'
            elif kind==3:
                require(type(value) in (str,int,float) and (not isinstance(value,str) or len(value)<=128), key+' must be a finite number')
                number=float(value)
                require(math.isfinite(number) and (number>=0 if key=='Weight' else number>0), key+' must be positive (Weight may be zero)')
                normalized[key]=format(number,'.15g')
            else:
                require(isinstance(value,str) and 0<len(value.strip())<=128, 'Invalid '+key)
                normalized[key]=value
        replacements=item.get('text_replacements')
        require(isinstance(replacements,dict) and set(replacements)==set(before['texts']), 'Explicitly replace every template label (unchanged labels may map to themselves)')
        require(all(isinstance(v,str) and 0<len(v.strip())<=128 for v in replacements.values()), 'Invalid replacement label')
        metadata=item.get('metadata',{})
        require(isinstance(metadata,dict) and set(metadata)<=set(CABLE_PART_META_FIELDS[:8]), 'Unsupported physical connector metadata')
        require(all(isinstance(v,str) and len(v)<=512 for v in metadata.values()), 'Invalid metadata')
        for key in ('StartGender','EndGender'):
            require(key not in metadata or metadata[key] in ('male','female','genderless','unknown'), 'Invalid connector gender')
        metadata={k:metadata.get(k,'') for k in CABLE_PART_META_FIELDS}
        metadata.update(TemplateSymbol=template,TemplateFingerprint=before['fingerprint'])
        plans.append((h,name,before,normalized,replacements,metadata))
    record=vs.GetObject(CABLE_PART_META)
    if record:
        require(vs.GetTypeN(record)==47 and vs.NumFields(record)==len(CABLE_PART_META_FIELDS), 'Metadata record conflict')
        require({vs.GetFldName(record,i):vs.GetFldType(record,i) for i in range(1,vs.NumFields(record)+1)}=={k:4 for k in CABLE_PART_META_FIELDS}, 'Metadata field conflict')
    created=[]
    try:
        if not record:
            for key in CABLE_PART_META_FIELDS: vs.NewField(CABLE_PART_META,key,'',4,0)
        for template,name,before,fields,replacements,metadata in plans:
            h=vs.CreateDuplicateObject(template,vs.GetParent(template))
            require(h, 'Native symbol duplication failed')
            receipt={'object_id':vs.GetObjectUuid(h),'symbol_name':name,'verified':False}; created.append(receipt)
            vs.SetName(h,name)
            for key,value in fields.items(): vs.SetRField(h,'CablePart',key,value)
            vs.SetRecord(h,CABLE_PART_META)
            for key,value in metadata.items(): vs.SetRField(h,CABLE_PART_META,key,value)
            child=vs.FInSymDef(h); count=0
            while child:
                count+=1; require(count<=100,'Unexpected copied graphics')
                if vs.GetTypeN(child)==10: vs.SetText(child,replacements[vs.GetText(child)])
                child=vs.NextObj(child)
            after=cable_part_symbol_snapshot(h)
            require(after['symbol_name']==name and after['graphic_types']==before['graphic_types'], 'Symbol structure readback mismatch')
            require(after['texts']==[replacements[t] for t in before['texts']], 'Visible labels did not update')
            for key,value in fields.items():
                actual=after['fields'][key]
                ok=math.isclose(float(actual),float(value),rel_tol=1e-9,abs_tol=1e-9) if CABLE_PART_TYPES[key]==3 else actual.lower()==value.lower() if key=='Use' else actual==value
                require(ok, 'Native field readback mismatch: '+key)
            require(all(vs.GetRField(h,CABLE_PART_META,k)==v for k,v in metadata.items()), 'Physical metadata readback mismatch')
            source_after=cable_part_symbol_snapshot(template)
            require(source_after['fingerprint']==before['fingerprint'] and source_after['metadata']==before['metadata'], 'Source template changed')
            receipt.update(verified=True,fields=after['fields'],texts=after['texts'],metadata=metadata)
    except Exception as exc:
        return {'status':'error','error':str(exc),'created':created,'retry_safe':False,
                'recovery':'Inspect returned UUIDs and metadata record before retrying; no automatic deletion.'}
    return {'created':created,'native_catalog_registered':False,'library_exported':False,
            'scope':'Current-document native parts only. Library export, native catalog refresh and cable configuration require separate verification. Physical connector metadata does not alter native electrical compatibility.'}


@command
def export_cable_part_library(p):
    guard(p); require(set(p)<= {'expected_document','path','object_ids','empty_library_sha256'}, 'Unsupported export setting')
    path=Path(p['path'])
    require(path.is_absolute() and path.suffix=='.vwx' and path.parent.is_dir(), 'Absolute .vwx path with existing parent required')
    existing=path.exists(); expected_hash=p.get('empty_library_sha256'); backup=None
    if existing:
        require(isinstance(expected_hash,str) and len(expected_hash)==64 and all(c in '0123456789abcdef' for c in expected_hash), 'Existing destination requires empty_library_sha256')
        require(path.is_file() and 0<path.stat().st_size<=268435456, 'Invalid empty-library file')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==expected_hash, 'Empty library changed since inspection')
        require(path_key(str(path))!=path_key(p['expected_document']), 'Destination must differ from active drawing')
    else: require(expected_hash is None, 'Expected empty-library file is missing')
    ids=batch(p.get('object_ids'),25)
    require(all(isinstance(x,str) and 0<len(x)<=128 for x in ids), 'Invalid UUID')
    require(len({x.lower() for x in ids})==len(ids), 'Duplicate UUIDs')
    before=[cable_part_symbol_snapshot(handle(x)) for x in ids]
    fn=getattr(vs,'VMExportSymbolLibrary',None)
    require(callable(fn), 'Native export extension unavailable; install staged bridge after closing Vectorworks normally')
    if existing:
        for kind in (16,47):
            resource_list,count=vs.BuildResourceListN(kind,str(path))
            require(count==0, 'Destination must contain no symbols or record formats')
    try:
        if existing:
            backup=Path(str(path)+'.before-export-'+expected_hash[:16])
            if not backup.exists():
                with backup.open('xb') as dst, path.open('rb') as src: shutil.copyfileobj(src,dst)
            require(hashlib.sha256(backup.read_bytes()).hexdigest()==expected_hash and hashlib.sha256(path.read_bytes()).hexdigest()==expected_hash, 'Library or backup changed before export')
        raw=fn(json.dumps({'expected_document':p['expected_document'],'path':str(path),'object_ids':ids,'allow_empty_existing':existing}))
        require(isinstance(raw,str) and len(raw)<=65536, 'Invalid native export response')
        data=json.loads(raw)
        require(data.get('contract_version')==1 and data.get('status')=='ok', 'Native export failed: '+str(data.get('error','unsupported response')))
        names=[x['symbol_name'] for x in before]
        require(data.get('object_ids')==ids and data.get('symbol_names')==names and Path(data.get('path',''))==path, 'Native export receipt mismatch')
        require(path.is_file() and 0<path.stat().st_size<=268435456, 'Export file missing, empty or oversized')
        resource_list,count=vs.BuildResourceListN(16,str(path))
        require(0<count<=1000,'Unexpected exported resource count')
        exported=[vs.GetNameFromResourceList(resource_list,i) for i in range(1,count+1)]
        require(all(name in exported for name in names),'Exported library is missing requested symbols')
        after=[cable_part_symbol_snapshot(handle(x)) for x in ids]
        require([(x['fingerprint'],x['metadata']) for x in before]==[(x['fingerprint'],x['metadata']) for x in after], 'Source symbol changed during export')
        return {'path':str(path),'object_ids':ids,'symbol_names':names,'bytes':path.stat().st_size,
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'backup_path':str(backup) if backup else None,'resource_names_verified':True,
                'source_records_and_labels_unchanged':True,'native_catalog_registered':False,
                'exported_records_verified':False,'scope':'Native SDK export and resource-name readback. Reopen/import separately to verify saved record values; native Manage Cable Parts refresh and run configuration remain separate.'}
    except Exception as exc:
        return {'status':'error','error':str(exc),'path':str(path),'object_ids':ids,
                'file_exists':path.exists(),'backup_path':str(backup) if backup else None,'retry_safe':False,
                'recovery':'Inspect the destination and source resources. A partial export may exist; no deletion or overwrite was attempted.'}


CABLE_FIELDS = {
    'CablePathObject': ('ID', 'Location', 'Length', 'CableCount', 'Cable Area',
        '__Circuits Count', '__Spotlight Cables Count', 'Set2DAttributes', 'Class2DAttributes'),
    'CableObject': ('CableRun_ID', 'Loom_ID', 'Universe', 'Rack_ID', 'Box_ID', 'Part_ID',
        'Location', 'CableType', 'StartConector', 'EndConnector', 'StartObjectName', 'EndObjectName',
        'StartObjectUUID', 'EndObjectUUID', 'StartObjectPort', 'EndObjectPort',
        'Length', 'LengthPartsTotal', 'Spare', 'Swag', 'UsedParts', 'UsedPartsOrdered',
        'AdapterStart', 'AdapterEnd', 'Volt', 'Ampere', 'VoltageDrop', 'DistWeight', 'TotalWeight',
        'StartLabelsClass', 'MiddleLabelsClass', 'EndLabelsClass', 'PathClass', 'TerminatorClass',
        'TapeColorCode', 'AdapterStartInventory', 'AdapterEndInventory',
        'ConnectorStartInventory', 'ConnectorEndInventory')}


def cable_geometry_snapshot(h, path, detail, point_limit):
    """Bounded, read-only path data. Never approximate curved lengths with chords."""
    try:
        require(path and vs.GetTypeN(path) == 111, 'NURBS path required')
        count = vs.NurbsCurveGetNumPieces(path)
        require(type(count) is int and 1 <= count <= min(1000, point_limit // 2), 'Path piece count exceeds limit or is invalid')
        specs = []; total = 0
        for s in range(count):
            degree, n, knots = vs.NurbsDegree(path,s), vs.NurbsGetNumPts(path,s), vs.NurbsNumKnots(path,s)
            require(type(n) is int and 2 <= n <= point_limit, 'Invalid control point count')
            require(type(degree) is int and 1 <= degree < n, 'Invalid NURBS degree')
            require(type(knots) is int and 2 <= knots <= 2 * n + 2, 'Invalid knot count')
            total += n
            require(total <= point_limit, 'Path control points exceed geometry_point_limit')
            specs.append((degree,n,knots))
        def finite(value):
            require(type(value) in (int,float) and math.isfinite(value), 'Nonfinite or invalid native geometry value')
            return float(value)
        def xyz(value):
            require(isinstance(value,(list,tuple)) and len(value)==3, 'Native point must have three coordinates')
            return [finite(v) for v in value]
        pose = matrix(h)
        require(len(pose)==5, 'Unexpected native matrix result')
        transform = {'origin_parent': xyz(pose[1]), 'rotation_degrees': [finite(a) for a in pose[2:]]}
        pieces = []
        for s,(degree,n,k) in enumerate(specs):
            pieces.append({'degree': degree,
                'control_points_local': [xyz(vs.NurbsGetPt3D(path,s,i)) for i in range(n)],
                'weights': [finite(vs.NurbsGetWeight(path,s,i)) for i in range(n)],
                'knots': [finite(vs.NurbsKnot(path,s,i)) for i in range(k)]})
        linear = all(r['degree']==1 and len(r['control_points_local'])==2 and
                     all(w>0 for w in r['weights']) and len(r['knots'])==4 and
                     r['knots'][0]==r['knots'][1] < r['knots'][2]==r['knots'][3] for r in pieces)
        continuous = all(math.dist(a['control_points_local'][-1],b['control_points_local'][0]) <= 1e-6
                         for a,b in zip(pieces,pieces[1:]))
        corner = linear and continuous
        length = sum(math.dist(r['control_points_local'][0],r['control_points_local'][-1]) for r in pieces) if corner else None
        require(length is None or math.isfinite(length), 'Nonfinite path length')
        data = {'pieces': pieces, 'object_transform': transform}
        digest = hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()
        result = {'status': 'ok', 'piece_count': count, 'control_point_count': total,
            'corner_polyline': corner, 'linear_length_local': length,
            'endpoints_local': [pieces[0]['control_points_local'][0],pieces[-1]['control_points_local'][-1]] if corner else None,
            'object_transform': transform, 'sha256': digest, 'world_coordinates_verified': False,
            'scope': 'Path-local control points/weights/knots and decomposed object-to-parent origin/angles. SHA-256 covers only these returned native data, not full affine scale/mirror, parent/layer transforms, connectivity or evaluated curved geometry. Local length/endpoints apply only to continuous clamped degree-one two-point pieces with positive weights.'}
        if detail == 'points': result['pieces'] = pieces
        return result
    except Exception as exc:
        return {'status': 'unavailable', 'error': str(exc)[:512], 'world_coordinates_verified': False}


def cable_connector_configuration(h, raw):
    """Compare stored connector choices with their style, never infer wiring."""
    try:
        style = vs.GetPluginStyle(h)
        require(isinstance(style, str) and len(style) <= 512, 'Invalid or oversized cable style name')
        definition = None; style_handle = None
        if style:
            style_handle = vs.GetObject(style)
            require(style_handle and vs.GetTypeN(style_handle) == 16, 'Cable style resource is unavailable')
            child = vs.FInSymDef(style_handle); found = []; visited = 0
            while child:
                visited += 1; require(visited <= 256, 'Cable style child limit exceeded')
                if plugin(child) == 'CableObject': found.append(child)
                child = vs.NextObj(child)
            require(len(found) == 1, 'Expected exactly one CableObject in the style definition')
            definition = found[0]
            rec = vs.GetParametricRecord(definition); count = vs.NumFields(rec)
            require(type(count) is int and 0 <= count <= 512, 'Invalid style field count')
            available = {vs.GetFldName(rec, i) for i in range(1, count + 1)}
        fields = {}; mismatches = []
        for label, field in (('type','CableType'), ('start','StartConector'), ('end','EndConnector')):
            value = raw.get(field)
            require(value is None or isinstance(value, str), 'Invalid cable connector field')
            mode = vs.GetParamStyleType(style_handle, field) if style_handle else 0
            control = {0:'by_instance', 1:'by_style', 2:'always_by_instance'}.get(mode, 'unknown')
            style_value = vs.GetRField(definition, 'CableObject', field) if definition and field in available else None
            require(style_value is None or isinstance(style_value, str), 'Invalid style connector field')
            truncated = any(isinstance(v,str) and len(v)>512 for v in (value,style_value))
            matches = (value == style_value) if mode == 1 and value is not None and style_value is not None and not truncated else None
            if matches is False: mismatches.append(field)
            fields[label] = {'field':field, 'value':value[:512] if value is not None else None,
                'control':control, 'style_value':style_value[:512] if style_value is not None else None,
                'matches_style':matches, 'truncated':truncated}
            if label != 'type':
                end = label.title()
                fields[label]['adapter'] = raw.get('Adapter'+end)
                fields[label]['adapter_inventory'] = raw.get('Adapter'+end+'Inventory')
                fields[label]['connector_inventory'] = raw.get('Connector'+end+'Inventory')
                for key in ('adapter','adapter_inventory','connector_inventory'):
                    text = fields[label][key]
                    require(text is None or isinstance(text,str), 'Invalid adapter field')
                    if text is not None:
                        fields[label]['truncated'] |= len(text)>512
                        fields[label][key] = text[:512]
        return {'status':'ok', 'style':style, 'parameters':fields, 'style_mismatches':mismatches,
            'physical_gender_verified':False, 'pin_wiring_verified':False, 'native_connections_verified':False,
            'scope':'Stored type, start/end connector families and adapter references, with per-parameter style ownership and exact style comparison. Matching families do not establish male/female hardware, compatible parts, adapter validity or connected device sockets.'}
    except Exception as exc:
        return {'status':'unavailable', 'error':str(exc)[:512], 'native_connections_verified':False}


@command
def get_cable_inspection(p):
    """Read stored modern cable/path data; endpoint references are not graph proof."""
    ids = batch(p.get('object_ids'), 50)
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), 'Unique UUID strings required')
    include, limit = p.get('include_fields', False), p.get('issue_limit', 50)
    require(type(include) is bool, 'include_fields must be boolean')
    connector_config = p.get('include_connector_configuration', False)
    require(type(connector_config) is bool, 'include_connector_configuration must be boolean')
    require(not connector_config or len(ids)<=10, 'Connector configuration inspection supports at most 10 objects')
    require(type(limit) is int and 1 <= limit <= 100, 'issue_limit must be 1..100')
    geometry_detail, point_limit = p.get('geometry_detail','none'), p.get('geometry_point_limit',500)
    require(geometry_detail in ('none','summary','points'), 'geometry_detail must be none, summary or points')
    require(type(point_limit) is int and 2 <= point_limit <= 2000, 'geometry_point_limit must be 2..2000')
    require(geometry_detail=='none' or len(ids)<=10, 'Geometry inspection supports at most 10 objects; narrow the scope')
    handles = [handle(i, 86) for i in ids]
    require(all(plugin(h) in CABLE_FIELDS for h in handles), 'Only modern CableObject and CablePathObject are supported')
    objects, issues, counts, looms = [], [], Counter(), Counter()
    for h in handles:
        row = identity(h); oid, kind = row['object_id'], row['plugin']
        rec = vs.GetParametricRecord(h); count = vs.NumFields(rec)
        require(0 <= count <= 512, 'Unexpected cable schema size')
        available = {vs.GetFldName(rec, i) for i in range(1, count + 1)}
        raw = {f: vs.GetRField(h, kind, f) if f in available else None for f in CABLE_FIELDS[kind]}
        if kind == 'CableObject':
            # Read-only diagnostics. Never use these private fields as connection setters.
            for f in ('__StartConnectorUUID', '__EndConnectorUUID'):
                if f in available: raw[f] = vs.GetRField(h, kind, f)
        def issue(code, field=None):
            counts[code] += 1
            if len(issues) < limit: issues.append({'object_id': oid, 'code': code, 'field': field, 'severity': 'review'})
        def dimension(field):
            value = raw.get(field)
            if value is None or not value.strip(): return None
            ok, numeric = vs.ValidNumStr(value)
            if not ok or not math.isfinite(numeric):
                issue('invalid_dimension', field); return None
            return numeric
        row['missing_fields'] = [f for f, v in raw.items() if v is None]
        row['truncated_fields'] = [f for f, v in raw.items() if isinstance(v, str) and len(v) > 512]
        if row['missing_fields']: issue('fields_missing')
        if row['truncated_fields']: issue('field_text_truncated')
        row['drawn_length'] = dimension('Length')
        if row['drawn_length'] is not None and row['drawn_length'] <= 0: issue('nonpositive_drawn_length', 'Length')
        path = vs.GetCustomObjectPath(h)
        row['path_type'] = vs.GetTypeN(path) if path else None
        if row['path_type'] != 111: issue('unsupported_path_geometry')
        if geometry_detail != 'none':
            row['geometry'] = cable_geometry_snapshot(h,path,geometry_detail,point_limit)
            if row['geometry']['status'] != 'ok': issue('geometry_unavailable')
        row['style'] = vs.GetPluginStyle(h)
        row['id'] = raw['ID' if kind == 'CablePathObject' else 'CableRun_ID']
        if kind == 'CableObject':
            if connector_config:
                config = cable_connector_configuration(h, raw)
                row['connector_configuration'] = config
                if config['status'] != 'ok': issue('connector_configuration_unavailable')
                else:
                    for field in config['style_mismatches']: issue('connector_style_mismatch', field)
            row['loom_id'] = raw['Loom_ID']; looms[raw['Loom_ID']] += 1
            row['parts_length'] = dimension('LengthPartsTotal')
            row['has_reported_parts'] = bool(raw['UsedParts'] or raw['UsedPartsOrdered'])
            if not row['has_reported_parts']: issue('no_reported_parts')
            if not all(raw.get(f) for f in ('CableType', 'StartConector', 'EndConnector')):
                issue('cable_style_data_incomplete')
            row['endpoints'] = {}
            for end in ('Start', 'End'):
                uuid, port = raw[end+'ObjectUUID'], raw[end+'ObjectPort']
                resolved = bool(vs.GetObjectByUuid(uuid)) if uuid else (False if uuid == '' else None)
                row['endpoints'][end.lower()] = {'stored_uuid': uuid[:512] if isinstance(uuid, str) else uuid,
                    'stored_port': port[:512] if isinstance(port, str) else port, 'resolves': resolved}
                component = raw.get('__'+end+'ConnectorUUID')
                state = ('field_unavailable' if component is None else 'blank' if component == '' else
                         'zero_uuid' if component == '00000000-0000-0000-0000-000000000000' else 'present_unverified')
                row['endpoints'][end.lower()].update(
                    stored_component_uuid=component[:512] if isinstance(component, str) else component,
                    component_reference_state=state)
                if uuid == '': issue('endpoint_unassigned', end+'ObjectUUID')
                elif uuid and not resolved: issue('endpoint_uuid_missing_object', end+'ObjectUUID')
                # Native power patch produced a cable with -1 ports and separate component UUIDs.
                # This value alone cannot establish an unassigned/disconnected endpoint.
                if port in ('', '-1'): issue('endpoint_port_unspecified', end+'ObjectPort')
        else:
            row['reported_cable_count'] = raw['CableCount']
        # Bound all exposed record strings, including summary identity fields.
        for key in ('id', 'loom_id'):
            if isinstance(row.get(key), str): row[key] = row[key][:512]
        if include: row['fields'] = {f: v[:512] if isinstance(v, str) else v for f, v in raw.items()}
        objects.append(row)
    return {'document': vs.GetFPathName(), 'units': vs.GetUnits(), 'object_count': len(objects),
            'objects': objects, 'issue_count': sum(counts.values()), 'issue_counts': dict(counts),
            'issues': issues, 'issues_truncated': sum(counts.values()) > len(issues),
            'loom_groups': [{'loom_id': k[:512] if isinstance(k, str) else k, 'count': n,
                             'truncated': isinstance(k, str) and len(k) > 512} for k, n in looms.items()],
            'native_connections_verified': False, 'sections_and_breaks_verified': False,
            'scope': 'Stored fields and resolvable endpoint object UUIDs, with optional bounded local NURBS data. Separate component reference strings are read-only, unverified diagnostics; zero UUIDs are preserved, not automatically invalid. Unspecified numeric ports alone do not prove disconnection. Port/pin links, movement/path following, section looms, parts completeness and electrical calculations are not verified.'}


CABLE_SECTION_METADATA = {'loom_id':('Loom ID','Loom_ID'), 'box_id':('Box ID','Box_ID'),
    'tape':('Tape','TapeColorCode')}
CABLE_SECTION_EDIT_FIELDS = {'name':'Name','start_slack_mm':'Start Slack',
    'end_slack_mm':'End Slack','swag_mm':'Swag',
    **{key:value[0] for key,value in CABLE_SECTION_METADATA.items()}}
CABLE_SECTION_LENGTH_FIELDS = {'drawn_length_mm':'Length','start_slack_mm':'Start Slack',
    'end_slack_mm':'End Slack','swag_mm':'Swag','vertical_drop_mm':'Total Vertical Drop'}


def cable_sections_snapshot(h):
    require(plugin(h)=='CableObject', 'Expected native CableObject')
    for name in ('GetCableSectionsCnt','GetCableBreaksCnt','GetCablePartsCnt','GetCableSectionData','GetCableBreakData'):
        require(callable(getattr(vs,name,None)), 'Required cable API unavailable: '+name)
    n=vs.GetCableSectionsCnt(h); b=vs.GetCableBreaksCnt(h); total=vs.GetCablePartsCnt(h,0)
    require(type(n) is int and 1<=n<=100 and type(b) is int and 0<=b<=100, 'Unsupported or uninitialized section/break count')
    require(type(total) is int and 0<=total<=500, 'Cable exceeds 500 parts')
    sections=[]; count=0
    def text_value(value,limit=512):
        require(isinstance(value,str) and len(value)<=limit, 'Invalid or oversized native section value')
        return value
    for i in range(1,n+1):
        parts=vs.GetCablePartsCnt(h,i)
        require(type(parts) is int and 0<=parts<=500, 'Invalid section part count')
        count+=parts; require(count<=500,'Sections exceed 500 parts')
        row={'index':i,'name':text_value(vs.GetCableSectionData(h,'Name',i,0)),
             'part_count':parts,'parts_ordered_raw':text_value(vs.GetCableSectionData(h,'Parts Ordered',i,0),8192),
             'parts':[text_value(vs.GetCableSectionData(h,'Parts Ordered',i,j)) for j in range(1,parts+1)]}
        for key,selector in CABLE_SECTION_LENGTH_FIELDS.items():
            value=text_value(vs.GetCableSectionData(h,selector,i,0)); number=float(value)
            require(math.isfinite(number) and number>=0,'Invalid section dimension: '+selector)
            row[key]=number
        for key,(selector,_) in CABLE_SECTION_METADATA.items():
            row[key]=text_value(vs.GetCableSectionData(h,selector,i,0))
        sections.append(row)
    breaks=[{'index':i,'name':text_value(vs.GetCableBreakData(h,'Name',i))} for i in range(1,b+1)]
    path=vs.GetCustomObjectPath(h); geometry=cable_geometry_snapshot(h,path,'summary',2000)
    require(geometry.get('status')=='ok','Cannot fingerprint cable path geometry')
    protected={'geometry_sha256':geometry['sha256'],'class':vs.GetClass(h),'layer_id':vs.GetObjectUuid(vs.GetLayer(h)),
               'style':vs.GetPluginStyle(h),'fields':{k:text_value(vs.GetRField(h,'CableObject',k)) for k in
                ('CableRun_ID','Loom_ID','Rack_ID','Box_ID','TapeColorCode','StartObjectUUID','EndObjectUUID',
                 'StartObjectPort','EndObjectPort','__StartConnectorUUID','__EndConnectorUUID')}}
    data={'object_id':vs.GetObjectUuid(h),'section_count':n,'break_count':b,'part_count':total,
          'sections':sections,'breaks':breaks,'protected':protected}
    data['fingerprint']=hashlib.sha256(json.dumps(data,sort_keys=True).encode('utf8')).hexdigest()
    return data


@command
def get_cable_length_audit(p):
    """Compare independent native length representations without repairing them."""
    require(set(p) <= {'object_ids','tolerance_mm'}, 'Unsupported length audit parameter')
    ids=batch(p.get('object_ids'),10); tolerance=p.get('tolerance_mm',1.0)
    require(all(isinstance(i,str) and 0<len(i)<=128 for i in ids) and len({i.lower() for i in ids})==len(ids), 'Unique UUIDs required')
    require(type(tolerance) in (int,float) and math.isfinite(tolerance) and 0<=tolerance<=100, 'tolerance_mm must be finite, 0..100')
    ok,one_mm=vs.ValidNumStr('1mm')
    require(ok and type(one_mm) in (int,float) and math.isfinite(one_mm) and one_mm>0, 'Cannot resolve document length units')
    output=[]
    for oid in ids:
        h=handle(oid,86); snapshot=cable_sections_snapshot(h)
        geometry=cable_geometry_snapshot(h,vs.GetCustomObjectPath(h),'summary',2000)
        raw=vs.GetRField(h,'CableObject','Length'); parsed=None
        if isinstance(raw,str) and 0<len(raw)<=512:
            valid,value=vs.ValidNumStr(raw)
            if valid and type(value) in (int,float) and math.isfinite(value) and value>=0:
                parsed=value/one_mm
                if not math.isfinite(parsed): parsed=None
        sections=snapshot['sections']; section_sum=sum(s['drawn_length_mm'] for s in sections)
        local=geometry.get('linear_length_local') if geometry.get('status')=='ok' else None
        local=local/one_mm if type(local) in (int,float) and math.isfinite(local) else None
        if local is not None and not math.isfinite(local): local=None
        # Multi-section and vertical-drop semantics have not yet been live-validated.
        comparable=snapshot['section_count']==1 and snapshot['break_count']==0 and sections[0]['vertical_drop_mm']==0
        checks={'pio_length_positive':parsed>0 if parsed is not None else None,
                'section_part_counts_match':snapshot['part_count']==sum(s['part_count'] for s in sections),
                'pio_matches_section':abs(parsed-section_sum)<=tolerance if comparable and parsed is not None else None,
                'local_path_matches_section':abs(local-section_sum)<=tolerance if comparable and local is not None else None}
        issues=[key for key,value in checks.items() if value is False]
        if parsed is None: issues.append('pio_length_unreadable')
        output.append({'object_id':oid,'name':vs.GetName(h),'pio_length_mm':parsed,
            'section_drawn_sum_mm':section_sum,'linear_path_local_mm':local,
            'section_count':snapshot['section_count'],'break_count':snapshot['break_count'],
            'part_count':snapshot['part_count'],'comparison_supported':comparable,
            'checks':checks,'issues':issues,
            'result':'mismatch' if issues else 'consistent_in_scope' if all(v is True for v in checks.values()) else 'incomplete'})
    return {'document':vs.GetFPathName(),'tolerance_mm':tolerance,'cables':output,
            'mismatch_count':sum(r['result']=='mismatch' for r in output),
            'incomplete_count':sum(r['result']=='incomplete' for r in output),
            'world_geometry_verified':False,'electrical_design_verified':False,
            'scope':'Read-only agreement of PIO length, native section data and linear path-local geometry. Length comparison supports one section, no breaks, and zero vertical drop only. Curves have no chord approximation. Agreement does not prove complete initialization, transformed world length, connector compatibility, stock sufficiency or electrical safety.'}


@command
def get_cable_sections(p):
    require(set(p)<= {'object_ids'}, 'Unsupported section inspection parameter')
    ids=batch(p.get('object_ids'),10)
    require(all(isinstance(i,str) and 0<len(i)<=128 for i in ids) and len({i.lower() for i in ids})==len(ids),'Unique UUIDs required')
    return {'document':vs.GetFPathName(),'cables':[cable_sections_snapshot(handle(i,86)) for i in ids],
            'scope':'Native 1-based sections/breaks and ordered part labels. Numeric section getters return millimetres in verified VW2026. Fingerprint covers returned data and scoped path/endpoint/organization fields, not the complete electrical graph or section looms. No mutation; quantities and engineering suitability require separate checks.'}


@command
def set_cable_sections(p):
    guard(p); require(set(p)=={'expected_document','object_id','expected_fingerprint','sections'},'Unsupported section edit parameter')
    oid=p['object_id']; expected=p['expected_fingerprint']
    require(isinstance(oid,str) and 0<len(oid)<=128,'Invalid cable UUID')
    require(isinstance(expected,str) and len(expected)==64 and all(c in '0123456789abcdefABCDEF' for c in expected),'Invalid expected_fingerprint')
    h=handle(oid,86); before=cable_sections_snapshot(h)
    require(before['fingerprint']==expected.lower(),'Cable changed since inspection')
    require(callable(getattr(vs,'SetCableSectionData',None)),'Native section setter unavailable')
    edits=[]; indexes=set()
    for row in batch(p['sections'],25):
        require(isinstance(row,dict) and set(row)<= {'index',*CABLE_SECTION_EDIT_FIELDS} and len(row)>1,'Unsupported section field; parts, lengths and drops are read-only')
        index=row.get('index')
        require(type(index) is int and 1<=index<=before['section_count'] and index not in indexes,'Invalid or repeated section index')
        indexes.add(index)
        for key,value in row.items():
            if key=='index': continue
            if key=='name': require(isinstance(value,str) and 0<len(value.strip())<=128,'Invalid section name')
            elif key in CABLE_SECTION_METADATA:
                require(before['section_count']==1 and before['break_count']==0, 'Metadata edits currently require one section and zero breaks; multi-section run synchronization is unverified')
                require(isinstance(value,str) and len(value)<=128 and (not value or bool(value.strip())), 'Metadata must be text up to 128 characters; empty text clears it')
            else: require(type(value) in (int,float) and math.isfinite(value) and 0<=value<=10000000,'Lengths must be finite nonnegative millimetres, at most 10000000')
            run_differs=key in CABLE_SECTION_METADATA and before['protected']['fields'][CABLE_SECTION_METADATA[key][1]]!=value
            if before['sections'][index-1][key]!=value or run_differs: edits.append({'index':index,'field':key,'value':value})
    target=[{k:row[k] for k in ('index','name',*CABLE_SECTION_LENGTH_FIELDS,*CABLE_SECTION_METADATA)} for row in before['sections']]
    protected=json.loads(json.dumps(before['protected']))
    attempted=[]
    try:
        for edit in edits:
            attempted.append(edit)
            value=edit['value'] if edit['field']=='name' or edit['field'] in CABLE_SECTION_METADATA else format(edit['value'],'.15g')+'mm'
            vs.SetCableSectionData(h,CABLE_SECTION_EDIT_FIELDS[edit['field']],edit['index'],value)
            target[edit['index']-1][edit['field']]=edit['value']
            if edit['field'] in CABLE_SECTION_METADATA:
                protected['fields'][CABLE_SECTION_METADATA[edit['field']][1]]=edit['value']
    except Exception as exc:
        return {'status':'error','error':str(exc),'object_id':oid,'attempted':attempted,'retry_safe':False,
                'recovery':'Inspect this cable after the native event; partial edits/rebuilt stock may remain. Do not repeat the mutation blindly.'}
    receipt={'object_id':before['object_id'],'protected':protected,'section_count':before['section_count'],
             'breaks':before['breaks'],'target_sections':target}
    return {'object_id':oid,'changed_field_count':len(attempted),'attempted':attempted,'receipt':receipt,
            'requires_verification':True,'next_command':'get_cable_section_verification',
            'scope':'Native section name/slack/swag and single-section loom/box/tape setters. Metadata edits verify native run-field synchronization. Explicit mm suffix prevents drawing-unit interpretation. No connector edits or forced parts selection; inspect post-event verification.'}


@command
def get_cable_section_verification(p):
    guard(p); receipt=p.get('receipt')
    require(isinstance(receipt,dict),'Section edit receipt required')
    after=cable_sections_snapshot(handle(receipt['object_id'],86))
    require(after['protected']==receipt['protected'],'Cable geometry, organization or endpoint fields changed')
    require(after['section_count']==receipt['section_count'] and after['breaks']==receipt['breaks'],'Cable topology changed')
    actual=[{k:row[k] for k in ('index','name',*CABLE_SECTION_LENGTH_FIELDS,*CABLE_SECTION_METADATA)} for row in after['sections']]
    target=receipt['target_sections']
    require(isinstance(target,list) and len(actual)==len(target) and all(isinstance(want,dict) and set(got)==set(want) and all(same(got[k],want[k]) for k in got) for got,want in zip(actual,target)),'Native section edit readback mismatch')
    return {'verified':True,'cable':after,'parts_sufficiency_verified':False,
            'scope':'Post-event section values and scoped geometry/endpoint/organization invariants match. Ordered parts are native readback, not proof of a complete safe electrical design.'}


@command
def create_cable_paths(p):
    """Create independent corner-vertex paths; host regeneration precedes readback."""
    guard(p); rows = batch(p.get('items'), 25); plans = []
    for row in rows:
        require(isinstance(row, dict), 'Each path must be an object')
        require(set(row) <= {'name','layer','class','route_id','vertices','location'}, 'Unknown path setting; connections and other options are not supported')
        for key in ('name', 'layer', 'class', 'route_id'):
            require(isinstance(row.get(key), str) and bool(row[key].strip()) and len(row[key]) <= 128, key+' requires 1..128 characters')
        require(isinstance(row.get('location', ''), str) and len(row.get('location', '')) <= 512, 'location must be text up to 512 characters')
        vertices = [point(v) for v in batch(row.get('vertices'), 200)]
        require(len(vertices) >= 2, 'At least two route vertices required')
        lengths = [math.dist(a, b) for a, b in zip(vertices, vertices[1:])]
        require(all(math.isfinite(n) and n > 1e-6 for n in lengths), 'Consecutive route vertices must be distinct and finite')
        require(math.isfinite(sum(lengths)), 'Route length must be finite')
        plans.append({**row, 'vertices': vertices, 'location': row.get('location', ''), 'expected_length': sum(lengths)})
    require(len({r['name'] for r in plans}) == len(plans), 'Duplicate object names')
    require(len({r['route_id'] for r in plans}) == len(plans), 'Duplicate route IDs')
    existing_ids = set()
    vs.ForEachObject(lambda h: existing_ids.add(vs.GetRField(h, 'CablePathObject', 'ID')), "(PON='CablePathObject')")
    for row in plans:
        require(not vs.GetObject(row['name']), 'Object name already exists: '+row['name'])
        require(row['route_id'] not in existing_ids, 'Route ID already exists: '+row['route_id'])
        layer = named(row['layer'], 31)
        require(vs.GetObjectVariableInt(layer, 154) == 1, 'Design layer required')
        named(row['class'], 94)
    definition = vs.DefineCustomObj('CablePathObject', 0)
    require(definition, 'CablePathObject unavailable')
    available = {vs.GetFldName(definition, i) for i in range(1, vs.NumFields(definition)+1)}
    require({'ID', 'Location', 'Length', 'Set2DAttributes', 'Class2DAttributes'} <= available, 'Unsupported installed cable path schema')
    prior = context(); out = []; current = None
    try:
        for row in plans:
            vs.Layer(row['layer']); vs.NameClass(row['class']); defaults_by_class()
            vs.BeginPoly3D()
            try:
                for xyz in row['vertices']: vs.Add3DPt(xyz)
            finally: vs.EndPoly3D()
            current = vs.LNewObj(); require(current, 'Path polygon creation failed')
            vs.SetPolyClosed(current, False)
            nurbs = vs.ConvertToNURBS(current, False); require(nurbs, 'NURBS conversion failed')
            current = nurbs; require(vs.GetTypeN(nurbs) == 111, 'Expected one NURBS curve')
            h = vs.CreateCustomObjectPath('CablePathObject', nurbs, None); require(h, 'Native path creation failed')
            current = h
            # Capture receipt before subsequent setters, so a partial failure has an address.
            receipt = {k: row[k] for k in ('name','layer','class','route_id','location','vertices','expected_length')}
            receipt['object_id'] = vs.GetObjectUuid(h); out.append(receipt)
            vs.SetName(h, row['name']); vs.SetClass(h, row['class']); attributes_by_class(h)
            put(h, 'CablePathObject', {'ID': row['route_id'], 'Location': row['location'],
                'Set2DAttributes': 'Class', 'Class2DAttributes': row['class']})
    except Exception as exc:
        return {'status': 'error', 'error': str(exc), 'created': out, 'retry_safe': False,
                'partial_object_id': vs.GetObjectUuid(current) if current else None,
                'recovery': 'Inspect created and partial object UUIDs before further work; do not repeat creation.'}
    finally: restore(prior)
    return {'created': out, 'count': len(out), 'requires_verification': True,
            'next_command': 'get_cable_path_verification', 'native_connections_verified': False,
            'scope': 'Corner-vertex route geometry only; joins, cable following and equipment connections are not established.'}


@command
def get_cable_path_verification(p):
    """Read-only second-event check of creation receipt, path geometry and native length."""
    guard(p); rows = batch(p.get('created'), 25); checked = []
    for row in rows:
        h = handle(row['object_id'], 86)
        require(plugin(h) == 'CablePathObject', 'Expected native cable path')
        actual = identity(h)
        require(all(actual[k] == row[k] for k in ('name','class','layer')), 'Path identity changed')
        vertices = [point(v) for v in batch(row['vertices'], 200)]
        require(len(vertices) >= 2, 'Incomplete route receipt')
        require(same(matrix(h), (True, vertices[0], 0, 0, 0)), 'Path transform differs from requested coordinates')
        path = vs.GetCustomObjectPath(h)
        require(path and vs.GetTypeN(path) == 111, 'Native route must have a NURBS path')
        require(vs.NurbsCurveGetNumPieces(path) == len(vertices)-1, 'Route segment count differs')
        for s in range(len(vertices)-1):
            require(vs.NurbsDegree(path, s) == 1 and vs.NurbsGetNumPts(path, s) == 2, 'Route is not a corner-vertex path')
            for i in (0, 1):
                expected = tuple(a-b for a,b in zip(vertices[s+i], vertices[0]))
                require(same(vs.NurbsGetPt3D(path,s,i), expected), 'Native route vertex differs')
        for field, value in [('ID',row['route_id']),('Location',row['location']),
                             ('Set2DAttributes','Class'),('Class2DAttributes',row['class'])]:
            require(vs.GetRField(h,'CablePathObject',field) == value, 'Path field differs: '+field)
        raw = vs.GetRField(h,'CablePathObject','Length'); ok, length = vs.ValidNumStr(raw)
        require(ok and math.isfinite(length) and length > 0 and same(length,row['expected_length']), 'Native route length mismatch')
        checked.append({'object_id': row['object_id'], 'length': length, 'length_raw': raw, 'vertices_verified': len(vertices)})
    return {'verified': True, 'paths': checked, 'native_connections_verified': False, 'visual_documentation_verified': False}


@command
def get_viewport_documentation(p):
    """Read viewport metadata and real annotation labels; flag review candidates."""
    ids = batch(p.get('viewport_ids'), 10)
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), 'Unique viewport UUID strings required')
    limit, include = p.get('limit', 50), p.get('include_labels', False)
    require(type(limit) is int and 1 <= limit <= 100, 'limit must be 1..100')
    require(type(include) is bool, 'include_labels must be boolean')
    viewports = [(oid, handle(oid, 122)) for oid in ids]
    coordination = vs.GetPref(544)
    issues, output, visited = [], [], 0
    # Exact conventional labels only. Arbitrary house titles are not classified.
    titles = {'top plan': 7, 'top/plan': 7, 'top view': 7,
              'front elevation': 3, 'front view': 3, 'back view': 4,
              'left view': 5, 'right view': 6, 'bottom view': 8}
    views = {0: 'custom', 3: 'front', 4: 'back', 5: 'left', 6: 'right',
             7: 'top', 8: 'bottom', 9: 'right isometric', 10: 'left isometric',
             11: 'right rear isometric', 12: 'left rear isometric',
             13: 'bottom right isometric', 14: 'bottom left isometric',
             15: 'bottom right rear isometric', 16: 'bottom left rear isometric'}

    def normalized(text):
        return ' '.join(text.casefold().split()) if isinstance(text, str) else ''

    for oid, vp in viewports:
        title = vs.GetObjectVariableString(vp, 1032)
        number = vs.GetObjectVariableString(vp, 1033)
        view = vs.GetObjectVariableInt(vp, 1007)
        section = bool(vs.GetObjectVariableBoolean(vp, 1054))
        sheet = vs.GetLName(vs.GetLayer(vp))
        labels = []

        def issue(code, label_id=None, field=None):
            issues.append({'code': code, 'viewport_id': oid, 'label_id': label_id,
                           'field': field, 'severity': 'review'})

        def review_title(value, label_id=None):
            expected = titles.get(normalized(value))
            if not section and view in views and view != 0 and expected is not None and expected != view:
                issue('title_view_review', label_id, 'Title')

        review_title(title)
        group = vs.GetVPGroup(vp, 2)
        stack = [vs.FInGroup(group)] if group else []
        while stack:
            h = stack.pop()
            while h:
                visited += 1
                require(visited <= 10000, 'Annotation traversal exceeds 10000 objects; narrow viewport scope')
                kind = vs.GetTypeN(h)
                if kind == 11:
                    stack.append(vs.FInGroup(h))
                elif kind == 86:
                    rec = vs.GetParametricRecord(h)
                    plugin = vs.GetName(rec) if rec else ''
                    if plugin in ('Drawing Label', 'Drawing Label2'):
                        count = vs.NumFields(rec)
                        require(0 <= count <= 256, 'Unexpected drawing-label field count')
                        available = {vs.GetFldName(rec, i) for i in range(1, count + 1)}
                        fields = ('Title', 'Drawing', 'Sheet', 'Custom Scale',
                                  'ScaleDisplay' if plugin == 'Drawing Label2' else 'fScale Config')
                        raw = {f: vs.GetRField(h, plugin, f) if f in available else None for f in fields}
                        lid = vs.GetObjectUuid(h)
                        missing = [f for f in fields if f not in available]
                        if missing: issue('label_fields_missing', lid)
                        for field, reference in [('Title', title), ('Drawing', number), ('Sheet', sheet)]:
                            if raw[field] is not None and normalized(raw[field]) != normalized(reference):
                                issue('label_' + field.lower() + '_differs', lid, field)
                        review_title(raw['Title'], lid)
                        if plugin == 'Drawing Label2' and normalized(raw['ScaleDisplay']) == 'custom':
                            issue('custom_scale_review', lid, 'Custom Scale')
                        labels.append({'id': lid, 'plugin': plugin, 'class': vs.GetClass(h),
                                       'style': vs.GetPluginStyle(h),
                                       'fields': {k: v[:512] if isinstance(v, str) else v for k, v in raw.items()},
                                       'missing_fields': missing,
                                       'truncated_fields': [k for k, v in raw.items() if isinstance(v, str) and len(v) > 512]})
                # Do not enter PIO caches or symbol definitions and count their geometry as labels.
                h = vs.NextObj(h)
        labels.sort(key=lambda r: r['id'])
        row = {'viewport_id': oid, 'sheet': sheet, 'drawing_title': title[:512],
               'drawing_number': number[:512], 'title_truncated': len(title) > 512,
               'number_truncated': len(number) > 512,
               'view_type': view, 'view_name': views.get(view, 'unknown'), 'is_section': section,
               'scale': vs.GetObjectVariableReal(vp, 1003), 'label_count': len(labels)}
        if include:
            row.update(labels=labels[:limit], labels_truncated=len(labels) > limit)
        output.append(row)
    return {'automatic_drawing_coordination': coordination, 'viewports': output,
            'issue_count': len(issues), 'issues': issues[:limit], 'issues_truncated': len(issues) > limit,
            'physical_scale_verified': False, 'rendered_label_content_verified': False,
            'scope': 'Selected viewport annotations, including plain groups; excludes symbol definitions, other PIO internals and standalone sheet labels. Conventional-title checks are review heuristics, not geometric certification.'}


def native_viewport_context(h, oid):
    fn = getattr(vs, 'VMGetViewportContext', None)
    if not callable(fn):
        return {'available': False, 'reason': 'Native viewport extension is not loaded; style and data visualization are unknown'}
    try:
        raw = fn(h)
        require(isinstance(raw, str) and len(raw) <= 1000000, 'Unexpected native context payload')
        value = json.loads(raw)
        require(value.get('contract_version') == 1 and value.get('status') == 'ok',
                'Native context contract failed: ' + str(value.get('error', 'unsupported version')))
        require(value.get('viewport_id', '').lower() == oid.lower(), 'Native viewport identity mismatch')
        return {'available': True, **value}
    except Exception as exc:
        return {'available': False, 'reason': str(exc)}


@command
def get_viewport_display(p):
    """Inspect stored viewport display settings; not final per-object visibility."""
    ids = batch(p.get('viewport_ids'), 10)
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), 'Unique viewport UUID strings required')
    detail = p.get('detail', 'summary')
    offset, limit = p.get('offset', 0), p.get('limit', 50)
    require(detail in ('summary', 'visibility'), 'detail must be summary or visibility')
    require(type(offset) is int and offset >= 0, 'offset must be a non-negative integer')
    require(type(limit) is int and 1 <= limit <= 200, 'limit must be 1..200')
    vps = [(oid, handle(oid, 122)) for oid in ids]
    classes = {vs.ClassList(i) for i in range(1, vs.ClassNum() + 1)}
    layers = {}
    h = vs.FLayer()
    while h:
        if vs.GetObjectVariableInt(h, 154) == 1:
            layers[vs.GetLName(h)] = h
        h = vs.NextLayer(h)

    def scope(key, available):
        selected = p.get(key)
        if selected is None:
            selected = list(available)
        require(isinstance(selected, list) and all(isinstance(n, str) for n in selected), key + ' must be a list of names')
        require(len(set(selected)) == len(selected), key + ' contains duplicate names')
        missing = set(selected) - set(available)
        require(not missing, key + ' not found: ' + ', '.join(sorted(missing)))
        return sorted(selected)

    class_names = scope('class_names', classes)
    layer_names = scope('layer_names', layers)
    require(len(ids) * (len(class_names) + len(layer_names)) <= 100000,
            'Scope exceeds 100000 visibility reads; provide class_names/layer_names')
    names = {-1: 'hidden', 0: 'visible', 2: 'gray'}
    output = []
    for oid, vp in vps:
        parent = vs.GetLayer(vp)
        override_count = vs.GetVPClOvrdCount(vp)
        require(0 <= override_count <= 10000, 'Unexpected class override count')
        overrides = {vs.GetVPClOvrdName(vp, i) for i in range(override_count)}
        class_rows, layer_rows = [], []
        for name in class_names:
            ok, visibility = vs.GetVPClassVisibility(vp, name)
            class_rows.append({'name': name, 'native_ok': bool(ok),
                               'visibility': visibility if ok else None,
                               'state': names.get(visibility, 'unknown') if ok else 'unknown',
                               'document_visibility': vs.GetCVis(name),
                               'has_attribute_override': name in overrides})
        for name in layer_names:
            layer = layers[name]
            ok, visibility = vs.GetVPLayerVisibility(vp, layer)
            layer_rows.append({'name': name, 'native_ok': bool(ok),
                               'visibility': visibility if ok else None,
                               'state': names.get(visibility, 'unknown') if ok else 'unknown',
                               'document_visibility': vs.GetLVis(layer), 'design_layer_scale': vs.GetLScale(layer)})
        scale = vs.GetObjectVariableReal(vp, 1003)
        row = {'viewport_id': oid, 'name': vs.GetName(vp), 'parent_layer': vs.GetLName(parent),
               'parent_layer_kind': vs.GetObjectVariableInt(parent, 154),
               'scale': scale, 'valid_scale': math.isfinite(scale) and scale > 0,
               'view_type': vs.GetObjectVariableInt(vp, 1007),
               'projection_type': vs.GetObjectVariableInt(vp, 1000),
               'out_of_date': vs.GetObjectVariableBoolean(vp, 1004),
               'has_crop': vs.VPHasCropObject(vp),
               'class_count': len(class_rows), 'layer_count': len(layer_rows),
               'class_visibility_counts': dict(Counter(r['state'] for r in class_rows)),
               'layer_visibility_counts': dict(Counter(r['state'] for r in layer_rows)),
               'class_attribute_override_count': override_count,
               'layer_attribute_override_count': vs.GetVPLrOvrdCount(vp),
               'native_context': native_viewport_context(vp, oid)}
        if detail == 'visibility':
            for key, rows_ in [('classes', class_rows), ('layers', layer_rows)]:
                row[key] = rows_[offset:offset + limit]
                end = offset + len(row[key])
                row[key + '_truncated'] = len(row[key]) < len(rows_)
                row[key + '_next_offset'] = end if end < len(rows_) else None
        output.append(row)
    return {'document': vs.GetFPathName(), 'detail': detail, 'viewports': output,
            'final_object_visibility_verified': False,
            'scope': 'Stored viewport layer/class settings. Crop, nested objects/viewports, per-object hides, styles and data visualization may affect final output.'}


@command
def get_data_sheet_inspection(p):
    """Read a named mapping's definition and optionally object-specific DSH values.

    IFC indexed getters are used deliberately: the VW2026 DSH Python index
    parameters are output-only and cannot reliably enumerate object sheets.
    A caller-supplied mapping is not proof that it applies to an object.
    """
    mapping = p.get('mapping_name', '')
    ds = p.get('data_sheet', '')
    ids = p.get('object_ids', [])
    offset, limit = p.get('field_offset', 0), p.get('field_limit', 25)
    require(isinstance(mapping, str) and mapping.strip(), 'mapping_name is required')
    require(isinstance(ds, str), 'data_sheet must be a string')
    require(type(offset) is int and offset >= 0, 'field_offset must be a non-negative integer')
    require(type(limit) is int and 1 <= limit <= 50, 'field_limit must be 1..50')
    require(isinstance(ids, list) and len(ids) <= 10 and
            all(isinstance(i, str) and i.strip() for i in ids), 'object_ids must contain at most 10 UUID strings')
    require(len(set(ids)) == len(ids), 'Duplicate object UUIDs are not allowed')
    require(not ids or ds.strip(), 'data_sheet is required when reading objects')

    def count_result(result, api):
        require(result[0] and type(result[1]) is int and result[1] >= 0,
                api + ' failed; this does not mean no data exists')
        return result[1]

    result = {'document': vs.GetFPathName(), 'mapping_name': mapping}
    if not ds:
        count = count_result(vs.IFC_GetDSCount(mapping), 'IFC_GetDSCount')
        names = []
        for i in range(min(count, 100)):
            ok, name = vs.IFC_GetDSNameAt(mapping, i)
            require(ok, 'IFC_GetDSNameAt failed at index %s' % i)
            names.append(name)
        return {**result, 'sheet_count': count, 'sheet_names': names,
                'sheets_truncated': count > len(names)}

    count = count_result(vs.IFC_GetDSFieldsCount(mapping, ds), 'IFC_GetDSFieldsCount')
    fields = []
    for i in range(offset, min(count, offset + limit)):
        ok, label, visible, formula = vs.IFC_GetDSFieldInfoAt(mapping, ds, i)
        require(ok, 'IFC_GetDSFieldInfoAt failed at index %s' % i)
        fields.append({'index': i, 'label': label, 'visible': visible, 'by_formula': formula})
    objects, failed_reads, object_errors = [], 0, 0
    sources = {-1: 'not_set', 0: 'instance', 1: 'mapping', 2: 'instance_mapped', 3: 'guid'}
    for oid in ids:
        item = {'object_id': oid}
        objects.append(item)
        try:
            h = handle(oid)
            object_count = count_result(vs.DSH_GetDSFieldsCount(h, ds), 'DSH_GetDSFieldsCount')
            item['object_sheet_field_count'] = object_count
            item['values'] = []
            for field in fields:
                ok, value, status, source = vs.DSH_GetDSFieldValue(h, ds, field['label'])
                failed_reads += int(not ok)
                item['values'].append({'label': field['label'], 'native_ok': bool(ok),
                                       'value': value[:512] if ok else None,
                                       'truncated': bool(ok and len(value) > 512),
                                       'operation_status': status, 'source_code': source,
                                       'source': sources.get(source, 'unknown')})
        except Exception as exc:
            item['error'] = str(exc)
            object_errors += 1
    end = offset + len(fields)
    return {**result, 'data_sheet': ds, 'field_count': count, 'field_offset': offset,
            'fields': fields, 'next_field_offset': end if end < count else None,
            'objects': objects, 'failed_reads': failed_reads, 'object_errors': object_errors,
            'mapping_application_verified': False}


def attributes_by_class(h):
    # A new PIO otherwise inherits transient tool attributes, including no pen.
    for setter in (vs.SetPenColorByClass, vs.SetFillColorByClass, vs.SetFPatByClass,
                   vs.SetLWByClass, vs.SetLSByClass):
        setter(h)


def defaults_by_class():
    # PIOs capture tool defaults during their first internal geometry generation.
    for setter in (vs.PenColorByClass, vs.FillColorByClass, vs.FPatByClass,
                   vs.LWByClass, vs.LSByClass):
        setter()


def number(value, label='number', positive=False):
    require(not isinstance(value, bool), label + ' must be numeric')
    n = float(value)
    require(math.isfinite(n) and (not positive or n > 0), label + ' must be finite' + (' and positive' if positive else ''))
    return n


def point(value, size=3):
    require(isinstance(value, (list, tuple)) and len(value) == size, 'Expected %s coordinates' % size)
    return tuple(number(v, 'coordinate') for v in value)


def batch(value, maximum=100):
    require(isinstance(value, list) and 0 < len(value) <= maximum, 'Expected 1..%s items' % maximum)
    return value


def path_key(value):
    return os.path.normcase(os.path.abspath(value))


def guard(p):
    expected = p.get('expected_document', '')
    require(expected and os.path.isabs(expected), 'expected_document must be the full active VWX path')
    actual = vs.GetFPathName()
    require(actual and path_key(actual) == path_key(expected), 'Active document mismatch: %r' % actual)
    return actual


def handle(oid, type_code=None):
    h = vs.GetObjectByUuid(str(oid))
    require(h, 'Object UUID not found: %s' % oid)
    if type_code is not None:
        require(vs.GetTypeN(h) == type_code, 'Wrong object type for %s' % oid)
    return h


def named(name, type_code=None):
    require(isinstance(name, str) and name.strip(), 'A non-empty name is required')
    h = vs.GetObject(name)
    require(h, 'Named resource/object not found: %s' % name)
    if type_code is not None:
        require(vs.GetTypeN(h) == type_code, 'Wrong type for %s' % name)
    return h


def sheet(name):
    h = named(name, 31)
    require(vs.GetObjectVariableInt(h, 154) == 2, 'Expected sheet layer: ' + name)
    return h


def plugin(h):
    r = vs.GetParametricRecord(h)
    return vs.GetName(r) if r else ''


def fields(h, record):
    r = vs.GetObject(record)
    require(r, 'Missing record definition: ' + record)
    return {vs.GetFldName(r, i): vs.GetRField(h, record, vs.GetFldName(r, i)) for i in range(1, vs.NumFields(r) + 1)}


def validate_fields(h, record, values):
    available = fields(h, record)
    require(isinstance(values, dict), 'fields must be a dictionary')
    require(all(k in available and not k.startswith('__') for k in values),
            'Unknown/private parameter: ' + ', '.join(k for k in values if k not in available or k.startswith('__')))
    require(all(isinstance(v, (str, int, float, bool)) for v in values.values()), 'Field values must be scalar')


def scalar(v):
    return ('True' if v else 'False') if isinstance(v, bool) else str(v)


def put(h, record, values):
    for k, v in values.items():
        vs.SetRField(h, record, k, scalar(v))


def matrix(h):
    result = vs.GetEntityMatrix(h)
    require(result[0], 'Native matrix read failed')
    return result


def same(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)
    return a == b


def rotation_axes(angles):
    x, y, z = map(math.radians, angles)
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    u = (cz*cy, sz*cy, -sy)
    v = (cz*sy*sx-sz*cx, sz*sy*sx+cz*cx, cy*sx)
    w = (cz*sy*cx+sz*sx, sz*sy*cx-cz*sx, cy*cx)
    return u,v,w


def set_matrix(h, xyz, angles):
    u,v,w=rotation_axes(angles)
    require(vs.SetEntityMatrixN(h, u, v, w, xyz), 'Native matrix assignment failed')


def identity(h):
    return {'object_id': vs.GetObjectUuid(h), 'name': vs.GetName(h), 'plugin': plugin(h),
            'class': vs.GetClass(h), 'layer': vs.GetLName(vs.GetLayer(h)),
            'layer_elevation_and_thickness': vs.GetLayerElevation(vs.GetLayer(h))}


def light(h):
    require(plugin(h) == 'Lighting Device', 'Expected native Lighting Device')
    hp = vs.OLDGetHangingPos(h, 0)  # Never use this legacy call on LEDWall/LEDAccessory.
    out = {**identity(h), 'matrix': matrix(h), 'hanging_position_id': vs.GetObjectUuid(hp) if hp else None}
    out['fields'] = {k: vs.GetRField(h, 'Lighting Device', k) for k in
                     ['FixtureID', 'Symbol Name', 'Position', 'Channel', 'Universe', 'DMX Address', 'Body Inventory', 'Lens Inventory', 'Accessory Inventory']}
    # Setter expects mm, getter returns DOCUMENT units in this VW2026 build.
    mm_per_unit=25.4/number(vs.GetUnits()[3],'units per inch',True)
    out['accessories']=[]
    for i in range(vs.LDevice_GetAccCount(h,0)):
        pose=vs.LDevice_GetAccPos3D(h,0,i)
        out['accessories'].append({'index':i,'symbol':vs.LDevice_GetParamStr(h,0,i,'Symbol Name'),
                                  'pose_mm':(tuple(x*mm_per_unit for x in pose[0]),*pose[1:])})
    return out


def context():
    prior = vs.GetLName(vs.ActLayer()), vs.ActiveClass()
    vs.PushAttrs()
    return prior


def restore(prior):
    vs.PopAttrs()
    vs.Layer(prior[0]); vs.NameClass(prior[1])


@command
def get_entertainment_state(p):
    """Compact live summary, paged equipment listing, or explicit full native detail."""
    detail=p.get('detail','summary'); require(detail in ('summary','devices','full'),'detail must be summary, devices or full')
    limit = int(p.get('limit', 50)); require(1 <= limit <= 1000, 'limit must be 1..1000')
    offset=int(p.get('offset',0)); require(offset>=0,'offset must be nonnegative')
    include_structure=p.get('include_structure',detail=='full')
    criteria = p.get('criteria', "(PON='Lighting Device')")
    devices = []
    vs.ForEachObject(lambda h: devices.append(h) if plugin(h) == 'Lighting Device' else None, criteria)
    # Stable UUID order supports pagination; every call still reads live state.
    devices.sort(key=lambda h:vs.GetObjectUuid(h))
    rows=[]; inventory=Counter()
    for h in devices:
        hp=vs.OLDGetHangingPos(h,0)  # LD only: the legacy API is unsafe for LEDWall.
        values={k:vs.GetRField(h,'Lighting Device',k) for k in
                ('FixtureID','Symbol Name','Position','Body Inventory','Lens Inventory','Accessory Inventory')}
        row={'object_id':vs.GetObjectUuid(h),'name':vs.GetName(h),'layer':vs.GetLName(vs.GetLayer(h)),
             'class':vs.GetClass(h),'fixture_id':values['FixtureID'],'symbol':values['Symbol Name'],
             'position_name':values['Position'],'hanging_position_id':vs.GetObjectUuid(hp) if hp else None,
             'accessory_count':vs.LDevice_GetAccCount(h,0),
             'sources':{k:values[k] for k in ('Body Inventory','Lens Inventory','Accessory Inventory')}}
        rows.append(row)
        inventory[(row['symbol'],*row['sources'].values())]+=1
    groups=sorted(inventory.items(),key=lambda x:(-x[1],x[0]))
    layers = []; layer_count=0; h = vs.FLayer()
    while h:
        layer_count+=1
        if include_structure:
            layers.append({'object_id': vs.GetObjectUuid(h), 'name': vs.GetLName(h), 'kind': vs.GetObjectVariableInt(h, 154),
                           'scale': vs.GetLScale(h), 'elevation': vs.GetLayerElevation(h)})
        h = vs.NextLayer(h)
    out={'version': VERSION, 'document': vs.GetFPathName(), 'units': vs.GetUnits(),'detail':detail,
            'layer_count':layer_count,'class_count':vs.ClassNum(),
            'native_counts': {n: vs.Count("(INOBJECT & (PON='%s'))" % n) for n in
                              ['Lighting Device', 'Light Position Obj', 'TrussItem', 'Stage Deck', 'Stage Steps', 'LEDWall', 'LEDPanel', 'LEDAccessory', 'Side Arm']},
            'criteria': criteria, 'matched_devices': len(devices),
            'summary':{'attached_devices':sum(bool(r['hanging_position_id']) for r in rows),
                       'unattached_devices':sum(not r['hanging_position_id'] for r in rows),
                       'accessories_cell_0':sum(r['accessory_count'] for r in rows)},
            'inventory':{'distinct_groups':len(groups),'truncated':len(groups)>50,
                         'groups':[{'symbol':k[0],'body_source':k[1],'lens_source':k[2],'accessory_source':k[3],'count':n} for k,n in groups[:50]]},
            'scope_note':'native_counts covers the document; summary/inventory cover matching Lighting Devices. Sources are recorded identifiers, not stock availability. Accessories are cell 0.'}
    if detail!='summary':
        page=rows[offset:offset+limit] if detail=='devices' else [light(h) for h in devices[offset:offset+limit]]
        next_offset=offset+len(page) if offset+len(page)<len(devices) else None
        out.update(devices=page,offset=offset,returned=len(page),next_offset=next_offset,truncated=next_offset is not None,
                   pagination_note='UUID-sorted live listing; requery after edits. This is not a frozen model snapshot.')
    if include_structure:
        out.update(layers=layers,classes=[{'name':vs.ClassList(i),'visibility':vs.GetCVis(vs.ClassList(i))} for i in range(1,vs.ClassNum()+1)],
                   origin=vs.GetOrigin(),working_plane=vs.GetWorkingPlane())
    return out


@command
def get_native_schema(p):
    """Inspect actual parameter names/types/values, without opening Object Info or editing geometry."""
    h = handle(p['object_id']); out = identity(h); records = []
    for i in range(1, vs.NumRecords(h)+1):
        r = vs.GetRecord(h, i); rn = vs.GetName(r); row = {'name': rn, 'fields': []}
        for j in range(1, vs.NumFields(r)+1):
            n = vs.GetFldName(r, j); v = vs.GetRField(h, rn, n)
            row['fields'].append({'name': n, 'type': vs.GetFldType(r, j), 'value': v[:1000], 'truncated': len(v)>1000})
        records.append(row)
    return {**out, 'records': records, 'lighting': light(h) if plugin(h) == 'Lighting Device' else None}


def audit_patch_parts(parts, limit=50):
    """Audit recorded single-break DMX intervals; never infer modes or change patch."""
    buckets={'error':[],'review':[]}; counts=Counter(); severity_counts=Counter(); universes={}; totals=Counter()
    labels={p['part_id']:p.get('fixture_id') or p.get('name') or p['part_id'] for p in parts}
    def issue(code,severity,part_ids,**details):
        counts[code]+=1; severity_counts[severity]+=1
        if len(buckets[severity])<limit:buckets[severity].append({'code':code,'severity':severity,'parts':part_ids,
                                                                'labels':[labels[k] for k in part_ids],**details})
    for part in parts:
        key=part['part_id']; address=part['address']; footprint=part['footprint']
        # Only an accessory with neither footprint nor patch is excluded.
        if part['accessory_index']>=0 and footprint==0 and address==0:
            totals['non_control_accessories']+=1; continue
        totals['control_parts']+=1
        if not part['fixture_mode'] and not part['gdtf_mode']:
            issue('mode_unspecified','review',[key])
        valid=True
        if footprint==0 and address==0:
            issue('zero_footprint_unpatched','review',[key]); valid=False
        elif footprint<1 or footprint>512:
            issue('invalid_footprint','error',[key],footprint=footprint); valid=False
        if address==0:
            totals['unpatched_parts']+=1; issue('unpatched','review',[key]); continue
        totals['patched_parts']+=1
        if not 1<=address<=512:
            issue('invalid_address','error',[key],address=address); valid=False
        system=part['system'].strip(); universe=part['universe'].strip()
        if len(system)!=1 or system not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            issue('invalid_system','error',[key],system=system); valid=False
        if not universe or universe=='0':
            issue('missing_universe','error',[key]); valid=False
        end=address+footprint-1
        if valid and end>512:
            issue('universe_overflow','error',[key],end_address=end); valid=False
        if valid:universes.setdefault((system,universe),[]).append((address,end,part))
    for (system,universe),entries in sorted(universes.items()):
        active=[]
        for start,end,part in sorted(entries,key=lambda x:(x[0],x[2]['part_id'])):
            active=[a for a in active if a[1]>=start]
            for other_start,other_end,other in active:
                if start==other_start:
                    code='identical_patch' if part['channel']==other['channel'] else 'same_address_different_channel'
                else:code='address_overlap'
                issue(code,'review' if code=='identical_patch' else 'error',[other['part_id'],part['part_id']],
                      system=system,universe=universe,overlap=[start,min(end,other_end)])
            active.append((start,end,part))
    issues=(buckets['error']+buckets['review'])[:limit]
    return {'parts_scanned':len(parts),**{k:totals[k] for k in ('control_parts','non_control_accessories','patched_parts','unpatched_parts')},
            'issue_counts':dict(counts),'severity_counts':dict(severity_counts),
            'has_errors':bool(severity_counts['error']),'needs_review':bool(issues or counts),
            'issue_count':sum(counts.values()),'issues':issues,'issues_truncated':sum(counts.values())>len(issues)}


@command
def get_lighting_patch_audit(p):
    """Read every selected LD cell/accessory through typed native getters and audit patch intervals."""
    limit=int(p.get('limit',50)); require(1<=limit<=1000,'limit must be 1..1000')
    criteria=p.get('criteria',"(PON='Lighting Device')"); devices=[]; schematic=[]
    def collect(h):
        if plugin(h)=='Lighting Device':
            (schematic if vs.IsLDSchematicViewObj(h) else devices).append(h)
    vs.ForEachObject(collect,criteria)
    require(len(devices)<=2000,'More than 2000 devices: narrow criteria; no partial audit is reported')
    parts=[]; unreadable=[]
    for h in sorted(devices,key=lambda h:vs.GetObjectUuid(h)):
        uid=vs.GetObjectUuid(h); cells=vs.LDevice_GetCellCount(h)
        if cells<1:unreadable.append(uid); continue
        require(len(parts)+cells<=2000,'More than 2000 parts: narrow criteria')
        for cell in range(cells):
            accessories=vs.LDevice_GetAccCount(h,cell)
            require(accessories>=0 and len(parts)+accessories+1<=2000,'Invalid or excessive part count; narrow criteria')
            for acc in [-2,*range(accessories)]:
                def value(name):return vs.LDevice_GetParamStr(h,cell,acc,name)
                parts.append({'part_id':uid+':'+str(cell)+':'+str(acc),'object_id':uid,'name':vs.GetName(h),
                              'cell_index':cell,'accessory_index':acc,'symbol':value('Symbol Name'),
                              'fixture_id':value('FixtureID'),'channel':value('Channel'),'system':value('System'),
                              'universe':value('Universe'),'address':vs.LDevice_GetParamLong(h,cell,acc,'DMX Address'),
                              'footprint':vs.LDevice_GetParamLong(h,cell,acc,'Num Channels'),
                              'fixture_mode':value('Fixture Mode'),'gdtf_mode':value('GDTF Fixture Mode')})
    out={'document':vs.GetFPathName(),'criteria':criteria,'matched_devices':len(devices),'excluded_schematic_views':len(schematic),
         **audit_patch_parts(parts,limit),'unreadable_device_ids':unreadable,'coverage_complete':not unreadable,
         'limits':['Recorded single-break footprint only; manufacturer/GDTF multi-break correctness is not verified.',
                   'Universe labels are compared exactly after trimming; configured universe existence/aliases are not checked.',
                   'Identical patch may be intentional and is reported for review. Unspecified modes are not guessed.',
                   'An unpatched body with zero footprint may use non-DMX control; review its purpose. control_parts includes all body cells.',
                   'Conflicts are limited to matched devices; use default criteria to check the whole document.']}
    if unreadable:out['needs_review']=True
    if p.get('include_parts',False):out.update(parts=parts[:limit],parts_truncated=len(parts)>limit)
    return out


@command
def ensure_drawing_structure(p):
    """Create missing layers/classes; validate existing layer kinds/scales instead of silently altering them."""
    guard(p); layers = p.get('layers', []); classes = p.get('classes', [])
    require(len(layers) <= 100 and len(classes) <= 250, 'Structure batch too large')
    names = [x['name'] for x in layers] + classes
    require(all(isinstance(n, str) and n.strip() for n in names) and len(names) == len(set(names)), 'Duplicate/empty names')
    plans = []
    for row in layers:
        kind = row.get('kind', 'design'); require(kind in ('design', 'sheet'), 'kind must be design or sheet')
        scale = number(row.get('scale', 48 if kind == 'design' else 1), 'scale', True)
        if row.get('paper_size') is not None:
            require(kind=='sheet','paper_size is only for sheet layers')
            require(all(n>0 for n in point(row['paper_size'],2)),'Positive paper dimensions required')
        h = vs.GetObject(row['name'])
        if h:
            require(vs.GetTypeN(h) == 31 and vs.GetObjectVariableInt(h,154) == (1 if kind=='design' else 2), 'Layer name/type conflict: '+row['name'])
            require(same(vs.GetLScale(h), scale), 'Existing layer scale differs: '+row['name'])
        plans.append((row, kind, scale, h))
    for name in classes:
        h=vs.GetObject(name); require(not h or vs.GetTypeN(h)==94, 'Class name conflict: '+name)
    prior=context(); out=[]
    try:
        for row, kind, scale, h in plans:
            created=not bool(h)
            if created:
                h=vs.CreateLayer(row['name'],1 if kind=='design' else 2); require(h,'CreateLayer failed')
                if kind=='design': vs.SetLScale(h,scale)
            if row.get('paper_size') is not None:
                vs.Layer(row['name']); vs.SetSheetLayerUserOrigin(h,0,0); vs.SetDrawingRect(*point(row['paper_size'],2))
            out.append({'name':row['name'],'object_id':vs.GetObjectUuid(h),'created':created,'scale':vs.GetLScale(h)})
        for name in classes: vs.NameClass(name)
    finally: restore(prior)
    return {'layers':out,'classes':classes}


@command
def list_native_library_resources(p):
    """List names in a local library without importing objects or opening Resource Manager."""
    source=Path(p['path']); require(source.is_absolute() and source.is_file() and source.suffix.lower()=='.vwx','Local VWX library required')
    kind=int(p.get('resource_type',16)); require(kind in (16,47),'Supported resource types:16,47')
    limit=int(p.get('limit',100)); require(1<=limit<=500,'limit must be1..500')
    lid,count=vs.BuildResourceListN(kind,str(source)); q=p.get('filter','').casefold()
    names=[vs.GetNameFromResourceList(lid,i) for i in range(1,count+1)]
    names=[n for n in names if q in n.casefold()]
    return {'path':str(source),'resource_type':kind,'matched':len(names),'truncated':len(names)>limit,
            'resources':[{'name':n,'already_in_document':bool(vs.GetObject(n))} for n in names[:limit]]}


@command
def import_native_resources(p):
    """Import explicit names from a local VWX library in one event; refuse symbol-name replacement."""
    guard(p); source=Path(p['path']); require(source.is_absolute() and source.is_file() and source.suffix.lower()=='.vwx','Local VWX library path required')
    names=batch(p['names']); require(len(names)==len(set(names)),'Duplicate resource names')
    kind=int(p.get('resource_type',16)); require(kind in (16,47),'Supported resource types:16 symbol/style,47 record')
    lid,count=vs.BuildResourceListN(kind,str(source))
    available={vs.GetNameFromResourceList(lid,i):i for i in range(1,count+1)}
    require(all(n in available for n in names),'Requested names missing from library: '+', '.join(n for n in names if n not in available))
    require(not any(vs.GetObject(n) for n in names),'A requested resource name already exists; inspect/reuse it explicitly')
    out=[]
    for name in names:
        h=vs.ImportResourceToCurrentFile(lid,available[name]); require(h,'Import failed: '+name)
        out.append({'name':name,'object_id':vs.GetObjectUuid(h),'source':str(source)})
    return {'resources':out}


STAGE_LENGTHS = ('Width','Depth','Height','TopThick','TrimHeight','LegDia','LegSpace','RailHeight')
STAGE_RAILS = ('None','Straight','Box Open','Box Filled','Toe','Straight+Toe','Box Open+Toe','Box Filled+Toe')
STAGE_FIELDS = ('DeckShape','StgStyle','LegProfile','Additions','HideDeck','ClassParts',
                'RailFront','RailBack','RailLeft','RailRight','RailProfile','RailCount',
                'Unit','Location','Position','Vendor','Brand','Model','Purpose','Note',
                'DeckSize','LegTotal','TopSurfaceArea')


def stage_grid_plan(p):
    allowed = {'expected_document','name','layer','class','origin_mm','columns','rows',
               'deck_size_mm','rotation','structure','top_thickness_mm','trim_height_mm',
               'leg_size_mm','leg_spacing_mm','leg_profile','rail_edges','rail_type','rail_height_mm',
               'vendor','brand','model','location','dry_run'}
    require(set(p)<=allowed, 'Unsupported stage grid setting')
    for key in ('name','layer','class'):
        require(isinstance(p.get(key),str) and 0<len(p[key].strip())<=100, 'Invalid '+key)
    cols=p.get('columns'); rows=p.get('rows')
    require(type(cols) is int and type(rows) is int and cols>0 and rows>0 and cols*rows<=25,
            'Use positive integer rows/columns, at most 25 decks')
    origin=point(p['origin_mm']); w,d,h=point(p['deck_size_mm'])
    require(min(w,d,h)>0, 'Deck width, depth and height must be positive millimetres')
    angle=number(p.get('rotation',0)); c=math.cos(math.radians(angle)); s=math.sin(math.radians(angle))
    upi=number(vs.GetUnits()[3], 'document units per inch', positive=True); factor=upi/25.4
    structure=p.get('structure','Legs-Braced')
    require(structure in ('Legs-Basic','Legs-Braced','Folding','Deck Only'), 'Unsupported stage structure')
    profile=p.get('leg_profile','Square'); require(profile in ('Square','Octagonal','Round'), 'Invalid leg profile')
    edges=p.get('rail_edges',[]); rail=p.get('rail_type','Straight')
    require(isinstance(edges,list) and len(edges)==len(set(edges)) and set(edges)<={'front','back','left','right'}, 'Invalid/duplicate rail edges')
    require(rail in STAGE_RAILS and (not edges or rail!='None'), 'Invalid rail type')
    require(type(p.get('dry_run',False)) is bool, 'dry_run must be boolean')
    lengths={'Width':w,'Depth':d,'Height':h}
    for field,key,default in [('TopThick','top_thickness_mm',25.4),('TrimHeight','trim_height_mm',152.4),
                              ('LegDia','leg_size_mm',76.2),('LegSpace','leg_spacing_mm',914.4),
                              ('RailHeight','rail_height_mm',1066.8)]:
        lengths[field]=number(p.get(key,default),key,positive=True)
    require(lengths['TopThick']<h and lengths['TrimHeight']<=h, 'Top/trim must fit deck height')
    for key in ('vendor','brand','model','location'):
        require(isinstance(p.get(key,''),str) and len(p.get(key,''))<=512, 'Invalid '+key)
    common={'DeckShape':'Rectangular','StgStyle':structure,'LegProfile':profile,'Additions':'None',
            'HideDeck':False,'ClassParts':False,'RailProfile':'Square','RailCount':'2',
            'AddlVertsFB':'0','AddlVertsLR':'0','TreadColor':'Black','EdgeColor':'Black',
            'LgFrmColor':'Black','RailColor':'Black','Vendor':p.get('vendor',''),
            'Brand':p.get('brand',''),'Model':p.get('model',''),'Location':p.get('location',p['name']),
            'Position':p.get('location',p['name']),'Purpose':'','Note':''}
    common.update({k:format(v,'.15g')+'mm' for k,v in lengths.items()})
    plans=[]
    for row in range(rows):
        for col in range(cols):
            name='%s-R%02d-C%02d'%(p['name'],row+1,col+1)
            # Native rectangular deck Width follows local X; Depth follows local Y.
            x,y=col*w,row*d
            position=[(origin[0]+c*x-s*y)*factor,(origin[1]+s*x+c*y)*factor,origin[2]*factor]
            point(position)  # Reject overflow before any document mutation.
            values={**common,'Unit':name}
            for edge,boundary in [('front',row==0),('back',row==rows-1),('left',col==0),('right',col==cols-1)]:
                values['Rail'+edge.title()]=rail if edge in edges and boundary else 'None'
            plans.append({'name':name,'layer':p['layer'],'class':p['class'],'position':position,
                          'rotation':[0,0,angle],'fields':values,'lengths_mm':dict(lengths)})
    return plans


@command
def create_stage_deck_grid(p):
    """New native rectangular decks, followed by an independent read event."""
    guard(p); plans=stage_grid_plan(p)
    layer=named(p['layer'],31); require(vs.GetObjectVariableInt(layer,154)==1, 'Use a design layer')
    named(p['class'],94)
    existing=set()
    vs.ForEachObject(lambda h:existing.add(vs.GetRField(h,'Stage Deck','Unit').casefold()), "(PON='Stage Deck')")
    for row in plans:
        require(not vs.GetObject(row['name']) and row['name'].casefold() not in existing, 'Existing object name or deck Unit: '+row['name'])
    if p.get('dry_run',False):
        return {'dry_run':True,'count':len(plans),'planned':plans,'created':[]}
    definition=vs.DefineCustomObj('Stage Deck',0); require(definition, 'Stage Deck unavailable')
    available={vs.GetFldName(definition,i) for i in range(1,vs.NumFields(definition)+1)}
    require(set(plans[0]['fields'])<=available, 'Installed Stage Deck schema differs')
    for key in ('StgStyle','LegProfile','RailFront','RailBack','RailLeft','RailRight','RailProfile'):
        choices={vs.GetCustomObjectChoice('Stage Deck',key,i) for i in range(1,vs.NumCustomObjectChoices('Stage Deck',key)+1)}
        require(all(row['fields'][key] in choices for row in plans), 'Unsupported installed choice: '+key)
    created=[]; prior=context()
    try:
        for row in plans:
            vs.Layer(row['layer']); vs.NameClass(row['class']); defaults_by_class()
            h=vs.CreateCustomObjectN('Stage Deck',tuple(row['position'][:2]),row['rotation'][2],False)
            require(h, 'Stage Deck insertion failed')
            receipt={**row,'object_id':vs.GetObjectUuid(h)}; created.append(receipt)
            vs.SetName(h,row['name']); vs.SetClass(h,row['class']); attributes_by_class(h)
            put(h,'Stage Deck',row['fields']); set_matrix(h,point(row['position']),point(row['rotation'])); vs.ResetObject(h)
            require(same(matrix(h)[1],row['position']), 'Native stage placement differs; inspect retained UUIDs')
    except Exception as exc:
        return {'status':'error','error':str(exc),'created':created,'retry_safe':False,
                'recovery':'Inspect retained deck UUIDs and names; do not repeat creation.'}
    finally: restore(prior)
    return {'count':len(created),'created':created,'requires_verification':True,
            'next_command':'get_stage_deck_verification'}


def stage_deck_snapshot(h):
    require(vs.GetTypeN(h)==86 and plugin(h)=='Stage Deck', 'Expected native Stage Deck')
    upi=number(vs.GetUnits()[3],positive=True); lengths={}
    for key in STAGE_LENGTHS:
        ok,value=vs.ValidNumStr(vs.GetRField(h,'Stage Deck',key))
        require(ok, 'Cannot parse native deck dimension '+key)
        lengths[key]=number(value)*25.4/upi
    return {**identity(h),'matrix':matrix(h),'lengths_mm':lengths,
            'fields':{k:vs.GetRField(h,'Stage Deck',k) for k in STAGE_FIELDS},
            'native_geometry_present':bool(vs.FInGroup(h))}


@command
def get_stage_deck_inspection(p):
    ids=batch(p.get('object_ids'),25); require(len(set(ids))==len(ids),'Duplicate UUIDs')
    return {'document':vs.GetFPathName(),'decks':[stage_deck_snapshot(handle(oid,86)) for oid in ids],
            'scope':'Native deck fields, calculated leg count, layer/class and layer-relative poses. Manufacturer inventory assignment and structural capacity are separate.'}


@command
def get_stage_deck_verification(p):
    guard(p); created=batch(p.get('created'),25); out=[]
    for receipt in created:
        h=handle(receipt['object_id'],86); actual=stage_deck_snapshot(h); out.append(actual)
        require(actual['native_geometry_present'], 'Native deck regeneration has not finished')
        require(all(actual[k]==receipt[k] for k in ('name','layer','class')), 'Deck organization changed')
        require(same(actual['matrix'][1],receipt['position']) and
                same(rotation_axes(actual['matrix'][2:5]),rotation_axes(receipt['rotation'])), 'Deck pose mismatch')
        require(same(actual['lengths_mm'],receipt['lengths_mm']) or all(
            math.isclose(actual['lengths_mm'][k],v,abs_tol=0.001) for k,v in receipt['lengths_mm'].items()), 'Native deck dimensions differ')
        for key,value in receipt['fields'].items():
            if key not in STAGE_LENGTHS:
                require(vs.GetRField(h,'Stage Deck',key)==scalar(value), 'Native deck field differs: '+key)
        if receipt['fields']['StgStyle'] in ('Legs-Basic','Legs-Braced'):
            require(float(actual['fields']['LegTotal'])>=4, 'Native leg calculation incomplete')
    return {'verified':True,'decks':out,'scope':'Post-event native dimensions, requested fields, poses, organization, generated geometry and leg counts. No structural rating or shared-leg optimization.'}


@command
def create_native_objects(p):
    """Batch-create native Lighting Device/Deck/Steps/Side Arm/LEDWall; leave existing objects untouched."""
    guard(p); items=batch(p['items'],25); names=[x['name'] for x in items]
    require(len(names)==len(set(names)),'Duplicate object names')
    for row in items:
        require(row['plugin'] in NATIVE_TYPES,'Unsupported native type; use the dedicated rigging tool for truss/positions')
        require(not vs.GetObject(row['name']),'Object name already exists: '+row['name'])
        layer=named(row['layer'],31); require(vs.GetObjectVariableInt(layer,154)==1,'Use a design layer')
        named(row['class'],94); point(row['position']); point(row.get('rotation',[0,0,0]))
        if row['plugin']=='Lighting Device': named(row['symbol'],16)
    prior=context(); out=[]
    try:
        for row in items:
            pn=row['plugin']; xyz=point(row['position']); angles=point(row.get('rotation',[0,0,0]))
            vs.Layer(row['layer']); vs.NameClass(row['class']); defaults_by_class()
            h=vs.CreateCustomObjectN(pn,xyz[:2],angles[2],False); require(h,'Native object creation failed: '+pn)
            # Validate actual installed parameter names before retaining a new object.
            try: validate_fields(h,pn,row.get('fields',{}))
            except Exception:
                vs.DelObject(h); raise
            vs.SetName(h,row['name']); vs.SetClass(h,row['class']); attributes_by_class(h)
            if pn=='Lighting Device':
                symbol=named(row['symbol'],16)
                values={'Symbol Name':row['symbol'],'Symbol Definition':row['symbol'],'Use Active Symbol':'False',
                        'Use Legend':'None','Draw Beam':'False','Light On':'False','UseGDTFGeometry':'False',
                        'xRot':angles[0],'yRot':angles[1],'zRot':angles[2]}
                for f in ['Inst Type','Device Type','Wattage','Weight','Beam Angle','Field Angle','Num Channels']:
                    v=vs.GetRField(symbol,'Light Info Record',f)
                    if v: values[f]=v
                values.update({'Position':'','Channel':'','Universe':'','DMX Address':'0',
                               'Body Inventory':'','Lens Inventory':'','Accessory Inventory':''})
                put(h,pn,values)
            put(h,pn,row.get('fields',{})); set_matrix(h,xyz,angles)
            if pn=='Lighting Device': vs.LDevice_Reset(h)
            else: vs.ResetObject(h)
            actual=matrix(h); require(same(actual[1],xyz),'Native regeneration moved '+row['name'])
            out.append({**identity(h),'matrix':actual})
    finally: restore(prior)
    return {'created':out,'count':len(out),'requires_finalization':True,
            'next_command':'finalize_native_objects'}


@command
def finalize_native_objects(p):
    """Second native event: regenerate initialized PIOs with their explicit class attributes."""
    guard(p); rows=batch(p['created'],25); plans=[]
    for row in rows:
        h=handle(row['object_id']); require(plugin(h) in NATIVE_TYPES,'Unsupported finalization type')
        require(vs.GetName(h)==row['name'] and vs.GetClass(h)==row['class'],'Created object identity changed')
        require(same(matrix(h),row['matrix']),'Created object pose changed; inspect before finalizing')
        require(vs.FInGroup(h),'First native regeneration has not finished; retry ONLY finalize_native_objects')
        plans.append(h)
    for h in plans:
        attributes_by_class(h)
        if plugin(h)=='Lighting Device': vs.LDevice_Reset(h)
        else: vs.ResetObject(h)
    return {'finalized_ids':[vs.GetObjectUuid(h) for h in plans]}


LIGHTING_DOCUMENTATION = {'unit_number':'Unit Number','channel':'Channel','purpose':'Purpose','color':'Color'}
LIGHTING_PROTECTED_TEXT = ('FixtureID','Symbol Name','Position','Use Legend','Focus',
    'Fixture Mode','GDTF Fixture Name','GDTF Fixture Mode','System','Universe','UniverseAddress',
    'Body Inventory','Lens Inventory','Accessory Inventory','Circuit Number','Circuit Name','Dimmer')
LIGHTING_PROTECTED_LONG = ('DMX Address','Absolute Address','Num Channels')


def lighting_documentation_snapshot(h):
    require(vs.GetTypeN(h)==86 and plugin(h)=='Lighting Device', 'Expected native Lighting Device')
    require(not vs.IsLDSchematicViewObj(h), 'Edit the actual device, not a schematic representation')
    require(vs.LDevice_GetCellCount(h)==1, 'This workflow requires a single-cell Lighting Device')
    require(0<=vs.LDevice_GetAccCount(h,0)<=20, 'Requires 0..20 accessories on this device')
    base=light(h)
    count=len(base['accessories']); require(count<=20, 'More than 20 accessories on this device')
    def part(index):
        return {**{k:vs.LDevice_GetParamStr(h,0,index,k) for k in LIGHTING_PROTECTED_TEXT},
                **{k:vs.LDevice_GetParamLong(h,0,index,k) for k in LIGHTING_PROTECTED_LONG}}
    values={key:vs.LDevice_GetParamStr(h,0,-2,field) for key,field in LIGHTING_DOCUMENTATION.items()}
    record_values={key:vs.GetRField(h,'Lighting Device',field) for key,field in LIGHTING_DOCUMENTATION.items()}
    # Native record values feed worksheet formulas; keep both views in the receipt.
    protected={k:v for k,v in base.items() if k!='fields'}
    protected['parent']=part(-2)
    protected['gdtf_fields']={k:vs.GetRField(h,'Lighting Device',k) for k in (
        'GDTF Fixture Name','GDTF Fixture Mode','GDTF Fixture Type ID','GDTF Fixture Custom ID','UseGDTFGeometry')}
    protected['accessory_parameters']=[part(i) for i in range(count)]
    payload={'values':values,'record_values':record_values,'protected':protected}
    encoded=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    require(len(encoded)<=262144, 'Lighting snapshot exceeds 256 KB')
    return {'object_id':base['object_id'],**json.loads(encoded),'fingerprint':hashlib.sha256(encoded).hexdigest()}


def lighting_documentation_public(snapshot):
    protected=snapshot['protected']
    return {k:snapshot[k] for k in ('object_id','values','record_values','fingerprint')} | {
        k:protected[k] for k in ('name','layer','class','hanging_position_id')} | {
        'accessory_count':len(protected['accessories'])}


@command
def get_lighting_documentation(p):
    ids=batch(p.get('object_ids'),25)
    require(all(isinstance(oid,str) and 0<len(oid)<=128 for oid in ids),'Invalid object UUID')
    require(len(set(ids))==len(ids),'Duplicate UUIDs')
    return {'document':vs.GetFPathName(),'devices':[lighting_documentation_public(lighting_documentation_snapshot(handle(oid,86))) for oid in ids],
            'scope':'Single-cell native devices: unit/channel/purpose/color, worksheet record values and scoped protected state. Channel is an identifier, not a DMX address.'}


@command
def set_lighting_documentation(p):
    guard(p); require(set(p)<={'expected_document','items','dry_run'},'Unsupported lighting edit setting')
    rows=batch(p.get('items'),25); require(type(p.get('dry_run',False)) is bool,'dry_run must be boolean')
    plans=[]; seen=set()
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'object_id','expected_fingerprint','values'}, 'Use object_id, expected_fingerprint and values')
        oid=row['object_id']; require(isinstance(oid,str) and oid and oid.casefold() not in seen,'Invalid/duplicate object UUID')
        seen.add(oid.casefold()); values=row['values']
        require(isinstance(values,dict) and values and set(values)<=set(LIGHTING_DOCUMENTATION), 'Only unit_number, channel, purpose and color are editable')
        require(all(isinstance(v,str) and len(v)<=512 and '\x00' not in v for v in values.values()), 'Use text values up to 512 characters; empty text clears')
        h=handle(oid,86); before=lighting_documentation_snapshot(h)
        require(row['expected_fingerprint']==before['fingerprint'], 'Stale lighting data; read the device again before editing')
        validate_fields(h,'Lighting Device',{LIGHTING_DOCUMENTATION[k]:v for k,v in values.items()})
        changed={k:v for k,v in values.items() if before['values'][k]!=v or before['record_values'][k]!=v}
        plans.append((h,before,changed))
    receipt=[{'object_id':b['object_id'],'before':b,'expected_values':{**b['values'],**v},'changes':v} for h,b,v in plans]
    if p.get('dry_run',False):
        return {'dry_run':True,'planned':[{'object_id':b['object_id'],'before':b['values'],'changes':v} for h,b,v in plans],
                'changed_field_count':sum(len(v) for h,b,v in plans)}
    attempted=[]
    try:
        for h,b,values in plans:
            if not values:continue
            attempted.append(b['object_id'])
            for key,value in values.items():
                vs.LDevice_SetParamStr(h,0,-2,LIGHTING_DOCUMENTATION[key],value)
            vs.LDevice_Reset(h)
    except Exception as exc:
        return {'status':'error','error':str(exc),'attempted_ids':attempted,'receipt':receipt,'retry_safe':False,
                'recovery':'Read the retained UUIDs and receipt after regeneration; do not blindly repeat or roll back uncertain edits.'}
    return {'attempted_ids':attempted,'changed_field_count':sum(len(v) for h,b,v in plans),'receipt':receipt,
            'requires_verification':True,'next_command':'get_lighting_documentation_verification'}


@command
def number_lighting_devices(p):
    guard(p)
    require(set(p)<={'expected_document','items','field','start','increment','prefix','suffix','padding','dry_run'},'Unsupported numbering setting')
    rows=batch(p.get('items'),25); field=p.get('field','unit_number')
    require(field in ('unit_number','channel'), 'Number only unit_number or channel')
    start=p.get('start',1); step=p.get('increment',1); padding=p.get('padding',0)
    require(type(start) is int and 0<=start<=999999999,'start must be an integer 0..999999999')
    require(type(step) is int and 0<step<=999999999,'increment must be a positive integer')
    require(type(padding) is int and 0<=padding<=12,'padding must be 0..12')
    prefix=p.get('prefix',''); suffix=p.get('suffix','')
    require(all(isinstance(s,str) and len(s)<=128 for s in (prefix,suffix)),'Prefix/suffix must be text up to 128 characters')
    edits=[]
    for i,row in enumerate(rows):
        require(isinstance(row,dict) and set(row)=={'object_id','expected_fingerprint'},'Supply ordered UUID/fingerprint pairs')
        n=start+i*step;require(n<=999999999,'Numbering exceeds 999999999')
        edits.append({**row,'values':{field:prefix+str(n).zfill(padding)+suffix}})
    result=set_lighting_documentation({'expected_document':p['expected_document'],'items':edits,'dry_run':p.get('dry_run',False)})
    result['numbering_scope']='Caller order; no spatial sorting, per-position reset, or collision check against unselected devices. Repeated channels can be intentional.'
    return result


@command
def get_lighting_documentation_verification(p):
    guard(p); rows=batch(p.get('receipt'),25); out=[]
    for row in rows:
        after=lighting_documentation_snapshot(handle(row['object_id'],86));out.append(lighting_documentation_public(after))
        require(after['values']==row['expected_values'],'Native lighting field readback differs: '+row['object_id'])
        for key in row['changes']:
            require(after['record_values'][key]==row['expected_values'][key],'Worksheet source record differs: '+key)
        require(after['protected']==row['before']['protected'], 'Fixture pose, organization, attachment, accessory hardware, mode or patch changed: '+row['object_id'])
    return {'verified':True,'devices':out,
            'scope':'Native fields and edited worksheet source values agree after regeneration; scoped pose/organization/attachment/accessory/patch state preserved. Label layout and worksheet recalculation are separate.'}


@command
def get_lighting_gdtf(p):
    rows=batch(p.get('object_ids'),25); require(len(set(rows))==len(rows),'Duplicate UUIDs')
    out=[]
    for oid in rows:
        s=lighting_documentation_snapshot(handle(oid,86))
        out.append({'object_id':oid,'fingerprint':s['fingerprint'],'fields':s['protected']['gdtf_fields'],
            'footprint':s['protected']['parent']['Num Channels'],
            'symbol':s['protected']['parent']['Symbol Name'],
            'channel':s['values']['channel'],'native_exchange_available':callable(getattr(vs,'VMGDTFExchange',None))})
    return {'document':vs.GetFPathName(),'devices':out,
            'scope':'Stored native GDTF assignment and footprint for single-cell devices. File contents, mode validity and MVR embedding require separate checks.'}


@command
def assign_gdtf_file(p):
    """Use the SDK importer, never synthesize GDTF assignment fields."""
    import gdtf_files
    guard(p)
    require(set(p)=={'expected_document','object_id','expected_fingerprint','path','expected_sha256','mode','use_gdtf_geometry'},'Incorrect GDTF assignment fields')
    require(type(p['use_gdtf_geometry']) is bool,'use_gdtf_geometry must be boolean')
    digest=p['expected_sha256']
    require(isinstance(digest,str) and len(digest)==64 and all(c in '0123456789abcdefABCDEF' for c in digest),'Explicit SHA256 from get_gdtf_file required')
    info=gdtf_files.inspect_gdtf(p['path'],p['expected_sha256'])
    matches=[m for m in info['modes'] if m['name']==p['mode']]
    require(len(matches)==1,'Exact requested mode is absent from the GDTF file')
    mode=matches[0];require(mode['simple_single_break_footprint'] is not None,'Initial assignment scope requires a resolved simple single-break mode')
    require(info['fixture_type_id'],'GDTF FixtureTypeID required')
    h=handle(p['object_id'],86);before=lighting_documentation_snapshot(h)
    require(before['fingerprint']==p['expected_fingerprint'],'Stale device state; inspect again')
    require(before['protected']['parent']['DMX Address']==0,'Initial GDTF assignment scope requires an unpatched device')
    require(callable(getattr(vs,'VMGDTFExchange',None)),'Native GDTF extension must be installed and Vectorworks restarted before assignment')
    receipt={'object_id':before['object_id'],'before':before,'file':info,'mode':mode,
             'use_gdtf_geometry':p['use_gdtf_geometry']}
    request={k:p[k] for k in ('expected_document','object_id','path','mode')};request['operation']='import'
    native=json.loads(vs.VMGDTFExchange(json.dumps(request)))
    if native.get('status')!='ok':
        return {'status':'error','error':'Native GDTF import did not complete','native':native,'receipt':receipt,'retry_safe':native.get('retry_safe',False)}
    try:
        vs.SetRField(h,'Lighting Device','UseGDTFGeometry',scalar(p['use_gdtf_geometry']))
        vs.LDevice_Reset(h)
    except Exception as exc:
        return {'status':'error','error':str(exc),'receipt':receipt,'native':native,'retry_safe':False}
    return {'receipt':receipt,'native':native,'requires_verification':True,'next_command':'get_gdtf_assignment_verification'}


@command
def get_gdtf_assignment_verification(p):
    guard(p);r=p['receipt'];after=lighting_documentation_snapshot(handle(r['object_id'],86))
    actual=after['protected']['gdtf_fields']
    require(actual['GDTF Fixture Name'] and actual['GDTF Fixture Mode']==r['mode']['name'],'Native GDTF file/mode assignment differs')
    require(actual['UseGDTFGeometry']==scalar(r['use_gdtf_geometry']),'Native GDTF geometry setting differs')
    require(after['protected']['parent']['Num Channels']==r['mode']['simple_single_break_footprint'],'Native GDTF mode footprint differs')
    # The importer may intentionally alter GDTF resource identifiers and footprint only.
    old=json.loads(json.dumps(r['before']['protected']));new=json.loads(json.dumps(after['protected']))
    for snapshot in (old,new):
        snapshot.pop('gdtf_fields',None)
        for key in ('GDTF Fixture Name','GDTF Fixture Mode','Num Channels'):snapshot['parent'].pop(key,None)
    require(old==new,'GDTF import changed protected geometry, organization, hardware, sources or patch')
    require(after['values']==r['before']['values'],'GDTF import changed fixture documentation')
    return {'verified':True,'device':lighting_documentation_public(after),'gdtf_fields':actual,
            'source_sha256':r['file']['sha256'],'source_fixture_type_id':r['file']['fixture_type_id'],
            'embedded_file_verified':False,'mvr_export_verified':False,'visual_geometry_verified':False,
            'scope':'Native assignment, requested mode, simple footprint and geometry switch readback only. Export and inspect embedded GDTF to establish file identity; MVR audit and visual review remain separate.'}


@command
def export_lighting_gdtf(p):
    import gdtf_files
    guard(p); require(set(p)=={'expected_document','object_id','path'},'Incorrect GDTF export fields')
    h=handle(p['object_id'],86);before=lighting_documentation_snapshot(h)
    target=Path(p['path']);require(target.is_absolute() and target.suffix.lower()=='.gdtf' and not target.exists() and target.parent.is_dir(),'Unused absolute .gdtf destination required')
    require(callable(getattr(vs,'VMGDTFExchange',None)),'Native GDTF extension must be installed and Vectorworks restarted before export')
    result=json.loads(vs.VMGDTFExchange(json.dumps({**p,'operation':'export'})))
    if result.get('status')!='ok':return result
    try:
        exported=gdtf_files.inspect_gdtf(str(target))
        require(lighting_documentation_snapshot(h)==before,'Source fixture changed during GDTF export')
    except Exception as exc:return {'status':'error','error':str(exc),'native':result,'path':str(target),'retry_safe':False}
    return {'native':result,'file':exported,'source_preserved':True,
            'scope':'Native exported GDTF content; export may generate a generic file when manufacturer data is absent. Match hashes/FixtureTypeID and modes against the intended source.'}


@command
def set_lighting_accessories(p):
    """Ensure native accessories on cell 0; offsets explicitly in mm. Verify fixture pose/HP unchanged."""
    guard(p); devices=[handle(i) for i in batch(p['device_ids'],100)]; parts=batch(p['accessories'],20)
    require(len(set(p['device_ids']))==len(devices),'Duplicate device IDs')
    require(len({r['symbol'] for r in parts})==len(parts),'Use an assembly symbol for repeated identical clamps')
    before=[light(h) for h in devices]
    for row in parts:
        named(row['symbol'],16); point(row['position_mm']); point(row.get('rotation',[0,0,0]))
        for b in before:
            require(sum(a['symbol']==row['symbol'] for a in b['accessories'])<=1,'Ambiguous existing accessory; inspect first')
    for h,b in zip(devices,before):
        for row in parts:
            matches=[a['index'] for a in b['accessories'] if a['symbol']==row['symbol']]
            index=matches[0] if matches else vs.LDevice_AddAccessory(h,0,named(row['symbol'],16))
            require(index>=0,'Accessory creation failed')
            vs.LDevice_SetAccPos3D(h,0,index,point(row['position_mm']),*point(row.get('rotation',[0,0,0])))
        vs.LDevice_Reset(h)
        after=light(h)
        require(same(b['matrix'],after['matrix']) and b['hanging_position_id']==after['hanging_position_id'],'Fixture pose/attachment changed; inspect '+b['name'])
        for row in parts:
            matches=[a for a in after['accessories'] if a['symbol']==row['symbol']]
            require(len(matches)==1,'Accessory verification failed')
            require(same(matches[0]['pose_mm'][0],row['position_mm']),'Accessory position readback differs')
    return {'devices':[light(h) for h in devices],'offset_units':'millimetres'}


@command
def set_lighting_sources(p):
    """Assign native body/lens/accessory inventory fields without duplicate equipment geometry."""
    guard(p); rows=batch(p['assignments']); plans=[]
    allowed={'Body Inventory','Lens Inventory','Accessory Inventory'}
    for row in rows:
        h=handle(row['object_id']); b=light(h); values=row['sources']
        require(values and set(values)<=allowed,'Use Body Inventory, Lens Inventory or Accessory Inventory')
        validate_fields(h,'Lighting Device',values); plans.append((h,b,values))
    for h,b,values in plans:
        put(h,'Lighting Device',values); vs.LDevice_Reset(h); a=light(h)
        require(same(a['matrix'],b['matrix']) and a['hanging_position_id']==b['hanging_position_id'],'Source update changed geometry/attachment')
        require(all(a['fields'][k]==str(v) for k,v in values.items()),'Native source readback differs')
    return {'devices':[light(h) for h,_,_ in plans],
            'note':'Source names are exact native inventory identifiers supplied by the caller; stock availability is not inferred.'}


@command
def create_truss_position(p):
    """Create a native Hanging Position with new library-backed TrussItems; member coordinates are HP-local."""
    guard(p); members=batch(p['members'],40); xyz=point(p['position']); angles=point(p.get('rotation',[0,0,0]))
    names=[p['name']]+[r['name'] for r in members]
    require(len(names)==len(set(names)) and not any(vs.GetObject(n) for n in names),'Rigging names must be new and unique')
    layer=named(p['layer'],31); require(vs.GetObjectVariableInt(layer,154)==1,'Design layer required'); named(p['class'],94)
    string_fields=('Name','Type','Count','ItemType','CornerType','CenterBased','Vertical','ConStart','ConEnd','ConLeft','ConRight','ConBottom','ConTop','ConHeight','ConLow','ConRot','ConLeftRot','ConLowRot','ConRightRot','ConBottomRot','ConHeightRot','ConTopRot','HingeMinAngle','HingeMaxAngle','HingeGeometry','Arc')
    plans=[]
    for row in members:
        sym=named(row['symbol'],16); src=fields(sym,'BrxTrussItemRecord')
        require(src.get('ItemType') in ('Line','Corner'),'Library resource lacks supported native truss data')
        values={k:src[k] for k in string_fields}
        for f in ('Length','Height','Width','Diameter','HingeL1','HingeL2'):
            values[f]=str(number(src[f])/25.4)+'"'
        mass=number(src['Weight']); length=number(src['Length'])
        require(mass>=0 and length>=0,'Invalid library truss mass/length')
        values.update({'Weight':str(mass*1000),'Distributed weight':str(mass*1000/length if length else 0),
                       'CrossSection':src['Section'],'ConnectionIdent':src['Connection'],'Symbol':row['symbol'],'Only3D':'False','ClassSettet':'True'})
        for part in ('Right','Top','Bottom','High','Low','Center'):
            for a in ('X','Y','Z'): values[part.upper()+'_'+a]=str(number(src[part+' '+a])/25.4)+'"'
            if part!='Center': values[part.upper()+'_VALID']=src[part+' Valid']
        plans.append((row,values,point(row['position']),point(row.get('rotation',[0,0,0]))))
    prior=context(); trusses=[]
    try:
        vs.Layer(p['layer']); vs.NameClass(p['class']); defaults_by_class()
        for row,values,loc,rot in plans:
            h=vs.CreateCustomObjectN('TrussItem',loc[:2],rot[2],False); require(h,'Truss creation failed')
            vs.SetName(h,row['name']); attributes_by_class(h); put(h,'TrussItem',values); set_matrix(h,loc,rot); vs.ResetObject(h)
            trusses.append(h)
        hp=vs.CreateCustomObjectN('Light Position Obj',(0,0),0,False); require(hp,'Hanging Position creation failed'); vs.SetName(hp,p['name'])
        attributes_by_class(hp)
        put(hp,'Light Position Obj',{'Position Name':p['position_name'],'Position Summary':'False','Symbol Name':'','Auto':'False','ShowWitnessLines':'True'})
        vs.BeginGroup()
        try: vs.Locus3D((0,0,0))
        finally: vs.EndGroup()
        group=vs.LNewObj()
        for h in trusses: require(vs.SetParent(h,group),'Truss reparenting failed')
        require(vs.SetCustomObjectProfileGroup(hp,group),'Native profile assignment failed'); set_matrix(hp,xyz,angles); vs.ResetObject(hp)
        return {'position':identity(hp),'members':[identity(h) for h in trusses],
                'connection_status':'Native truss metadata and HP membership established. Inter-member snapping/connections are not synthesized or certified.'}
    finally: restore(prior)


@command
def attach_loads_to_position(p):
    """Run native HP auto-attachment and report actual Lighting Device links; never infer links from labels."""
    guard(p); hp=handle(p['position_id']); require(plugin(hp)=='Light Position Obj','Expected native Hanging Position')
    expected=[handle(i) for i in batch(p['expected_device_ids'])]
    for h in expected: require(plugin(h)=='Lighting Device','Expected Lighting Devices')
    devices=[]; vs.ForEachObject(lambda h:devices.append(h),"(PON='Lighting Device')")
    before={vs.GetObjectUuid(h):light(h) for h in devices}
    vs.HP_AutoAttachLoads(hp)
    after={vs.GetObjectUuid(h):light(h) for h in devices}
    moved=[uid for uid,a in after.items() if not same(a['matrix'],before[uid]['matrix'])]
    changed=[uid for uid,a in after.items() if a['hanging_position_id']!=before[uid]['hanging_position_id']]
    missing=[vs.GetObjectUuid(h) for h in expected if after[vs.GetObjectUuid(h)]['hanging_position_id']!=p['position_id']]
    return {'position_id':p['position_id'],'attached_expected':not missing,'unattached_device_ids':missing,
            'changed_attachment_ids':changed,'moved_device_ids':moved,
            'note':'Native auto-attachment scopes the entire hanging position. No capacity/retention validation is implied.'}


@command
def set_fixture_label_layout(p):
    """Apply an existing native legend and edit known label-handle offsets in mm without moving fixtures."""
    guard(p); legend=named(p['legend'],16); rows=batch(p['devices']); plans=[]
    require(vs.GetRField(legend,'Legends Rec','Use2DLayout')=='True','Use a native 2D-layout legend; single-label mode ignores Non-Rotating')
    for row in rows:
        h=handle(row['object_id']); before=light(h); point(row['offset_mm'],2)
        raw=vs.GetRField(h,'Lighting Device','__LabelHandlesData'); data=json.loads(raw)
        index=int(row['label_index']); matches=[x for x in data.get('handles',[]) if x.get('index')==index]
        require(len(matches)==1,'Label handle index absent/ambiguous; inspect a configured fixture first')
        matches[0].update({'override':True,'x':row['offset_mm'][0],'y':row['offset_mm'][1]}); plans.append((h,before,data))
    for h,before,data in plans:
        vs.SetRField(h,'Lighting Device','Use Legend',p['legend'])
        vs.SetRField(h,'Lighting Device','__LabelHandlesData',json.dumps(data)); vs.LDevice_Reset(h)
        after=light(h); require(same(before['matrix'],after['matrix']) and before['hanging_position_id']==after['hanging_position_id'],'Label edit changed device state')
    return {'devices':len(plans),'legend':p['legend'],'offset_units':'millimetres','model_transforms_preserved':True}


def worksheet_errors(ws):
    nr,nc=vs.GetWSRowColumnCount(ws); errors=[]
    for r in range(1,nr+1):
        for c in range(1,nc+1):
            vals=[(0,vs.GetWSCellStringN(ws,r,c))]
            vals += [(s,vs.GetWSSubrowCellString(ws,r,c,s)) for s in range(1,vs.GetWSSubrowCount(ws,r)+1)]
            errors += [{'row':r,'column':c,'subrow':s,'value':v} for s,v in vals if v.startswith(('#NAME','#OBJ','#DIV/0','#VALUE','#REF'))]
    return errors


@command
def upsert_database_worksheet(p):
    """Create/update a formatted two-row live database report; existing resources require explicit update."""
    guard(p); name=p['name']; cols=batch(p['columns'],30); criteria=p['criteria']
    require(isinstance(criteria,str) and criteria.startswith('('),'Explicit native criteria required')
    for col in cols:
        require(isinstance(col['header'],str) and isinstance(col['formula'],str),'Header/formula strings required')
        number(col.get('width',150),'column width',True)
    size=number(p.get('font_size',10),'font size',True); ws=vs.GetObject(name)
    if ws:
        require(p.get('update',False),'Worksheet exists; set update=true to change its formulas')
        require(vs.GetTypeN(ws)==18 and vs.GetWSRowColumnCount(ws)==(2,len(cols)),'Existing worksheet shape/type differs; preserve it')
    else: ws=vs.CreateWS(name,2,len(cols)); require(ws,'CreateWS failed')
    vs.SetWSCellFormula(ws,2,0,2,0,'=DATABASE('+criteria+')')
    for c,col in enumerate(cols,1):
        vs.SetWSCellFormula(ws,1,c,1,c,col['header']); vs.SetWSCellFormula(ws,2,c,2,c,col['formula'])
        vs.SetWSColumnWidth(ws,c,c,int(col.get('width',150)))
    vs.SetWSCellTextFormat(ws,1,1,2,len(cols),vs.GetFontID('Arial'),int(size),0)
    vs.RecalculateWS(ws); errors=worksheet_errors(ws)
    return {'object_id':vs.GetObjectUuid(ws),'name':name,'database_rows':vs.GetWSSubrowCount(ws,2),'errors':errors,'valid':not errors}


@command
def place_shared_worksheet(p):
    """Place another image of ONE worksheet resource; paper-space anchor is top left."""
    guard(p); ws=named(p['worksheet'],18); target=sheet(p['sheet']); xy=point(p['position'],2); name=p['name']
    existing=vs.GetObject(name)
    if existing:
        require(vs.GetWSFromImage(existing)==ws and vs.GetLayer(existing)==target,'Image name collision')
        return {'object_id':vs.GetObjectUuid(existing),'worksheet_id':vs.GetObjectUuid(ws),'reused':True}
    prior=context()
    try:
        vs.Layer(p['sheet']); canonical=vs.GetWSImage(ws)
        if canonical:
            im=vs.HDuplicate(canonical,0,0); require(im and vs.SetParent(im,target),'Worksheet image duplication failed')
        else: im=vs.CreateWSImage(ws,xy)
        require(im,'Worksheet placement failed'); vs.SetName(im,name)
        (left,top),_=vs.GetBBox(im); vs.HMove(im,xy[0]-left,xy[1]-top)
        require(vs.GetWSFromImage(im)==ws,'Image does not reference the requested worksheet')
        return {'object_id':vs.GetObjectUuid(im),'worksheet_id':vs.GetObjectUuid(ws),'bounds':vs.GetBBox(im),'reused':False}
    finally: restore(prior)


@command
def update_title_block_data(p):
    """Update linked native title-block data; synchronize shared project fields before resetting any border."""
    guard(p); all_borders=[]; vs.ForEachObject(lambda h:all_borders.append(h),"(PON='Title Block Border')")
    require(all_borders,'No native title blocks; author/import a linked layout first')
    project=p.get('project',{}); sheet_rows=p.get('sheets',[]); plans=[]
    for h in all_borders: validate_fields(h,'Title Block Project Data',project)
    for row in sheet_rows:
        target=sheet(row['sheet']); matches=[h for h in all_borders if vs.GetLayer(h)==target]
        require(len(matches)==1,'Sheet must contain exactly one title block: '+row['sheet'])
        validate_fields(matches[0],'Title Block Sheet Data',row['fields']); plans.append((matches[0],row['fields']))
    # Shared defaults + ALL instances must be written before the first ResetObject.
    if project:
        put(named('Title Block Project Data'),'Title Block Project Data',project)
        for h in all_borders: put(h,'Title Block Project Data',project)
    for h,values in plans: put(h,'Title Block Sheet Data',values)
    for h in all_borders: vs.ResetObject(h)
    require(all(all(vs.GetRField(h,'Title Block Project Data',k)==scalar(v) for k,v in project.items()) for h in all_borders),'Shared project data failed to persist')
    return {'borders':len(all_borders),'sheets_updated':len(plans),'project':project}


@command
def get_sheet_paperwork_audit(p):
    """Read sheet contents without activation, regeneration, or worksheet recalculation."""
    names=batch(p.get('sheets'),10);limit=p.get('limit',25)
    require(all(isinstance(n,str) and n.strip() for n in names) and len(set(names))==len(names),'Unique sheet names required')
    require(type(limit) is int and 1<=limit<=100,'limit must be 1..100')
    sheets=[(name,sheet(name)) for name in names];out=[];issues=[];shared={};visited=set();nodes=0
    def issue(code,name,oid=None,severity='review',**extra):
        issues.append({'code':code,'severity':severity,'sheet':name,'object_id':oid,**extra})
    for name,layer in sheets:
        viewports=[];images=[];borders=[];numbers={}
        # Enter ordinary groups only; symbols, annotation groups and generated PIOs are separate scopes.
        stack=[vs.FInLayer(layer)]
        while stack:
            h=stack.pop()
            while h:
                nodes+=1;require(nodes<=10000,'More than 10000 sheet objects; narrow sheet scope')
                oid=vs.GetObjectUuid(h);require(oid and oid not in visited,'Missing/repeated sheet object UUID or traversal cycle')
                visited.add(oid);kind=vs.GetTypeN(h)
                if kind==11:stack.append(vs.FInGroup(h))
                elif kind==122:
                    scale=vs.GetObjectVariableReal(h,1003)
                    title=vs.GetObjectVariableString(h,1032);number_text=vs.GetObjectVariableString(h,1033)
                    require(isinstance(title,str) and isinstance(number_text,str),'Viewport metadata read failed')
                    valid_scale=isinstance(scale,(int,float)) and math.isfinite(scale) and scale>0
                    item={'object_id':oid,'name':vs.GetName(h),'class':vs.GetClass(h),
                          'drawing_title':title[:512],'drawing_number':number_text[:512],
                          'scale':scale if valid_scale else None,'view_type':vs.GetObjectVariableInt(h,1007),
                          'projection_type':vs.GetObjectVariableInt(h,1000),
                          'out_of_date':vs.GetObjectVariableBoolean(h,1004),'has_crop':vs.VPHasCropObject(h),
                          'metadata_truncated':len(title)>512 or len(number_text)>512}
                    viewports.append(item)
                    if not valid_scale:issue('invalid_viewport_scale',name,oid,'error')
                    if not title.strip():issue('missing_drawing_title',name,oid)
                    if not number_text.strip():issue('missing_drawing_number',name,oid)
                    else:numbers.setdefault(number_text.strip(),[]).append(oid)
                    if item['out_of_date']:issue('viewport_needs_update',name,oid)
                elif kind==56:
                    ws=vs.GetWSFromImage(h)
                    image={'object_id':oid,'name':vs.GetName(h),'class':vs.GetClass(h),'worksheet_id':None}
                    if not ws or vs.GetTypeN(ws)!=18:
                        issue('missing_worksheet_resource',name,oid,'error')
                    else:
                        wid=vs.GetObjectUuid(ws);require(wid,'Worksheet resource UUID unavailable')
                        scale=vs.GetWSImageScaleF(h);rows,cols=vs.GetWSRowColumnCount(ws)
                        require(type(rows) is int and type(cols) is int and rows>=0 and cols>=0,'Invalid worksheet dimensions')
                        valid=isinstance(scale,(int,float)) and math.isfinite(scale) and scale>0
                        image.update(worksheet_id=wid,worksheet=vs.GetName(ws),scale_factor=scale if valid else None,
                                     rows=rows,columns=cols)
                        if not valid:issue('invalid_worksheet_image_scale',name,oid,'error')
                        group=shared.setdefault(wid,{'worksheet_id':wid,'worksheet':vs.GetName(ws),'images':0,'sheets':set()})
                        group['images']+=1;group['sheets'].add(name)
                    images.append(image)
                elif kind==86 and plugin(h)=='Title Block Border':
                    borders.append({'object_id':oid,'name':vs.GetName(h),'class':vs.GetClass(h)})
                h=vs.NextObj(h)
        for number_text,ids in numbers.items():
            if len(ids)>1:issue('duplicate_drawing_number',name,severity='error',drawing_number=number_text[:512],viewport_ids=ids[:limit],count=len(ids))
        if not borders:issue('no_title_block_review',name)
        elif len(borders)>1:issue('multiple_title_blocks_review',name,count=len(borders))
        out.append({'sheet':name,'object_id':vs.GetObjectUuid(layer),
            'viewport_count':len(viewports),'worksheet_image_count':len(images),'title_block_count':len(borders),
            'viewports':viewports[:limit],'worksheet_images':images[:limit],'title_blocks':borders[:limit],
            'details_truncated':any(len(v)>limit for v in (viewports,images,borders))})
    issues.sort(key=lambda r:r['severity']!='error')
    resources=[{**r,'sheets':sorted(r['sheets'])} for r in shared.values()]
    resources.sort(key=lambda r:(r['worksheet'],r['worksheet_id']))
    return {'document':vs.GetFPathName(),'sheets':out,'issue_counts':dict(Counter(r['code'] for r in issues)),
        'issue_count':len(issues),'issues':issues[:limit],'issues_truncated':len(issues)>limit,
        'has_errors':any(r['severity']=='error' for r in issues),
        'worksheet_resource_count':len(resources),'worksheet_resources':resources[:limit],
        'worksheet_resources_truncated':len(resources)>limit,
        'scope':'Selected sheets and nested ordinary groups. Drawing numbers are unique within each sheet, not across the set. Shared worksheet identity is established by UUID. No changes or recalculation; no final visibility, annotations, linked title-block contents, inventory/formula accuracy, page fit, legibility or PDF physical-scale certification.'}


@command
def create_sheet_viewport(p):
    """Create a native orthographic viewport with explicit layer/class scope and model-bounds crop."""
    guard(p); target=sheet(p['sheet']); name=p['name']; require(not vs.GetObject(name),'Viewport name already exists')
    scale=number(p['scale'],'scale',True); bounds=point(p['bounds'],4); center=point(p['center'],2)
    x1,y1,x2,y2=bounds; require(x2>x1 and y1>y2,'Bounds order: left,top,right,bottom')
    view=p.get('view','plan'); require(view in ('plan','front','isometric'),'Unsupported view')
    layer_names=batch(p['layers']); layer_handles=[named(n,31) for n in layer_names]
    require(all(vs.GetObjectVariableInt(h,154)==1 for h in layer_handles),'Viewport input must be design layers')
    hidden=p.get('hidden_classes',[])
    for n in hidden:named(n,94)
    prior=context()
    try:
        vs.Layer(p['sheet']); vp=vs.CreateVP(target); require(vp,'CreateVP failed'); vs.SetName(vp,name)
        vs.SetObjectVariableReal(vp,1003,scale); vs.SetObjectVariableInt(vp,1000,6 if view=='plan' else 0)
        vs.SetObjectVariableInt(vp,1007,7 if view=='plan' else 3)
        vs.SetObjectVariableInt(vp,1001,6 if p.get('hidden_line',False) else 0)
        vs.SetObjectVariableBoolean(vp,1005,view=='plan')  # Project native 2D components (decks/lighting plans).
        vs.SetObjectVariableBoolean(vp,1035,True)
        vs.SetObjectVariableBoolean(vp,1030,False)
        vs.SetObjectVariableInt(vp,1047,1)
        if view!='plan': vs.SetViewMatrix(vp,(0,0,0),*(-90,0,0) if view=='front' else (-45,-35.264389682754654,-30))
        h=vs.FLayer()
        while h:
            if vs.GetObjectVariableInt(h,154)==1: vs.SetVPLayerVisibility(vp,h,0 if h in layer_handles else -1)
            h=vs.NextLayer(h)
        for i in range(1,vs.ClassNum()+1):
            n=vs.ClassList(i)
            helper=not p.get('include_helper_geometry',False) and any(s in n for s in HELPER_CLASSES)
            vs.SetVPClassVisibility(vp,n,-1 if n in hidden or helper else 0)
        vs.NameClass('None'); vs.Rect(x1/scale,y1/scale,x2/scale,y2/scale); crop=vs.LNewObj(); vs.SetFPat(crop,0)
        require(vs.SetVPCropObject(vp,crop),'Viewport crop failed')
        vs.ResetObject(vp); vs.ResetBBox(vp)
        dx=center[0]-(x1+x2)/(2*scale); dy=center[1]-(y1+y2)/(2*scale)
        vs.HMove(vp,dx,dy); vs.ResetBBox(vp); vs.UpdateVP(vp); vs.ResetBBox(vp)
        return {'object_id':vs.GetObjectUuid(vp),'scale':vs.GetObjectVariableReal(vp,1003),
                'bounds':vs.GetBBox(vp),'annotation_offset':[dx*scale,dy*scale],
                'note':'Bounds and annotation coordinates are view-plane coordinates; non-plan views require projected points.'}
    finally: restore(prior)


@command
def annotate_viewport(p):
    """Add native dimensions/text in the viewport plane with correct paper-point text sizing."""
    guard(p); vp=handle(p['viewport_id'],122); require(vs.GetObjectVariableInt(vs.GetLayer(vp),154)==2,'Sheet viewport required')
    scale=vs.GetObjectVariableReal(vp,1003); offset=point(p['annotation_offset'],2)
    items=batch(p['items']); names=[r['name'] for r in items]
    require(len(names)==len(set(names)) and not any(vs.GetObject(n) for n in names),'Annotation names must be new and unique')
    for row in items:
        require(row['kind'] in ('text','dimension'),'kind must be text/dimension'); point(row['position'],2)
        number(row.get('font_size',10),'font size',True)
        if row['kind']=='dimension': point(row['end'],2); number(row.get('offset',0)); require(row.get('direction','aligned') in ('horizontal','vertical','aligned'),'Invalid direction')
    prior=context(); out=[]
    try:
        vs.Layer(vs.GetLName(vs.GetLayer(vp))); vs.NameClass('None'); defaults_by_class()
        for row in items:
            a=point(row['position'],2); a=(a[0]+offset[0],a[1]+offset[1]); fs=number(row.get('font_size',10))
            if row['kind']=='dimension':
                b=point(row['end'],2); b=(b[0]+offset[0],b[1]+offset[1])
                dt={'horizontal':0,'vertical':1,'aligned':4}[row.get('direction','aligned')]
                vs.LinearDim(a,b,number(row.get('offset',0)),dt,769,1025,0); h=vs.LNewObj()
            else:
                txt=row['text']; vs.MoveTo(*a); vs.CreateText(txt); h=vs.LNewObj()
            require(h and vs.AddVPAnnotationObject(vp,h),'Annotation insertion failed'); vs.SetName(h,row['name'])
            attributes_by_class(h)
            if row['kind']=='dimension':
                # Reparenting can rescale text. Apply physical size AFTER adoption.
                vs.SetObjectVariableInt(h,28,vs.GetFontID('Arial'))
                vs.SetObjectVariableReal(h,17,fs/72*25.4*scale)
                vs.ResetObject(h)
            else:
                vs.SetTextFont(h,0,len(txt),vs.GetFontID('Arial'))
                vs.SetTextSize(h,0,len(txt),fs*scale/vs.GetLScale(vs.ActLayer()))
                vs.SetFPat(h,0)
            out.append(vs.GetObjectUuid(h))
        return {'object_ids':out,'scale':scale}
    finally: restore(prior)


@command
def save_document_checked(p):
    """Save the already-saved active file; verify the native result and actual disk artifact."""
    path=guard(p); result=vs.SaveActiveDocument(path)
    require(result==0,'SaveActiveDocument returned %s'%result)
    f=Path(path); require(f.is_file() and f.stat().st_size>0,'Saved artifact missing')
    return {'path':str(f),'bytes':f.stat().st_size,'modified_ns':f.stat().st_mtime_ns,'native_result':result}


@command
def export_sheet_set_checked(p):
    """Reuse configured native PDF settings, verify the actual output, then copy to requested destination."""
    guard(p); names=batch(p['sheets']); require(len(names)==len(set(names)),'Duplicate sheet names')
    for n in names: sheet(n)
    configured=Path(p['configured_output']); destination=Path(p['destination'])
    require(configured.is_absolute() and destination.is_absolute() and configured.suffix.lower()=='.pdf' and destination.suffix.lower()=='.pdf','Absolute PDF paths required')
    require(configured.parent.is_dir() and destination.parent.is_dir(),'Output directories must exist')
    before=configured.stat().st_mtime_ns if configured.exists() else None
    prior=context(); results=[]
    try:
        if p.get('configure',False):
            require(vs.AcquireExportPDFSettingsAndLocation(False),'PDF settings cancelled')
        require(vs.OpenPDFDocument(str(configured)),'Native PDF export could not open; configure the native PDF destination once')
        try:
            for name in names:
                vs.Layer(name); r=vs.ExportPDFPages(''); results.append({'sheet':name,'result':r})
                require(r==1,'Native page export failed: '+name)
        finally: vs.ClosePDFDocument()
    finally: restore(prior)
    require(configured.exists() and configured.stat().st_mtime_ns!=before,'Configured native destination differs or no PDF was written; no delivery copy made')
    with configured.open('rb') as f: require(f.read(5)==b'%PDF-','Output is not a PDF')
    if path_key(str(configured))!=path_key(str(destination)): shutil.copy2(configured,destination)
    return {'path':str(destination),'bytes':destination.stat().st_size,'pages_requested':results,
            'verification':'Native page return codes + updated PDF header/file. Independently render/check page count and scale.'}
