"""Run the optional native audit in an isolated FreeCAD console subprocess.

A process/report completion result is not a claim of CAD validity. Read the
report's restore/recompute mode, object states and feature diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def run_audit(
    freecad: Path,
    source: Path,
    report: Path,
    *,
    module_paths: tuple[Path, ...] = (),
    recompute: str = "none",
    shape_scope: str = "terminal",
    validate_shapes: bool = False,
    timeout_s: float = 180,
    document_names: tuple[str, ...] = (),
    object_names: tuple[str, ...] = (),
) -> dict:
    """Preserve checkpoint and logs on timeout; never overwrite existing runs."""
    if not freecad.is_file() or not source.is_file():
        raise ValueError("FreeCAD executable and source document must exist")
    if source.suffix.casefold() != ".fcstd":
        raise ValueError("source must be a native FreeCAD document")
    if report.suffix.lower() != ".json" or report.exists():
        raise ValueError("report must be a new JSON path")
    if recompute not in {"none", "changed", "force"}:
        raise ValueError("invalid recompute mode")
    if shape_scope not in {"none", "terminal", "all"}:
        raise ValueError("invalid shape scope")
    if not 0 < timeout_s <= 7200:
        raise ValueError("timeout must be positive and at most7200seconds")
    if any(not path.is_dir() for path in module_paths):
        raise ValueError("module paths must be existing addon directories")
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    run_directory = report.with_suffix(".run")
    run_directory.mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(
        RAFTEL_RUN_FREECAD_AUDIT="1",
        RAFTEL_FREECAD_ASSEMBLY=str(source.resolve()),
        RAFTEL_FREECAD_REPORT=str(report),
        RAFTEL_FREECAD_RECOMPUTE=recompute,
        RAFTEL_FREECAD_SHAPE_SCOPE=shape_scope,
        RAFTEL_FREECAD_VALIDATE_SHAPES=str(int(validate_shapes)),
        RAFTEL_FREECAD_DOCUMENTS=",".join(document_names),
        RAFTEL_FREECAD_OBJECTS=",".join(object_names),
        PYTHONNOUSERSITE="1",
    )
    command = [
        str(freecad.resolve()),
        "-u",
        str(run_directory / "user.cfg"),
        "-s",
        str(run_directory / "system.cfg"),
        "--log-file",
        str(run_directory / "native.log"),
    ]
    for path in module_paths:
        command.extend(("-M", str(path.resolve())))
    command.append(str(Path(__file__).with_name("audit_freecad_assembly.py").resolve()))
    metadata = {
        "command": command,
        "timeout_s": timeout_s,
        "recompute_mode": recompute,
        "shape_scope": shape_scope,
        "validate_shapes": validate_shapes,
        "outcome": "starting",
    }
    try:
        result = subprocess.run(
            command, input="", capture_output=True, text=True, env=env, timeout=timeout_s
        )
        metadata.update(outcome="process_completed", process_returncode=result.returncode)
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        metadata.update(outcome="timed_out", process_returncode=None)
        stdout, stderr = error.stdout or b"", error.stderr or b""
    for name, value in (("stdout.log", stdout), ("stderr.log", stderr)):
        text = value.decode(errors="replace") if isinstance(value, bytes) else value
        (run_directory / name).write_text(text)
    metadata["checkpoint_exists"] = report.exists()
    metadata["audit_status"] = None
    if report.exists():
        try:
            metadata["audit_status"] = json.loads(report.read_text()).get("status")
        except (OSError, ValueError, AttributeError) as error:
            metadata["report_read_error"] = str(error)
    (run_directory / "runner.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--module-path", action="append", type=Path, default=[])
    parser.add_argument("--recompute", choices=("none", "changed", "force"), default="none")
    parser.add_argument("--shape-scope", choices=("none", "terminal", "all"), default="terminal")
    parser.add_argument("--validate-shapes", action="store_true")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--document", action="append", default=[])
    parser.add_argument("--object", action="append", default=[])
    args = parser.parse_args()
    try:
        metadata = run_audit(
            args.freecad,
            args.source,
            args.report,
            module_paths=tuple(args.module_path),
            recompute=args.recompute,
            shape_scope=args.shape_scope,
            validate_shapes=args.validate_shapes,
            timeout_s=args.timeout,
            document_names=tuple(args.document),
            object_names=tuple(args.object),
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(metadata, indent=2))
    if metadata["outcome"] == "timed_out":
        return 124
    return int(bool(metadata["process_returncode"]) or metadata["audit_status"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())
