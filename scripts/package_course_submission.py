#!/usr/bin/env python3
"""Package the course deliverables without development archives or duplicate copies."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from check_report_artifacts import check as check_report
from submission_files import RESULT_FILES, copy_source

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    target = args.output_directory.resolve()
    archive = target.with_suffix(".zip")
    if target.exists() or archive.exists():
        raise SystemExit("Choose a new output directory")
    report = check_report(ROOT, require_current_inputs=True)
    review = json.loads((ROOT / "test-results/refinement-validation.json").read_text())
    if not review["passed"]:
        raise SystemExit("Source validation has not passed")
    for name, expected in review["inputs"].items():
        if digest(ROOT / name) != expected:
            raise SystemExit(f"Input changed after verification: {name}")
    presentation = json.loads((ROOT / "test-results/presentation-validation.json").read_text())
    if digest(ROOT / "presentations/第3组_松鼠备份_答辩.pptx") != presentation["finalSha256"]:
        raise SystemExit("Presentation changed after verification")
    target.mkdir(parents=True)

    def copy(relative, destination):
        source = ROOT / relative
        output = target / destination
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)

    for suffix in ("docx", "pdf"):
        name = f"第3组_松鼠备份_实验报告.{suffix}"
        copy(f"docs/{name}", f"01_实验报告/{name}")
    for suffix in ("pptx", "pdf"):
        name = f"第3组_松鼠备份_答辩.{suffix}"
        copy(f"presentations/{name}", f"02_答辩PPT/{name}")
    copy_source(ROOT, target / "03_源代码")
    for name in RESULT_FILES:
        copy(f"test-results/{name}", f"03_源代码/test-results/{name}")
    app = target / "04_可执行程序"
    app.mkdir()
    shutil.copytree(
        ROOT / "build/SquirrelBackup.app",
        app / "SquirrelBackup.app",
        ignore=shutil.ignore_patterns("*.dSYM", ".DS_Store"),
    )
    copy("build/squirrel", "04_可执行程序/squirrel")
    copy("resources/submission-guide/使用说明.pdf", "04_可执行程序/使用说明.pdf")
    copy("presentations/video/松鼠备份_115秒演示.mp4", "05_演示视频/松鼠备份_项目演示.mp4")
    copy("docs/uml/SquirrelBackup.mdj", "06_设计附件/SquirrelBackup.mdj")
    # The referenced view structures retain the upstream MIT notice.
    copy("scripts/LICENSE-StarUML-Samples.txt", "06_设计附件/LICENSE-StarUML-Samples.txt")

    files = sorted(path for path in target.rglob("*") if path.is_file())
    hashes = {path.relative_to(target).as_posix(): digest(path) for path in files}
    with ZipFile(archive, "x", ZIP_DEFLATED, compresslevel=9) as package:
        for path in files:
            if path.is_symlink():
                raise ValueError(f"Unexpected symbolic link: {path}")
            package.write(path, Path(target.name) / path.relative_to(target))
    with ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        for name, expected in hashes.items():
            actual = hashlib.sha256(package.read(f"{target.name}/{name}")).hexdigest()
            if actual != expected:
                raise RuntimeError(f"Archive content mismatch: {name}")
    # Packaging records stay beside the ZIP and are not course attachments.
    validation = {
        "passed": True,
        "archive_sha256": digest(archive),
        "file_count": len(files),
        "report_pages": report["pages"],
        "files": hashes,
        "ai_screenshot_pending": True,
        "school_submission_performed": False,
    }
    archive.with_suffix(".validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n"
    )
    archive.with_suffix(".zip.sha256").write_text(f"{digest(archive)}  {archive.name}\n")
    print(
        json.dumps(
            {"archive": str(archive), "files": len(files), "bytes": archive.stat().st_size},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
