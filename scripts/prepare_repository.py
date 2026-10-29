#!/usr/bin/env python3
"""Prepare and verify a local GitHub handoff without contacting a remote."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]


def git(*arguments, cwd=ROOT, data=None):
    return subprocess.check_output(['git', *arguments], cwd=cwd, input=data)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_history():
    """Check reachable names and common credential signatures, without printing secrets."""
    objects = git('rev-list', '--objects', '--all').splitlines()
    sizes = git('cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)',
                data=b'\n'.join(row.split(b' ', 1)[0] for row in objects) + b'\n')
    metadata = {oid: (kind, int(size)) for oid, kind, size in
                (row.split() for row in sizes.splitlines())}
    signatures = {
        'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
        'github_token': rb'\bgh[pousr]_[A-Za-z0-9]{36,255}\b|\bgithub_pat_[A-Za-z0-9_]{40,255}\b',
        'aws_access_key': rb'\bAKIA[A-Z0-9]{16}\b',
        'aliyun_access_key': rb'\bLTAI[A-Za-z0-9]{16,30}\b',
    }
    findings, scanned, largest = [], 0, []
    forbidden = {'.env', 'credentials', 'cookies.json', 'storage-state.json', 'id_rsa', 'id_ed25519'}
    for row in objects:
        if b' ' not in row:
            continue
        oid, raw_name = row.split(b' ', 1)
        name = raw_name.decode('utf-8')
        kind, size = metadata[oid]
        if kind != b'blob':
            continue
        largest.append({'path': name, 'bytes': size})
        if Path(name).name in forbidden or '/个人证书/' in '/' + name:
            findings.append({'path': name, 'kind': 'private_file_name'})
        if size >= 100 * 1024 * 1024:
            findings.append({'path': name, 'kind': 'oversized_git_blob'})
        content = git('cat-file', 'blob', oid.decode())
        if b'\0' not in content[:8192]:
            scanned += 1
            for label, pattern in signatures.items():
                if re.search(pattern, content):
                    findings.append({'path': name, 'kind': label, 'object': oid.decode()})
    return {
        'method': 'Reachable Git object names, blob sizes and selected credential signatures',
        'reachable_objects': len(objects), 'text_blobs_scanned': scanned,
        'findings': findings,
        'largest_blobs': sorted(largest, key=lambda item: item['bytes'], reverse=True)[:5],
        'limits': 'Pattern checks do not prove the absence of every possible secret. '
                  'Student names and IDs in course documents are intentional; prefer a private repository.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_directory', type=Path)
    args = parser.parse_args()
    target = args.output_directory.resolve()
    zipped = target.with_suffix('.zip')
    if target.exists() or zipped.exists() or not target.parent.is_dir():
        raise SystemExit('Choose a new directory under an existing parent')
    if Path(git('rev-parse', '--show-toplevel').decode().strip()) != ROOT:
        raise SystemExit('Expected a dedicated project repository')
    if git('status', '--porcelain').strip():
        raise SystemExit('Commit the reviewed changes before preparing repository materials')
    audit = audit_history()
    if audit['findings']:
        raise SystemExit(json.dumps(audit['findings'], ensure_ascii=False))
    head = git('rev-parse', 'HEAD').decode().strip()
    branch = git('branch', '--show-current').decode().strip()
    if branch != 'main':
        raise SystemExit('Preparation expects the reviewed main branch')
    refs = git('for-each-ref', '--format=%(refname) %(objectname)',
               'refs/heads', 'refs/tags').decode().splitlines()
    with tempfile.TemporaryDirectory(prefix='repository-preparation-', dir=target.parent) as temp:
        stage = Path(temp) / target.name
        stage.mkdir()
        bundle = stage / 'source-history.bundle'
        git('bundle', 'create', str(bundle), '--all')
        with (stage / 'bundle-verification.log').open('wb') as log:
            subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        clone = Path(temp) / 'local-clone'
        with (stage / 'clone-verification.log').open('wb') as log:
            subprocess.run(['git', 'clone', '--no-hardlinks', str(bundle), str(clone)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['git', 'fsck', '--full'], cwd=clone,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        assert git('rev-parse', 'HEAD', cwd=clone).decode().strip() == head
        assert not git('status', '--porcelain', cwd=clone).strip()
        source = stage / 'source'
        source.mkdir()
        files = [name.decode() for name in git('ls-files', '-z').split(b'\0') if name]
        for name in files:
            original, copy = ROOT / name, source / name
            assert not original.is_symlink(), name
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, copy)
            assert digest(copy) == digest(clone / name), name
        dependency = ROOT / 'vendor/googletest'
        offline = stage / 'offline-dependencies/googletest'
        if dependency.exists():
            shutil.copytree(dependency, offline)
        else:
            dependency = ROOT / '.tools/src/googletest'
            shutil.copytree(dependency / 'googletest', offline / 'googletest')
            shutil.copy2(dependency / 'LICENSE', offline / 'LICENSE')
        plan = {
            'prepared_at': datetime.now(timezone.utc).isoformat(),
            'owner': 'Peregrinate-PG', 'suggested_name': 'SquirrelBackup',
            'suggested_visibility': 'private',
            'description': '第3组软件开发综合实验：macOS文件备份与恢复工具',
            'default_branch': branch, 'head': head, 'refs': refs,
            'bundle_sha256': digest(bundle), 'tracked_files_verified': len(files),
            'local_clone_and_fsck_passed': True,
            'remote_repository_created': False, 'remote_write_performed': False,
            'personal_certificates_included': False,
            'scope': 'Current local preparation snapshot; regenerate after final document review.',
        }
        (stage / 'repository-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
        (stage / 'history-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
        (stage / '真实提交记录.txt').write_bytes(
            git('log', '--all', '--date=iso-strict', '--format=%h %ad %an <%ae> %s'))
        guide = f'''# 第3组 GitHub仓库准备材料

拟用账号为Peregrinate-PG，仓库名SquirrelBackup，默认分支main。材料已在本地准备并验证，没有建立远程仓库，也没有上传文件。本快照对应提交{head[:12]}；报告补充和长测结束后应重新生成，最后发布经核对的版本。

## 包内材料

source是当前提交的全部跟踪文件；source-history.bundle保存真实Git历史；offline-dependencies附带GoogleTest离线构建依赖。JSON文件记录基线、文件数量和检查范围。个人证书不在包内，课程文档中保留小组姓名和学号，建议先建私有仓库，再按课程要求给老师访问权限。

历史作者和提交时间保持原样。不要把Codex提交改成成员姓名，也不要补造过去的协作记录。后续三人分别用自己的账号提交实际修改、测试或复核内容。

## 本地复核

在本目录打开终端，可执行以下步骤。它们只从本地bundle复制历史并构建，不连接GitHub。

```sh
git clone source-history.bundle SquirrelBackup
mkdir -p SquirrelBackup/vendor
cp -R offline-dependencies/googletest SquirrelBackup/vendor/googletest
cd SquirrelBackup
make -j4 all
make test
```

构建平台为macOS 13及以上的Apple Silicon，需要Command Line Tools。离线依赖由准备包单独附带，复制后显示为本地未跟踪文件属于正常现象；原Git历史没有改写。

## 批准发布后的操作

先在Peregrinate-PG账号下创建空的SquirrelBackup仓库，选择私有，不预先生成README、许可证或.gitignore。取得发布批准后，才在上面克隆的SquirrelBackup目录执行以下命令；本次没有执行。

```sh
git remote remove origin
git remote add origin https://github.com/Peregrinate-PG/SquirrelBackup.git
git push -u origin main
```

首次推送后应重新读取在线仓库的默认分支提交号，与repository-plan.json的head比较。若材料已更新，先重新准备并核对新提交号。网页上能看到文件和完整历史后，再把实际链接写入报告、答辩材料和提交检查表；拟定地址不能算在线仓库完成证据。

程序安装包和课程提交包单独交付，不必把历史ZIP、个人证书、账号会话或运行时缓存加进源码仓库。准备过程会扫描可达历史中的常见密钥格式和私密文件名，检查结果见history-audit.json；该扫描有明确范围，不等于证明不存在任何形式的敏感信息。
'''
        (stage / '00_仓库准备说明.md').write_text(guide)
        with (stage / 'SHA256SUMS').open('w') as hashes:
            for path in sorted(stage.rglob('*')):
                if path.is_file() and path != stage / 'SHA256SUMS':
                    hashes.write(digest(path) + '  ' + path.relative_to(stage).as_posix() + '\n')
        with ZipFile(zipped, 'x', ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    name = unicodedata.normalize('NFC',
                        (Path(target.name) / path.relative_to(stage)).as_posix())
                    archive.write(path, name)
        with ZipFile(zipped) as archive:
            assert archive.testzip() is None
            for row in archive.read(target.name + '/SHA256SUMS').decode().splitlines():
                expected, name = row.split('  ', 1)
                assert hashlib.sha256(archive.read(target.name + '/' + name)).hexdigest() == expected
        shutil.move(stage, target)
    zipped.with_suffix('.zip.sha256').write_text(digest(zipped) + '  ' + zipped.name + '\n')
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print(zipped)


if __name__ == '__main__':
    main()
