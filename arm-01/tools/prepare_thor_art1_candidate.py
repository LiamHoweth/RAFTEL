"""Save one explicitly unaccepted Art1 diagnostic and test reversible radius edits.

Uses the existing copied-document runner and snapshots. Never saves an upstream
or input-copy path, never overwrites a candidate, and never accepts a migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import runpy
from pathlib import Path


def _load_probe() -> dict:
    if os.environ.get("RAFTEL_RUN_THOR_ART1_PROBE") == "1":
        raise ValueError("conflicting native helper opt-in must be unset before loading")
    return runpy.run_path(str(Path(__file__).with_name("probe_thor_art1_freecad.py")))


PROBE = _load_probe()
FLAG = "RAFTEL_PREPARE_THOR_ART1_CANDIDATE"
CLASS = "native_unaccepted_derived_Art1_candidate_partial_A6"


def candidate_path(output: Path, run_directory: Path) -> Path:
    output = output.resolve()
    allowed = run_directory.resolve().parent / "candidates"
    if (
        not output.is_relative_to(allowed)
        or output.suffix.casefold() != ".fcstd"
        or "UNACCEPTED" not in output.name
        or output.exists()
    ):
        raise ValueError(
            "candidate must be a fresh UNACCEPTED native path under sibling candidates/"
        )
    if (
        output == Path(os.environ.get("RAFTEL_THOR_ART1_SOURCE", ".")).resolve()
        or output == Path(os.environ.get("RAFTEL_THOR_ART1_COPY", ".")).resolve()
    ):
        raise ValueError("candidate must differ from original and input copy")
    return output


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _constraint_records(document) -> dict:
    records = {}
    for obj in document.Objects:
        expressions = list(getattr(obj, "ExpressionEngine", []))
        if not any("M3BoltBodyRadius" in expression for _, expression in expressions):
            continue
        records[obj.Name] = {
            "expressions": [list(value) for value in expressions],
            "constraints": [
                {
                    key: getattr(c, key, None)
                    for key in (
                        "Type",
                        "Value",
                        "First",
                        "FirstPos",
                        "Second",
                        "SecondPos",
                        "Third",
                        "ThirdPos",
                        "Name",
                    )
                }
                for c in getattr(obj, "Constraints", [])
            ],
        }
    if not records:
        raise ValueError("no affected M3 radius expressions were observed")
    return records


def _structure(records: dict) -> dict:
    return {
        name: {
            "expressions": record["expressions"],
            "constraints": [
                {key: value for key, value in c.items() if key != "Value"}
                for c in record["constraints"]
            ],
        }
        for name, record in records.items()
    }


def native_candidate_actions(
    App, document, contract: dict, report: dict, report_path: Path
) -> None:
    """Trusted callback; all writes target one new derived file, exactly once."""
    output = candidate_path(
        Path(os.environ["RAFTEL_THOR_ART1_CANDIDATE_OUTPUT"]), report_path.parent
    )
    copied = Path(os.environ["RAFTEL_THOR_ART1_COPY"]).resolve()
    if Path(document.FileName).resolve() != copied:
        raise ValueError("the active native document must be the pinned input copy")
    report["evidence_class"] = CLASS
    report["source_saved"] = False
    report["new_candidate_saved"] = False
    report["candidate_accepted"] = False
    study = {
        "status": "starting",
        "candidate_output": str(output),
        "input_copy_document_filename": document.FileName,
        "candidate_worker_sha256": _sha(Path(__file__)),
        "radius_values_millimetres": [1.69, 1.71, 1.7],
        "source_migration_accepted": False,
        "all_53_attachment_semantics_verified": False,
        "manufacturing_released": False,
        "phases": [],
    }
    report["candidate_study"] = study
    sheet = document.getObject("Spreadsheet")
    if sheet.getAlias("B2") != "M3BoltBodyRadius" or float(sheet.get("B2")) != 1.7:
        raise ValueError("actual Spreadsheet B2 alias/value differs from the pinned nominal input")
    initial_constraints = _constraint_records(document)
    initial_body = PROBE["native_shape_metrics"](document.getObject("Body").Shape)

    def phase(name: str, current) -> dict:
        current_sheet = current.getObject("Spreadsheet")
        constraints = _constraint_records(current)
        result = {
            "phase": name,
            "document_filename": current.FileName,
            "cell_alias": current_sheet.getAlias("B2"),
            "cell_value": current_sheet.get("B2"),
            "affected_constraints_and_expressions": constraints,
            "expression_and_constraint_structure_preserved": _structure(constraints)
            == _structure(initial_constraints),
            "sketch004_circle_radius_mm": current.getObject("Sketch004").Geometry[0].Radius,
            "all_document_own_states": {obj.Name: list(obj.State) for obj in current.Objects},
            "body": PROBE["native_shape_metrics"](current.getObject("Body").Shape),
            "algebraic_pocket_volume_delta_mm3": current.getObject("Pad002").Shape.Volume
            - current.getObject("Pocket").Shape.Volume,
        }
        study["phases"].append(result)
        return result

    phase("before_new_candidate_save", document)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("candidate appeared concurrently; refusing overwrite")
    document.saveAs(str(output))
    report["native_document_saved"] = True
    report["new_candidate_saved"] = True
    study["candidate_sha256_immediately_after_save"] = _sha(output)
    study["saved_candidate_document_filename"] = document.FileName
    PROBE["_checkpoint"](report_path, report)
    App.closeDocument(document.Name)
    reopened = App.openDocument(str(output), True)
    reopened.recompute(None, True)
    phase("reopened_forced_nominal", reopened)
    expected_previous = 1.7
    for value, label in (
        (1.69, "radius_minus_0_01_mm"),
        (1.71, "radius_plus_0_01_mm"),
        (1.7, "restored_nominal_radius"),
    ):
        current_sheet = reopened.getObject("Spreadsheet")
        if current_sheet.getAlias("B2") != "M3BoltBodyRadius":
            raise ValueError("controlled cell alias changed before a perturbation")
        if float(current_sheet.get("B2")) != expected_previous:
            raise ValueError("controlled cell value changed before a perturbation")
        before = _constraint_records(reopened)
        if _structure(before) != _structure(initial_constraints):
            raise ValueError("constraint/expression structure changed before perturbation")
        current_sheet.set("B2", str(value))
        reopened.recompute(None, True)
        measured = phase(label, reopened)
        measured["pre_perturbation_constraints_and_expressions"] = before
        if not math.isclose(
            measured["sketch004_circle_radius_mm"], value, rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError("native radius did not follow the controlled spreadsheet value")
        expected_previous = value
        PROBE["_checkpoint"](report_path, report)
    restored = study["phases"][-1]
    study["restored_nominal_body_volume_error_mm3"] = abs(
        restored["body"]["volume_mm3"] - initial_body["volume_mm3"]
    )
    study["candidate_sha256_after_reopen_and_perturbations"] = _sha(output)
    study["candidate_bytes_unchanged_after_single_save"] = (
        study["candidate_sha256_immediately_after_save"]
        == study["candidate_sha256_after_reopen_and_perturbations"]
    )
    study["all_phase_own_states_up_to_date"] = all(
        states == ["Up-to-date"]
        for p in study["phases"]
        for states in p["all_document_own_states"].values()
    )
    study["restored_volume_within_1e_minus_6_mm3"] = (
        study["restored_nominal_body_volume_error_mm3"] < 1e-6
    )
    study["status"] = "procedure_completed_not_migration_acceptance"


def candidate_procedure_complete(capture: dict, runner: dict) -> bool:
    """Check retained procedural coverage, including failed geometry outcomes.

    This validates metadata bindings, not the authenticity of a supplied capture
    or the engineering acceptability of its candidate.
    """
    try:
        return _candidate_coverage_complete(capture, runner)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return False


def _candidate_coverage_complete(capture: dict, runner: dict) -> bool:
    study = capture.get("candidate_study", {})
    flags = (
        capture.get("evidence_class") == CLASS
        and capture.get("new_candidate_saved") is True
        and capture.get("native_document_saved") is True
        and capture.get("source_saved") is False
        and capture.get("migration_accepted") is False
        and capture.get("candidate_accepted") is False
        and capture.get("source_and_copy_bytes_unchanged") is True
        and runner.get("capture_snapshot_bytes_unchanged") is True
        and runner.get("source_and_copy_bytes_unchanged") is True
        and runner.get("outcome") == "process_completed"
        and runner.get("process_returncode") == 0
        and study.get("status") == "procedure_completed_not_migration_acceptance"
        and study.get("candidate_bytes_unchanged_after_single_save") is True
    )
    if not flags:
        return False

    def digest(value):
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(c in "0123456789abcdef" for c in value)
        )

    def finite(value):
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )

    def filename(value):
        return value.replace("\\", "/").casefold()

    source = PROBE["SOURCE_SHA256"]
    if (
        type(capture["schema_version"]) is not int
        or capture["schema_version"] != 1
        or capture["source_revision"] != PROBE["DIAGNOSTICS"]["SOURCE_REVISION"]
        or capture["experiment"] != "intersection_pocket_through_all"
        or runner["experiment"] != capture["experiment"]
        or capture["audit_status"] != "complete_probe_not_migration_acceptance"
        or runner["native_audit_status"] != capture["audit_status"]
        or not isinstance(capture["freecad_version"], list)
        or len(capture["freecad_version"]) < 3
        or not all(isinstance(v, str) and v for v in capture["freecad_version"][:3])
        or any(
            capture[k] != source
            for k in (
                "source_sha256_before",
                "source_sha256_after",
                "copied_source_sha256_before",
                "copied_source_sha256_after",
            )
        )
        or any(
            runner[k] != source
            for k in ("source_sha256_before", "source_sha256_after", "copy_sha256_after")
        )
    ):
        return False
    before = runner["capture_snapshot_sha256_before"]
    if before != runner["capture_snapshot_sha256_after"] or len(before) != 4:
        return False
    snapshots = {p.replace("\\", "/").rsplit("/", 1)[-1]: h for p, h in before.items()}
    identities = {
        "probe_thor_art1_freecad.py": capture["capture_script_sha256"],
        "thor_art1_diagnostics.py": capture["diagnostic_helper_sha256"],
        "thor-art1-migration-evidence.json": capture["migration_evidence_sha256"],
        "prepare_thor_art1_candidate.py": study["candidate_worker_sha256"],
    }
    executable = runner["native_executable_sha256"]
    if (
        snapshots != identities
        or not all(digest(v) for v in identities.values())
        or not digest(executable)
        or executable != capture["runner_declared_native_executable_sha256"]
        or executable != runner["expected_native_executable_sha256"]
        or runner["executable_matches_caller_pin"] is not True
        or not digest(study["candidate_sha256_immediately_after_save"])
        or study["candidate_sha256_immediately_after_save"]
        != study["candidate_sha256_after_reopen_and_perturbations"]
        or study["source_migration_accepted"] is not False
        or study["all_53_attachment_semantics_verified"] is not False
        or study["manufacturing_released"] is not False
    ):
        return False
    phases = study["phases"]
    expected = [
        ("before_new_candidate_save", 1.7),
        ("reopened_forced_nominal", 1.7),
        ("radius_minus_0_01_mm", 1.69),
        ("radius_plus_0_01_mm", 1.71),
        ("restored_nominal_radius", 1.7),
    ]
    if len(phases) != len(expected):
        return False
    candidate = study["candidate_output"]
    copied = study["input_copy_document_filename"]
    if (
        not candidate
        or not copied
        or filename(candidate) == filename(copied)
        or filename(study["saved_candidate_document_filename"]) != filename(candidate)
    ):
        return False
    states = capture["all_document_object_states"]
    required = {"Sketch004", "Sketch008", "Sketch009", "Sketch010", "Sketch012"}
    if not {"Body", "Spreadsheet", *required}.issubset(states):
        return False
    baseline = phases[0]["affected_constraints_and_expressions"]
    if set(baseline) != required:
        return False
    for index, (phase, (label, value)) in enumerate(zip(phases, expected, strict=True)):
        body = phase["body"]
        constraints = phase["affected_constraints_and_expressions"]
        own_states = phase["all_document_own_states"]
        if (
            phase["phase"] != label
            or phase["cell_alias"] != "M3BoltBodyRadius"
            or float(phase["cell_value"]) != value
            or not finite(phase["sketch004_circle_radius_mm"])
            or abs(phase["sketch004_circle_radius_mm"] - value) > 1e-12
            or filename(phase["document_filename"]) != filename(copied if index == 0 else candidate)
            or set(own_states) != set(states)
            or not all(
                isinstance(v, list) and all(isinstance(s, str) for s in v)
                for v in own_states.values()
            )
            or not isinstance(body["valid"], bool)
            or not isinstance(body["is_null"], bool)
            or not finite(body["volume_mm3"])
            or len(body["bounds_mm"]) != 6
            or not all(finite(v) for v in body["bounds_mm"])
            or len(body["center_of_mass_mm"]) != 3
            or not all(finite(v) for v in body["center_of_mass_mm"])
            or not finite(phase["algebraic_pocket_volume_delta_mm3"])
            or set(constraints) != required
            or _structure(constraints) != _structure(baseline)
            or phase["expression_and_constraint_structure_preserved"] is not True
        ):
            return False
        for record in constraints.values():
            if (
                not isinstance(record["expressions"], list)
                or not record["expressions"]
                or not isinstance(record["constraints"], list)
                or not record["constraints"]
                or not all(
                    isinstance(c, dict) and {"Type", "Value", "First"}.issubset(c)
                    for c in record["constraints"]
                )
            ):
                return False
    error = abs(phases[-1]["body"]["volume_mm3"] - phases[0]["body"]["volume_mm3"])
    return (
        study["all_phase_own_states_up_to_date"]
        is all(
            states == ["Up-to-date"]
            for phase in phases
            for states in phase["all_document_own_states"].values()
        )
        and finite(study["restored_nominal_body_volume_error_mm3"])
        and math.isclose(
            study["restored_nominal_body_volume_error_mm3"], error, rel_tol=0, abs_tol=1e-12
        )
        and study["restored_volume_within_1e_minus_6_mm3"] is (error < 1e-6)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path, required=True)
    parser.add_argument("--expected-executable-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        output = candidate_path(args.candidate_output, args.run_directory)
        runner = PROBE["run_probe"](
            args.freecad,
            args.source,
            args.run_directory,
            experiment="intersection_pocket_through_all",
            timeout_s=180,
            expected_executable_sha256=args.expected_executable_sha256,
            candidate_output=output,
        )
        report_path = args.run_directory / "probe.json"
        capture = PROBE["DIAGNOSTICS"]["_load"](report_path)
        completed = candidate_procedure_complete(capture, runner)
        result = {
            "evidence_class": CLASS,
            "candidate_procedure_completed": completed,
            "migration_accepted": False,
            "candidate_accepted": False,
            "candidate_output": str(output),
            "report_path": str(report_path),
        }
        with (args.run_directory / "candidate-runner.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if completed else 1
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    return 2


if os.environ.get(FLAG) == "1":
    PROBE["native_capture"](after_capture=native_candidate_actions)
elif __name__ == "__main__":
    raise SystemExit(main())
