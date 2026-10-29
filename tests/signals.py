#!/usr/bin/env python3
"""Send real OS signals during observed I/O, using only disposable fixtures."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "binary_sha256": digest(binary),
        "fixture_bytes": 256 * 1024 * 1024,
        "results": results,
        "passed": False,
    }

    def run(*arguments, env):
        return subprocess.run(
            [str(binary), *map(str, arguments)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

    def interrupt(name, arguments, env, parent, pattern, signum, expected, validate, wait_for=None):
        process = subprocess.Popen(
            [str(binary), *map(str, arguments)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        started = time.monotonic()
        try:
            deadline = started + 45
            observed = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("Process finished before I/O observation")
                if wait_for is None or wait_for():
                    for path in parent.glob(pattern):
                        try:
                            size = path.stat().st_size
                        except FileNotFoundError:
                            continue
                        if size >= 4 * 1024 * 1024:
                            observed = {"path": str(path.relative_to(parent)), "bytes": size}
                            break
                if observed:
                    break
                time.sleep(0.001)
            assert observed, "No active I/O observed within 45 seconds"
            sent = time.monotonic()
            process.send_signal(signum)
            stdout, stderr = process.communicate(timeout=10)
            latency = time.monotonic() - sent
            (output / (name + ".log")).write_text(stdout + stderr)
            assert process.returncode == expected, (process.returncode, stdout, stderr)
            if expected == 130:
                assert "Cancelled; incomplete output removed." in stderr
                assert not stdout, "Cancelled operation unexpectedly emitted a result"
            assert not list(parent.rglob(".squirrel-*")), "Private staging directory remains"
            validate()
            results.append(
                {
                    "name": name,
                    "signal": signal.Signals(signum).name,
                    "observed_io": observed,
                    "exit_code": process.returncode,
                    "exit_after_signal_seconds": round(latency, 4),
                    "passed": True,
                }
            )
            print("PASS", name, f"{latency:.4f}s", flush=True)
        except BaseException as error:
            results.append({"name": name, "passed": False, "error": str(error)})
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)

    def absent(path):
        assert not path.exists(), "Cancelled output was published: " + str(path)

    try:
        with tempfile.TemporaryDirectory(prefix="signal-fixture-", dir=output) as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            data = source / "data.bin"
            with data.open("wb") as file:
                file.write(b"Squirrel signal cancellation fixture\n")
                file.truncate(report["fixture_bytes"])
            original = digest(data)
            env = dict(os.environ, SQUIRREL_SIGNAL_PASSWORD="fixture-password-only")
            for encrypted in (False, True):
                label = "encrypted" if encrypted else "plain"
                password = ["--password-env", "SQUIRREL_SIGNAL_PASSWORD"] if encrypted else []
                archive = root / (label + ".sqbk")
                run("backup", source, archive, "--no-compress", *password, env=env)
                archive_hash = digest(archive)
                for signum in (signal.SIGINT, signal.SIGTERM):
                    sig = signal.Signals(signum).name
                    for command in ("backup", "restore", "verify", "list"):
                        name = f"{label}-{command}-{sig}"
                        case = root / name
                        case.mkdir()
                        case_env = dict(env, TMPDIR=str(case))
                        target = case / "result"
                        if command == "backup":
                            arguments = ["backup", source, target, "--no-compress", *password]
                            pattern = ".squirrel-*/tree"
                        elif command == "restore":
                            arguments = ["restore", archive, target, *password]
                            pattern = ".squirrel-*/restored/data.bin"
                        else:
                            arguments = [command, archive, *password]
                            pattern = ".squirrel-*/tree"
                        interrupt(
                            name,
                            arguments,
                            case_env,
                            case,
                            pattern,
                            signum,
                            130,
                            lambda: absent(target),
                        )
                assert digest(archive) == archive_hash, "Original archive changed"
                run("verify", archive, *password, env=env)
            for command in ("schedule", "watch"):
                for signum in (signal.SIGINT, signal.SIGTERM):
                    name = f"{command}-active-{signal.Signals(signum).name}"
                    case = root / name
                    case.mkdir()
                    # Wait for a committed first snapshot and interrupt its successor.
                    first = lambda: list(case.glob("squirrel-job-*/snapshot-1.sqbk"))
                    if command == "watch":
                        # watch requires a stable source change after its first snapshot.
                        changed = [False]

                        def ready():
                            if first() and not changed[0]:
                                (source / "change.txt").write_text(name)
                                changed[0] = True
                            return changed[0]

                    else:
                        ready = first

                    def validate_job():
                        copies = list(case.glob("squirrel-job-*/*.sqbk"))
                        assert len(copies) == 1 and copies[0].name == "snapshot-1.sqbk"
                        run("verify", copies[0], env=env)

                    option = "--every" if command == "schedule" else "--poll"
                    interrupt(
                        name,
                        [command, source, case, "--no-compress", option, "1", "--keep", "1"],
                        env,
                        case,
                        "squirrel-job-*/.squirrel-*/tree",
                        signum,
                        0,
                        validate_job,
                        wait_for=ready,
                    )
            assert digest(data) == original, "Source contents changed"
            report["source_and_archives_unchanged"] = True
            report["passed"] = all(case["passed"] for case in results) and len(results) == 20
    except BaseException as error:
        report["error"] = str(error)
    finally:
        (output / "signals.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
