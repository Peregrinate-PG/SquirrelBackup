#!/usr/bin/env python3
"""Create task-local fontconfig settings for headless Office rendering on macOS."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
args = parser.parse_args()
output = args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
cache = output.parent / "font-cache"
cache.mkdir(exist_ok=True)
root = ET.Element("fontconfig")
for directory in ("/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts"):
    if Path(directory).is_dir():
        ET.SubElement(root, "dir").text = directory
ET.SubElement(root, "cachedir").text = str(cache)
aliases = {
    "宋体": ["Songti SC"],
    "SimSun": ["Songti SC"],
    "黑体": ["Heiti SC"],
    "SimHei": ["Heiti SC"],
    "微软雅黑": ["PingFang SC"],
    "Microsoft YaHei": ["PingFang SC"],
    "sans-serif": ["Arial", "PingFang SC"],
    "serif": ["Times New Roman", "Songti SC"],
}
for name, replacements in aliases.items():
    alias = ET.SubElement(root, "alias")
    ET.SubElement(alias, "family").text = name
    preferred = ET.SubElement(alias, "prefer")
    for replacement in replacements:
        ET.SubElement(preferred, "family").text = replacement
ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
print(output)
