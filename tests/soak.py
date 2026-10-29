#!/usr/bin/env python3
"""Bounded real-time soak. Separate from the short named regression test suite.

Uses only a newly created run directory, keeps raw logs, samples process memory,
and verifies actual retained archives periodically. Never reports a future pass.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import traceback


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    pending.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--seconds', type=int, default=72000)
    parser.add_argument('--checkpoint-seconds', type=int, default=300)
    args = parser.parse_args()
    if args.seconds < 12 or args.checkpoint_seconds < 5:
        parser.error('Use at least 12 seconds and checkpoint intervals of at least 5 seconds')
    binary = args.binary.resolve()
    base = args.run_directory.resolve()
    base.mkdir(parents=True, exist_ok=False)
    frozen = base / 'squirrel-under-test'
    shutil.copy2(binary, frozen)
    frozen.chmod(0o755)
    binary = frozen
    source = base / 'source'
    source.mkdir()
    (source / '空目录').mkdir()
    (source / 'constant.bin').write_bytes(os.urandom(256 * 1024))
    expected_hash = sha(source / 'constant.bin')
    os.link(source / 'constant.bin', source / 'hardlink.bin')
    os.symlink('constant.bin', source / 'symbolic-link')
    os.mkfifo(source / 'named-pipe')
    (source / 'changing.txt').write_text('revision=0\n')
    (source / 'read-only').mkdir()
    (source / 'read-only' / 'keep.txt').write_text('permission fixture\n')
    (source / 'read-only').chmod(0o555)
    env = dict(os.environ, SQUIRREL_SOAK_PASSWORD='local-soak-fixture-password')
    logs, processes, repos = {}, {}, {}
    begin = time.monotonic()
    result = dict(status='running', started_at=utc_now(), requested_seconds=args.seconds,
                  binary_sha256=sha(binary), version=subprocess.check_output(
                      [str(binary), '--version'], text=True).strip(),
                  pid=os.getpid(), edits=0, checkpoints=[], errors=[],
                  tested=['schedule', 'watch encrypted', 'retention', 'restore hashes',
                          'symlink', 'hardlink', 'FIFO', 'read-only directory', 'SIGINT cleanup'])
    write_json(base / 'status.json', result)

    def command(*params, encrypted=False):
        argv = [str(binary), *map(str, params)]
        if encrypted:
            argv += ['--password-env', 'SQUIRREL_SOAK_PASSWORD']
        return subprocess.run(argv, env=env, capture_output=True, text=True,
                              check=True, timeout=30)

    def check(final=False):
        point = dict(at=utc_now(), elapsed_seconds=time.monotonic() - begin,
                     edits=result['edits'], final=final, jobs={})
        check_dir = base / 'checkpoint'
        if check_dir.exists():
            # This tree contains only our restored fixture. Repair its read-only child.
            for directory, _, _ in os.walk(check_dir):
                Path(directory).chmod(0o700)
            shutil.rmtree(check_dir)
        check_dir.mkdir()
        for name, repo in repos.items():
            process = processes[name]
            if not final and process.poll() is not None:
                raise AssertionError(f'{name} exited unexpectedly: {process.returncode}')
            originals = sorted(repo.glob('squirrel-job-*/*.sqbk'),
                               key=lambda p: int(p.stem.split('-')[1]))
            if not originals:
                raise AssertionError(f'{name} has no completed snapshot')
            # At publication there may briefly be keep+1 files before retention finishes.
            if len(originals) > (3 if final else 4):
                raise AssertionError(f'{name} retention exceeded: {len(originals)}')
            encrypted = name == 'watch'
            copies = []
            for index, original in enumerate(originals):
                copy = check_dir / f'{name}-{index}.sqbk'
                try:
                    shutil.copyfile(original, copy)
                except FileNotFoundError:
                    if original == originals[-1] or final:
                        raise
                    continue  # The oldest snapshot can expire while copying.
                command('verify', copy, encrypted=encrypted)
                copies.append(copy)
            restored = check_dir / f'{name}-restored'
            command('restore', copies[-1], restored, encrypted=encrypted)
            assert sha(restored / 'constant.bin') == expected_hash
            assert (restored / 'hardlink.bin').stat().st_ino == (
                restored / 'constant.bin').stat().st_ino
            assert os.readlink(restored / 'symbolic-link') == 'constant.bin'
            import stat
            assert stat.S_ISFIFO((restored / 'named-pipe').stat().st_mode)
            assert (restored / 'read-only').stat().st_mode & 0o777 == 0o555
            revision_text = (restored / 'changing.txt').read_text()
            assert revision_text.startswith('revision=')
            revision = int(revision_text.strip().split('=')[1])
            assert 0 <= revision <= result['edits']
            rss = None
            if not final:
                sample = subprocess.run(['/bin/ps', '-o', 'rss=', '-p', str(process.pid)],
                                        text=True, capture_output=True)
                if sample.returncode == 0 and sample.stdout.strip():
                    rss = int(sample.stdout.strip()) * 1024
            point['jobs'][name] = dict(retained=len(originals), verified=len(copies),
                                      restored_revision=revision, rss_bytes=rss,
                                      metadata_and_hashes_passed=True)
        result['checkpoints'].append(point)
        result['elapsed_seconds'] = time.monotonic() - begin
        write_json(base / 'status.json', result)
        print(json.dumps(point, ensure_ascii=False), flush=True)

    try:
        for name in ['schedule', 'watch']:
            repo = base / f'{name}-repo'
            repo.mkdir()
            (repo / 'unrelated.sqbk').write_text('must be preserved')
            repos[name] = repo
            logs[name] = (base / f'{name}.log').open('w')
            argv = [str(binary), name, str(source), str(repo), '--keep', '3']
            argv += ['--every', '3'] if name == 'schedule' else [
                '--poll', '1', '--password-env', 'SQUIRREL_SOAK_PASSWORD']
            processes[name] = subprocess.Popen(argv, stdout=logs[name], stderr=logs[name], env=env)
        next_edit = begin + 1
        next_checkpoint = begin + max(10, args.checkpoint_seconds)
        while time.monotonic() - begin < args.seconds:
            for name, process in processes.items():
                assert process.poll() is None, f'{name} exited before deadline'
            now = time.monotonic()
            if now >= next_edit:
                result['edits'] += 1
                revision = result['edits']
                stage = source / 'next.tmp'
                stage.write_text(f'revision={revision}\n')
                stage.replace(source / 'changing.txt')
                # A burst followed by a stable interval exercises debounce and idle polling.
                next_edit = now + (0.15 if revision % 7 < 4 else 3.2)
            if now >= next_checkpoint:
                check()
                next_checkpoint = time.monotonic() + args.checkpoint_seconds
            time.sleep(0.1)
        # Let both jobs observe the final edit before testing graceful cancellation.
        time.sleep(3)
        for process in processes.values():
            process.send_signal(signal.SIGINT)
        for name, process in processes.items():
            assert process.wait(timeout=10) == 0, f'{name} did not stop cleanly'
        check(final=True)
        for name, repo in repos.items():
            assert (repo / 'unrelated.sqbk').read_text() == 'must be preserved'
            assert not list(repo.glob('squirrel-job-*/.squirrel-*'))
        result['status'] = 'passed'
    except BaseException as error:
        result['status'] = 'failed'
        result['errors'].append(dict(type=type(error).__name__, message=str(error),
                                     traceback=traceback.format_exc()))
    finally:
        for process in processes.values():
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs.values():
            log.close()
        result['finished_at'] = utc_now()
        result['elapsed_seconds'] = time.monotonic() - begin
        result['completed_snapshots'] = {
            name: (base / f'{name}.log').read_text().count('Backup complete:') for name in logs}
        result['retry_warnings'] = {
            name: (base / f'{name}.log').read_text().count('scheduled backup failed') for name in logs}
        write_json(base / 'status.json', result)
        print(json.dumps({key: value for key, value in result.items() if key != 'checkpoints'},
                         ensure_ascii=False, indent=2), flush=True)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
