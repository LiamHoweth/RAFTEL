"""Preliminary static loads and an optimistic floor-reach bound, in SI units.

This is an analytical sensitivity study, not a model of verified ARM-01 CAD.
Run from arm-01 with: python tools/engineering_analysis.py
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

GRAVITY_M_S2 = 9.80665


@dataclass(frozen=True)
class PointLoad:
    """Mass and horizontal center of mass measured from the shoulder."""

    name: str
    mass_kg: float
    x_m: float

    def __post_init__(self) -> None:
        if not self.name or not math.isfinite(self.mass_kg) or self.mass_kg < 0:
            raise ValueError("Point load needs a name and finite nonnegative mass")
        if not math.isfinite(self.x_m) or self.x_m < 0:
            raise ValueError("Center of mass must be finite and nonnegative")


def static_torque_nm(loads: tuple[PointLoad, ...], joint_x_m: float = 0.0) -> float:
    """Horizontal-pose gravity moment; proximal loads are not downstream.

    This deliberately does not model other poses, inertia, friction, collisions,
    transmissions or the torque of a vertical yaw/roll axis.
    """
    if not math.isfinite(joint_x_m) or joint_x_m < 0:
        raise ValueError("Joint position must be finite and nonnegative")
    return GRAVITY_M_S2 * sum(
        load.mass_kg * (load.x_m - joint_x_m) for load in loads if load.x_m >= joint_x_m
    )


def proposed_loads(payload_kg: float = 0.2, length_scale: float = 1.0) -> tuple[PointLoad, ...]:
    """Unmeasured mass estimates; 0.40 m full extension at scale 1."""
    if not math.isfinite(length_scale) or length_scale <= 0:
        raise ValueError("Length scale must be finite and positive")
    assumed = (
        ("upper_link", 0.120, 0.090),
        ("elbow_flex_servo", 0.055, 0.180),
        ("forearm_link", 0.100, 0.250),
        ("added_elbow_roll_servo", 0.055, 0.210),
        ("wrist_pitch_servo", 0.055, 0.320),
        ("wrist_roll_servo", 0.055, 0.350),
        ("gripper_servo", 0.055, 0.375),
        ("gripper_jaws", 0.060, 0.390),
        ("payload", payload_kg, 0.400),
    )
    return tuple(PointLoad(name, mass, position * length_scale) for name, mass, position in assumed)


def floor_outer_radius_m(
    reach_m: float, shoulder_height_m: float, tcp_height_m: float = 0.025
) -> float | None:
    """Optimistic horizontal radius from a sphere; None means outside it.

    A returned radius is only a necessary outer bound. It does not establish a
    reachable orientation, joint-limit feasibility, or chassis clearance.
    """
    values = (reach_m, shoulder_height_m, tcp_height_m)
    if not all(math.isfinite(value) and value >= 0 for value in values) or reach_m == 0:
        raise ValueError("Reach must be positive; heights finite and nonnegative")
    dz = abs(shoulder_height_m - tcp_height_m)
    if math.isclose(dz, reach_m, rel_tol=0.0, abs_tol=1e-12):
        return 0.0
    if dz > reach_m:
        return None
    return math.sqrt(max(0.0, reach_m**2 - dz**2))


def report() -> dict[str, object]:
    """Return reproducible scenarios, with validation class in the output."""
    scenarios = []
    for length_scale in (1.0, 0.75):
        for payload_kg in (0.0, 0.1, 0.2):
            loads = proposed_loads(payload_kg, length_scale)
            shoulder = static_torque_nm(loads)
            elbow = static_torque_nm(loads, 0.18 * length_scale)
            scenarios.append(
                {
                    "reach_m": 0.4 * length_scale,
                    "payload_kg": payload_kg,
                    "shoulder_static_nm": round(shoulder, 6),
                    "elbow_static_nm": round(elbow, 6),
                    "shoulder_with_1p5_allowance_nm": round(shoulder * 1.5, 6),
                    "elbow_with_1p5_allowance_nm": round(elbow * 1.5, 6),
                }
            )
    return {
        "validation_class": "preliminary_analytical_estimate_not_hardware_or_ik",
        "assumptions": {
            "gravity_m_s2": GRAVITY_M_S2,
            "loads_at_full_extension": [asdict(load) for load in proposed_loads()],
            "allowance_factor": 1.5,
            "allowance_is_not_a_dynamic_or_thermal_validation": True,
        },
        "static_scenarios": scenarios,
        "floor_outer_bounds": [
            {
                "mount_height_m": height,
                "shoulder_offset_above_mount_m": 0.06,
                "tcp_height_m": 0.025,
                "max_horizontal_radius_m": round(floor_outer_radius_m(0.4, height + 0.06), 6),
                "chassis_and_joint_limits_checked": False,
            }
            for height in (0.15, 0.225, 0.3)
        ],
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, allow_nan=False))
