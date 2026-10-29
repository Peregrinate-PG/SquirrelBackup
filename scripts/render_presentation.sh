#!/bin/bash
# Convert without opening the desktop application or sharing the user's profile.
set -euo pipefail
cd "$(dirname "$0")/.."
SOFFICE=${SOFFICE:-$(command -v soffice || command -v libreoffice || true)}
if [ -z "$SOFFICE" ]; then
  echo 'Set SOFFICE to the LibreOffice command-line executable.' >&2
  exit 2
fi
INPUT=${1:-presentations/第3组_松鼠备份_答辩.pptx}
OUTPUT=${2:-.preflight/ppt-build/pdf}
mkdir -p "$OUTPUT" .preflight/ppt-build
if [ -z "${FONTCONFIG_FILE:-}" ] && [ "$(uname -s)" = Darwin ]; then
  FONTCONFIG_FILE=$(python3 scripts/macos_fontconfig.py .preflight/ppt-build/fonts.conf)
  export FONTCONFIG_FILE
fi
PROFILE=$(mktemp -d "$PWD/.preflight/ppt-build/lo-profile-XXXXXX")
trap 'rm -rf "$PROFILE"' EXIT
PROFILE_URI=$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).as_uri())' "$PROFILE")
"$SOFFICE" "-env:UserInstallation=$PROFILE_URI" --headless --convert-to pdf --outdir "$OUTPUT" "$INPUT"
