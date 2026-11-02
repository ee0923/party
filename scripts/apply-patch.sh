#!/usr/bin/env bash
set -euo pipefail
set +x
# Preserve the GitHub runner's Bash; never accidentally select Windows WSL.
export CLASH_PARTY_BASH="$BASH"
if command -v cygpath >/dev/null 2>&1; then
  CLASH_PARTY_BASH="$(cygpath -w "$BASH")"
fi
python3 scripts/customize.py "$@"
