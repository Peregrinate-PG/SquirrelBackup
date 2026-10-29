#!/usr/bin/env python3
"""Bounded running-process test with repeated edits and safe retention."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

binary = str(Path(sys.argv[1]).resolve())
duration = int(sys.argv[2]) if len(sys.argv) > 2 else 180
start = time.monotonic()
with tempfile.TemporaryDirectory(prefix="squirrel-stability-") as tmp:
    base = Path(tmp)
    src = base / "source"
    repo = base / "repo"
    src.mkdir()
    repo.mkdir()
    file = src / "changing.txt"
    file.write_text("version 0")
    (src / "constant.bin").write_bytes(os.urandom(1048576))
    with (base / "job.log").open("w") as log:
        process = subprocess.Popen(
            [binary, "schedule", str(src), str(repo), "--every", "2", "--keep", "3"],
            stdout=log,
            stderr=log,
        )
        edits = 0
        try:
            while time.monotonic() - start < duration:
                assert process.poll() is None, "Scheduler exited unexpectedly"
                edits += 1
                staged = src / "next.tmp"
                staged.write_text(f"version {edits}")
                staged.replace(file)
                time.sleep(0.4)
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=15) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    files = list(repo.glob("squirrel-job-*/*.sqbk"))
    assert len(files) == 3, f"Expected retention=3, got {len(files)}"
    for archive in files:
        subprocess.run([binary, "verify", str(archive)], capture_output=True, check=True)
    latest = max(files, key=lambda p: int(p.stem.split("-")[1]))
    subprocess.run(
        [binary, "restore", str(latest), str(base / "restored")], capture_output=True, check=True
    )
    text = (base / "restored" / "changing.txt").read_text()
    assert text.startswith("version ")
    from hashlib import sha256

    assert (
        sha256((src / "constant.bin").read_bytes()).digest()
        == sha256((base / "restored" / "constant.bin").read_bytes()).digest()
    )
    lines = (base / "job.log").read_text()
    result = dict(
        passed=True,
        duration_seconds=time.monotonic() - start,
        edits=edits,
        completed_snapshots=lines.count("Backup complete:"),
        retained=len(files),
        all_retained_verified=True,
        latest_content=text,
        constant_file_hash_equal=True,
    )
    Path(sys.argv[3] if len(sys.argv) > 3 else "test-results/stability.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps(result, indent=2))
