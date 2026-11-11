"""Bounded synthetic identification of an explicitly declared elbow model.

The model is phi = zero + carrier*q2 + signed_ratio*q3. Its coordinates are
known, exact, unwrapped synthetic joint/output radians, not controller D/Z or
motor steps. An unknown output scale makes carrier and ratio unidentifiable as
physical parameters. No physical data loader, controller settings, or hardware
interface exists here. Regression uncertainty is conditional on exact predictors
and independent output noise; it does not cover backlash or predictor errors.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from numbers import Real

EVIDENCE_CLASS = "synthetic_identification_not_physical_calibration"
COORDINATES = "exact_unwrapped_relative_joint_and_output_radians"
_MAX_SAMPLES = 10_000
_MAX_ANGLE_RAD = 1_000_000
_MIN_NORMALIZED_DETERMINANT = 1e-10  # numerical rank guard, not physical acceptance


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be finite numeric data")
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be finite numeric data") from error
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric data")
    return value


@dataclass(frozen=True)
class SyntheticElbowObservation:
    q2_rad: float
    q3_rad: float
    phi_rad: float
    approach_direction: int

    def __post_init__(self) -> None:
        for name in ("q2_rad", "q3_rad", "phi_rad"):
            value = _finite(getattr(self, name), name)
            if abs(value) > _MAX_ANGLE_RAD:
                raise ValueError("angle exceeds bounded unwrapped-radian diagnostic domain")
            object.__setattr__(self, name, value)
        if type(self.approach_direction) is not int or self.approach_direction not in {-1, 1}:
            raise ValueError("approach_direction must be an explicit +1 or -1 fixture label")


@dataclass(frozen=True)
class IdentificationPolicy:
    """Caller-declared synthetic experiment gates, never physical tolerances.

    A positive noise floor prevents zero-residual fixtures from claiming exact
    parameter certainty. The multiplier creates a conditional sigma interval;
    it is not asserted to be a confidence level for quantized or biased data.
    """

    minimum_axis_span_rad: float
    max_output_residual_rad: float
    max_direction_half_bias_rad: float
    output_noise_floor_std_rad: float
    uncertainty_sigma_multiplier: float
    output_scale_known: bool

    def __post_init__(self) -> None:
        for name in (
            "minimum_axis_span_rad",
            "max_output_residual_rad",
            "max_direction_half_bias_rad",
            "output_noise_floor_std_rad",
            "uncertainty_sigma_multiplier",
        ):
            value = _finite(getattr(self, name), name)
            if value < 0 or value > _MAX_ANGLE_RAD:
                raise ValueError(f"{name} must be within the bounded nonnegative domain")
            object.__setattr__(self, name, value)
        if self.minimum_axis_span_rad == 0 or self.output_noise_floor_std_rad == 0:
            raise ValueError("excitation span and output noise floor must be positive")
        if self.output_noise_floor_std_rad**2 == 0:
            raise ValueError("output noise variance must remain positive at machine precision")
        if not 1 <= self.uncertainty_sigma_multiplier <= 10:
            raise ValueError("uncertainty sigma multiplier must be within 1..10")
        if type(self.output_scale_known) is not bool:
            raise ValueError("output_scale_known must be explicit boolean synthetic knowledge")


@dataclass(frozen=True)
class ElbowCoefficients:
    zero_rad: float
    carrier_coefficient: float
    signed_ratio: float


@dataclass(frozen=True)
class ElbowIdentification:
    accepted_for_synthetic_model: bool
    reasons: tuple[str, ...]
    observations_sha256: str
    sample_count: int
    distinct_pose_count: int
    paired_direction_pose_count: int
    axis_spans_rad: tuple[float, float]
    predictor_correlation: float | None
    normalized_information_determinant: float | None
    coefficients: ElbowCoefficients | None
    coefficient_standard_errors: ElbowCoefficients | None
    coefficient_covariance: tuple[tuple[float, ...], ...] | None
    residual_rms_rad: float | None
    max_abs_residual_rad: float | None
    mean_paired_direction_half_bias_rad: float | None
    max_abs_paired_direction_half_bias_rad: float | None
    identified_ratio_magnitude: float | None
    identified_ratio_sign: int | None
    evidence_class: str = EVIDENCE_CLASS
    coordinates: str = COORDINATES
    commissioned: bool = False
    uncertainty_scope: str = (
        "conditional_exact_synthetic_predictors_independent_output_noise_only_"
        "not_predictor_noise_quantization_or_hysteresis_coverage"
    )


def fit_elbow_model(
    observations: Sequence[SyntheticElbowObservation], *, policy: IdentificationPolicy
) -> ElbowIdentification:
    """Identify only the three coefficients of a declared synthetic linear model.

    Both independently excited input axes and at least three distinct poses
    observed from both direction labels are required for an accepted fixture.
    Poor excitation, collinearity, unknown output scale, contradictory residuals,
    directional bias or an interval containing zero leave explicit gates open.
    Fitted coefficients may be returned on failure as diagnostics, never settings.
    """
    if not isinstance(observations, Sequence) or isinstance(observations, str | bytes):
        raise ValueError("observations must be a bounded sequence")
    if not 1 <= len(observations) <= _MAX_SAMPLES:
        raise ValueError("synthetic experiment requires 1..10000 observations")
    if not isinstance(policy, IdentificationPolicy):
        raise ValueError("an explicit identification policy is required")
    if any(not isinstance(item, SyntheticElbowObservation) for item in observations):
        raise ValueError("only explicit synthetic observations are supported")
    records = [asdict(item) for item in observations]
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    n = len(observations)
    x = [item.q2_rad for item in observations]
    z = [item.q3_rad for item in observations]
    y = [item.phi_rad for item in observations]
    spans = (max(x) - min(x), max(z) - min(z))
    groups: dict[tuple[float, float], dict[int, list[float]]] = {}
    for item in observations:
        group = groups.setdefault((item.q2_rad, item.q3_rad), {-1: [], 1: []})
        group[item.approach_direction].append(item.phi_rad)
    paired_bias = [
        (math.fsum(group[1]) / len(group[1]) - math.fsum(group[-1]) / len(group[-1])) / 2
        for group in groups.values()
        if group[1] and group[-1]
    ]
    mean_bias = math.fsum(paired_bias) / len(paired_bias) if paired_bias else None
    max_bias = max(abs(bias) for bias in paired_bias) if paired_bias else None
    reasons: list[str] = []
    if n < 6:
        reasons.append("insufficient_samples_for_redundant_three_parameter_fit")
    if min(spans) < policy.minimum_axis_span_rad:
        reasons.append("insufficient_independent_axis_excitation")
    if len(paired_bias) < 3:
        reasons.append("direction_bias_unassessed_requires_three_paired_poses")
    if max_bias is not None and max_bias > policy.max_direction_half_bias_rad:
        reasons.append("direction_dependent_bias_exceeds_declared_fixture_gate")
    if not policy.output_scale_known:
        reasons.append("unknown_output_scale_conflates_carrier_ratio_and_scale")

    def result(
        *,
        correlation: float | None = None,
        determinant: float | None = None,
        coefficients: ElbowCoefficients | None = None,
        standard_errors: ElbowCoefficients | None = None,
        covariance: tuple[tuple[float, ...], ...] | None = None,
        rms: float | None = None,
        maximum: float | None = None,
        magnitude: float | None = None,
        sign: int | None = None,
    ) -> ElbowIdentification:
        return ElbowIdentification(
            not reasons,
            tuple(reasons),
            digest,
            n,
            len(groups),
            len(paired_bias),
            spans,
            correlation,
            determinant,
            coefficients,
            standard_errors,
            covariance,
            rms,
            maximum,
            mean_bias,
            max_bias,
            magnitude,
            sign,
        )

    if n <= 3 or min(spans) == 0:
        reasons.append("rank_deficient_design_matrix")
        return result()
    mx, mz, my = math.fsum(x) / n, math.fsum(z) / n, math.fsum(y) / n
    dx, dz, dy = [v - mx for v in x], [v - mz for v in z], [v - my for v in y]
    sxx, szz = math.fsum(v * v for v in dx), math.fsum(v * v for v in dz)
    if sxx == 0 or szz == 0:
        reasons.append("rank_deficient_design_matrix")
        return result()
    nx, nz = math.sqrt(sxx), math.sqrt(szz)
    ux, uz = [v / nx for v in dx], [v / nz for v in dz]
    correlation = max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(ux, uz, strict=True))))
    determinant = 1 - correlation**2
    if determinant <= _MIN_NORMALIZED_DETERMINANT:
        reasons.append("rank_deficient_or_ill_conditioned_design_matrix")
        return result(correlation=correlation, determinant=determinant)
    if min(sxx * determinant, szz * determinant, nx * nz * determinant) == 0:
        reasons.append("numerically_unrepresentable_design_matrix")
        return result(correlation=correlation, determinant=determinant)
    bx = math.fsum(a * b for a, b in zip(ux, dy, strict=True))
    bz = math.fsum(a * b for a, b in zip(uz, dy, strict=True))
    carrier = (bx - correlation * bz) / determinant / nx
    signed_ratio = (bz - correlation * bx) / determinant / nz
    zero = my - carrier * mx - signed_ratio * mz
    residuals = [
        item.phi_rad - (zero + carrier * item.q2_rad + signed_ratio * item.q3_rad)
        for item in observations
    ]
    residual_sum_sq = math.fsum(v * v for v in residuals)
    rms = math.sqrt(residual_sum_sq / n)
    maximum = max(abs(v) for v in residuals)
    if maximum > policy.max_output_residual_rad:
        reasons.append("residuals_contradict_declared_linear_fixture_model")
    variance = max(policy.output_noise_floor_std_rad**2, residual_sum_sq / (n - 3))
    vc = variance / (sxx * determinant)
    vk = variance / (szz * determinant)
    ck = -variance * correlation / (nx * nz * determinant)
    vzero = max(0.0, variance / n + mx * mx * vc + mz * mz * vk + 2 * mx * mz * ck)
    zc, zk = -mx * vc - mz * ck, -mz * vk - mx * ck
    covariance = ((vzero, zc, zk), (zc, vc, ck), (zk, ck, vk))
    se = ElbowCoefficients(math.sqrt(vzero), math.sqrt(vc), math.sqrt(vk))
    if not all(math.isfinite(v) for row in covariance for v in row):
        reasons.append("numerically_unrepresentable_coefficient_uncertainty")
        return result(correlation=correlation, determinant=determinant)
    half_interval = policy.uncertainty_sigma_multiplier * se.signed_ratio
    sign = (
        1 if signed_ratio - half_interval > 0 else -1 if signed_ratio + half_interval < 0 else None
    )
    if sign is None:
        reasons.append("ratio_sign_ambiguous_under_declared_noise_model")
    # Coefficients remain diagnostic on rejection; do not promote their sign
    # or magnitude to an identified parameter when any experiment gate fails.
    identified_sign = sign if not reasons else None
    return result(
        correlation=correlation,
        determinant=determinant,
        coefficients=ElbowCoefficients(zero, carrier, signed_ratio),
        standard_errors=se,
        covariance=covariance,
        rms=rms,
        maximum=maximum,
        magnitude=abs(signed_ratio) if identified_sign is not None else None,
        sign=identified_sign,
    )
