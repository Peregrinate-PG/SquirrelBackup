#!/usr/bin/env python3
"""Read-only comparison of a prepared acceptance tree and a restored directory."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import sys

IGNORED = {'.DS_Store'}
# Desktop selection and newly created files can acquire these system labels
# after fixture preparation. Keep user-owned extended attributes strict.
IGNORED_XATTRS = {'com.apple.macl', 'com.apple.provenance'}
if sys.platform != 'darwin':
    raise SystemExit('此验收工具使用macOS扩展属性接口，请在Mac上运行。')
LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
LIBC.listxattr.restype = ctypes.c_ssize_t
LIBC.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                        ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
LIBC.getxattr.restype = ctypes.c_ssize_t
LIBC.setxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                        ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
LIBC.setxattr.restype = ctypes.c_int
XATTR_NOFOLLOW = 1


def attributes(path):
    encoded = os.fsencode(path)
    count = LIBC.listxattr(encoded, None, 0, XATTR_NOFOLLOW)
    if count < 0:
        raise OSError(ctypes.get_errno(), '无法读取扩展属性名称', str(path))
    if count == 0:
        return {}
    if count > 1024 * 1024:
        raise ValueError('扩展属性名称过多，超出验收工具范围。')
    names = ctypes.create_string_buffer(count)
    actual = LIBC.listxattr(encoded, names, count, XATTR_NOFOLLOW)
    if actual != count:
        raise ValueError('扩展属性在核对期间发生变化。')
    values = {}
    for name in sorted(names.raw.rstrip(b'\0').split(b'\0')):
        size = LIBC.getxattr(encoded, name, None, 0, 0, XATTR_NOFOLLOW)
        if size < 0:
            raise OSError(ctypes.get_errno(), '无法读取扩展属性长度', str(path))
        if size > 64 * 1024 * 1024:
            raise ValueError('扩展属性过大，超出验收工具范围。')
        buffer = ctypes.create_string_buffer(size)
        got = LIBC.getxattr(encoded, name, buffer, size, 0, XATTR_NOFOLLOW)
        if got != size:
            raise ValueError('扩展属性在核对期间发生变化。')
        values[name.decode('utf-8')] = hashlib.sha256(buffer.raw[:got]).hexdigest()
    return values


def set_demo_attribute(path):
    value = b'acceptance-fixture-only'
    if LIBC.setxattr(os.fsencode(path), b'user.squirrel.demo', value, len(value),
                    0, XATTR_NOFOLLOW) != 0:
        raise OSError(ctypes.get_errno(), '无法设置演示扩展属性', str(path))


def snapshot(root):
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('请选择真实目录，不能使用指向目录的软链接。')
    entries = {}
    regular_inodes = {}

    for directory, dirs, files, directory_fd in os.fwalk(root, follow_symlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED)
        relative_dir = Path(directory).relative_to(root)
        names = ['.'] if relative_dir == Path('.') else []
        names += sorted(dirs + [name for name in files if name not in IGNORED])
        for name in names:
            path = Path(directory) if name == '.' else Path(directory) / name
            relative = path.relative_to(root).as_posix()
            s = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            kind = ('directory' if stat.S_ISDIR(s.st_mode) else
                    'file' if stat.S_ISREG(s.st_mode) else
                    'symlink' if stat.S_ISLNK(s.st_mode) else
                    'fifo' if stat.S_ISFIFO(s.st_mode) else 'unsupported')
            item = {'type': kind, 'mode': s.st_mode & 0o777,
                    'uid': s.st_uid, 'gid': s.st_gid,
                    'xattrs_sha256': attributes(path)}
            if kind != 'directory':
                item['mtime_ns'] = s.st_mtime_ns
            if kind == 'symlink':
                item['target'] = os.readlink(name, dir_fd=directory_fd)
            elif kind == 'file':
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory_fd)
                with os.fdopen(fd, 'rb') as stream:
                    opened = os.fstat(stream.fileno())
                    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (s.st_dev, s.st_ino):
                        raise ValueError('文件在核对期间被替换：' + relative)
                    h = hashlib.sha256()
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(block)
                    after = os.fstat(stream.fileno())
                if (s.st_size, s.st_mtime_ns, s.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('文件在核对期间发生变化：' + relative)
                item.update(size=s.st_size, sha256=h.hexdigest())
                regular_inodes.setdefault((s.st_dev, s.st_ino), []).append(relative)
            elif kind == 'unsupported':
                raise ValueError('验收数据中含不支持的文件类型：' + relative)
            entries[relative] = item
    for names in regular_inodes.values():
        group = sorted(names)
        for name in names:
            entries[name]['hardlink_group'] = group
    return entries


def compare(expected, actual):
    differences = []
    for name in sorted(expected.keys() - actual.keys()):
        differences.append({'path': name, 'field': 'entry', 'expected': 'present', 'actual': 'missing'})
    for name in sorted(actual.keys() - expected.keys()):
        differences.append({'path': name, 'field': 'entry', 'expected': 'absent', 'actual': 'unexpected'})
    for name in sorted(expected.keys() & actual.keys()):
        for field in sorted(expected[name].keys() | actual[name].keys()):
            before, after = expected[name].get(field), actual[name].get(field)
            if field == 'xattrs_sha256':
                before = {k: v for k, v in (before or {}).items() if k not in IGNORED_XATTRS}
                after = {k: v for k, v in (after or {}).items() if k not in IGNORED_XATTRS}
            if before != after:
                differences.append({'path': name, 'field': field,
                                    'expected': expected[name].get(field), 'actual': actual[name].get(field)})
    return differences


def input_path(prompt):
    raw = input(prompt).strip()
    direct = Path(raw).expanduser()
    if direct.exists():
        return direct
    words = shlex.split(raw)
    if len(words) != 1:
        raise ValueError('请每次只拖入一个目录。')
    return Path(words[0]).expanduser()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fixture', type=Path, nargs='?')
    parser.add_argument('restored', type=Path, nargs='?')
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()
    if args.interactive:
        args.fixture = input_path('将“验收数据-日期”目录拖入窗口，然后按回车：\n')
        args.restored = input_path('将本次恢复出的目录拖入窗口，然后按回车：\n')
    if not args.fixture or not args.restored:
        parser.error('需要验收数据目录和恢复目录，或使用--interactive。')
    fixture = args.fixture.resolve(strict=True)
    baseline = json.loads((fixture / '验收基准.json').read_text())
    if baseline.get('format') != 'squirrel-acceptance-v1':
        raise ValueError('验收基准格式不正确。')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'scope': '文件和元数据自动核对，不证明真人GUI操作已完成。',
              'manual_gui_verified': False,
              'ignored_names': sorted(IGNORED),
              'ignored_system_xattrs': sorted(IGNORED_XATTRS),
              'excluded_metadata': ['atime', 'ctime', 'directory_mtime', 'birthtime', 'ACL', 'flags']}
    try:
        actual = snapshot(args.restored)
        differences = compare(baseline['entries'], actual)
        report.update(compared_entries=len(baseline['entries']), actual_entries=len(actual),
                      differences=differences, passed=not differences)
    except Exception as error:
        report['error'] = str(error)
    filename = '核对结果-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json'
    output = fixture / filename
    with output.open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('核对通过。' if report['passed'] else '核对未通过，请查看差异记录。')
    print(output)
    for item in report.get('differences', [])[:20]:
        print(item['path'], item['field'], '不一致')
    if report.get('error'):
        print(report['error'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        raise SystemExit('核对未执行：' + str(error))
