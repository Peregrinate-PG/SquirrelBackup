#!/usr/bin/env python3
"""Package the built application, CLI, and buildable source tree."""
import argparse
from pathlib import Path
import shutil
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

from submission_files import copy_source

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    version = subprocess.check_output([ROOT / "build/squirrel", "--version"], text=True).strip()
    target = args.output or ROOT / "dist" / f"SquirrelBackup-{version}-macOS-arm64"
    archive = target.with_name(target.name + ".zip")
    if target.exists() or archive.exists():
        raise SystemExit("Output already exists; choose a new directory with --output")
    target.mkdir(parents=True)
    shutil.copytree(
        ROOT / "build/SquirrelBackup.app",
        target / "SquirrelBackup.app",
        ignore=shutil.ignore_patterns("*.dSYM", ".DS_Store"),
    )
    shutil.copy2(ROOT / "build/squirrel", target / "squirrel")
    copy_source(ROOT, target / "source")
    with ZipFile(archive, "x", ZIP_DEFLATED) as package:
        for path in sorted(target.rglob("*")):
            package.write(path, Path(target.name) / path.relative_to(target))
    with ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
    print(archive)


if __name__ == "__main__":
    main()
