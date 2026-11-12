"""Synthetic captures test guards; only Root executes copied native CAD."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review = load(ROOT / "tools/thor_wrist_frame_capture_review.py", "wrist_capture_review")
contract = load(ROOT / "tools/thor_wrist_pose_contract.py", "wrist_capture_contract")
native = load(ROOT / "tools/probe_thor_wrist_frames_desktop.py", "wrist_capture_native")


def transform_from_points(function):
    origin = function([0, 0, 0])
    axes = [function([float(i == j) for i in range(3)]) for j in range(3)]
    return [[axes[j][i] - origin[i] for j in range(3)] + [origin[i]] for i in range(3)] + [
        [0, 0, 0, 1]
    ]


def pose_fixture():
    reference, _ = review.source_marker_reference()
    poses = []
    identity = review._identity()
    for name, q5, q6 in review.POSES:
        fold = transform_from_points(
            lambda p, a=q5, b=q6: contract.expected_marker(p, a, b, roll=False)
        )
        pose = {
            "name": name,
            "q5_rad": q5,
            "q6_rad": q6,
            "master_wrist_placement": {"matrix": fold},
            "bodies": [],
        }
        for key in review.BODY_NAMES:
            stationary = key == "AssemblyArt4"
            if stationary:
                asset, points, indices = (
                    "AssemblyArt4",
                    [[0, 0, 0], [3, 0, 0], [0, 4, 0]],
                    [0, 1, 2],
                )
                source = points
                world = points
                placement = identity
            else:
                asset = key.split("_")[0]
                variant = reference[asset + "::Body"]
                points = variant["source_vertices_mm"]
                indices = native.select_marker_indices(points)
                source = [points[i] for i in indices]
                transform = transform_from_points(
                    lambda p, a=q5, b=q6, k=key: contract.expected_marker(
                        p, a, b, roll=k != review.BODY_NAMES[2]
                    )
                )
                placement = review.compose(review.inverse(fold), transform)
                world = [
                    contract.expected_marker(p, q5, q6, roll=key != review.BODY_NAMES[2])
                    for p in source
                ]
            raw = [
                list(
                    review._module("probe_thor_printed_tensor_frames.py", "test_point_math").point(
                        placement, p
                    )
                )
                for p in source
            ]
            body = {
                "document": "Assembly" if stationary else "AssemblyArt56",
                "object": key,
                "type_id": "App::Link",
                "linked_document": asset,
                "linked_object": "Model" if stationary else "Body",
                "vertex_count": len(points),
                "marker_vertex_indices_zero_based": indices,
                "raw_shape_markers_subassembly_mm": raw,
                "actual_markers_native_world_mm": world,
                "marker_frame_native_world_mm": native.marker_frame(world),
                "body_frame_native_world_mm": identity
                if stationary
                else review.compose(fold, placement),
                "placement_in_subassembly": {"matrix": placement},
                "shape_placement": {"matrix": placement},
                "linked_source_placement": {"matrix": identity},
                "link_transform": False,
                "linked_source_markers_mm": source,
                "linked_source_vertex_count": len(points),
                "shape_own_placement_not_applied_twice": True,
                "ordered_raw_vertices_sha256": hashlib.sha256(json.dumps(raw).encode()).hexdigest(),
                "state": ["Touched"],
            }
            if not stationary:
                variant = reference[asset + "::Body"]
                pinned = variant["source_binding"]
                body.update(
                    cached_source_binding={
                        **pinned,
                        "source_file": Path(pinned["source_file"]).name,
                        "source_raw_placement": [v for row in identity for v in row],
                    },
                    cached_source_markers_mm=source,
                    cached_source_vertex_count=len(points),
                )
            pose["bodies"].append(body)
        poses.append(pose)
    return json.loads(json.dumps(poses))


def test_actual_markers_source_link_products_refresh_stationary_and_return():
    result = review.review_body_observations(pose_fixture(), contract.expected_marker)
    assert result["observed_bodies_per_pose"] == 4
    assert result["maximum_motion_error_mm"] < 1e-9


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p[1]["bodies"][0].update(
            raw_shape_markers_subassembly_mm=p[0]["bodies"][0]["raw_shape_markers_subassembly_mm"]
        ),
        lambda p: p[1]["bodies"][0].update(linked_document="OtherSource"),
        lambda p: p[0]["bodies"][0]["linked_source_markers_mm"][0].__setitem__(0, 999),
        lambda p: p[0]["bodies"][0]["cached_source_binding"].update(brep_sha256="0" * 64),
        lambda p: p[1]["bodies"][0]["body_frame_native_world_mm"][0].__setitem__(0, -2),
        lambda p: p[1]["bodies"][0].update(
            ordered_raw_vertices_sha256=p[0]["bodies"][0]["ordered_raw_vertices_sha256"]
        ),
        lambda p: p[2]["bodies"][0]["raw_shape_markers_subassembly_mm"][0].__setitem__(0, 1),
        lambda p: p[1]["bodies"][3]["actual_markers_native_world_mm"][0].__setitem__(0, 1),
        lambda p: p[0]["bodies"][0].update(marker_vertex_indices_zero_based=[0, 0, 1]),
        lambda p: p[0]["bodies"][0]["shape_placement"]["matrix"][0].__setitem__(3, 0.01),
        lambda p: p[1].update(q5_rad=True),
        lambda p: p.reverse(),
    ],
)
def test_counterfeit_or_stale_native_witnesses_rejected(mutate):
    poses = copy.deepcopy(pose_fixture())
    mutate(poses)
    with pytest.raises(ValueError):
        review.review_body_observations(poses, contract.expected_marker)


@pytest.mark.parametrize("points", [[[0, 0, 0]] * 3, [[0, 0, 0], [1, 1, 1], [2, 2, 2]]])
def test_collinear_marker_frame_is_not_rotation_evidence(points):
    with pytest.raises(ValueError, match="noncollinear"):
        review._marker_frame(points)


@pytest.mark.parametrize("capture", [None, {}, [], {"schema_version": True}, {"schema_version": 1}])
def test_partial_report_never_complete(capture):
    assert review.report_is_complete(capture) is False


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"[]"])
def test_file_entry_strict_json_rejects_ambiguous_values(tmp_path, raw):
    reader = review._module("thor_printed_inertia_study.py", "wrist_test_json")
    path = tmp_path / "capture.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        reader.strict_json(path)


def capture_fixture():
    declaration = load(
        ROOT / "tests/test_wrist_pose_contract.py", "wrist_capture_declaration"
    ).PINNED_DECLARATION
    _, pins = review.source_marker_reference()
    paths = {k: "C:/isolated/" + k for k in review.PATH_KEYS}
    poses = pose_fixture()
    drivers = [
        {
            "document": Path(b["document"]).stem,
            "object": b["object"],
            "expressions": b["saved_expression_engine"],
            "offset": {"matrix": review.saved_placement_matrix(b["saved_attachment_offset"])},
        }
        for b in declaration["bindings"][:2]
    ]
    for pose in poses:
        pose.update(
            state_summary={"invalid_or_error": []},
            recompute_returns={"wrist": 60, "master": 2},
            driver_readbacks=copy.deepcopy(drivers),
        )
    foundation = json.loads(
        (ROOT / "hardware/cad/thor-windows-native-foundation-v1.json").read_text()
    )
    module_pins = {
        k: {"root": "C:/addons", "sha256": v["sha256"]}
        for k, v in foundation["smoke"]["modules"].items()
        if "sha256" in v
    }
    capture = {
        "schema_version": 1,
        "evidence_class": "native_existing_AppLink_wrist_offsets_and_cached_shape_refresh",
        "status": "complete_native_wrist_observations_pending_independent_review",
        "errors": [],
        "request": {
            "schema_version": 1,
            "source_contract": declaration,
            "source_sha256": pins,
            "poses": [{"name": n, "q5_rad": a, "q6_rad": b} for n, a, b in review.POSES],
        },
        "capture_script_sha256": hashlib.sha256(
            (ROOT / "tools/probe_thor_wrist_frames_desktop.py").read_bytes()
        ).hexdigest(),
        "request_sha256": "1" * 64,
        "helper_sha256": {
            k: hashlib.sha256((ROOT / "tools" / f).read_bytes()).hexdigest()
            for k, f in (
                ("audit_helper_sha256", "audit_freecad_assembly.py"),
                ("pose_helper_sha256", "probe_thor_pose_frames_desktop.py"),
                ("contract_helper_sha256", "thor_wrist_pose_contract.py"),
            )
        },
        "source_copy_sha256_before": pins,
        "source_copy_sha256_after": pins,
        "open_document_count_before": 0,
        "open_document_count_after_close": 0,
        "elapsed_s": 120,
        "runtime_isolation": {
            "requested": True,
            "verified": True,
            "root": "C:/isolated",
            "actual_paths": paths,
        },
        "expected_runtime_paths": copy.deepcopy(paths),
        "modules": {
            k: {"path": "C:/addons/" + k + ".py", "sha256": v["sha256"], "origin_verified": True}
            for k, v in module_pins.items()
        },
        "loaded_documents": [
            {
                "document": row["document"],
                "filename": "C:/isolated/source/" + review._path(row["path"]).name,
                "sha256": row["sha256"],
            }
            for row in review._baseline_capture()["loaded_document_sources"]
        ],
        "freecad_version": ["1", "1", "4"],
        "opencascade_version": "7.8.1",
        "final_loaded_document_states": [],
        "final_state_summary": {
            "documents": 0,
            "objects": 0,
            "non_up_to_date": [],
            "invalid_or_error": [],
        },
        "driver_original_readback": drivers,
        "poses": poses,
    }
    for key in (
        "cad_documents_saved",
        "forced_feature_history_rebuild",
        "constraint_kinematics_solved",
        "side_differential_gears_driven",
        "physical_calibration_or_contact_or_TCP_qualified",
    ):
        capture[key] = False
    for key in (
        "source_copy_bytes_unchanged",
        "preexisting_documents_preserved",
        "saved_offsets_restored_in_memory",
        "offset_cleanup_assignment_completed",
    ):
        capture[key] = True
    for pose in poses:
        pose["driver_readbacks"][0]["offset"]["matrix"] = review.compose(
            drivers[0]["offset"]["matrix"], review._rotation((1, 0, 0), pose["q5_rad"])
        )
        pose["driver_readbacks"][1]["offset"]["matrix"] = review.compose(
            review._rotation((0, 0, 1), pose["q6_rad"]), drivers[1]["offset"]["matrix"]
        )
    capture["final_loaded_document_states"] = [
        {"document": row["document"], "objects": []} for row in capture["loaded_documents"]
    ]
    capture["final_state_summary"]["documents"] = 53
    return json.loads(json.dumps(capture)), {
        "expected_module_pins": module_pins,
        "expected_request_sha256": "1" * 64,
    }


def test_complete_host_capture_checks_all_source_and_runtime_evidence():
    capture, pins = capture_fixture()
    assert review.validate_capture(capture, **pins)["physical_calibration_qualified"] is False


@pytest.mark.parametrize("value", [True, False, -1, 1.0, "60", None, 100001])
def test_native_recompute_object_count_is_bounded_integer_not_truth_value(value):
    capture, pins = capture_fixture()
    capture["poses"][0]["recompute_returns"]["wrist"] = value
    with pytest.raises(ValueError, match="recompute return"):
        review.validate_capture(capture, **pins)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.update(source_copy_bytes_unchanged=False),
        lambda c: c.update(open_document_count_before=True),
        lambda c: c.update(status="starting"),
        lambda c: c.update(capture_script_sha256="0" * 64),
        lambda c: c.update(request_sha256="0" * 64),
        lambda c: c["helper_sha256"].update(contract_helper_sha256="0" * 64),
        lambda c: c["source_copy_sha256_after"].update(unknown="0" * 64),
        lambda c: c["request"]["source_contract"].update(angle_units="degrees"),
        lambda c: c["request"]["poses"][0].update(q5_rad=False),
        lambda c: c["runtime_isolation"]["actual_paths"].update(UserHomePath="C:/outside"),
        lambda c: c["runtime_isolation"]["actual_paths"].update(
            UserHomePath="C:/isolated/../outside"
        ),
        lambda c: c["expected_runtime_paths"].update(UserHomePath="C:/elsewhere"),
        lambda c: c["modules"]["FastenersCmd"].update(sha256="0" * 64),
        lambda c: c["modules"]["FastenersCmd"].update(path="C:/other/unreviewed.py"),
        lambda c: c["loaded_documents"][0].update(filename="C:/outside/Assembly.FCStd"),
        lambda c: c["loaded_documents"][0].update(document="SubstitutedDocument"),
        lambda c: c["poses"][1]["driver_readbacks"][0].update(
            offset=c["driver_original_readback"][0]["offset"]
        ),
        lambda c: c["final_loaded_document_states"].append(
            {
                "document": "Hidden",
                "objects": [{"name": "Broken", "type": "PartDesign::Body", "state": ["Invalid"]}],
            }
        ),
        lambda c: c["poses"][2]["driver_readbacks"][0]["offset"]["matrix"][0].__setitem__(3, 1),
        lambda c: c["poses"][1]["driver_readbacks"][0].update(expressions=[]),
    ],
)
def test_full_capture_preservation_runtime_identity_and_return_negative_guards(mutate):
    capture, pins = capture_fixture()
    mutate(capture)
    with pytest.raises(ValueError):
        review.validate_capture(capture, **pins)
