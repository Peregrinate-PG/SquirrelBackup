#!/usr/bin/env python3
"""Regression coverage for invalid jobs and polling changes, using isolated fixtures."""
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


def run(*args, ok=True, timeout=5):
    result = subprocess.run([BIN, *map(str, args)], capture_output=True,
                            text=True, timeout=timeout)
    if (result.returncode == 0) != ok:
        raise AssertionError(f'{args}: rc={result.returncode}\n{result.stderr}')
    return result


def case(name, fn):
    start = time.monotonic()
    try:
        fn()
    except Exception as error:
        RESULTS.append(dict(name=name, passed=False,
                            seconds=time.monotonic() - start, error=str(error)))
        print('FAIL', name, error)
    else:
        RESULTS.append(dict(name=name, passed=True, seconds=time.monotonic() - start))
        print('PASS', name)


def stop(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise AssertionError('Job did not respond to SIGINT')


with tempfile.TemporaryDirectory(prefix='squirrel-workflow-') as tmp:
    base = Path(tmp)
    source = base / 'source'
    source.mkdir()
    regular = base / 'regular-file'
    regular.write_text('not a directory')
    (source / 'sample.txt').write_text('sample')

    def invalid_source(command):
        repo = base / f'{command}-invalid-source'
        repo.mkdir()
        result = run(command, regular, repo, '--runs', '1', ok=False, timeout=3)
        assert 'Source must be a directory' in result.stderr, result.stderr
        assert not list(repo.iterdir()), 'Invalid job created a repository directory'

    case('FLOW-01 schedule rejects a file source immediately',
         lambda: invalid_source('schedule'))
    case('FLOW-02 watch rejects a file source immediately',
         lambda: invalid_source('watch'))

    def inappropriate_option(command, option):
        repo = base / f'{command}-wrong-option'
        repo.mkdir()
        result = run(command, source, repo, option, '1', '--runs', '1', ok=False)
        assert 'Option not valid for this command' in result.stderr, result.stderr
        assert not list(repo.iterdir()), 'Rejected options started a job'

    case('FLOW-03 schedule rejects ineffective --poll',
         lambda: inappropriate_option('schedule', '--poll'))
    case('FLOW-04 watch rejects ineffective --every',
         lambda: inappropriate_option('watch', '--every'))

    def preserved_mtime_change():
        src = base / 'watch-source'
        src.mkdir()
        sample = src / 'content.txt'
        sample.write_text('before')
        repo = base / 'watch-repository'
        repo.mkdir()
        process = subprocess.Popen([BIN, 'watch', str(src), str(repo), '--poll', '1',
                                    '--runs', '2'], text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not list(repo.rglob('snapshot-1.sqbk')):
                assert process.poll() is None, 'Watch terminated before first snapshot'
                if time.monotonic() >= deadline:
                    raise AssertionError('Initial snapshot did not appear')
                time.sleep(0.05)
            initial = sample.stat()
            sample.write_text('after!')
            os.utime(sample, ns=(initial.st_atime_ns, initial.st_mtime_ns))
            changed = sample.stat()
            assert changed.st_ino == initial.st_ino
            assert changed.st_size == initial.st_size
            assert changed.st_mtime_ns == initial.st_mtime_ns
            stdout, stderr = process.communicate(timeout=7)
            assert process.returncode == 0, stdout + stderr
            snapshots = sorted(repo.rglob('*.sqbk'))
            assert len(snapshots) == 2, stderr
            restored = base / 'watch-restored'
            run('restore', snapshots[-1], restored)
            assert (restored / 'content.txt').read_text() == 'after!'
        finally:
            stop(process)

    case('FLOW-05 watch detects same-size edits with preserved mtime', preserved_mtime_change)

    def no_self_trigger():
        repo = base / 'watch-idle'
        repo.mkdir()
        process = subprocess.Popen([BIN, 'watch', str(source), str(repo), '--poll', '1'],
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not list(repo.rglob('*.sqbk')):
                assert process.poll() is None, 'Watch terminated before first snapshot'
                if time.monotonic() >= deadline:
                    raise AssertionError('Initial snapshot did not appear')
                time.sleep(0.05)
            # Reading a source may update atime, but must not generate another snapshot.
            (source / 'sample.txt').read_bytes()
            time.sleep(2.5)
            assert len(list(repo.rglob('*.sqbk'))) == 1, 'Watch reacted to its own reads'
        finally:
            stdout, stderr = stop(process)
        assert process.returncode == 0, stdout + stderr

    case('FLOW-06 watch does not generate snapshots for unchanged sources', no_self_trigger)

output = Path('test-results')
output.mkdir(exist_ok=True)
(output / 'workflow-regression.json').write_text(
    json.dumps(RESULTS, ensure_ascii=False, indent=2))
print(f'{sum(result["passed"] for result in RESULTS)}/{len(RESULTS)} workflow tests passed')
sys.exit(0 if all(result['passed'] for result in RESULTS) else 1)
