"""Explicit offline transmission coordinates, independent of controller commands.

The classes evaluate declared ideal mechanisms. Ratios, signs, carrier references
and evidence are required inputs. They do not calibrate shafts, emit commands,
apply losses, or qualify physical torque capacity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


def _finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("values must be finite real numbers")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("values must be finite real numbers") from error
    if not math.isfinite(result):
        raise ValueError("values must be finite real numbers")
    return result


def _positive(value: float) -> float:
    value = _finite(value)
    if value <= 0:
        raise ValueError("ratio must remain positive at machine precision")
    return value


def _sign(value: int) -> int:
    if type(value) is not int or value not in {-1, 1}:
        raise ValueError("sign must be explicitly +1 or -1")
    return value


@dataclass(frozen=True)
class ElbowTransmission:
    """Declared local linear transmission model, with uncalibrated angle signs.

    theta_B = N_s*q2; theta_C = N_s*q2
    theta_E = N_e*(c*q2 + s*k*q3), k=R_pitch/r_pitch.

    theta values are hypothetical physical rotor angles in the declared model,
    not source GRBL address values. c=1 is the moving-carrier belt hypothesis;
    this is not inferred silently. The model assumes a constant local radius.
    """

    driver_radius_m: float
    drum_radius_m: float
    elbow_gearbox_ratio: float
    shoulder_branch_ratio: float
    carrier_coupling: float
    belt_sign: int

    def __post_init__(self) -> None:
        for name in (
            "driver_radius_m",
            "drum_radius_m",
            "elbow_gearbox_ratio",
            "shoulder_branch_ratio",
        ):
            if _finite(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        _finite(self.carrier_coupling)
        if type(self.belt_sign) is not int or self.belt_sign not in {-1, 1}:
            raise ValueError("belt_sign must be explicitly +1 or -1")
        if self.belt_ratio <= 0:
            raise ValueError("belt ratio must remain positive at machine precision")
        _positive(self.elbow_gearbox_ratio * self.belt_ratio)

    @property
    def belt_ratio(self) -> float:
        return _finite(self.drum_radius_m / self.driver_radius_m)

    def rotor_coordinates(self, q2: float, q3: float) -> tuple[float, float, float]:
        q2, q3 = _finite(q2), _finite(q3)
        shoulder = _finite(self.shoulder_branch_ratio * q2)
        elbow = _finite(
            self.elbow_gearbox_ratio
            * (self.carrier_coupling * q2 + self.belt_sign * self.belt_ratio * q3)
        )
        return shoulder, shoulder, elbow

    def joint_coordinates(self, b: float, c: float, e: float) -> tuple[float, float]:
        """Invert the declared model; branch equality is numerical, not a safety limit."""
        b, c, e = _finite(b), _finite(c), _finite(e)
        if not math.isclose(b, c, abs_tol=1e-9, rel_tol=0):
            raise ValueError("shoulder rotor branch coordinates must agree")
        q2 = _finite(b / self.shoulder_branch_ratio)
        q3 = _finite(
            (e / self.elbow_gearbox_ratio - self.carrier_coupling * q2)
            / (self.belt_sign * self.belt_ratio)
        )
        return q2, q3

    def joint_efforts(self, b: float, c: float, e: float) -> tuple[float, float]:
        """J transpose times rotor effort, from virtual work; ideal lossless map."""
        b, c, e = _finite(b), _finite(c), _finite(e)
        return (
            _finite(
                self.shoulder_branch_ratio * (b + c)
                + self.elbow_gearbox_ratio * self.carrier_coupling * e
            ),
            _finite(self.elbow_gearbox_ratio * self.belt_sign * self.belt_ratio * e),
        )

    def ideal_rotor_efforts(
        self, shoulder_joint_nm: float, elbow_joint_nm: float, shoulder_b_fraction: float
    ) -> dict:
        """Resolve redundancy only with an explicitly caller-selected B/C split."""
        t2, t3 = _finite(shoulder_joint_nm), _finite(elbow_joint_nm)
        share = _finite(shoulder_b_fraction)
        if not 0 <= share <= 1:
            raise ValueError("shoulder share must be in 0..1")
        elbow_output = _finite(t3 / (self.belt_sign * self.belt_ratio))
        elbow_rotor = _finite(elbow_output / self.elbow_gearbox_ratio)
        shoulder_net = _finite(t2 - self.carrier_coupling * elbow_output)
        return {
            "rotor_B_nm": _finite(share * shoulder_net / self.shoulder_branch_ratio),
            "rotor_C_nm": _finite((1 - share) * shoulder_net / self.shoulder_branch_ratio),
            "rotor_E_nm": elbow_rotor,
            "elbow_gearbox_output_nm": elbow_output,
            "shoulder_branch_total_joint_nm": shoulder_net,
            "remote_elbow_contribution_at_shoulder_nm": _finite(
                self.carrier_coupling * elbow_output
            ),
            "shoulder_B_fraction_assumed": share,
            "physical_load_sharing_verified": False,
            "lossless": True,
        }

    def elbow_proxy_coordinate(self, q2: float, q3: float) -> float:
        """Return phi/(s*k), a normalized uncoupled elbow coordinate.

        This equals q3 + c*q2/(s*k). If a diagonal channel scale were calibrated
        to this proxy, the carrier term would need to be included upstream. The
        returned value is a mathematical coordinate, never a GRBL command.
        """
        q2, q3 = _finite(q2), _finite(q3)
        return _finite(q3 + self.carrier_coupling * q2 / (self.belt_sign * self.belt_ratio))

    def relative_elbow_from_proxy(self, q2: float, proxy: float) -> float:
        """Invert the normalized proxy at a specified physical shoulder angle."""
        q2, proxy = _finite(q2), _finite(proxy)
        return _finite(proxy - self.carrier_coupling * q2 / (self.belt_sign * self.belt_ratio))


@dataclass(frozen=True)
class WristDifferential:
    """Declared common-axis wrist differential and signed belt scales.

    alpha_minus = q5 + handedness*bevel_ratio*q6
    alpha_plus  = q5 - handedness*bevel_ratio*q6
    theta_minus = negative_y_rotor_scale*alpha_minus
    theta_plus  = positive_y_rotor_scale*alpha_plus

    alpha values use common native +Y; q6 uses the carried native +Z axis.
    Signed rotor scales include caller-declared belt ratio/polarity. Nothing
    here infers motor wiring, addresses, contact validity, or physical zeros.
    """

    bevel_ratio: float
    handedness: int
    negative_y_rotor_scale: float
    positive_y_rotor_scale: float
    evidence: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "bevel_ratio", _positive(self.bevel_ratio))
        _sign(self.handedness)
        for name in ("negative_y_rotor_scale", "positive_y_rotor_scale"):
            value = _finite(getattr(self, name))
            if value == 0:
                raise ValueError("signed rotor scale must be nonzero")
            _positive(abs(value) * self.bevel_ratio)
            object.__setattr__(self, name, value)
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("explicit mechanism evidence or assumption required")

    def side_angles(self, q5: float, q6: float) -> tuple[float, float]:
        """Return negative-Y and positive-Y shaft angles, both about native +Y."""
        q5, q6 = _finite(q5), _finite(q6)
        differential = _finite(self.handedness * self.bevel_ratio * q6)
        return _finite(q5 + differential), _finite(q5 - differential)

    def joint_angles(self, negative_y: float, positive_y: float) -> tuple[float, float]:
        """Invert common-axis side angles, not nominal source addresses."""
        negative_y, positive_y = _finite(negative_y), _finite(positive_y)
        return (
            _finite(negative_y / 2 + positive_y / 2),
            _finite((negative_y / 2 - positive_y / 2) / self.bevel_ratio / self.handedness),
        )

    def rotor_angles(self, q5: float, q6: float) -> tuple[float, float]:
        negative_y, positive_y = self.side_angles(q5, q6)
        return (
            _finite(self.negative_y_rotor_scale * negative_y),
            _finite(self.positive_y_rotor_scale * positive_y),
        )

    def joints_from_rotors(self, negative_y: float, positive_y: float) -> tuple[float, float]:
        return self.joint_angles(
            _finite(_finite(negative_y) / self.negative_y_rotor_scale),
            _finite(_finite(positive_y) / self.positive_y_rotor_scale),
        )

    def joint_efforts(self, negative_y_nm: float, positive_y_nm: float) -> tuple[float, float]:
        """Ideal rotor effort J transpose; no efficiency or capacity inference."""
        minus = _finite(_finite(negative_y_nm) * self.negative_y_rotor_scale)
        plus = _finite(_finite(positive_y_nm) * self.positive_y_rotor_scale)
        return (
            _finite(minus + plus),
            _finite(self.handedness * self.bevel_ratio * _finite(minus - plus)),
        )

    def rotor_efforts(self, q5_nm: float, q6_nm: float) -> tuple[float, float]:
        """Invert the ideal generalized effort map for the declared scales."""
        fold = _finite(q5_nm) / 2
        differential = _finite(q6_nm) / 2 / self.bevel_ratio / self.handedness
        return (
            _finite((fold + differential) / self.negative_y_rotor_scale),
            _finite((fold - differential) / self.positive_y_rotor_scale),
        )

    def opposed_references(self, q5: float, q6: float, y_side: str) -> tuple[float, float]:
        """Express one shaft negatively and the other positively.

        y_side is an explicit assignment of the negative-reference coordinate
        to a common-axis shaft; the returned pair is not a hardware command.
        Compare it to the nominal source's Y/Z algebra only after selecting
        that side assignment and an equal magnitude bevel coefficient.
        """
        negative_y, positive_y = self.side_angles(q5, q6)
        if y_side == "negative_y":
            return -negative_y, positive_y
        if y_side == "positive_y":
            return -positive_y, negative_y
        raise ValueError("y_side must be negative_y or positive_y")
