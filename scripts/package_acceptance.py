#!/usr/bin/env python3
"""Create the human-acceptance kit in a new directory, without opening any UI."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = args.output.expanduser().absolute()
archive = output.with_name(output.name + ".zip")
if output.exists() or archive.exists():
    raise SystemExit("请选择尚不存在的工具包目录和ZIP名称。")
output.mkdir(parents=False)
(output / "tools").mkdir()
for name in ["prepare_acceptance.py", "verify_acceptance.py"]:
    shutil.copy2(root / "scripts" / name, output / "tools" / name)
for source in sorted((root / "resources/acceptance-kit").iterdir()):
    if source.suffix in (".command", ".pdf", ".txt"):
        shutil.copy2(source, output / source.name)
shutil.copy2(root / "docs/pdf/08_提交前验收清单.pdf", output / "提交前验收清单.pdf")
shutil.copy2(root / "test-results/acceptance-tools-020.json", output / "辅助工具自检.json")
rows = []
for line in (root / "docs/08_提交前验收清单.md").read_text().splitlines():
    if line.startswith("| G"):
        rows.append([x.strip() for x in line.strip("|").split("|")])
assert len(rows) == 12
with (output / "真人操作记录.csv").open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(
        ["编号", "操作", "预期", "结果", "执行人", "日期", "程序版本", "证据文件", "备注"]
    )
    for row in rows:
        writer.writerow([*row[:3], "待验", "", "", "0.2.0", "", ""])
with (output / "SHA256SUMS").open("w") as f:
    for p in sorted(output.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            f.write(
                hashlib.sha256(p.read_bytes()).hexdigest()
                + "  "
                + p.relative_to(output).as_posix()
                + "\n"
            )
with ZipFile(archive, "x", ZIP_DEFLATED, compresslevel=9) as zipped:
    for p in sorted(output.rglob("*")):
        if p.is_file():
            zipped.write(p, (Path(output.name) / p.relative_to(output)).as_posix())
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
with archive.with_name(archive.name + ".sha256").open("x") as f:
    f.write(checksum + "  " + archive.name + "\n")
print(
    json.dumps(
        {"directory": str(output), "archive": str(archive), "sha256": checksum}, ensure_ascii=False
    )
)
