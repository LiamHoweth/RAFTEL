#!/bin/sh
# Keep the POSIX entry point while CI and contributors share one verifier.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PY="$ROOT/arm-01/.venv/bin/python"
test -x "$PY" || { echo 'Run make setup first.' >&2; exit 2; }
exec "$PY" "$ROOT/scripts/verify.py" "$@"
