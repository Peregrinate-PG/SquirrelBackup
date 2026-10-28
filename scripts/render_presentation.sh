#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .preflight/ppt-build/quicklook .preflight/ppt-build/rendered
clang++ -std=c++17 -fobjc-arc -Wno-deprecated-declarations -framework Cocoa -framework WebKit scripts/render_ppt_preview.mm -o .preflight/ppt-build/render_preview
qlmanage -p -o .preflight/ppt-build/quicklook presentations/松鼠备份_三分钟演示.pptx
.preflight/ppt-build/render_preview "$PWD/.preflight/ppt-build/quicklook/松鼠备份_三分钟演示.pptx.qlpreview/Preview.html" "$PWD/.preflight/ppt-build/rendered"
.tools/venv/bin/python scripts/collect_presentation_preview.py
