#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
BIN="${SQUIRREL_BIN:-build/squirrel}"
if [ ! -x "$BIN" ]; then make cli; fi
TASK_DEMO="$(mktemp -d "$PWD/demo-XXXXXX")"
export TASK_DEMO
python3 - <<'PY'
import os
from pathlib import Path
root=Path(os.environ['TASK_DEMO'])/'源文件'
(root/'空目录').mkdir(parents=True)
(root/'课程资料').mkdir()
(root/'课程资料'/'说明.txt').write_text('松鼠备份课程演示\n'*5000)
(root/'随机数据.bin').write_bytes(os.urandom(65536))
(root/'排除.tmp').write_text('这份文件将被筛除')
os.symlink('课程资料/说明.txt',root/'说明快捷方式')
os.link(root/'课程资料'/'说明.txt',root/'说明硬链接')
os.mkfifo(root/'命名管道',0o600)
print('Demo source:',root)
PY
"$BIN" backup "$TASK_DEMO/源文件" "$TASK_DEMO/课程演示.sqbk" --exclude '*.tmp'
"$BIN" list "$TASK_DEMO/课程演示.sqbk"
"$BIN" verify "$TASK_DEMO/课程演示.sqbk"
"$BIN" restore "$TASK_DEMO/课程演示.sqbk" "$TASK_DEMO/恢复副本"
python3 - <<'PY'
import hashlib,os,stat
from pathlib import Path
base=Path(os.environ['TASK_DEMO']);src=base/'源文件';dst=base/'恢复副本'
for rel in ['课程资料/说明.txt','随机数据.bin']:
 assert hashlib.sha256((src/rel).read_bytes()).digest()==hashlib.sha256((dst/rel).read_bytes()).digest()
assert (dst/'空目录').is_dir()
assert not (dst/'排除.tmp').exists()
assert (dst/'说明快捷方式').is_symlink()
assert os.path.samefile(dst/'说明硬链接',dst/'课程资料/说明.txt')
assert stat.S_ISFIFO((dst/'命名管道').stat().st_mode)
print('PASS: 内容哈希、空目录、筛选、软硬链接与 FIFO。')
print('演示文件保留在',base)
PY
