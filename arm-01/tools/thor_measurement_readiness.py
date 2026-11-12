"""Offline uncertainty/calibration metadata beside existing cleaned-mass forms.

This checks declarations, identity, dates and artifact availability only. It
does not authenticate instrument metrology or accept physical measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from raftel_arm01.engineering.fabrication_records import validate_fabrication_records
from raftel_arm01.engineering.scenarios import canonical_sha256, finite_number

CLASS = "cleaned_mass_metadata_readiness_not_measurement_acceptance"
QUALIFICATION = {
    "physical_measurement_authenticated": False,
    "mass_ledger_modified": False,
    "manufacturing_release": False,
    "hardware_operation_authorized": False,
}


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(label + " fields differ")


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("nonempty bounded text required")
    return value


def digest(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("lowercase SHA-256 required")
    return value


def stamp(value, *, utc=True):
    try:
        parsed = datetime.fromisoformat(text(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("explicit timezone timestamp required") from error
    if parsed.utcoffset() is None or (utc and parsed.utcoffset().total_seconds() != 0):
        raise ValueError("explicit UTC timestamp required")
    return parsed.astimezone(UTC)


def strict_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("readiness input exceeds one MiB")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("nonfinite JSON constant")

    result = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique,
        parse_float=lambda v: finite_number(float(v)),
        parse_constant=reject,
    )
    if not isinstance(result, dict):
        raise ValueError("JSON root must be object")
    return result


def template(fabrication, manifest):
    validate_fabrication_records(fabrication, manifest)
    weighed = [row["weighing"] for row in fabrication["records"] if row["weighing"] is not None]
    return {
        "schema_version": 1,
        "evidence_class": CLASS,
        "fabrication_records_canonical_sha256": canonical_sha256(fabrication),
        "units": {"mass": "kg"},
        "instruments": [
            {"instrument_id": identifier, "calibration": None}
            for identifier in sorted({row["instrument_id"] for row in weighed})
        ],
        "records": [
            {
                "instance_id": row["instance_id"],
                "weighing_canonical_sha256": canonical_sha256(row["weighing"])
                if row["weighing"] is not None
                else None,
                "uncertainty": None,
            }
            for row in fabrication["records"]
        ],
        "qualification": dict(QUALIFICATION),
    }


def evidence(reference, root):
    """Return availability, without interpreting or authenticating contents."""
    keys(reference, {"path", "sha256"}, "evidence reference")
    name = text(reference["path"])
    digest(reference["sha256"])
    if (
        "\\" in name
        or ":" in name
        or PurePosixPath(name).is_absolute()
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise ValueError("evidence path must be contained relative POSIX path")
    root = Path(root).resolve()
    path = root
    for part in name.split("/"):
        path = path / part
        if path.is_symlink():
            raise ValueError("evidence symlinks are not permitted")
    if not path.resolve().is_relative_to(root):
        raise ValueError("evidence path escaped root")
    if not path.is_file():
        return "missing"
    hasher = hashlib.sha256()
    remaining = 32 * 1024**2
    with path.open("rb") as stream:
        while remaining:
            chunk = stream.read(min(1048576, remaining))
            if not chunk:
                break
            hasher.update(chunk)
            remaining -= len(chunk)
        if stream.read(1):
            return "exceeds_32_MiB_bound"
    return (
        "available_matching_bytes" if hasher.hexdigest() == reference["sha256"] else "stale_bytes"
    )


def calibration(record, root):
    if record is None:
        return None
    keys(
        record,
        {
            "evidence_state",
            "calibrated_at_utc",
            "valid_until_utc",
            "applicable_conditions",
            "evidence",
            "invalidation",
        },
        "instrument calibration",
    )
    if not isinstance(record["evidence_state"], str) or record["evidence_state"] not in {
        "observed",
        "synthetic",
    }:
        raise ValueError("calibration declaration must be observed or synthetic")
    start, end = stamp(record["calibrated_at_utc"]), stamp(record["valid_until_utc"])
    if end <= start:
        raise ValueError("calibration validity interval must have positive duration")
    text(record["applicable_conditions"])
    result = {
        "state": record["evidence_state"],
        "start": start,
        "end": end,
        "evidence": evidence(record["evidence"], root),
        "invalidation": None,
    }
    invalid = record["invalidation"]
    if invalid is not None:
        keys(
            invalid,
            {"recorded_at_utc", "affects_measurements_from_utc", "reason", "evidence"},
            "calibration invalidation",
        )
        text(invalid["reason"])
        result["invalidation"] = {
            "recorded": stamp(invalid["recorded_at_utc"]),
            "effective": stamp(invalid["affects_measurements_from_utc"]),
            "evidence": evidence(invalid["evidence"], root),
        }
        if result["invalidation"]["effective"] > result["invalidation"]["recorded"]:
            raise ValueError("invalidation effective time cannot follow its recorded time")
        if result["invalidation"]["recorded"] < start:
            raise ValueError("calibration cannot be invalidated before it was issued")
    return result


def uncertainty(record, root):
    if record is None:
        return None
    keys(
        record,
        {
            "standard_uncertainty_kg",
            "coverage_factor",
            "expanded_uncertainty_kg",
            "budget_description",
            "resolution_accounted_for",
            "repeatability_accounted_for",
            "calibration_accounted_for",
            "uncertainty_evidence",
            "conditions_applicability_evidence",
        },
        "uncertainty declaration",
    )
    standard, factor, expanded = [
        finite_number(record[key])
        for key in ("standard_uncertainty_kg", "coverage_factor", "expanded_uncertainty_kg")
    ]
    if standard <= 0 or expanded <= 0 or factor < 1:
        raise ValueError("positive uncertainty and coverage factor >=1 required")
    product = finite_number(standard * factor)
    if not math.isclose(expanded, product, rel_tol=1e-12, abs_tol=0):
        raise ValueError(
            "expanded uncertainty must equal standard uncertainty times coverage factor"
        )
    text(record["budget_description"])
    for field in (
        "resolution_accounted_for",
        "repeatability_accounted_for",
        "calibration_accounted_for",
    ):
        if record[field] is not True:
            raise ValueError("budget must explicitly account for " + field)
    return {
        "uncertainty_evidence": evidence(record["uncertainty_evidence"], root),
        "conditions_applicability_evidence": evidence(
            record["conditions_applicability_evidence"], root
        ),
    }


def assess(sidecar, fabrication, manifest, *, evidence_root, as_of_utc):
    base = validate_fabrication_records(fabrication, manifest)
    now = stamp(as_of_utc)
    keys(
        sidecar,
        {
            "schema_version",
            "evidence_class",
            "fabrication_records_canonical_sha256",
            "units",
            "instruments",
            "records",
            "qualification",
        },
        "readiness sidecar",
    )
    if (
        type(sidecar["schema_version"]) is not int
        or sidecar["schema_version"] != 1
        or sidecar["evidence_class"] != CLASS
    ):
        raise ValueError("unsupported offline readiness schema")
    if sidecar["fabrication_records_canonical_sha256"] != canonical_sha256(fabrication):
        raise ValueError("stale fabrication document binding")
    if sidecar["units"] != {"mass": "kg"}:
        raise ValueError("readiness uncertainty must use kg")
    keys(sidecar["qualification"], QUALIFICATION, "qualification")
    if any(sidecar["qualification"][key] is not False for key in QUALIFICATION):
        raise ValueError("readiness cannot grant acceptance, release or operation")
    if not isinstance(sidecar["instruments"], list) or not isinstance(sidecar["records"], list):
        raise ValueError("instrument and readiness records must be lists")
    instruments = {}
    for row in sidecar["instruments"]:
        keys(row, {"instrument_id", "calibration"}, "instrument")
        identifier = text(row["instrument_id"])
        if identifier in instruments:
            raise ValueError("duplicate instrument identity")
        instruments[identifier] = calibration(row["calibration"], evidence_root)
    expected_instruments = {
        row["weighing"]["instrument_id"]
        for row in fabrication["records"]
        if row["weighing"] is not None
    }
    if set(instruments) != expected_instruments:
        raise ValueError("instrument identities differ from existing weighing records")
    source = {row["instance_id"]: row for row in fabrication["records"]}
    seen, outcomes = set(), []
    for row in sidecar["records"]:
        keys(row, {"instance_id", "weighing_canonical_sha256", "uncertainty"}, "readiness record")
        identifier = row["instance_id"]
        if not isinstance(identifier, str) or identifier not in source or identifier in seen:
            raise ValueError("unknown or duplicate installed weighing identity")
        seen.add(identifier)
        weighed = source[identifier]["weighing"]
        expected_hash = canonical_sha256(weighed) if weighed is not None else None
        if row["weighing_canonical_sha256"] != expected_hash:
            raise ValueError("stale weighing row binding")
        reasons = []
        expired_now = None
        if weighed is None:
            if row["uncertainty"] is not None:
                raise ValueError("unknown weighing cannot have a known uncertainty budget")
            reasons.append("weighing_unknown")
            state = "unknown"
        else:
            state = weighed["evidence_state"]
            measured = stamp(weighed["provenance"]["captured_at"], utc=False)
            if measured > now:
                reasons.append("measurement_in_future")
            budget = uncertainty(row["uncertainty"], evidence_root)
            if budget is None:
                reasons.append("uncertainty_unknown")
            else:
                reasons.extend(
                    key + "_" + value
                    for key, value in budget.items()
                    if value != "available_matching_bytes"
                )
            instrument = instruments[weighed["instrument_id"]]
            if instrument is None:
                reasons.append("calibration_unknown")
            else:
                expired_now = now >= instrument["end"]
                if instrument["start"] > now:
                    reasons.append("calibration_in_future")
                if measured < instrument["start"] or measured >= instrument["end"]:
                    reasons.append("calibration_not_valid_at_measurement")
                if instrument["state"] != state:
                    reasons.append("calibration_evidence_state_mismatch")
                if instrument["evidence"] != "available_matching_bytes":
                    reasons.append("calibration_evidence_" + instrument["evidence"])
                invalid = instrument["invalidation"]
                if invalid is not None:
                    if invalid["recorded"] > now:
                        reasons.append("invalidation_record_in_future")
                    if measured >= invalid["effective"]:
                        reasons.append("calibration_invalidated_for_measurement")
                    if invalid["evidence"] != "available_matching_bytes":
                        reasons.append("invalidation_evidence_" + invalid["evidence"])
        ready = state == "observed" and not reasons
        outcomes.append(
            {
                "instance_id": identifier,
                "declared_weighing_state": state,
                "ready_for_engineering_review": ready,
                "synthetic_fixture_complete": state == "synthetic" and not reasons,
                "blocking_reasons": reasons,
                "calibration_expired_at_review_time": expired_now,
            }
        )
    if seen != set(source):
        raise ValueError("readiness records must cover exactly the supplied fabrication rows")
    return {
        "schema_version": 1,
        "evidence_class": CLASS,
        "as_of_utc": now.isoformat(),
        "input_canonical_sha256": {
            "fabrication_records": canonical_sha256(fabrication),
            "printable_manifest": canonical_sha256(manifest),
            "readiness_sidecar": canonical_sha256(sidecar),
        },
        "declarations_and_artifact_availability_only": True,
        "certificate_or_uncertainty_content_authenticated": False,
        "confidence_probability_inferred_from_coverage_factor": None,
        "ready_observed_record_count": sum(row["ready_for_engineering_review"] for row in outcomes),
        "complete_synthetic_fixture_count": sum(
            row["synthetic_fixture_complete"] for row in outcomes
        ),
        "unreported_instance_ids": base["unreported_instance_ids"],
        "qualification": dict(QUALIFICATION),
        "records": outcomes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["template", "assess"])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "hardware/cad/thor-printable-assets-v1.json",
    )
    parser.add_argument("--fabrication", type=Path, required=True)
    parser.add_argument("--readiness", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--as-of-utc")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fabrication, manifest = strict_json(args.fabrication), strict_json(args.manifest)
    if args.mode == "template":
        if any(value is not None for value in (args.readiness, args.evidence_root, args.as_of_utc)):
            parser.error("template mode does not consume assessment arguments")
        result = template(fabrication, manifest)
    else:
        if args.readiness is None or args.evidence_root is None or args.as_of_utc is None:
            parser.error("assess requires readiness, evidence-root and as-of-utc")
        result = assess(
            strict_json(args.readiness),
            fabrication,
            manifest,
            evidence_root=args.evidence_root,
            as_of_utc=args.as_of_utc,
        )
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
