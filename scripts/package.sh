#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
make -j4 all
python3 scripts/package_software.py "$@"
