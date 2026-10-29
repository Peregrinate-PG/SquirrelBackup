#!/usr/bin/env python3
"""Malformed valid-checksum archives exercise the parser beyond envelope checks."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time

binary = str(Path(sys.argv[1]).resolve())
results = []


def text(value):
    data = value.encode()
    return struct.pack("<I", len(data)) + data


def entry(kind, path, link="", size=0, mode=0o755):
    return (
        bytes([kind])
        + text(path)
        + struct.pack("<IIIqIqIQ", mode, os.getuid(), os.getgid(), 0, 0, 0, 0, size)
        + text(link)
        + struct.pack("<I", 0)
    )


def tree(records, count=None):
    return (
        b"SQTREE01"
        + struct.pack("<Q", len(records) if count is None else count)
        + b"".join(records)
        + b"SQEND001"
    )


def envelope(payload):
    body = b"SQBK0001" + bytes(36) + payload
    return body + hashlib.sha256(body).digest()


root = entry(1, "")
cases = {
    "SEC-01 parent traversal": tree([root, entry(2, "../escape")]),
    "SEC-02 absolute path": tree([root, entry(2, "/tmp/squirrel-escape")]),
    "SEC-03 repeated separators": tree([root, entry(2, "a//b")]),
    "SEC-04 dot component": tree([root, entry(2, "./a")]),
    "SEC-05 duplicate path": tree([root, entry(2, "same"), entry(2, "same")]),
    "SEC-06 symlink parent escape": tree([root, entry(3, "sym", "/tmp"), entry(2, "sym/escape")]),
    "SEC-07 hardlink external": tree([root, entry(4, "hard", "../escape")]),
    "SEC-08 unknown file type": tree([root, entry(99, "bad")]),
    "SEC-09 oversized entry count": tree([root], 1000001),
    "SEC-10 missing root": tree([entry(2, "bad")]),
    "SEC-11 size overflow": tree([root, entry(2, "bad", size=2**63)]),
    "SEC-12 invalid mode": tree([root, entry(2, "bad", mode=0o4777)]),
    "SEC-13 trailing tree data": tree([root]) + b"garbage",
    "SEC-14 NUL filename": tree([root, entry(2, "a\x00b")]),
    "SEC-15 missing parent directory": tree([root, entry(2, "a/b")]),
    "SEC-16 bad Huffman block": tree(
        [root, entry(2, "file", size=10) + struct.pack("<BII", 1, 10, 3) + b"bad"]
    ),
    "SEC-17 short raw block": tree(
        [root, entry(2, "file", size=10) + struct.pack("<BII", 0, 10, 3) + b"bad"]
    ),
}
with tempfile.TemporaryDirectory(prefix="squirrel-security-") as tmp:
    base = Path(tmp)
    for index, (name, payload) in enumerate(cases.items()):
        archive = base / f"{index}.sqbk"
        dest = base / f"output-{index}"
        archive.write_bytes(envelope(payload))
        p = subprocess.run(
            [binary, "restore", str(archive), str(dest)], capture_output=True, text=True, timeout=10
        )
        good = p.returncode != 0 and not dest.exists() and not (base / "escape").exists()
        results.append(dict(name=name, passed=good, output=p.stderr.strip()))
        print("PASS" if good else "FAIL", name)
    # Two publishers racing for the same filename must leave exactly one valid archive.
    src = base / "src"
    src.mkdir()
    (src / "data").write_bytes(b"A" * 1000000)
    target = base / "race.sqbk"
    commands = [[binary, "backup", str(src), str(target)] for _ in range(2)]
    ps = [subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for c in commands]
    for p in ps:
        p.communicate(timeout=20)
    verified = subprocess.run([binary, "verify", str(target)], capture_output=True).returncode == 0
    good = sorted(p.returncode for p in ps) == [0, 1] and verified
    results.append(dict(name="SEC-18 concurrent publication", passed=good))
    print("PASS" if good else "FAIL", "SEC-18 concurrent publication")
Path("test-results/security.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
sys.exit(0 if all(r["passed"] for r in results) else 1)
