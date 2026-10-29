#!/usr/bin/env python3
"""Build an optional offline libFuzzer harness; production binaries are untouched."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/archive-fuzzer")
    parser.add_argument("--compiler", default="clang++")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    vendor = ROOT / "vendor/libfuzzer"
    upstream = json.loads((vendor / "UPSTREAM.json").read_text())
    for name, expected in upstream["files"].items():
        if digest(vendor / name) != expected:
            raise RuntimeError(f"Upstream file changed: {name}")
    source_names = [
        "tests/archive_reader_fuzz.cpp",
        "src/archive.cpp",
        "src/huffman.cpp",
        "src/internal.h",
        "include/squirrel/backup.h",
    ]
    compiler = subprocess.check_output([args.compiler, "--version"], text=True)

    def compile_one(path):
        obj = out / (path.stem + ".o")
        command = [
            args.compiler,
            "-g",
            "-O2",
            "-fno-omit-frame-pointer",
            "-std=c++11",
            "-c",
            str(path),
            "-o",
            str(obj),
        ]
        subprocess.run(command, check=True)
        return obj

    sources = sorted(vendor.glob("*.cpp"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        objects = list(pool.map(compile_one, sources))
    library = out / "libFuzzer.a"
    # Use a new archive, so removed source files cannot leave stale members.
    temporary = out / "libFuzzer.pending.a"
    if temporary.exists():
        temporary.unlink()
    subprocess.run(["ar", "rcs", str(temporary), *map(str, objects)], check=True)
    temporary.replace(library)
    binary = out / "archive-reader-fuzz"
    command = [
        args.compiler,
        "-std=c++17",
        "-O1",
        "-g",
        "-fno-omit-frame-pointer",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-fsanitize=fuzzer-no-link,address,undefined",
        "-I" + str(ROOT / "include"),
        "-I" + str(ROOT / "src"),
        *[str(ROOT / name) for name in source_names[:3]],
        str(library),
        "-o",
        str(binary),
    ]
    subprocess.run(command, check=True)
    record = dict(
        engine="LLVM libFuzzer 14.0.6",
        compiler=compiler,
        source_sha256={name: digest(ROOT / name) for name in source_names},
        upstream_manifest_sha256=digest(vendor / "UPSTREAM.json"),
        runtime_objects=len(objects),
        binary_sha256=digest(binary),
        sanitizers=["address", "undefined"],
        harness_command=command,
    )
    (out / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    print(binary)


if __name__ == "__main__":
    main()
