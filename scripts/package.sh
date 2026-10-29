#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(build/squirrel --version)
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Unexpected version string.' >&2
  exit 2
fi
APP_VERSION=$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' build/SquirrelBackup.app/Contents/Info.plist)
[ "$VERSION" = "$APP_VERSION" ] || { echo 'CLI and GUI versions differ.' >&2; exit 2; }
python3 scripts/check_report_artifacts.py . --require-current-inputs
if [ "$(git rev-parse --show-toplevel 2>/dev/null || true)" != "$(pwd -P)" ]; then
  echo 'Package from the dedicated project repository.' >&2
  exit 2
fi
if [ -n "$(git status --porcelain)" ]; then
  echo 'Review and commit project changes before packaging.' >&2
  exit 2
fi
RELEASE="dist/SquirrelBackup-${VERSION}-macOS-arm64"
# The path is constrained to the project's generated dist directory.
rm -rf "$RELEASE"
mkdir -p "$RELEASE/source" "$RELEASE/documents" "$RELEASE/test-results"
cp -R build/SquirrelBackup.app "$RELEASE/SquirrelBackup.app"
rm -rf "$RELEASE/SquirrelBackup.app/Contents/MacOS/SquirrelBackup.dSYM"
cp build/squirrel "$RELEASE/squirrel"
strip -S "$RELEASE/squirrel" "$RELEASE/SquirrelBackup.app/Contents/MacOS/SquirrelBackup"
codesign --force --sign - "$RELEASE/SquirrelBackup.app"
codesign --force --sign - "$RELEASE/squirrel"
codesign --verify --deep --strict "$RELEASE/SquirrelBackup.app"
codesign --verify --strict "$RELEASE/squirrel"
# Export one reviewed commit; ignored scratch files never enter the release.
git archive HEAD | tar -x -C "$RELEASE/source"
test -f "$RELEASE/source/vendor/googletest/googletest/src/gtest-all.cc"
cp -R "$RELEASE/source/docs/." "$RELEASE/documents/"
cp -R "$RELEASE/source/presentations" "$RELEASE/presentations"
cp -R "$RELEASE/source/test-results/." "$RELEASE/test-results/"
git bundle create "$RELEASE/source-history.bundle" --all
mkdir -p "$RELEASE/version-history"
git log --date=iso-strict --format='%h %ad %an %s' > "$RELEASE/version-history/版本管理记录.txt"
git status --porcelain > "$RELEASE/version-history/打包时工作区状态.txt"
git rev-parse HEAD > "$RELEASE/version-history/历史基线提交.txt"
cat > "$RELEASE/打开说明.txt" <<NOTE
松鼠备份 ${VERSION} · 第3组

双击 SquirrelBackup.app；macOS 13.0及以上 Apple Silicon。
命令行：终端执行 ./squirrel --help。
先读 documents/08_提交前验收清单.md，了解本人仍需完成的项目。

报告：documents 中有课程Word模板报告、PDF和可编辑Markdown。
模型：documents/uml/SquirrelBackup.mdj，七张可编辑UML图。
答辩：presentations/第3组_松鼠备份_答辩.pptx、PDF及三分钟讲稿。
视频：presentations/video/松鼠备份_115秒演示.mp4，中文字幕，无音轨。
源码：source 中执行 make all、make test，可离线构建和验证。
历史：source-history.bundle保留Git历史，version-history记录本次打包提交；source内旧版本记录原样保留。
证据：test-results 与 documents/03_软件测试报告.md，持续运行按实际状态记录。

视频来自真实应用后台操作，不包含系统选择器与真人鼠标验收。
本地签名未经Apple公证，其他电脑启动需实际检查。
恢复目标必须是尚不存在的新目录，备份输出也不可覆盖已有文件。
当前材料完成状态见source/resources/submission-readiness.json与验收清单。
打包不等于已经提交课程平台，证书每人单独提交。
NOTE
python3 - "$RELEASE" "$VERSION" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
root=Path(sys.argv[1]);summary=json.loads((root/'test-results/summary.json').read_text())
assert sys.argv[2]==summary['version'], 'Test summary version differs from the build'
report=json.loads((root/'test-results/report-visual-qa.json').read_text())
manifest={'version':sys.argv[2],
          'source_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'tracked_source_files':len(subprocess.check_output(['git','ls-files','-z']).split(b'\0'))-1,
          'built_cli_sha256':hashlib.sha256(Path('build/squirrel').read_bytes()).hexdigest(),
          'test_summary_cli_sha256':summary['binary_sha256'],
          'packaged_cli_sha256':hashlib.sha256((root/'squirrel').read_bytes()).hexdigest(),
          'packaged_gui_sha256':hashlib.sha256((root/'SquirrelBackup.app/Contents/MacOS/SquirrelBackup').read_bytes()).hexdigest(),
          'report_docx_sha256':report['docx_sha256'],'report_pdf_sha256':report['pdf_sha256'],
          'note':'Packaged binaries have debug symbols stripped and are ad-hoc signed. The test summary identifies its own tested binary; an independent build may have different debug/link metadata.'}
(root/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with (root/'SHA256SUMS').open('w') as out:
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name!='SHA256SUMS':
            out.write(hashlib.sha256(path.read_bytes()).hexdigest()+'  ./'+path.relative_to(root).as_posix()+'\n')
PY
python3 scripts/zip_release.py "$RELEASE"
python3 - "$RELEASE.zip" <<'PY'
from pathlib import Path
import hashlib,sys
archive=Path(sys.argv[1])
Path(str(archive)+'.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
PY
printf 'Release ready: %s\n' "$RELEASE.zip"
