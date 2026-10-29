#!/usr/bin/env python3
"""Verify a locally produced release in a fresh directory; never open GUI windows."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

parser=argparse.ArgumentParser()
parser.add_argument('archive',type=Path)
parser.add_argument('output',type=Path,help='A new directory, whose parent already exists')
parser.add_argument('--with-gui-self-test', action='store_true',
                    help='Also exercise offscreen AppKit in a macOS graphical login session')
a=parser.parse_args();archive=a.archive.resolve();output=a.output.resolve()
if output.exists() or not output.parent.is_dir():raise SystemExit('Choose a new directory under an existing parent')
with ZipFile(archive) as z:
    assert z.testzip() is None,'ZIP CRC failed'
    roots=set()
    for entry in z.infolist():
        p=Path(entry.filename)
        assert not p.is_absolute() and '..' not in p.parts,'Unsafe ZIP path'
        roots.add(p.parts[0])
        if any(ord(c)>127 for c in entry.filename):assert entry.flag_bits&0x800,'Missing UTF-8 flag'
    assert len(roots)==1,'Expected one release directory'
output.mkdir();began=time.monotonic();checks=[]
def run(name,args,cwd=None,timeout=600):
    with (output/(name+'.log')).open('w') as f:
        proc=subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    checks.append({'name':name,'exit_code':proc.returncode,'passed':proc.returncode==0})
    if proc.returncode:raise RuntimeError(name+' failed; see log')
result={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'passed':False,'checks':checks}
try:
    run('extract',['ditto','-x','-k',archive,output])
    release=output/next(iter(roots));source=release/'source'
    records=(release/'SHA256SUMS').read_text().splitlines()
    for record in records:
        expected,name=record.split('  ',1);p=release/name
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected,'Hash mismatch: '+name
    result['verified_files']=len(records)
    assert os.access(release/'squirrel',os.X_OK),'CLI executable bit missing'
    assert os.access(release/'SquirrelBackup.app/Contents/MacOS/SquirrelBackup',os.X_OK),'GUI executable bit missing'
    run('cli-signature',['codesign','--verify','--strict',release/'squirrel'])
    run('app-signature',['codesign','--verify','--deep','--strict',release/'SquirrelBackup.app'])
    if a.with_gui_self_test:
        gui_results=output/'published-gui-selftest'
        run('published-gui',[release/'SquirrelBackup.app/Contents/MacOS/SquirrelBackup',
                             '--self-test',gui_results])
        gui=json.loads((gui_results/'gui-selftest.json').read_text())
        assert gui['passed'] and gui['assertions']==53,'Packaged GUI self-test failed'
        result['gui_assertions']=gui['assertions']
    run('version',[release/'squirrel','--version'])
    result['version']=(output/'version.log').read_text().strip()
    manifest=json.loads((release/'release-manifest.json').read_text())
    assert result['version']==manifest['version']
    for label,path in [('cli',release/'squirrel'),
                       ('gui',release/'SquirrelBackup.app/Contents/MacOS/SquirrelBackup')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['packaged_'+label+'_sha256']
    run('report-artifacts',[sys.executable,source/'scripts/check_report_artifacts.py',source,
                            '--require-current-inputs'])
    report=json.loads((output/'report-artifacts.log').read_text())
    for kind in ('docx','pdf'):
        digest=report[kind+'_sha256']
        assert digest==manifest['report_'+kind+'_sha256']
        assert hashlib.sha256((release/'documents'/('第3组_松鼠备份_实验报告.'+kind)).read_bytes()).hexdigest()==digest
    result['report_pages']=report['pages']
    history=output/'history-check'
    run('git-history',['git','clone',release/'source-history.bundle',history])
    run('git-bundle',['git','bundle','verify',release/'source-history.bundle'],cwd=history)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=history,text=True).strip()
    assert commit==(release/'version-history/历史基线提交.txt').read_text().strip()==manifest['source_head']
    names=subprocess.check_output(['git','ls-files','-z'],cwd=history).decode().rstrip('\0').split('\0')
    assert len(names)==manifest['tracked_source_files']
    actual={path.relative_to(source).as_posix() for path in source.rglob('*') if path.is_file()}
    assert actual==set(names), 'Packaged source file set differs from the committed tree'
    for name in names:
        assert (history/name).read_bytes()==(source/name).read_bytes(), 'Source differs from history: '+name
    result['source_files_matched_to_history']=len(names)
    result['source_head']=commit
    run('offline-build-test',['make','-j4','all','test'],cwd=source)
    unit=ET.parse(source/'test-results/unit.xml').getroot()
    assert int(unit.attrib['failures'])==int(unit.attrib['errors'])==0
    counts={'unit':int(unit.attrib['tests'])}
    for group in ['integration','security','workflow-regression']:
        rows=json.loads((source/'test-results'/(group+'.json')).read_text())
        assert rows and all(row['passed'] for row in rows)
        counts[group]=len(rows)
    result['rebuilt_core_tests']=counts
    # Exercise the distributed executable too, not only the freshly linked CLI.
    published_tests=output/'published-cli-tests'
    published_tests.mkdir()
    for name,script in [('integration','integration.py'),('security','adversarial.py'),
                        ('workflow-regression','workflow_regression.py')]:
        run('published-'+name,[sys.executable,source/'tests'/script,release/'squirrel'],
            cwd=published_tests)
        rows=json.loads((published_tests/'test-results'/(name+'.json')).read_text())
        assert len(rows)==counts[name] and all(row['passed'] for row in rows)
    result['packaged_cli_cases_replayed']=sum(counts[n] for n in counts if n!='unit')
    run('demo-cli',['bash','scripts/demo.sh'],cwd=source)
    fixture=output/'published-smoke';fixture.mkdir();(fixture/'source').mkdir()
    (fixture/'source'/'中文.txt').write_text('Release binary round trip\n')
    run('published-backup',[release/'squirrel','backup',fixture/'source',fixture/'smoke.sqbk'])
    run('published-verify',[release/'squirrel','verify',fixture/'smoke.sqbk'])
    run('published-restore',[release/'squirrel','restore',fixture/'smoke.sqbk',fixture/'restored'])
    assert (fixture/'restored/中文.txt').read_bytes()==(fixture/'source/中文.txt').read_bytes()
    result['passed']=True
except BaseException as error:
    result['error']=str(error)
finally:
    result['elapsed_seconds']=time.monotonic()-began
    (output/'release-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(0 if result['passed'] else 1)
