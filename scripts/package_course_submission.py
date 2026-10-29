#!/usr/bin/env python3
"""Arrange an independently verified release for the course submission."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from zipfile import ZipFile, ZIP_DEFLATED


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_zip', type=Path)
    parser.add_argument('validation_json', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('--layout-check', action='store_true',
                        help='Prepare a layout preview without claiming submission readiness')
    parser.add_argument('--allow-deferred-ai', action='store_true',
                        help='Prepare the user-authorized handoff with the AI screenshot explicitly pending')
    args = parser.parse_args()
    archive = args.release_zip.resolve()
    validation = json.loads(args.validation_json.read_text())
    if not validation.get('passed') or validation.get('archive_sha256') != sha(archive):
        raise SystemExit('Release validation does not match this ZIP')
    target = args.output_directory.resolve()
    zipped = target.with_suffix('.zip')
    if target.exists() or zipped.exists() or not target.parent.is_dir():
        raise SystemExit('Choose a new output directory under an existing parent')
    with ZipFile(archive) as source_zip:
        assert source_zip.testzip() is None, 'Release CRC mismatch'
        roots = set()
        for entry in source_zip.infolist():
            name = PurePosixPath(entry.filename)
            assert not name.is_absolute() and '..' not in name.parts
            roots.add(name.parts[0])
        assert len(roots) == 1
    with tempfile.TemporaryDirectory(prefix='squirrel-course-', dir=target.parent) as scratch:
        subprocess.run(['ditto', '-x', '-k', str(archive), scratch], check=True)
        release = Path(scratch) / roots.pop()
        source = release / 'source'
        for row in (release / 'SHA256SUMS').read_text().splitlines():
            expected, name = row.split('  ', 1)
            assert sha(release / name) == expected, name
        check = [sys.executable, str(source / 'scripts/check_report_artifacts.py'), str(source)]
        if not args.layout_check:
            check.append('--require-current-inputs')
        subprocess.run(check, check=True, stdout=subprocess.DEVNULL)
        presentation = json.loads((release / 'test-results/presentation-validation.json').read_text())
        assert sha(release / 'presentations/第3组_松鼠备份_答辩.pptx') == presentation['finalSha256']
        if not args.layout_check:
            readiness = json.loads((source / 'resources/submission-readiness.json').read_text())
            required = ['online_group_confirmed', 'online_repository_verified',
                        'materials_consistent', 'final_visual_review_passed',
                        'local_acceptance_verified']
            assert all(readiness.get(key) is True for key in required), 'Submission checks incomplete'
            if args.allow_deferred_ai:
                assert readiness.get('report_body_complete') is True
                assert readiness.get('ai_screenshot_deferred_to_roommate') is True
                assert readiness.get('ai_evidence_included') is False
                assert readiness['remaining'] == ['roommate_ai_screenshot', 'other_two_certificates']
                assert (source / 'resources/submission-guide/补齐说明.txt').is_file()
            else:
                assert readiness.get('report_complete') is True and readiness.get('ai_evidence_included') is True
                assert readiness['remaining'] == ['other_two_certificates']
            guides = json.loads((source / 'test-results/submission-guides-qa.json').read_text())
            assert guides['passed'] and len(guides['files']) == 2
            for guide in guides['files']:
                assert guide['all_pages_visually_reviewed'] and guide['pages'] > 0
                assert sha(source / guide['file']) == guide['sha256'], 'Guide changed after review'
        target.mkdir()

        def copy_file(relative, destination):
            original = release / relative
            new = target / destination
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, new)
            assert sha(original) == sha(new)

        for suffix in ['docx', 'pdf']:
            name = '第3组_松鼠备份_实验报告.' + suffix
            copy_file('documents/' + name, '01_项目报告/' + name)
        for suffix in ['pptx', 'pdf']:
            name = '第3组_松鼠备份_答辩.' + suffix
            copy_file('presentations/' + name, '02_答辩材料/' + name)
        for name in ['演示讲稿.md', '讲稿数据.json']:
            copy_file('presentations/' + name, '02_答辩材料/讲稿/' + name)
        executable = target / '03_可执行程序'
        executable.mkdir()
        shutil.copytree(release / 'SquirrelBackup.app', executable / 'SquirrelBackup.app', symlinks=True)
        copy_file('squirrel', '03_可执行程序/squirrel')
        shutil.copytree(source, target / '04_项目源码', symlinks=True)
        copy_file('presentations/video/松鼠备份_115秒演示.mp4',
                  '05_演示视频/松鼠备份_项目演示.mp4')
        attachments = target / '06_设计与验证附件'
        attachments.mkdir()
        shutil.copytree(release / 'documents/uml', attachments / 'UML模型与图')
        shutil.copytree(release / 'test-results', attachments / '测试记录')
        for number in ['01', '02', '03', '06', '07', '08']:
            for file in (release / 'documents/pdf').glob(number + '_*.pdf'):
                copy_file(file.relative_to(release), Path('06_设计与验证附件/阅读文档') / file.name)
        copy_file('source-history.bundle', '06_设计与验证附件/版本记录/source-history.bundle')
        for name in ['版本管理记录.txt', '历史基线提交.txt']:
            metadata = 'version-history/' + name
            if args.layout_check and not (release / metadata).exists():
                metadata = 'source/' + name
            copy_file(metadata, '06_设计与验证附件/版本记录/' + name)
        readme = source / 'resources/submission-guide/00_阅读说明.pdf'
        if readme.exists():
            copy_file(readme.relative_to(release), '00_阅读说明.pdf')
        elif not args.layout_check:
            raise RuntimeError('Reviewed course reading guide missing')
        guide = source / 'resources/submission-guide/使用说明.pdf'
        if guide.exists():
            copy_file(guide.relative_to(release), '03_可执行程序/使用说明.pdf')
        elif not args.layout_check:
            raise RuntimeError('Reviewed application usage guide missing')
        kit_script = source / 'scripts/package_acceptance.py'
        if kit_script.exists():
            kit = attachments / '本机验收工具'
            subprocess.run([sys.executable, str(kit_script), str(kit)], check=True,
                           stdout=subprocess.DEVNULL)
            kit.with_name(kit.name + '.zip').unlink()
            kit.with_name(kit.name + '.zip.sha256').unlink()
        elif not args.layout_check:
            raise RuntimeError('Acceptance kit missing')
        if args.allow_deferred_ai and not args.layout_check:
            copy_file('source/resources/submission-guide/补齐说明.txt', '提交前补齐说明.txt')
        if args.layout_check:
            (target / '布局检查版.txt').write_text(
                '本目录只检查课程提交目录与文件复制。来源为已验证的历史候选包，'
                '没有合并后续修订，不是正式提交版。\n')
        record = dict(created_at=datetime.now(timezone.utc).isoformat(),
                      source_release_sha256=sha(archive), layout_check=args.layout_check,
                      external_submission_performed=False,
                      ai_screenshot_pending=bool(args.allow_deferred_ai),
                      school_submission_ready=not args.layout_check and not args.allow_deferred_ai)
        (target / '交付清单.json').write_text(json.dumps(record, indent=2) + '\n')
        with (target / 'SHA256SUMS').open('w') as hashes:
            for path in sorted(target.rglob('*')):
                if path.is_file() and path != target / 'SHA256SUMS':
                    hashes.write(sha(path) + '  ' + path.relative_to(target).as_posix() + '\n')
        with ZipFile(zipped, 'x', ZIP_DEFLATED, compresslevel=6) as package:
            for path in [target, *sorted(target.rglob('*'))]:
                assert not path.is_symlink(), 'Unexpected symlink in submission layout'
                name = unicodedata.normalize('NFC', (Path(target.name) / path.relative_to(target)).as_posix())
                package.write(path, name + ('/' if path.is_dir() else ''))
    with ZipFile(zipped) as package:
        assert package.testzip() is None
        hashes = package.read(target.name + '/SHA256SUMS').decode().splitlines()
        for row in hashes:
            expected, name = row.split('  ', 1)
            assert hashlib.sha256(package.read(target.name + '/' + name)).hexdigest() == expected
    zipped.with_suffix('.zip.sha256').write_text(sha(zipped) + '  ' + zipped.name + '\n')
    print(json.dumps(dict(archive=str(zipped), sha256=sha(zipped),
                         verified_hashes=len(hashes), layout_check=args.layout_check), ensure_ascii=False))


if __name__ == '__main__':
    main()
