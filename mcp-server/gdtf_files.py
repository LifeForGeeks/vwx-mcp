"""Bounded, read-only GDTF metadata and MVR embedded-mode validation. No extraction."""
import hashlib
import io
from pathlib import Path
from collections import Counter
import xml.etree.ElementTree as ET
from zipfile import ZipFile

MAX_BYTES=100*1024*1024

def require(test,message):
    if not test:raise ValueError(message)

def file_bytes(path,suffix):
    p=Path(path)
    require(p.is_absolute() and p.suffix.lower()==suffix and p.is_file(),'Existing absolute '+suffix+' file required')
    require(p.stat().st_size<=MAX_BYTES,'Archive exceeds 100 MB')
    with p.open('rb') as f:data=f.read(MAX_BYTES+1)
    require(len(data)<=MAX_BYTES,'Archive grew beyond 100 MB')
    return data

def xml_member(z,name):
    entries=z.infolist()
    require(len(entries)<=10000,'More than 10000 archive members')
    require(sum(e.filename==name for e in entries)==1,'Missing or duplicate '+name)
    info=z.getinfo(name);require(info.file_size<=16*1024*1024,'XML exceeds 16 MB')
    data=z.read(info)
    # Check decoded XML too: UTF-16 can hide declarations from an ASCII byte scan.
    probe=data.replace(b'\x00',b'').upper()
    require(b'<!DOCTYPE' not in probe and b'<!ENTITY' not in probe,'DTD/entity declarations unsupported')
    return ET.fromstring(data)

def gdtf_metadata(data):
    require(len(data)<=MAX_BYTES,'GDTF exceeds 100 MB')
    with ZipFile(io.BytesIO(data)) as z:
        root=xml_member(z,'description.xml')
        require(root.tag=='GDTF','Expected GDTF root')
        fixtures=root.findall('FixtureType');require(len(fixtures)==1,'Exactly one FixtureType required')
        fixture=fixtures[0];modes=[];names=set()
        references=list(fixture.iter('GeometryReference'))
        for mode in fixture.findall('./DMXModes/DMXMode'):
            name=mode.get('Name','');require(name and name not in names,'Missing/duplicate DMX mode name')
            names.add(name);require(len(names)<=200,'More than 200 modes')
            channels=mode.findall('./DMXChannels/DMXChannel');require(len(channels)<=10000,'More than 10000 channel definitions')
            spans={};virtual=0;unresolved=[]
            for channel in channels:
                offset=channel.get('Offset','None');br=channel.get('DMXBreak','1')
                if offset in ('None',''):
                    virtual+=1;continue
                try:
                    slots=[int(s.strip()) for s in offset.split(',')]
                    require(1<=len(slots)<=4 and all(1<=s<=512 for s in slots),'Invalid DMX channel offsets')
                    break_number=int(br);require(break_number>=1,'Invalid DMX break')
                except ValueError:
                    unresolved.append({'offset':offset,'break':br});continue
                spans[str(break_number)]=max(spans.get(str(break_number),0),max(slots))
            simple=not references and not unresolved and set(spans)<={'1'}
            modes.append({'name':name,'geometry':mode.get('Geometry',''),'channel_definitions':len(channels),
                'virtual_channels':virtual,'declared_break_spans':spans,'unresolved_channels':len(unresolved),
                'simple_single_break_footprint':spans.get('1',0) if simple else None})
        require(modes,'GDTF has no DMX modes')
        return {'sha256':hashlib.sha256(data).hexdigest(),'data_version':root.get('DataVersion',''),
            'fixture_name':fixture.get('Name',''),'manufacturer':fixture.get('Manufacturer',''),
            'fixture_type_id':fixture.get('FixtureTypeID',''),'modes':modes,
            'geometry_references':len(references),'model_count':len(fixture.findall('./Models/Model')),
            'scope':'Declared metadata and exact mode names. Simple footprint excludes geometry references and unresolved breaks; no manufacturer authenticity or geometry certification.'}

def inspect_gdtf(path,expected_sha256=None):
    result=gdtf_metadata(file_bytes(path,'.gdtf'))
    require(expected_sha256 is None or expected_sha256.lower()==result['sha256'],'GDTF file hash changed')
    return {'status':'ok','path':str(Path(path)),**result}

def audit_mvr(path,limit=50):
    require(type(limit) is int and 1<=limit<=100,'limit must be 1..100')
    data=file_bytes(path,'.mvr');issues=[];counts=Counter();groups=Counter();checked={}
    def issue(kind,uuid,**extra):
        counts[kind]+=1
        if len(issues)<limit:issues.append({'issue':kind,'object_id':uuid,**extra})
    with ZipFile(io.BytesIO(data)) as z:
        root=xml_member(z,'GeneralSceneDescription.xml')
        require(root.tag=='GeneralSceneDescription','Expected GeneralSceneDescription root')
        fixtures=list(root.iter('Fixture'));require(len(fixtures)<=10000,'More than 10000 fixtures')
        entries=Counter(z.namelist());total_embedded=0;seen=set()
        for fixture in fixtures:
            uuid=fixture.get('uuid','');spec=(fixture.findtext('GDTFSpec') or '').strip();mode=(fixture.findtext('GDTFMode') or '').strip()
            groups[(spec,mode)]+=1
            if not uuid or uuid.casefold() in seen:issue('missing_or_duplicate_fixture_uuid',uuid)
            seen.add(uuid.casefold())
            if not spec:
                issue('missing_gdtf_reference',uuid);continue
            if entries[spec]!=1:
                issue('missing_or_duplicate_embedded_gdtf',uuid,gdtf=spec);continue
            if spec not in checked:
                require(len(checked)<200,'More than 200 referenced GDTFs')
                total_embedded+=z.getinfo(spec).file_size;require(total_embedded<=MAX_BYTES,'Referenced GDTFs exceed 100 MB total')
                try:checked[spec]=gdtf_metadata(z.read(spec))
                except Exception as exc:checked[spec]={'error':str(exc)}
            metadata=checked[spec]
            if metadata.get('error'):
                issue('invalid_embedded_gdtf',uuid,gdtf=spec,error=metadata['error']);continue
            if not mode:issue('missing_gdtf_mode',uuid,gdtf=spec)
            elif mode not in {m['name'] for m in metadata['modes']}:issue('mode_not_in_embedded_gdtf',uuid,gdtf=spec,mode=mode)
    return {'status':'ok','path':str(Path(path)),'sha256':hashlib.sha256(data).hexdigest(),
        'mvr_version':root.attrib,'fixture_count':len(fixtures),'checked_gdtf_count':len(checked),
        'issue_counts':dict(counts),'issues':issues,'issues_truncated':sum(counts.values())>len(issues),
        'gdtf_mode_references_consistent':bool(fixtures) and not counts,
        'groups':[{'gdtf':spec,'mode':mode,'count':n} for (spec,mode),n in groups.most_common(limit)],
        'groups_truncated':len(groups)>limit,
        'scope':'Fixture UUID presence/uniqueness, embedded GDTF availability and exact mode references only. No transform, patch, external visualizer round trip or manufacturer certification.'}

def dispatch(command,p):
    try:
        if command=='get_gdtf_file':return inspect_gdtf(p['path'],p.get('expected_sha256'))
        if command=='get_mvr_gdtf_audit':return audit_mvr(p['path'],p.get('limit',50))
        raise ValueError('Unknown GDTF file command')
    except Exception as exc:return {'status':'error','error':str(exc),'retry_safe':True}
