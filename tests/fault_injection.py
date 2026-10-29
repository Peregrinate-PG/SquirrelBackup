#!/usr/bin/env python3
"""Test injected errors and SIGKILL using a frozen CLI and private fixtures only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("library", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False, parents=True)
    binary = output / "squirrel-under-test"
    shutil.copy2(args.binary.resolve(), binary)
    library = args.library.resolve()
    cases = []
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "binary_sha256": digest(binary),
        "injection_library_sha256": digest(library),
        "results": cases,
        "passed": False,
        "scope": "Injected errno and real SIGKILL; not a physical full-disk or power-loss test.",
    }
    base_env = dict(os.environ, SQUIRREL_FAULT_PASSWORD="test-only-fault-password")
    base_env.pop("DYLD_INSERT_LIBRARIES", None)

    def run(argv, env=base_env):
        return subprocess.run(
            [str(binary), *map(str, argv)], env=env, capture_output=True, text=True, timeout=90
        )

    def good(argv):
        r = run(argv)
        assert r.returncode == 0, (argv, r.returncode, r.stderr)
        return r

    def record(name, fn):
        item = {"name": name, "passed": False}
        started = time.monotonic()
        try:
            item.update(fn())
            item["passed"] = True
        except Exception as error:
            item["error"] = repr(error)
        item["elapsed_seconds"] = round(time.monotonic() - started, 4)
        cases.append(item)
        print(("PASS" if item["passed"] else "FAIL"), name, item.get("error", ""), flush=True)

    try:
        assert shutil.disk_usage(output).free > 4 * 1024**3, "Need 4 GiB free for isolated fixtures"
        with tempfile.TemporaryDirectory(prefix="fixtures-", dir=output) as td:
            root = Path(td)
            source = root / "source"
            source.mkdir()
            (source / "data.bin").write_bytes(bytes(range(256)) * 65536)
            original = digest(source / "data.bin")
            for encrypted in (False, True):
                label = "encrypted" if encrypted else "plain"
                password = ["--password-env", "SQUIRREL_FAULT_PASSWORD"] if encrypted else []
                archive = root / (label + ".sqbk")
                good(["backup", source, archive, "--no-compress", *password])
                original_archive = digest(archive)
                failures = [
                    ("backup", "fwrite-enospc", "/tree", "pack-enospc"),
                    ("backup", "fwrite-enospc", "/sealed", "seal-enospc"),
                    ("backup", "fsync-eio", "/sealed", "flush-eio"),
                    ("backup", "link-eacces", "/result", "publish-eacces"),
                    ("restore", "fwrite-enospc", "/tree", "decode-enospc"),
                    ("restore", "write-enospc", "/restored/data.bin", "write-enospc"),
                    ("restore", "rename-eio", "/result", "publish-eio"),
                    ("restore", "chmod-eperm", "/restored/data.bin", "metadata-eperm"),
                ]
                for verb, operation, suffix, name in failures:

                    def failure(verb=verb, operation=operation, suffix=suffix, name=name):
                        case = root / (label + "-" + name)
                        case.mkdir()
                        target = case / "result"
                        argv = [verb, source if verb == "backup" else archive, target, *password]
                        if verb == "backup":
                            argv.append("--no-compress")
                        env = dict(
                            base_env,
                            DYLD_INSERT_LIBRARIES=str(library),
                            SQUIRREL_FAULT_ROOT=str(case),
                            SQUIRREL_FAULT_OP=operation,
                            SQUIRREL_FAULT_SUFFIX=suffix,
                        )
                        r = run(argv, env)
                        (output / (label + "-" + name + ".log")).write_text(r.stdout + r.stderr)
                        assert "[fault] " + operation in r.stderr, "Fault hook was not exercised"
                        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
                        assert not r.stdout, "Failure emitted success statistics"
                        assert (
                            "complete:" not in r.stderr.lower()
                        ), "Failure logged a completed output"
                        assert not target.exists(), "Failed operation published a target"
                        assert not list(
                            case.rglob(".squirrel-*")
                        ), "Staging remains after handled error"
                        assert digest(archive) == original_archive, "Prior archive changed"
                        good(argv)  # A normal retry can use exactly the same target name.
                        if verb == "backup":
                            good(["verify", target, *password])
                        else:
                            assert digest(target / "data.bin") == original
                        return {
                            "injected": operation,
                            "target_suffix": suffix,
                            "exit_code": r.returncode,
                            "unpublished_on_failure": True,
                            "staging_cleaned": True,
                            "prior_archive_unchanged": True,
                            "same_target_retry_passed": True,
                        }

                    record(label + "-" + name, failure)
                for operation in ["write-eintr", "write-short"]:

                    def retry(operation=operation):
                        case = root / (label + "-" + operation)
                        case.mkdir()
                        target = case / "result"
                        env = dict(
                            base_env,
                            DYLD_INSERT_LIBRARIES=str(library),
                            SQUIRREL_FAULT_ROOT=str(case),
                            SQUIRREL_FAULT_OP=operation,
                            SQUIRREL_FAULT_SUFFIX="/restored/data.bin",
                        )
                        r = run(["restore", archive, target, *password], env)
                        (output / (label + "-" + operation + ".log")).write_text(
                            r.stdout + r.stderr
                        )
                        assert "[fault] " + operation in r.stderr, "Retry hook was not exercised"
                        assert r.returncode == 0, r.stderr
                        assert digest(target / "data.bin") == original
                        assert not list(case.rglob(".squirrel-*"))
                        assert digest(archive) == original_archive
                        return {
                            "injected": operation,
                            "exit_code": 0,
                            "restored_hash_matches": True,
                            "staging_cleaned": True,
                            "prior_archive_unchanged": True,
                        }

                    record(label + "-" + operation, retry)
                assert digest(source / "data.bin") == original

            large_source = root / "large-source"
            large_source.mkdir()
            with (large_source / "data.bin").open("wb") as f:
                f.write(b"Squirrel forced-termination test fixture\n")
                f.truncate(256 * 1024 * 1024)
            large_hash = digest(large_source / "data.bin")
            for encrypted in (False, True):
                label = "encrypted" if encrypted else "plain"
                password = ["--password-env", "SQUIRREL_FAULT_PASSWORD"] if encrypted else []
                archive = root / ("large-" + label + ".sqbk")
                good(["backup", large_source, archive, "--no-compress", *password])
                archive_hash = digest(archive)
                for verb in ["backup", "restore"]:

                    def killed(verb=verb):
                        name = label + "-" + verb + "-SIGKILL"
                        case = root / name
                        case.mkdir()
                        target = case / "result"
                        argv = [
                            verb,
                            large_source if verb == "backup" else archive,
                            target,
                            *password,
                        ]
                        if verb == "backup":
                            argv.append("--no-compress")
                        process = subprocess.Popen(
                            [str(binary), *map(str, argv)],
                            env=base_env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        try:
                            pattern = (
                                ".squirrel-*/tree"
                                if verb == "backup"
                                else ".squirrel-*/restored/data.bin"
                            )
                            deadline = time.monotonic() + 45
                            observed = None
                            while time.monotonic() < deadline:
                                assert process.poll() is None, "Process finished before kill"
                                for p in case.glob(pattern):
                                    try:
                                        size = p.stat().st_size
                                    except FileNotFoundError:
                                        continue
                                    if size >= 4 * 1024 * 1024:
                                        observed = {"path": str(p.relative_to(case)), "bytes": size}
                                        break
                                if observed:
                                    break
                                time.sleep(0.001)
                            assert observed, "No observed I/O"
                            process.send_signal(signal.SIGKILL)
                            stdout, stderr = process.communicate(timeout=10)
                            (output / (name + ".log")).write_text(stdout + stderr)
                            assert process.returncode == -signal.SIGKILL
                            assert not target.exists(), "Killed process published output"
                            staging = list(case.glob(".squirrel-*"))
                            assert staging, "Expected unreclaimed private staging after SIGKILL"
                            assert all(p.stat().st_mode & 0o777 == 0o700 for p in staging)
                            assert digest(archive) == archive_hash
                            assert digest(large_source / "data.bin") == large_hash
                            good(argv)
                            if verb == "backup":
                                good(["verify", target, *password])
                            else:
                                assert digest(target / "data.bin") == large_hash
                            assert set(case.glob(".squirrel-*")) == set(
                                staging
                            ), "Retry touched old staging"
                            return {
                                "signal": "SIGKILL",
                                "exit_code": process.returncode,
                                "observed_io": observed,
                                "unpublished_on_kill": True,
                                "prior_archive_unchanged": True,
                                "source_unchanged": True,
                                "private_staging_left_by_kill": len(staging),
                                "staging_root_mode": "0700",
                                "same_target_retry_passed": True,
                                "old_staging_not_removed_by_retry": True,
                            }
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.communicate(timeout=10)

                    record(label + "-" + verb + "-SIGKILL", killed)
            report["fixture_contents_unchanged"] = digest(source / "data.bin") == original
            report["passed"] = len(cases) == 24 and all(c["passed"] for c in cases)
    except Exception as error:
        report["error"] = repr(error)
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "fault-injection.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
