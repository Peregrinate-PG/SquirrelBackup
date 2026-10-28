#!/usr/bin/env python3
"""Create a portable UTF-8 ZIP while preserving executable Unix permissions."""
from pathlib import Path
import os
import stat
import sys
import unicodedata
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root=Path(sys.argv[1])
output=Path(str(root)+'.zip')
with ZipFile(output,'w',compression=ZIP_DEFLATED,compresslevel=6) as archive:
    for path in [root]+sorted(root.rglob('*')):
        name=unicodedata.normalize('NFC',(Path(root.name)/path.relative_to(root)).as_posix())
        if path.is_symlink():
            info=ZipInfo(name);info.create_system=3
            info.external_attr=(path.lstat().st_mode & 0xffff)<<16
            archive.writestr(info,os.readlink(path).encode())
        else:
            archive.write(path,name+('/' if path.is_dir() else ''))
with ZipFile(output) as archive:
    if archive.testzip() is not None:raise SystemExit('ZIP CRC validation failed')
    for info in archive.infolist():
        if any(ord(c)>127 for c in info.filename) and not info.flag_bits & 0x800:
            raise SystemExit('ZIP UTF-8 filename flag is missing')
print('ZIP CRC and UTF-8 filename flags validated')
