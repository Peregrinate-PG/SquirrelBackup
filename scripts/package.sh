#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
RELEASE=dist/SquirrelBackup-0.1.1-macOS-arm64
rm -rf "$RELEASE"
mkdir -p "$RELEASE/source" "$RELEASE/documents" "$RELEASE/test-results"
rm -rf "$RELEASE/SquirrelBackup.app"
cp -R build/SquirrelBackup.app "$RELEASE/SquirrelBackup.app"
rm -rf "$RELEASE/SquirrelBackup.app/Contents/MacOS/SquirrelBackup.dSYM"
cp build/squirrel "$RELEASE/squirrel"
strip -S "$RELEASE/squirrel" "$RELEASE/SquirrelBackup.app/Contents/MacOS/SquirrelBackup"
codesign --force --sign - "$RELEASE/SquirrelBackup.app"
codesign --force --sign - "$RELEASE/squirrel"
codesign --verify --deep --strict "$RELEASE/SquirrelBackup.app"
cp -R include src tests scripts resources .vscode "$RELEASE/source/"
cp Makefile .gitignore .clang-format README.md LICENSE THIRD_PARTY.md CHANGELOG.md "$RELEASE/source/"
cp -R docs/. "$RELEASE/documents/"
cp -R docs "$RELEASE/source/"
cp -R presentations "$RELEASE/source/"
find "$RELEASE/source" -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir -p "$RELEASE/presentations"
cp -R presentations/. "$RELEASE/presentations/"
cp -R test-results/. "$RELEASE/test-results/"
mkdir -p "$RELEASE/source/vendor/googletest"
if [ -d vendor/googletest ]; then
  cp -R vendor/googletest/. "$RELEASE/source/vendor/googletest/"
else
  cp -R .tools/src/googletest/googletest "$RELEASE/source/vendor/googletest/"
  cp .tools/src/googletest/LICENSE "$RELEASE/source/vendor/googletest/"
fi
# Never bundle a parent workspace's unrelated Git history.
if [ "$(git rev-parse --show-toplevel 2>/dev/null || true)" = "$(pwd -P)" ]; then
  git bundle create "$RELEASE/source-history.bundle" --all
  git log --date=iso-strict --format='%h %ad %s' > "$RELEASE/source/版本管理记录.txt"
fi
cat > "$RELEASE/打开说明.txt" <<'NOTE'
松鼠备份 0.1.1 复核修订版

macOS Apple Silicon 应用；构建最低版本 13.0。其他机器需实际验收。
CLI：在终端执行 ./squirrel --help。
文档：documents 目录包含 PDF、HTML 与可编辑 Markdown。
验收与提交：先读 documents/08_提交前验收清单.md 和 09_复核结论与后续安排.md。
演示：presentations 为 0.1.0 原始草稿，测试数字、时间与人员信息须按新版文档修订。
源码：source 目录；执行 make all，make test 可离线构建与测试。
程序演示：在 source 执行 bash scripts/demo.sh。

软件仅做本地临时签名，未公证；未验收其他电脑上的 Gatekeeper 行为。
恢复目标必须是尚不存在的新路径。首次使用请先备份演示数据。
自动验证和人工未验收范围见 documents/03_软件测试报告.md 与 test-results。
人员信息、UML 手工绘图、演示视频和 AI 学习证书须本人补齐。
NOTE
(cd "$RELEASE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS)
python3 scripts/zip_release.py "$RELEASE"
shasum -a 256 "$RELEASE.zip" > "$RELEASE.zip.sha256"
printf 'Release ready: %s\n' "$RELEASE.zip"
