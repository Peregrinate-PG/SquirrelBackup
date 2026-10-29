#!/usr/bin/env python3
"""Run bounded SQTREE parser fuzzing in a new disposable directory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('run_directory', type=Path)
    bound = parser.add_mutually_exclusive_group()
    bound.add_argument('--seconds', type=int, default=600)
    bound.add_argument('--runs', type=int)
    parser.add_argument('--seed', type=int, default=20261029)
    args = parser.parse_args()
    if args.seconds < 1 or (args.runs is not None and args.runs < 1):
        parser.error('Time and run bounds must be positive')
    binary = args.binary.resolve()
    build = json.loads(binary.with_name('build.json').read_text())
    if digest(binary) != build['binary_sha256']:
        raise RuntimeError('Fuzzer binary does not match its build record')
    run = args.run_directory.resolve()
    run.mkdir(parents=True, exist_ok=False)
    run.chmod(0o700)
    corpus = run / 'corpus'
    corpus.mkdir()
    artifacts = run / 'artifacts'
    artifacts.mkdir()
    seeds_dir = ROOT / 'tests/archive-fuzz-seeds'
    seeds = json.loads((seeds_dir / 'manifest.json').read_text())
    for seed in seeds:
        path = seeds_dir / seed['name']
        if path.parent != seeds_dir or digest(path) != seed['sha256']:
            raise RuntimeError('Seed name or checksum mismatch')
        shutil.copy2(path, corpus / path.name)
    result = dict(status='running', passed=False,
                  started_at=datetime.now(timezone.utc).isoformat(),
                  requested_seconds=args.seconds if args.runs is None else None,
                  requested_runs=args.runs, seed=args.seed,
                  engine=build['engine'], binary_sha256=digest(binary),
                  source_sha256=build['source_sha256'], seed_corpus=seeds,
                  scope='SQTREE parsing and Huffman decode with a null destination; '
                        'does not cover restoration writes, encryption, GUI or the whole project',
                  max_input_bytes=65536, rss_limit_mb=512)

    def save():
        pending = run / 'status.pending'
        pending.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        pending.replace(run / 'status.json')

    try:
        os.nice(max(0, 15 - os.getpriority(os.PRIO_PROCESS, 0)))
        result['nice'] = os.getpriority(os.PRIO_PROCESS, 0)
    except OSError as error:
        result['priority_note'] = str(error)
    limit = f'-runs={args.runs}' if args.runs is not None else f'-max_total_time={args.seconds}'
    command = [str(binary), str(corpus), limit, '-max_len=65536', f'-seed={args.seed}',
               '-timeout=5', '-rss_limit_mb=512', '-malloc_limit_mb=256',
               '-print_final_stats=1', '-use_value_profile=1',
               '-artifact_prefix=' + str(artifacts) + '/']
    result['command'] = command
    env = dict(os.environ, SQUIRREL_FUZZ_DIRECTORY=str(run),
               ASAN_OPTIONS='abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    started = time.monotonic()
    save()
    try:
        with (run / 'fuzzer.log').open('w') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            result['pid'] = process.pid
            while process.poll() is None:
                result['elapsed_seconds'] = round(time.monotonic() - started, 3)
                save()
                # Fixed-count smoke runs also have a wall-time bound.
                wall_limit = (args.seconds + 30) if args.runs is None else 600
                if result['elapsed_seconds'] > wall_limit:
                    process.kill()
                    process.wait()
                    raise RuntimeError('Fuzzer exceeded its wall-time allowance')
                time.sleep(1)
            result['exit_code'] = process.returncode
    except BaseException as error:
        if 'process' in locals() and process.poll() is None:
            process.kill()
            process.wait()
        result['runner_error'] = str(error)
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    text = (run / 'fuzzer.log').read_text(errors='replace')
    result['stats'] = {name: int(value) for name, value in
                       re.findall(r'stat::([a-z_]+):\s+(\d+)', text)}
    done = re.findall(r'#(\d+)\s+DONE\s+cov:\s+(\d+)\s+ft:\s+(\d+)', text)
    result['last_done'] = dict(zip(['runs', 'coverage_counters', 'features'],
                                   map(int, done[-1]))) if done else None
    result['artifacts'] = sorted(path.name for path in artifacts.iterdir())
    result['corpus_files'] = sum(path.is_file() for path in corpus.iterdir())
    result['sanitizer_error_markers'] = any(marker in text for marker in
        ['ERROR: AddressSanitizer', 'runtime error:', 'ERROR: libFuzzer'])
    bound_reached = (result['stats'].get('number_of_executed_units', 0) >= args.runs
                     if args.runs is not None else result['elapsed_seconds'] >= args.seconds)
    result['passed'] = bool(result.get('exit_code') == 0 and done and bound_reached
                            and not result['artifacts'] and not result['sanitizer_error_markers']
                            and 'runner_error' not in result)
    result['status'] = 'passed' if result['passed'] else 'failed'
    save()
    print(json.dumps({key: result[key] for key in ['status', 'elapsed_seconds', 'stats']}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
