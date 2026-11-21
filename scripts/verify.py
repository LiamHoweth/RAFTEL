"""Run ARM-01's portable checks and retain evidence in a fresh directory."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARM = ROOT / "arm-01"


def python(*args: str | Path, expected: int = 0) -> None:
    command = [sys.executable, *map(str, args)]
    print(subprocess.list2cmdline(command), flush=True)
    actual = subprocess.run(command, cwd=ARM, check=False).returncode
    if actual != expected:
        raise SystemExit(f"Expected status {expected}, got {actual}: {' '.join(command[1:])}")


def verify(out: Path) -> None:
    python("-m", "pip", "check")
    python("-m", "ruff", "check", "--config", "pyproject.toml", ".", "../scripts/verify.py")
    python(
        "-m", "ruff", "format", "--check", "--config", "pyproject.toml", ".", "../scripts/verify.py"
    )
    python("-m", "compileall", "-q", "src", "../scripts/verify.py")
    python("tools/check_evidence_line_endings.py", "--include-untracked")
    python("-m", "pytest", "--junitxml", out / "pytest.xml")
    python(
        "-m",
        "raftel_arm01.cli",
        "--seed",
        "42",
        "--log",
        out / "sorting-events.jsonl",
        "--report",
        out / "benchsort.json",
        "--svg",
        out / "benchsort.svg",
    )
    python(
        "-m",
        "raftel_arm01.cli",
        "--scene",
        "config/benchsort-failure.json",
        "--fail-grasp",
        "red-retry",
        "--report",
        out / "benchsort-failure.json",
        "--svg",
        out / "benchsort-failure.svg",
        expected=1,
    )
    failure = json.loads((out / "benchsort-failure.json").read_text(encoding="utf-8"))["summary"]
    if (failure["sorted"], failure["skipped"], failure["failed"]) != (1, 2, 1):
        raise SystemExit("Unexpected BenchSort failure scene outcome")
    python(
        "-m",
        "raftel_arm01.evaluation.cli",
        "benchmark",
        "--seed",
        "42",
        "--layouts",
        "10",
        "--output",
        out / "logical-evaluation.json",
    )
    python("tools/engineering_analysis.py")
    inventory = "hardware/cad/thor-mounted-geometry.json"
    python(
        "tools/thor_load_analysis.py", "--cad-inventory", inventory, "--output", out / "load.json"
    )
    python(
        "tools/thor_load_analysis.py",
        "--cad-inventory",
        inventory,
        "--compare-materials",
        "--output",
        out / "materials.json",
    )
    python(
        "tools/thor_load_analysis.py",
        "--cad-inventory",
        inventory,
        "--wrist-membership",
        "hardware/cad/thor-wrist-membership.json",
        "--output",
        out / "wrist.json",
    )
    python(
        "tools/thor_load_analysis.py",
        "--cad-inventory",
        "hardware/cad/thor-mounted-geometry-v2.json",
        "--wrist-membership",
        "hardware/cad/thor-wrist-membership-v2.json",
        "--output",
        out / "wrist-v2.json",
    )
    python(
        "tools/thor_elbow_loads.py",
        "--load-study",
        "hardware/cad/thor-load-study.json",
        "--drum-pitch-radius-mm",
        "37",
        "--carrier-coupling",
        "1",
        "--belt-sign",
        "1",
        "--shoulder-b-fraction",
        "0.5",
        "--geometry-evidence",
        "Explicit CAD-surface-radius scenario; not calibrated pitch radius",
        "--output",
        out / "elbow.json",
    )
    python(
        "tools/thor_art1_diagnostics.py",
        "history",
        "hardware/cad/thor-art1-migration-evidence.json",
        "--output",
        out / "art1.json",
    )
    python(
        "tools/thor_jaw_reconciliation.py",
        "--check-ledger",
        "hardware/cad/thor-jaw-body-ledger.json",
    )
    python("tools/thor_kinematics.py", "--output", out / "kinematics.json")
    python(
        "tools/thor_scenario_analysis.py",
        "config/thor-scenario-v1.json",
        "--output",
        out / "scenario.json",
    )
    python(
        "tools/thor_controller_replay.py",
        "--calibration",
        "config/thor-calibration-template.json",
        "--output",
        out / "controller.json",
    )
    python(
        "tools/thor_fabrication_assets.py",
        "--validate-records",
        "hardware/measurements/thor-fabrication-template.json",
        "--output",
        out / "fabrication.json",
    )
    python(
        "tools/review_desktop_evidence.py",
        "--math-checks",
        "--output",
        out / "desktop-evidence.json",
    )
    wheel_dir = out / "wheel"
    python(
        "-m",
        "pip",
        "--isolated",
        "wheel",
        "--no-index",
        "--no-deps",
        "--no-build-isolation",
        "--check-build-dependencies",
        "--wheel-dir",
        wheel_dir,
        ".",
    )
    (wheel,) = wheel_dir.glob("raftel_arm01-*.whl")
    run_dir = out / "offline-wheel"
    python("tools/verify_installed_wheel.py", "--wheel", wheel, "--run-dir", run_dir)
    # The offline-wheel verifier created this environment beneath a fresh run directory.
    wheel_venv = run_dir / "venv"
    if wheel_venv.resolve() != wheel_venv:
        raise SystemExit(f"Unexpected wheel environment path: {wheel_venv}")
    shutil.rmtree(wheel_venv)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / ".work/verification")
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="run-", dir=output_root))
    print(f"Evidence: {out}", flush=True)
    verify(out)
    print(f"Verification passed. Evidence: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
