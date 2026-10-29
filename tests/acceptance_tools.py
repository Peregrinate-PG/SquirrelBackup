#!/usr/bin/env python3
"""Positive and negative checks for the optional manual-acceptance helper."""
import argparse
import ctypes
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    a = argparse.ArgumentParser()
    a.add_argument('binary', type=Path)
    a.add_argument('output', type=Path)
    args = a.parse_args()
    repo = Path(__file__).resolve().parents[1]
    binary = args.binary.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / 'fixture'
    helper = repo / 'scripts/verify_acceptance.py'
    subprocess.run([sys.executable, str(repo / 'scripts/prepare_acceptance.py'), str(fixture)],
                   check=True, capture_output=True, timeout=10)
    spec = importlib.util.spec_from_file_location('acceptance_helper', helper)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    source = fixture / '演示源目录'
    baseline = json.loads((fixture / '验收基准.json').read_text())['entries']
    env = dict(os.environ, ACCEPTANCE_TEST_PASSWORD='test-only-acceptance-password')
    cases = []

    def cli(*argv):
        subprocess.run([str(binary), *map(str, argv)], env=env, check=True,
                       capture_output=True, timeout=10)

    archives = {}
    for label, password in [('plain', []), ('encrypted', ['--password-env', 'ACCEPTANCE_TEST_PASSWORD'])]:
        archive = output / (label + '.sqbk')
        cli('backup', source, archive, *password)
        archives[label] = (archive, password)

    def run_case(name, mutation=None, field=None, encrypted=False, expect_error=False):
        record = {'name': name, 'passed': False}
        target = output / name
        archive, password = archives['encrypted' if encrypted else 'plain']
        try:
            cli('restore', archive, target, *password)
            if mutation:
                replacement = mutation(target)
                if replacement is not None: target = replacement
            existing = set(fixture.glob('核对结果-*.json'))
            r = subprocess.run([sys.executable, str(helper), str(fixture), str(target)],
                               capture_output=True, text=True, timeout=5)
            results = set(fixture.glob('核对结果-*.json')) - existing
            assert len(results) == 1
            detail = json.loads(results.pop().read_text())
            assert detail['manual_gui_verified'] is False
            expected_success = field is None and not expect_error
            assert (r.returncode == 0) == expected_success, r.stdout + r.stderr
            assert detail['passed'] == expected_success
            if field:
                assert any(item['field'] == field for item in detail['differences']), detail
            if expect_error:
                assert detail.get('error'), detail
            record.update(passed=True, comparison_passed=detail['passed'],
                          detected_fields=sorted({x['field'] for x in detail.get('differences', [])}),
                          reported_error=detail.get('error'))
        except Exception as error:
            record['error'] = repr(error)
        cases.append(record)
        print(('PASS' if record['passed'] else 'FAIL'), name, record.get('error', ''), flush=True)

    run_case('plain-roundtrip')
    run_case('encrypted-roundtrip', encrypted=True)

    def change_content(root):
        p = root / '说明.txt'; before = p.stat()
        data = bytearray(p.read_bytes()); data[0] ^= 1; p.write_bytes(data)
        os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns))
    run_case('detect-content-with-preserved-mtime', change_content, 'sha256')

    def change_link(root):
        p = root / '软链接'; p.unlink(); p.symlink_to('../outside-sentinel')
    sentinel = output / 'outside-sentinel'; sentinel.write_bytes(b'outside remains unchanged')
    run_case('detect-symlink-target', change_link, 'target')
    assert sentinel.read_bytes() == b'outside remains unchanged'

    def split_hardlink(root):
        p = root / '硬链接.txt'; q = root / 'replacement'
        shutil.copy2(p, q); q.replace(p)
    run_case('detect-broken-hardlink', split_hardlink, 'hardlink_group')
    run_case('detect-mode', lambda p: (p / '普通二进制.bin').chmod(0o600), 'mode')

    def change_attribute(root):
        value = b'different-attribute'
        rc = module.LIBC.setxattr(os.fsencode(root / '普通二进制.bin'), b'user.squirrel.demo',
                                 value, len(value), 0, module.XATTR_NOFOLLOW)
        assert rc == 0, ctypes.get_errno()
    run_case('detect-xattr', change_attribute, 'xattrs_sha256')

    def replace_fifo(root):
        p = root / '命名管道'; p.unlink(); p.write_bytes(b'')
    run_case('detect-fifo-type', replace_fifo, 'type')
    run_case('detect-missing-entry', lambda p: (p / '空文件.txt').unlink(), 'entry')

    def extra_file(root):
        (root / 'extra.txt').write_text('unexpected')
    run_case('detect-extra-entry', extra_file, 'entry')

    def finder_file(root):
        (root / '.DS_Store').write_bytes(b'finder-fixture-only')
    run_case('ignore-finder-store', finder_file)

    def symlink_root(root):
        alias = root.with_name(root.name + '-alias'); alias.symlink_to(root, target_is_directory=True)
        return alias
    run_case('reject-symlink-root', symlink_root, expect_error=True)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'passed': len(cases) == 12 and all(x['passed'] for x in cases),
              'scope': 'Checks the acceptance helper only; does not certify human GUI operation.',
              'baseline_entries': len(baseline), 'cases': cases}
    (output / 'acceptance-tools.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
