"""Honest full-native queue provenance; unchanged existing 3MF serializer gates."""

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
draft = importlib.import_module("compose_thor_full_print_drafts")


@pytest.fixture(scope="module")
def inputs():
    joined, _, _, _ = draft.full.load_evidence()
    return (
        json.loads(draft.AUDIT_PATH.read_bytes()),
        json.loads(draft.PARENT_PATH.read_bytes()),
        joined,
    )


def test_full_queue_separates_mesh_candidate_counts_from_existing_Art1_gate(inputs):
    audit, parent, joined = inputs
    plan = draft.full_native_draft_plan(audit, parent, joined)
    assert plan["evidence_class"] == draft.composer.NATIVE_PLAN_CLASS
    assert audit["evidence_class"] == draft.full.HOST_CLASS
    assert plan["native_mesh_audit_canonical_sha256"] == draft.canonical_sha256(audit)
    assert plan["counts"] == {
        "full_registry_variants": 47,
        "full_registry_installed_instances": 65,
        "host_mesh_candidates": 45,
        "composer_candidate_variants": 44,
        "composer_candidate_instances": 61,
        "composer_blocked_variants": 3,
        "composer_blocked_instances": 4,
    }
    blocked = {row["asset_id"]: row for row in plan["blocked_groups"]}
    assert set(blocked) == {"Art1Body::Body", "Art23Optodisk::Body", "Art4TransmissionColumn::Body"}
    assert (
        "existing_composer_Art1_history_exact_solid_gate_remains_unaccepted"
        in blocked["Art1Body::Body"]["blockers"]
    )
    assert blocked["Art23Optodisk::Body"]["quantity"] == 2
    assert not any(plan["qualification"].values())


def test_each_candidate_keeps_actual_per_batch_pins_and_passes_unchanged_composer_preflight(inputs):
    audit, parent, joined = inputs
    plan = draft.full_native_draft_plan(audit, parent, joined)
    by_identity = {
        (row["installed_asset_id"], row["geometry_variant"]): row for row in audit["selections"]
    }
    for group in plan["draft_plate_groups"]:
        identity = group["asset_id"], group["geometry_variant"]
        source = by_identity[identity]
        _, mesh, _, _, _ = draft.composer._draft_inputs(
            plan, identity[0], group["repeat_plate_count"], identity[1]
        )
        binding = mesh["native_export_binding"]
        actual = source["actual_batch_bindings"]
        assert binding["native_capture_raw_sha256"] == actual["raw_capture_sha256"]
        assert binding["native_launcher_raw_sha256"] == actual["raw_runner_sha256"]
        assert binding["request_raw_sha256"] == actual["request_sha256"]
        assert binding["actual_batch_index"] == source["batch_index"]
        assert binding["source_binding"] == source["source_binding"]
        assert binding["native_to_installed_transform"] is None
        assert binding["surface_equivalence_qualified"] is False
    assert (
        len(
            {
                row["native_export_binding"]["native_capture_raw_sha256"]
                for row in plan["mesh_audit"]
                if "native_export_binding" in row
            }
        )
        == 6
    )


@pytest.mark.parametrize(
    "bad",
    [
        "audit_class",
        "whole_capture_hash",
        "wrong_request",
        "missing_row",
        "duplicate_row",
        "source_binding",
        "batch_capture",
        "quantity",
        "installed_id",
        "frame",
        "qualification",
        "missing_qualification",
        "counts",
        "parent_quantity",
        "parent_class",
    ],
)
def test_full_queue_rejects_stale_misclassified_or_mixed_provenance(inputs, bad):
    original, parent_original, joined = inputs
    audit, parent = copy.deepcopy(original), copy.deepcopy(parent_original)
    row = audit["selections"][0]
    if bad == "audit_class":
        audit["evidence_class"] = draft.full.selected_audit.HOST_CLASS
    elif bad == "whole_capture_hash":
        audit["native_aggregate_canonical_sha256"] = "0" * 64
    elif bad == "wrong_request":
        audit["full_request_raw_sha256"] = "0" * 64
    elif bad == "missing_row":
        audit["selections"].pop()
    elif bad == "duplicate_row":
        audit["selections"][-1] = copy.deepcopy(row)
    elif bad == "source_binding":
        row["source_binding"]["object_name"] = "unaccepted_candidate"
    elif bad == "batch_capture":
        row["actual_batch_bindings"]["raw_capture_sha256"] = "0" * 64
    elif bad == "quantity":
        row["installed_quantity"] += 1
    elif bad == "installed_id":
        row["installed_instance_ids"][0] = "invented physical instance"
    elif bad == "frame":
        row["coordinate_frame"] = "inferred_installed"
    elif bad == "qualification":
        row["qualification"]["manufacturing_release"] = True
    elif bad == "missing_qualification":
        audit["qualification"] = {}
    elif bad == "counts":
        audit["counts"]["candidate_geometry_variants"] = 47
    elif bad == "parent_quantity":
        parent["draft_plate_groups"][0]["repeat_plate_count"] += 1
    else:
        parent["evidence_class"] = "invented_upstream_plan"
    with pytest.raises(ValueError):
        draft.full_native_draft_plan(audit, parent, joined)


def test_queue_only_cli_is_portable_explicitly_not_created_projects_and_exclusive(tmp_path):
    destination = tmp_path / "new-queue"
    command = [
        sys.executable,
        str(ROOT / "tools/compose_thor_full_print_drafts.py"),
        "--output-dir",
        str(destination),
        "--queue-only",
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    receipt = json.loads((destination / "receipt.json").read_bytes())
    assert receipt["queue_only"] and receipt["created_project_count"] == 0
    assert not receipt["complete_queue_export"] and receipt["requested_project_count"] == 61
    assert not receipt["manufacturing_release"]
    assert not list(destination.glob("*.3mf"))
    original = (destination / "receipt.json").read_bytes()
    assert b"\r\n" not in original
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode != 0 and (destination / "receipt.json").read_bytes() == original


def test_coherently_edited_optodisk_eligibility_fails_before_queue_or_files(
    inputs, tmp_path, monkeypatch
):
    original, parent, joined = inputs
    audit = copy.deepcopy(original)
    row = next(
        row for row in audit["selections"] if row["installed_asset_id"] == "Art23Optodisk::Body"
    )
    row["blockers"] = []
    row["draft_candidate"] = True
    audit["counts"].update(
        candidate_geometry_variants=46,
        blocked_geometry_variants=1,
        candidate_installed_instances=64,
        blocked_installed_instances=1,
    )
    with pytest.raises(ValueError, match="mesh topology is blocked"):
        draft.full_native_draft_plan(audit, parent, joined)
    candidate = tmp_path / "modified-audit.json"
    candidate.write_text(json.dumps(audit), encoding="utf-8", newline="\n")
    monkeypatch.setattr(draft, "AUDIT_PATH", candidate)
    destination = tmp_path / "must-not-be-created"
    with pytest.raises(SystemExit) as caught:
        draft.main(["--queue-only", "--output-dir", str(destination)])
    assert caught.value.code != 0 and not destination.exists()
