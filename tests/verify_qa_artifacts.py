"""Read-only PDF scale/text checks and hashes of the protected original deliverables.

Uses the bundled document runtime with pypdfium2. Does not edit Vectorworks.
"""
import hashlib
import json
from pathlib import Path
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'evidence/live-qa'
report={'pages':0,'details':[],'originals_unchanged':[]}
pdf=pdfium.PdfDocument(str(QA/'Velvet-Mirror-Toolkit-QA.pdf'))
assert len(pdf)==2
report['pages']=len(pdf)
for i in range(len(pdf)):
    page=pdf[i]
    assert page.get_size()==(2592.,1728.),page.get_size() # 36 x 24 inches
    text=page.get_textpage().get_text_range()
    assert 'TK-1' in text and 'TK-2' in text and 'OWN' in text and 'RENTAL' in text
    rectangles=[o.get_bounds() for o in page.get_objects() if o.type==2]
    # An 8 x 4 ft deck at 1:48 must print 144 x 72 pt, at the known QA placement.
    deck=[r for r in rectangles if all(abs(a-b)<.3 for a,b in zip(r,(816,954,960,1026))) ]
    assert deck, 'Actual PDF deck outline missing or wrong physical scale'
    if i==0:
        assert '8\'-0"' in text
        tp=page.get_textpage();char=tp.get_charbox(text.index('8\'-0"'))
        assert 6.5 < char[3]-char[1] < 8, '10-point dimension text not readable at paper scale'
    page.render(scale=.7).to_pil().save(str(QA/f'qa-page-{i+1}.png'))
    report['details'].append({'page':i+1,'size_points':page.get_size(),'text':text,'deck_outline_points':deck})
for item in json.loads((ROOT/'tests/original-artifact-hashes.json').read_text(encoding='utf-8-sig')):
    path=Path(item['Path'])
    actual=hashlib.sha256(path.read_bytes()).hexdigest().upper()
    assert actual==item['Hash'],f'Original changed: {path}'
    report['originals_unchanged'].append(str(path))
report['passed']=True
(QA/'pdf-and-originals-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PASS: two 24 x 36 sheets; deck printed 2 x 1 inches at 1:48; readable native dimension; shared inventories; original hashes unchanged.')
