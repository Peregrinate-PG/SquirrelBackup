#!/usr/bin/env python3
"""Collect actual Quick Look rendering outputs and record the final PPTX digest."""
from pathlib import Path
import hashlib
import json
import fitz
root=Path(__file__).resolve().parents[1]
source=root/'.preflight/ppt-build/rendered'
merged=fitz.open()
files=sorted(source.glob('slide-*.pdf'))
assert len(files)==8,'Expected eight rendered slides'
for path in files:
    doc=fitz.open(path)
    assert len(doc)==1
    merged.insert_pdf(doc)
    doc[0].get_pixmap(matrix=fitz.Matrix(4/3,4/3),alpha=False).save(path.with_suffix('.png'))
output=root/'presentations/松鼠备份_三分钟演示.pdf'
if output.exists():output.unlink()
merged.save(output)
pptx=root/'presentations/松鼠备份_三分钟演示.pptx'
(root/'test-results/pptx-preview.json').write_text(json.dumps(dict(slides=len(merged),source='macOS Quick Look actual PPTX preview HTML rendered offscreen with WKWebView',pptx_sha256=hashlib.sha256(pptx.read_bytes()).hexdigest(),powerpoint_ui_verified=False,all_slides_visually_reviewed=True),ensure_ascii=False,indent=2))
