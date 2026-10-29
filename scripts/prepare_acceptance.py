#!/usr/bin/env python3
"""Create fresh, disposable GUI acceptance data without changing existing files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit('Usage: python3 scripts/prepare_acceptance.py NEW_DIRECTORY')
base = Path(sys.argv[1]).expanduser().absolute()
base.mkdir(parents=False, exist_ok=False)
source = base / '演示源目录'
source.mkdir()
(source / '空文件夹').mkdir()
(source / '说明.txt').write_text('松鼠备份人工验收数据\n' * 200, encoding='utf-8')
(source / '普通二进制.bin').write_bytes(bytes(range(256)) * 4096)
(source / '应排除.tmp').write_text('筛选验收时应排除', encoding='utf-8')
(source / '空文件.txt').touch()
(source / '软链接').symlink_to('说明.txt')
os.link(source / '说明.txt', source / '硬链接.txt')
os.mkfifo(source / '命名管道')
(source / '只读文件夹').mkdir()
(source / '只读文件夹' / '内容.txt').write_text('只读目录恢复验收', encoding='utf-8')
(source / '只读文件夹').chmod(0o555)
(source / '普通二进制.bin').chmod(0o640)
(base / '备份仓库').mkdir()
manifest = {
    str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in source.rglob('*') if p.is_file() and not p.is_symlink()
}
(base / '内容SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
(base / '验收说明.txt').write_text(
    '此目录为人工验收生成的数据。请用 GUI 将演示源目录备份到此目录下的新 .sqbk 文件，'
    '再恢复到尚不存在的“恢复结果”文件夹。\n'
    '检查中文名、空目录、软硬链接、FIFO、权限和内容SHA256。\n'
    '测试加密时可用公开演示密码 course-demo-2026；不要用于个人数据。\n'
    '自动任务选择备份仓库，间隔2秒、保留2份。完成三份后停止并核对数量。\n'
    '完整步骤见 docs/08_提交前验收清单.md，未执行的步骤不能填写为通过。\n', encoding='utf-8')
print(base)
