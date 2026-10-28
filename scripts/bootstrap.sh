#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
xcrun --find clang++ >/dev/null
if [ ! -d .tools/src/googletest ]; then
  mkdir -p .tools/src
  if [ -d vendor/googletest ]; then
    cp -R vendor/googletest .tools/src/googletest
  else
    git clone --depth 1 --branch v1.15.2 https://github.com/google/googletest.git .tools/src/googletest
  fi
fi
if [ "${1:-}" = "--docs-tools" ]; then
  python3 -m venv .tools/venv
  .tools/venv/bin/python -m pip install -r scripts/requirements-tools.txt
fi
make -j4 all
