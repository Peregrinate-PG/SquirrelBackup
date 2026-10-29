#!/usr/bin/env python3
"""Check the filled report and the exact files covered by its visual review."""
import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as E
from pathlib import Path
from zipfile import ZipFile


def check_inputs(root):
    root = Path(root).resolve()
    receipt = json.loads((root / 'test-results/report-build-inputs.json').read_text())
    docx = root / 'docs/第3组_松鼠备份_实验报告.docx'
    assert receipt['schema'] == 1
    assert hashlib.sha256(docx.read_bytes()).hexdigest() == receipt['docx_sha256'], 'Report build receipt belongs to another DOCX'
    required = {'scripts/build_template_report.py', 'resources/实验报告模板.docx',
                'resources/report-sections.json', 'docs/01_需求分析说明书.md',
                'docs/02_系统设计文档.md', 'docs/03_软件测试报告.md'}
    assert required <= receipt['input_files'].keys(), 'Incomplete report input receipt'
    for name, expected in receipt['input_files'].items():
        path = root / name
        assert path.resolve().is_relative_to(root), 'Report input path is outside the project'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Report input changed after generation: ' + name
    profile = json.loads((root / 'resources/submission-readiness.json').read_text())
    assert receipt['profile_fields'] == {'laboratory': profile['laboratory']}, 'Report profile changed after generation'
    subprocess.run([sys.executable, str(root / 'scripts/write_report.py'), '--check'], check=True)
    return len(receipt['input_files'])


def check(root, require_current_inputs=False):
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
    result = {'docx_sha256': qa['docx_sha256'], 'pdf_sha256': qa['pdf_sha256'], 'pages': qa['pages']}
    if require_current_inputs:
        result['current_inputs_verified'] = check_inputs(root)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='.')
    parser.add_argument('--require-current-inputs', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.root, args.require_current_inputs), ensure_ascii=False))
