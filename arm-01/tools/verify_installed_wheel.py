"""Install a local ARM-01 wheel offline in a fresh, source-free venv workspace."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import io
import json
import os
import subprocess
import sys
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


def read_wheel(path: Path) -> bytes:
    with path.open("rb") as stream:
        wheel_bytes = stream.read(16 * 1024 * 1024 + 1)
    if len(wheel_bytes) > 16 * 1024 * 1024:
        raise ValueError("wheel compressed size limit exceeded")
    return wheel_bytes


def inspect_wheel(path: Path) -> dict:
    """Check one bounded snapshot, rather than reopening a mutable wheel path."""
    return inspect_wheel_bytes(read_wheel(path))


def inspect_wheel_bytes(wheel_bytes: bytes) -> dict:
    """Validate the exact bytes that will be staged for installation."""
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 1000:
            raise ValueError("duplicate or excessive wheel members")
        if sum(row.file_size for row in archive.infolist()) > 16 * 1024 * 1024:
            raise ValueError("wheel uncompressed size limit exceeded")
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise ValueError("expected one wheel distribution")
        prefix = metadata_paths[0].removesuffix("METADATA")
        if prefix != "raftel_arm01-0.1.0.dist-info/":
            raise ValueError("unexpected wheel metadata prefix")
        for name in names:
            item = PurePosixPath(name)
            if item.is_absolute() or ".." in item.parts or "\\" in name or ":" in name:
                raise ValueError("unsafe wheel member path")
            if not name.startswith(("raftel_arm01/", prefix)):
                raise ValueError("wheel contains an unexpected top-level package")
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
        if any(len(metadata.get_all(key, [])) != 1 for key in ("Name", "Version")):
            raise ValueError("wheel metadata identity must be unambiguous")
        if metadata["Name"] != "raftel-arm01" or metadata["Version"] != "0.1.0":
            raise ValueError("unexpected wheel identity/version")
        allowed = {'pytest==9.0.3; extra == "dev"', 'ruff==0.14.4; extra == "dev"'}
        requirements = metadata.get_all("Requires-Dist", [])
        if set(requirements) - allowed:
            raise ValueError("wheel introduces unexpected/runtime dependencies")
        required = {
            "raftel_arm01/defaults.json",
            "raftel_arm01/cli.py",
            "raftel_arm01/evaluation/cli.py",
            "raftel_arm01/kinematics/thor_model.py",
            "raftel_arm01/engineering/scenarios.py",
        }
        if not required <= set(names):
            raise ValueError("wheel is missing required package modules/resources")
        entrypoints = configparser.ConfigParser()
        try:
            entrypoints.read_string(archive.read(prefix + "entry_points.txt").decode("utf-8"))
        except configparser.Error as exc:
            raise ValueError("malformed wheel entry points") from exc
        expected = {
            "raftel-sort": "raftel_arm01.cli:main",
            "raftel-evaluate": "raftel_arm01.evaluation.cli:main",
        }
        if set(entrypoints.sections()) != {"console_scripts"}:
            raise ValueError("unexpected wheel entry points")
        try:
            if dict(entrypoints["console_scripts"]) != expected:
                raise ValueError("unexpected wheel entry points")
        except configparser.Error as exc:
            raise ValueError("malformed wheel entry points") from exc
    return {
        "wheel_sha256": hashlib.sha256(wheel_bytes).hexdigest(),
        "name": metadata["Name"],
        "version": metadata["Version"],
        "runtime_dependencies": [],
        "console_scripts": expected,
    }


def verify_wheel(wheel: Path, run_dir: Path, *, timeout_s: int = 120) -> dict:
    if type(timeout_s) is not int or not 10 <= timeout_s <= 600:
        raise ValueError("timeout_s must be integer10..600")
    wheel = wheel.resolve(strict=True)
    wheel_bytes = read_wheel(wheel)
    identity = inspect_wheel_bytes(wheel_bytes)
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    staged_wheel = run_dir / wheel.name
    with staged_wheel.open("xb") as stream:
        stream.write(wheel_bytes)
    environment = run_dir / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    binary = environment / ("Scripts" if os.name == "nt" else "bin")
    python = binary / ("python.exe" if os.name == "nt" else "python")
    suffix = ".exe" if os.name == "nt" else ""
    clean_env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        clean_env.pop(key, None)
    clean_env["PYTHONNOUSERSITE"] = "1"
    clean_env["PIP_NO_INDEX"] = "1"
    clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    steps = []

    def run(name: str, arguments: list[str], expected: int) -> str:
        result = subprocess.run(
            arguments,
            cwd=run_dir,
            env=clean_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s,
        )
        if result.returncode != expected:
            raise ValueError(
                f"{name} exit{result.returncode}, expected{expected}: {result.stderr[-2000:]}"
            )
        steps.append(
            {"name": name, "returncode": result.returncode, "expected_returncode": expected}
        )
        return result.stdout

    run(
        "offline_no_dependency_install",
        [
            str(python),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--no-index",
            "--no-deps",
            str(staged_wheel),
        ],
        0,
    )
    smoke = run(
        "installed_package_imports",
        [
            str(python),
            "-I",
            "-c",
            "import importlib,json,pkgutil,raftel_arm01; "
            "walk=pkgutil.walk_packages(raftel_arm01.__path__,raftel_arm01.__name__+'.'); "
            "mods=[m.name for m in walk]; "
            "paths={m:importlib.import_module(m).__file__ for m in mods}; "
            "print(json.dumps({'module_count':len(mods),'module_paths':paths,"
            "'package_path':raftel_arm01.__file__}))",
        ],
        0,
    )
    imported = json.loads(smoke)
    if not Path(imported["package_path"]).resolve().is_relative_to(environment):
        raise ValueError("smoke imported the checkout instead of the installed wheel")
    if any(
        not path or not Path(path).resolve().is_relative_to(environment)
        for path in imported["module_paths"].values()
    ):
        raise ValueError("smoke imported a module outside the fresh wheel environment")
    sorter = binary / ("raftel-sort" + suffix)
    evaluator = binary / ("raftel-evaluate" + suffix)
    result = run(
        "installed_sorter",
        [
            str(sorter),
            "--seed",
            "42",
            "--count",
            "10",
            "--report",
            "benchsort.json",
            "--svg",
            "benchsort.svg",
        ],
        0,
    )
    summary = json.loads(result.strip().splitlines()[-1])
    if summary != {
        "simulation": "logical_only",
        "sorted": 10,
        "skipped": 0,
        "failed": 0,
        "aborted": False,
        "pending": 0,
    }:
        raise ValueError("unexpected installed logical sorter outcome")
    report = json.loads((run_dir / "benchsort.json").read_text(encoding="utf-8"))
    if report["summary"] != summary or report["evidence_class"] != "logical_only":
        raise ValueError("unexpected installed BenchSort report")
    if not (run_dir / "benchsort.svg").is_file():
        raise ValueError("missing installed BenchSort illustration")
    run("installed_sorter_failure", [str(sorter), "--seed", "42", "--fail-grasp", "object-00"], 1)
    run("installed_sorter_invalid_input", [str(sorter), "--count", "0"], 2)
    result = run(
        "installed_evaluator",
        [str(evaluator), "benchmark", "--layouts", "3", "--bootstrap-resamples", "100"],
        0,
    )
    evaluation = json.loads(result)
    if evaluation["evidence_class"] != "logical_only" or evaluation["totals"]["correct"] != 30:
        raise ValueError("unexpected installed benchmark outcome")
    run(
        "installed_evaluator_failure",
        [
            str(evaluator),
            "benchmark",
            "--layouts",
            "2",
            "--fail-grasp",
            "object-00",
            "--bootstrap-resamples",
            "100",
        ],
        1,
    )
    run("installed_evaluator_invalid_input", [str(evaluator), "benchmark", "--layouts", "0"], 2)
    research_command = [
        str(python),
        "-I",
        "-m",
        "raftel_arm01.learning",
        "--train-seed",
        "42",
        "--train-layouts",
        "3",
        "--eval-seed",
        "1000",
        "--eval-layouts",
        "2",
    ]
    learning = run("installed_learning_baseline", research_command, 0)
    learning_repeat = run("installed_learning_baseline_repeat", research_command, 0)
    if learning != learning_repeat:
        raise ValueError("installed learning baseline results changed for identical inputs")
    if json.loads(learning)["evidence_class"] != "synthetic_logical_screening":
        raise ValueError("unexpected installed learning evidence class")
    (run_dir / "learning-baseline.json").write_text(learning, encoding="utf-8", newline="\n")
    if hashlib.sha256(read_wheel(staged_wheel)).hexdigest() != identity["wheel_sha256"]:
        raise ValueError("staged wheel bytes changed during verification")
    report = {
        "schema_version": 1,
        "validation_class": "offline_installed_wheel_logical_smoke",
        "wheel": identity,
        "python": sys.version,
        "platform": sys.platform,
        "installed_import": imported,
        "steps": steps,
        "network_package_install": False,
        "hardware_or_native_cad_validation": False,
    }
    (run_dir / "verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument(
        "--run-dir", type=Path, required=True, help="fresh retained scratch directory"
    )
    args = parser.parse_args(argv)
    try:
        report = verify_wheel(args.wheel, args.run_dir)
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
