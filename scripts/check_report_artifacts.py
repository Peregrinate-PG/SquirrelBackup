#!/usr/bin/env python3
"""Check the filled report and the exact files covered by its visual review."""
import hashlib
import json
import sys
import xml.etree.ElementTree as E
from pathlib import Path
from zipfile import ZipFile


def check(root):
    root = Path(root)
    stem = '第3组_松鼠备份_实验报告'
    docx = root / 'docs' / (stem + '.docx')
    pdf = root / 'docs' / (stem + '.pdf')
    qa = json.loads((root / 'test-results/report-visual-qa.json').read_text())
    assert qa.get('visual_review_passed') is True, 'Report visual review is incomplete'
    assert qa['pages'] > 0 and qa['reviewed_pages'] == list(range(1, qa['pages'] + 1))
    assert hashlib.sha256(docx.read_bytes()).hexdigest() == qa['docx_sha256'], 'Report DOCX changed after review'
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == qa['pdf_sha256'], 'Report PDF changed after review'
    assert pdf.read_bytes().startswith(b'%PDF-'), 'Report PDF missing or invalid'
    allowed = {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}
    template = root / 'resources/实验报告模板.docx'
    preservation = json.loads((root / 'test-results/template-preservation.json').read_text())
    assert hashlib.sha256(template.read_bytes()).hexdigest() == preservation['template_sha256']
    with ZipFile(template) as original, ZipFile(docx) as report:
        assert report.testzip() is None, 'Report DOCX ZIP CRC failed'
        kept = [name for name in original.namelist() if name not in allowed]
        assert len(kept) == preservation['preserved_parts']
        assert all(original.read(name) == report.read(name) for name in kept), 'Template opaque part changed'
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        def sections(z):
            return [E.tostring(x) for x in E.fromstring(z.read('word/document.xml')).findall('.//w:sectPr', ns)]
        assert sections(original) == sections(report), 'Template page/section setup changed'
    return {'docx_sha256': qa['docx_sha256'], 'pdf_sha256': qa['pdf_sha256'], 'pages': qa['pages']}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1] if len(sys.argv) > 1 else '.'), ensure_ascii=False))
