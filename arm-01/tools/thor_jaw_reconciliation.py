"""Bind saved jaw metadata and per-leaf ownership without a CAD runtime.

Generation requires pinned local source archives; check/replay is offline Python.
Never recomputes/saves CAD, downloads sources, or overwrites an evidence report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

from extract_thor_geometry import placement, transform_point

from raftel_arm01.kinematics.thor_jaw_bodies import (
    FRAME,
    SOURCE_REVISION,
    canonical_sha256,
    jaw_body_states,
    validate_jaw_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
PINNED = {
    "Assembly.FCStd": "5ee729246229e7494466010ab68e2c2367ba4ec1361b7701df21c0f8b00c2c1b",
    "AssemblyArt56.FCStd": "a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473",
    "GripperBot.FCStd": "a65e68644312adee7381e3a640b2b827f9c2c3362bbe4a842ccee9fea969d176",
    "GripperArm.FCStd": "f1511f4b319a5727cf07771abe4c75002d5527e0a10291d47c1fe8024a44c6fc",
    "GripperActiveArm.FCStd": "3ba5ba6f74c5d2f45eeca56f28534dc750e7f0ae735b6a0b3e16beeef21adc67",
    "GripperPassiveArm.FCStd": "d14ac1debf67735fd623e052d468a9773066c32356390799b4ea07addcba68d4",
    "GripperFinger.FCStd": "ab4daca4dd2f447029f4c76150b7f617fbdda74ae467cf6962938efe148d57a6",
}
BOT = "GripperBot_GripperBot"
ACTIVE = "GripperActiveArm_GripperActiveArm"
PASSIVE = "Unnamed3_GripperPassiveArm"
FINGER_SIDES = {
    "Unnamed1_GripperFinger": -1,
    "Nut021": -1,
    "Screw022": -1,
    "Screw023": -1,
    "Nut022": -1,
    "Unnamed1_GripperFinger_mirrored": 1,
    "Nut020": 1,
    "Screw024": 1,
    "Screw025": 1,
    "Nut019": 1,
}
LINKS = {
    ACTIVE: ("active_driven", -1),
    "Clone041003009009001": ("active_driven", -1),
    "Screw027": ("active_driven", -1),
    "Screw028": ("active_driven", -1),
    "Screw026": ("active_driven", -1),
    PASSIVE: ("passive_driven", 1),
    "Unnamed2_GripperArm001": ("left_auxiliary", -1),
    "Unnamed2_GripperArm": ("right_auxiliary", 1),
}


def _read_source(path: Path, expected_hash: str) -> dict[str, ET.Element]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError(f"source hash differs: {path.name}")
    with zipfile.ZipFile(path) as archive:
        if archive.getinfo("Document.xml").file_size > 20_000_000:
            raise ValueError("native XML exceeds selected-source audit bound")
        root = ET.fromstring(archive.read("Document.xml"))
    objects = root.findall("./ObjectData/Object")
    result = {obj.attrib["name"]: obj for obj in objects}
    if len(result) != len(objects):
        raise ValueError("duplicate native object ID")
    return result


def read_evidence_json(path: Path) -> dict:
    """Reject duplicate keys and every nonfinite JSON number at the file boundary."""

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def finite_float(raw):
        result = float(raw)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result

    def reject_constant(raw):
        raise ValueError(f"nonfinite JSON constant: {raw}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique,
        parse_float=finite_float,
        parse_constant=reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError("evidence JSON root must be an object")
    return value


def _frame(saved: dict) -> list[list[float]]:
    origin = saved["position_m"]
    basis = [transform_point(saved, [float(i == j) for i in range(3)]) for j in range(3)]
    return [[basis[j][i] - origin[i] for j in range(3)] + [origin[i]] for i in range(3)] + [
        [0, 0, 0, 1]
    ]


def _multiply(left: list, right: list) -> list[list[float]]:
    return [
        [math.fsum(left[i][k] * right[k][j] for k in range(4)) for j in range(4)] for i in range(4)
    ]


def _property_string(obj: ET.Element, name: str) -> str | None:
    value = obj.find(f'./Properties/Property[@name="{name}"]/String')
    return value.attrib["value"] if value is not None else None


def _verify_saved_points(source_objects: dict, capture: dict) -> None:
    """Recompute source placement arithmetic only, never native feature geometry."""
    assembly = source_objects["AssemblyArt56.FCStd"]
    bot = _frame(placement(assembly[BOT]))

    def in_bot(obj_name: str, local_mm: list[float]) -> list[float]:
        positioned = transform_point(placement(assembly[obj_name]), [v / 1000 for v in local_mm])
        delta = [positioned[i] - bot[i][3] for i in range(3)]
        return [math.fsum(bot[j][i] * delta[j] for j in range(3)) for i in range(3)]

    passive_tip = source_objects["GripperPassiveArm.FCStd"]["LCS_GripperPassiveArm_1"]
    passive_tip_mm = [v * 1000 for v in placement(passive_tip)["position_m"]]
    checks = {
        "active_driven_pivot": (ACTIVE, [0, 0, 2.3]),
        "active_driven_tip": (ACTIVE, [35, 0, 0]),
        "passive_driven_pivot": (PASSIVE, [0, 0, 0]),
        "passive_driven_tip": (PASSIVE, passive_tip_mm),
        "left_auxiliary_pivot": ("Unnamed2_GripperArm001", [0, 0, 0]),
        "left_auxiliary_tip": ("Unnamed2_GripperArm001", [0, 35, 0]),
        "right_auxiliary_pivot": ("Unnamed2_GripperArm", [0, 0, 0]),
        "right_auxiliary_tip": ("Unnamed2_GripperArm", [0, 35, 0]),
        "left_finger_driven_hole": ("Unnamed1_GripperFinger", [4, 4, 12.5]),
        "left_finger_auxiliary_hole": ("Unnamed1_GripperFinger", [12.5, 22.5, 12.5]),
        "right_finger_driven_hole": ("GripperFinger_sym001", [-4, 4, 12.5]),
        "right_finger_auxiliary_hole": ("GripperFinger_sym001", [-12.5, 22.5, 12.5]),
    }
    for key, (name, local_mm) in checks.items():
        expected = capture["saved_assembly_points_in_bot_frame_mm"][key]
        if math.dist(in_bot(name, local_mm), [v / 1000 for v in expected]) > 1e-12:
            raise ValueError(f"saved capture point disagrees with pinned XML: {key}")
    points = capture["saved_assembly_points_in_bot_frame_mm"]
    for side, driven in (("left", "active"), ("right", "passive")):
        for kind, endpoint in (
            ("driven", f"{driven}_driven_tip"),
            ("auxiliary", f"{side}_auxiliary_tip"),
        ):
            residual = capture["saved_loop_axis_residuals"][f"{side}_{kind}"]
            hole = points[f"{side}_finger_{kind}_hole"]
            delta = [points[endpoint][i] - hole[i] for i in (0, 1)]
            declared_delta = residual["projected_xy_delta_mm"]
            declared_norm = residual["projected_axis_misalignment_mm"]
            if (
                len(declared_delta) != 2
                or not all(math.isfinite(v) for v in (*declared_delta, declared_norm))
                or math.dist(delta, declared_delta) > 1e-9
                or abs(math.hypot(*delta) - declared_norm) > 1e-9
            ):
                raise ValueError(f"saved capture residual disagrees with its points: {side}_{kind}")


def _normalization(capture: dict, key: str, side: int) -> dict:
    points = capture["saved_assembly_points_in_bot_frame_mm"]
    pivot = [v / 1000 for v in points[key + "_pivot"]]
    tip = [v / 1000 for v in points[key + "_tip"]]
    phase = math.atan2(tip[1] - pivot[1], side * (tip[0] - pivot[0]))
    if key.endswith("auxiliary"):
        ideal = [side * 0.006, 0.051, pivot[2]]
    else:
        ideal = [side * 0.0145, 0.0325, pivot[2]]
    return {
        "saved_pivot_bot_m": pivot,
        "ideal_pivot_bot_m": ideal,
        "saved_closing_phase_rad": phase,
    }


def build_jaw_ledger(source: Path, inventory: dict, memberships: dict, capture: dict) -> dict:
    """Extract attachment ownership and an explicit conditional ideal overlay."""
    if (
        type(capture.get("schema_version")) is not int
        or capture["schema_version"] != 1
        or capture.get("validation_class")
        != "pinned_saved_geometry_and_conditional_nominal_jaw_model"
        or capture.get("recomputed") is not False
        or capture.get("saved_source_changes") is not False
    ):
        raise ValueError("jaw source capture must be the explicit saved-geometry evidence class")
    if capture.get("source_revision") != SOURCE_REVISION:
        raise ValueError("gripper capture uses a different source revision")
    if capture.get("source_sha256", {}).get("AssemblyArt56.FCStd") != PINNED["AssemblyArt56.FCStd"]:
        raise ValueError("gripper capture assembly hash differs")
    source_objects = {name: _read_source(source / name, digest) for name, digest in PINNED.items()}
    for name, digest in capture.get("source_sha256", {}).items():
        if PINNED.get(name) != digest:
            raise ValueError(f"gripper capture source hash differs: {name}")
    _verify_saved_points(source_objects, capture)
    master = source_objects["Assembly.FCStd"]
    assembly = source_objects["AssemblyArt56.FCStd"]
    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    for model in (master["Model"], assembly["Model"]):
        if _frame(placement(model)) != identity:
            raise ValueError("this audit expects the pinned identity Model group frames")
    native_from_bot = _multiply(
        _frame(placement(master["AssemblyArt56"])), _frame(placement(assembly[BOT]))
    )
    by_motion = {row["instance_id"]: row["motion_class"] for row in memberships["memberships"]}
    records = []
    found_moving = set()
    for body in inventory["mounted_bodies"]:
        if body["root_subassembly"] != "AssemblyArt56":
            continue
        leaf = body["instance_id"]
        name = leaf.rsplit("::", 1)[1]
        # Whole servo mass was consolidated at its parent asset in the existing ledger.
        mass_id = leaf.rsplit("/", 1)[0] if name == "Compound002" else leaf
        obj = assembly[name]
        owner_obj = assembly["Servomotor001"] if name == "Compound002" else obj
        record = {
            "mass_record_id": mass_id,
            "leaf_instance_ids": [leaf],
            "source_object": "AssemblyArt56::" + name,
            "source_attachment": _property_string(owner_obj, "AttachedTo"),
            "saved_com_native_m": body["zero_world_com_m"],
            "wrist_motion_class": by_motion[leaf],
            "jaw_motion_class": "jaw_fixed",
            "evidence": "No additional jaw COM motion; retain saved pose and v2 wrist membership.",
        }
        if name in FINGER_SIDES:
            record.update(
                jaw_motion_class="finger_translation",
                side=FINGER_SIDES[name],
                evidence=(
                    "Pinned finger/fastener attachment; constant orientation and ideal "
                    "parallelogram translation. Fastener retention is conditional."
                ),
            )
            found_moving.add(name)
        elif name in LINKS:
            key, side = LINKS[name]
            record.update(
                jaw_motion_class="link_rotation",
                side=side,
                evidence=(
                    "Pinned link/horn/fastener attachment; normalize saved phase about "
                    "source +Z, then apply side*q. Active pivot is explicitly symmetrized."
                ),
                **_normalization(capture, key, side),
            )
            found_moving.add(name)
        records.append(record)
    if found_moving != set(FINGER_SIDES) | set(LINKS):
        raise ValueError("missing explicit moving jaw body")
    result = {
        "schema_version": 1,
        "validation_class": "source_XML_ownership_and_conditional_ideal_COM_overlay",
        "source_revision": SOURCE_REVISION,
        "coordinate_frame": FRAME,
        "source_metadata_sha256": dict(PINNED),
        "input_canonical_sha256": {
            "inventory": canonical_sha256(inventory),
            "membership": canonical_sha256(memberships),
            "gripper_capture": canonical_sha256(capture),
        },
        "native_from_gripper_bot": native_from_bot,
        "transform_direction": "native_point = native_from_gripper_bot * bot_point",
        "transform_sources": [
            "Assembly::AssemblyArt56.Placement",
            "AssemblyArt56::GripperBot_GripperBot.Placement",
        ],
        "geometry_leaf_count": len(records),
        "mass_record_count": len(records),
        "motion_counts": dict(sorted(Counter(r["jaw_motion_class"] for r in records).items())),
        "jaw_coordinate": {
            "name": "ideal symmetric closing q from outward-horizontal links",
            "unit": "rad",
            "study_interval": "0 <= q < pi/2, not physical travel",
            "saved_pose_has_solved_q": False,
            "servo_conversion": None,
        },
        "ideal_zero_normalizations": {
            key: _normalization(capture, key, side)
            for key, side in (
                ("active_driven", -1),
                ("passive_driven", 1),
                ("left_auxiliary", -1),
                ("right_auxiliary", 1),
            )
        },
        "saved_loop_axis_residuals": capture["saved_loop_axis_residuals"],
        "assumptions": [
            "Ideal symmetric 35mm uncrossed parallelogram; saved loops remain unsolved.",
            "Finger fasteners translate with fingers; pin fasteners attached to base stay fixed.",
            "Horn and active-arm screws rotate together; actual retention requires inspection.",
            "Servo whole-asset COM remains fixed under balanced-internal-COM approximation.",
            "No rotor mass is added to the existing 55g servo or 2.120kg arm motor total.",
            "Saved native GripperBot orientation is preserved exactly, not rounded to axes.",
        ],
        "physical_motion_qualified": False,
        "native_recompute_performed": False,
        "source_saved": False,
        "remaining_gates": [
            "Native multi-pose driven/auxiliary loop and gear-contact reconciliation.",
            "Collision, travel stops, servo zero/range and jaw/TCP physical calibration.",
            "Actual mass/COM, pin retention, servo imbalance, grasp force and thermal duty.",
        ],
        "records": records,
    }
    validate_jaw_ledger(result, inventory, memberships)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument(
        "--inventory", type=Path, default=ROOT / "hardware/cad/thor-mounted-geometry-v2.json"
    )
    parser.add_argument(
        "--membership", type=Path, default=ROOT / "hardware/cad/thor-wrist-membership-v2.json"
    )
    parser.add_argument(
        "--gripper-capture", type=Path, default=ROOT / "hardware/cad/thor-gripper-kinematics.json"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-ledger", type=Path)
    args = parser.parse_args()
    try:
        inventory = read_evidence_json(args.inventory)
        membership = read_evidence_json(args.membership)
        if args.check_ledger:
            if args.source_dir or args.output:
                raise ValueError("check-ledger cannot be combined with generation options")
            ledger = read_evidence_json(args.check_ledger)
            validate_jaw_ledger(ledger, inventory, membership)
            capture = read_evidence_json(args.gripper_capture)
            if ledger["input_canonical_sha256"]["gripper_capture"] != canonical_sha256(capture):
                raise ValueError("stale gripper capture")
        else:
            if not args.source_dir or not args.output:
                raise ValueError("generation requires source-dir and a new output path")
            if args.output.exists():
                raise ValueError("jaw evidence output must be a new file")
            capture = read_evidence_json(args.gripper_capture)
            ledger = build_jaw_ledger(args.source_dir, inventory, membership, capture)
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(ledger, indent=2, allow_nan=False) + "\n")
        for q in (0, math.pi / 6, math.pi / 3):
            jaw_body_states(ledger, q)
        jaw_body_states(ledger, mode="saved")
        print(
            json.dumps(
                {
                    "validation_class": ledger["validation_class"],
                    "mass_record_count": ledger["mass_record_count"],
                    "motion_counts": ledger["motion_counts"],
                    "native_recompute_performed": False,
                    "physical_motion_qualified": False,
                },
                indent=2,
            )
        )
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        zipfile.BadZipFile,
        ET.ParseError,
    ) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
