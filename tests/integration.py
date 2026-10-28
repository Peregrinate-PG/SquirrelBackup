#!/usr/bin/env python3
"""Black-box CLI tests. All fixtures are disposable and isolated."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

BIN = str(Path(sys.argv[1]).resolve())
RESULTS = []

def run(*args, ok=True, env=None, timeout=30):
    p = subprocess.run([BIN, *map(str, args)], capture_output=True, text=True,
                       env=env, timeout=timeout)
    if (p.returncode == 0) != ok:
        raise AssertionError(f'{args}: rc={p.returncode}\n{p.stdout}\n{p.stderr}')
    return p

def case(name, fn):
    start = time.monotonic()
    try:
        fn()
    except Exception as error:
        RESULTS.append(dict(name=name, passed=False, seconds=time.monotonic()-start, error=str(error)))
        print('FAIL', name, error)
    else:
        RESULTS.append(dict(name=name, passed=True, seconds=time.monotonic()-start))
        print('PASS', name)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix='squirrel-integration-') as tmp:
    base = Path(tmp)
    src = base/'源目录'; src.mkdir()
    (src/'empty-dir').mkdir()
    (src/'a.txt').write_text('Hello 备份\n'*1000)
    (src/'binary.bin').write_bytes(bytes(range(256))*5000)
    (src/'skip.tmp').write_text('skip me')
    archive = base/'data.sqbk'
    case('CLI-01 help', lambda: run('--help'))
    case('CLI-02 backup', lambda: run('backup',src,archive))
    case('CLI-03 verify', lambda: run('verify',archive))
    case('CLI-04 list', lambda: run('list',archive))
    restored = base/'恢复目录'
    def roundtrip():
        run('restore',archive,restored)
        assert (restored/'empty-dir').is_dir()
        for name in ('a.txt','binary.bin','skip.tmp'):
            assert digest(src/name) == digest(restored/name)
    case('CLI-05 content hashes', roundtrip)
    case('CLI-06 restore no-clobber', lambda: run('restore',archive,restored,ok=False))
    case('CLI-07 backup no-clobber', lambda: run('backup',src,archive,ok=False))
    case('CLI-08 reject self-backup', lambda: run('backup',src,src/'bad.sqbk',ok=False))
    case('CLI-09 unknown option', lambda: run('backup',src,base/'x','--bogus','x',ok=False))
    case('CLI-10 missing value', lambda: run('backup',src,base/'x','--name',ok=False))
    case('CLI-11 invalid numeric option', lambda: run('backup',src,base/'x','--max-size','-1',ok=False))
    def filtered():
        file = base/'filtered.sqbk'
        run('backup',src,file,'--exclude','*.tmp','--name','*.txt')
        run('restore',file,base/'filtered')
        assert (base/'filtered'/'a.txt').exists()
        assert not (base/'filtered'/'binary.bin').exists()
        assert not (base/'filtered'/'skip.tmp').exists()
    case('CLI-12 combined filters',filtered)
    def encrypted():
        env = dict(os.environ, SQUIRREL_TEST_PASSWORD='test-password-2026')
        file = base/'encrypted.sqbk'
        run('backup',src,file,'--password-env','SQUIRREL_TEST_PASSWORD',env=env)
        assert 'test-password-2026'.encode() not in file.read_bytes()
        assert 'Hello 备份'.encode() not in file.read_bytes()
        run('verify',file,ok=False)
        run('restore',file,base/'encrypted-result','--password-env','SQUIRREL_TEST_PASSWORD',env=env)
        assert digest(src/'a.txt') == digest(base/'encrypted-result'/'a.txt')
    case('CLI-13 encrypted CLI',encrypted)
    def scheduled():
        repo = base/'jobs'; repo.mkdir(); (repo/'keep-me.sqbk').write_text('unrelated')
        run('schedule',src,repo,'--every','1','--keep','2','--runs','3',timeout=30)
        jobs = list(repo.glob('squirrel-job-*')); assert len(jobs) == 1
        files = list(jobs[0].glob('*.sqbk')); assert len(files) == 2
        assert (repo/'keep-me.sqbk').read_text() == 'unrelated'
        for file in files: run('verify',file)
    case('CLI-14 schedule retention isolation',scheduled)
    def watch():
        repo = base/'watch'; repo.mkdir()
        p = subprocess.Popen([BIN,'watch',str(src),str(repo),'--poll','1','--runs','4'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline = time.monotonic()+20
            while not list(repo.glob('squirrel-job-*/*.sqbk')):
                assert p.poll() is None and time.monotonic()<deadline
                time.sleep(0.1)
            def await_snapshot(number):
                deadline = time.monotonic()+20
                while not list(repo.glob(f'squirrel-job-*/snapshot-{number}.sqbk')):
                    assert p.poll() is None and time.monotonic()<deadline
                    time.sleep(0.1)
            (src/'changed.txt').write_text('new version')
            await_snapshot(2)
            (src/'changed.txt').rename(src/'renamed.txt')
            await_snapshot(3)
            (src/'renamed.txt').unlink()
            out, err = p.communicate(timeout=25)
            assert p.returncode == 0, out+err
            files = sorted(repo.glob('squirrel-job-*/*.sqbk'))
            assert len(files) == 4
            run('restore',files[2],base/'watch-renamed')
            assert (base/'watch-renamed'/'renamed.txt').read_text() == 'new version'
            run('restore',files[-1],base/'watch-restored')
            assert not (base/'watch-restored'/'changed.txt').exists()
            assert not (base/'watch-restored'/'renamed.txt').exists()
        finally:
            if p.poll() is None:
                p.terminate(); p.communicate(timeout=10)
    case('CLI-15 change detection',watch)
    def stop():
        repo = base/'stop'; repo.mkdir()
        p = subprocess.Popen([BIN,'schedule',str(src),str(repo),'--every','300'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline = time.monotonic()+20
            while not list(repo.glob('squirrel-job-*/*.sqbk')):
                assert p.poll() is None and time.monotonic()<deadline
                time.sleep(0.1)
            p.send_signal(signal.SIGINT); p.communicate(timeout=10)
            assert p.returncode == 0
        finally:
            if p.poll() is None: p.kill(); p.communicate()
    case('CLI-16 graceful stop',stop)
    case('CLI-17 invalid type filter',lambda:run('backup',src,base/'invalid','--type','z',ok=False))
    case('CLI-18 missing password env',lambda:run('verify',archive,'--password-env','SQUIRREL_MISSING_ENV',ok=False))
    def symlink_output():
        target = base/'broken.sqbk'; target.symlink_to('missing')
        run('backup',src,target,ok=False)
        assert target.is_symlink()
    case('CLI-19 do not overwrite dangling symlink',symlink_output)

output = Path('test-results'); output.mkdir(exist_ok=True)
(output/'integration.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2))
print(f'{sum(r["passed"] for r in RESULTS)}/{len(RESULTS)} integration tests passed')
sys.exit(0 if all(r['passed'] for r in RESULTS) else 1)
