#!/bin/sh
# Match the repository's portable CI checks, retaining unique local evidence.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT/arm-01"
PY="$PWD/.venv/bin/python"
export PATH="$PWD/.venv/bin:$PATH"
test -x "$PY" || { echo 'Run make setup first.' >&2; exit 2; }
mkdir -p "$ROOT/.work/verification"
OUT=$(mktemp -d "$ROOT/.work/verification/run-XXXXXX")
printf 'Evidence: %s\n' "$OUT"
"$PY" -m pip check
ruff check .
ruff format --check .
"$PY" -m compileall -q src
"$PY" tools/check_evidence_line_endings.py --include-untracked
"$PY" -m pytest
raftel-sort --seed 42 --log "$OUT/sorting-events.jsonl"
raftel-evaluate benchmark --seed 42 --layouts 10 --output "$OUT/logical-evaluation.json"
"$PY" tools/engineering_analysis.py
"$PY" tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --output "$OUT/load.json"
"$PY" tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --compare-materials --output "$OUT/materials.json"
"$PY" tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --wrist-membership hardware/cad/thor-wrist-membership.json --output "$OUT/wrist.json"
"$PY" tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry-v2.json --wrist-membership hardware/cad/thor-wrist-membership-v2.json --output "$OUT/wrist-v2.json"
"$PY" tools/thor_elbow_loads.py --load-study hardware/cad/thor-load-study.json --drum-pitch-radius-mm 37 --carrier-coupling 1 --belt-sign 1 --shoulder-b-fraction 0.5 --geometry-evidence 'Explicit CAD-surface-radius scenario; not calibrated pitch radius' --output "$OUT/elbow.json"
"$PY" tools/thor_art1_diagnostics.py history hardware/cad/thor-art1-migration-evidence.json --output "$OUT/art1.json"
"$PY" tools/thor_jaw_reconciliation.py --check-ledger hardware/cad/thor-jaw-body-ledger.json
"$PY" tools/thor_kinematics.py --output "$OUT/kinematics.json"
"$PY" tools/thor_scenario_analysis.py config/thor-scenario-v1.json --output "$OUT/scenario.json"
"$PY" tools/thor_controller_replay.py --calibration config/thor-calibration-template.json --output "$OUT/controller.json"
"$PY" tools/thor_fabrication_assets.py --validate-records hardware/measurements/thor-fabrication-template.json --output "$OUT/fabrication.json"
"$PY" tools/review_desktop_evidence.py --math-checks --output "$OUT/desktop-evidence.json"
"$PY" -m pip wheel --no-deps --wheel-dir "$OUT/wheel" .
"$PY" tools/verify_installed_wheel.py --wheel "$OUT/wheel/raftel_arm01-0.1.0-py3-none-any.whl" --run-dir "$OUT/offline-wheel"
# The wheel verifier's environment is disposable; preserve its report and wheel.
rm -rf "$OUT/offline-wheel/venv"
printf 'Verification passed. Evidence: %s\n' "$OUT"
