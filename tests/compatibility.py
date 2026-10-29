#!/usr/bin/env python3
"""Check both archive directions against an explicitly supplied earlier binary."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

old, new = [str(Path(p).resolve()) for p in sys.argv[1:3]]
results = []
versions = {p: subprocess.check_output([p, '--version'], text=True).strip() for p in [old,new]}
env = dict(os.environ, SQUIRREL_COMPAT_PASSWORD='compatibility-fixture-password')
with tempfile.TemporaryDirectory(prefix='squirrel-compat-') as temp:
    base=Path(temp);src=base/'source';src.mkdir();(src/'empty').mkdir()
    (src/'中文.txt').write_text('归档格式兼容性\n'*1000)
    (src/'data.bin').write_bytes(bytes(range(256))*6000)
    os.symlink('中文.txt', src/'link');os.link(src/'data.bin',src/'hardlink');os.mkfifo(src/'pipe')
    for direction,writer,reader in [('old_to_new',old,new),('new_to_old',new,old)]:
        for encrypted in [False, True]:
            name=direction+('_encrypted' if encrypted else '_plain')
            archive=base/(name+'.sqbk');dest=base/name
            opts=['--password-env','SQUIRREL_COMPAT_PASSWORD'] if encrypted else []
            for args in [[writer,'backup',str(src),str(archive)], [reader,'verify',str(archive)],
                         [reader,'restore',str(archive),str(dest)]]:
                subprocess.run(args+opts+['--quiet'],env=env,capture_output=True,check=True)
            for f in ['中文.txt','data.bin']:
                assert hashlib.sha256((src/f).read_bytes()).digest()==hashlib.sha256((dest/f).read_bytes()).digest()
            assert os.readlink(dest/'link')=='中文.txt'
            assert (dest/'hardlink').stat().st_ino==(dest/'data.bin').stat().st_ino
            assert (dest/'empty').is_dir()
            results.append({'case':name,'writer':versions[writer],'reader':versions[reader],'passed':True})
out={'tested_at':datetime.now(timezone.utc).isoformat(),'results':results}
Path('test-results/compatibility-020.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
