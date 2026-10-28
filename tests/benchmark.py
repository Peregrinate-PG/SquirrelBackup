#!/usr/bin/env python3
"""Small reproducible workload; results describe this machine, not a performance guarantee."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
binary=str(Path(sys.argv[1]).resolve())
results=[]
with tempfile.TemporaryDirectory(prefix='squirrel-benchmark-') as tmp:
    base=Path(tmp)
    for name,size,random in [('repeated',32*1024*1024,False),('random',8*1024*1024,True)]:
        src=base/name;src.mkdir()
        with (src/'data.bin').open('wb') as f:
            for _ in range(size//1048576):f.write(os.urandom(1048576) if random else b'A'*1048576)
        archive=base/(name+'.sqbk')
        start=time.perf_counter()
        p=subprocess.run([binary,'backup',str(src),str(archive),'--quiet'],capture_output=True,text=True,check=True)
        backup=time.perf_counter()-start
        start=time.perf_counter()
        subprocess.run([binary,'restore',str(archive),str(base/(name+'-restored')),'--quiet'],capture_output=True,check=True)
        restore=time.perf_counter()-start
        original=hashlib.sha256((src/'data.bin').read_bytes()).hexdigest()
        restored=hashlib.sha256((base/(name+'-restored')/'data.bin').read_bytes()).hexdigest()
        assert original==restored
        rss=next((line.strip().split()[0] for line in p.stderr.splitlines() if 'maximum resident set size' in line),None)
        results.append(dict(workload=name,source_bytes=size,archive_bytes=archive.stat().st_size,backup_seconds=backup,restore_seconds=restore,max_rss_bytes=int(rss) if rss else None,sha256_equal=True))
Path('test-results/benchmark.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
