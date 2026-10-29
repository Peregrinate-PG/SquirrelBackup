"""Select the files needed to build and test the application."""

from pathlib import Path
import shutil

ROOT_FILES = (
    ".clang-format",
    ".gitattributes",
    ".gitignore",
    "Makefile",
    "README.md",
    "LICENSE",
    "THIRD_PARTY.md",
)
SOURCE_DIRS = ("src", "include", "tests", "vendor")
SUPPORT_FILES = (
    "resources/Info.plist",
    "scripts/demo.sh",
    "scripts/prepare_acceptance.py",
    "scripts/verify_acceptance.py",
    "scripts/build_archive_fuzzer.py",
    "scripts/video_inspect.mm",
    "scripts/package.sh",
    "scripts/package_software.py",
    "scripts/submission_files.py",
    "scripts/LICENSE-StarUML-Samples.txt",
)
RESULT_FILES = (
    "unit.xml",
    "integration.json",
    "security.json",
    "workflow-regression.json",
    "test-matrix.csv",
    "summary.json",
    "gui-selftest.json",
    "gui-desktop-cases.json",
    "desktop-restore-comparison.json",
    "signals-020.json",
    "fault-injection-020.json",
    "compatibility-020.json",
    "benchmark.json",
)


def source_files(root):
    root = Path(root)
    files = {root / name for name in (*ROOT_FILES, *SUPPORT_FILES)}
    for directory in SOURCE_DIRS:
        for path in (root / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store":
                files.add(path)
    return sorted(files)


def copy_source(root, target):
    root, target = Path(root), Path(target)
    target.mkdir(parents=True, exist_ok=False)
    for source in source_files(root):
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Missing or unexpected source file: {source}")
        destination = target / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
