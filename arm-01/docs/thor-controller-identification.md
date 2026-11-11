# Synthetic elbow identification and an unpowered worksheet

[`thor_identification.py`](../src/raftel_arm01/control/thor_identification.py)
fits an explicitly declared synthetic linear model:

```text
phi = zero + carrier * q2 + signed_ratio * q3
signed_ratio = belt_sign * effective_drum_pitch_radius / input_pitch_radius
```

The [existing transmission model](thor-transmission-coordinates.md) establishes
the conditional mechanical relation. Here `q2` and `q3` are **known, exact,
unwrapped synthetic relative joint radians**, and `phi` is a known synthetic
gearbox-output angle relative to Art1. These are not source D/Z degrees, motor
steps or physical observations. The existing [pinned controller audit](thor-controller-compensation.md)
and [exact source replay](thor-controller-replay.md) remain distinct layers.

This closes C5's bounded synthetic identification implementation. It does not
calibrate a robot, resolve actual pitch radius, qualify a controller setting,
fit physical measurements or introduce a hardware interface.

## Identifiability and experiment gates

The implementation estimates zero, carrier and signed ratio using centered,
scaled least squares. It checks both input-axis spans and the normalized
two-column information determinant. Constant/one-axis and collinear excitation
cannot separate the coefficients; repeating an identical pose does not create
independent excitation. A small numerical determinant is rejected before solving.

A caller supplies an `IdentificationPolicy` with:

- Minimum independently excited input-axis span.
- Maximum output residual and maximum paired directional half-bias.
- A positive output-noise standard-deviation floor and explicit sigma multiplier.
- Whether the synthetic output scale is independently known.

All these values are **synthetic experiment gates**, not physical tolerances or
permissions for travel. The finite model bounds are computational safeguards.
At least six samples and three distinct poses observed from both approach
direction labels are required for an accepted fixture. Exactly repeated
synthetic predictors allow a directional half-difference to be inspected without
confounding it with carrier motion. Unpaired directions leave the bias gate
unassessed. A direction label is supplied evidence, not an inferred motor sign.

An unknown output scale confounds scale, carrier and ratio. Even a perfect fit
then returns `accepted_for_synthetic_model: false`. Likewise, large residuals,
directional bias, insufficient excitation, rank/conditioning failures and a
signed-ratio sigma interval containing zero produce explicit rejection reasons.
Coefficients can remain visible as diagnostics after rejection, but identified
ratio sign/magnitude stay null until every declared experiment gate passes.
Source-coordinate conversion, unknown scales/signs and independent zeros must
be resolved before this model could apply to a physical observation.

Uniformly scaling observations or consistently supplying degrees as radians
cannot be detected from the regression alone. The exact coordinate contract,
known output-scale declaration and independent provenance therefore matter.
The synthetic input loader requires the exact unwrapped-radian evidence class;
it rejects an input labeled physical. Wrapping a subset of output angles
violates the linear model and is exercised as a rejected fixture, but a
consistent whole-turn shift is indistinguishable from a changed fitted zero.

## Uncertainty and bias boundaries

The reported 3×3 covariance uses parameter order `[zero, carrier, signed_ratio]`:

```text
variance = max(declared_output_noise_floor_std², residual_sum_squares / (n - 3))
covariance = variance * inverse(X_transpose * X)
```

Tests independently check the matrix identity
`(X_transpose * X) * covariance = variance * I`. A positive declared noise floor
prevents a zero-residual synthetic fixture from claiming exact certainty.
The sigma multiplier is explicit; its interval is **not** called a confidence
level for biased, correlated or quantized observations.

This covariance is conditional on exact synthetic predictors and independent
output noise. It does not cover uncertain measured `q2/q3`, correlated samples,
quantization, backlash, direction hysteresis, model error or wrong units. Noise
and quantization fixtures test estimator behavior; they do not validate those
intervals for real instruments. Physical measurement fitting would need a
separately reviewed estimator, uncertainty model and acceptance process.

## Reproduction and observed synthetic results

From the installed development environment in `arm-01`:

```powershell
python tools/thor_identification_study.py --seed 42
python -m pytest tests/test_thor_identification.py
```

The default study has nine deterministic cases. The generated carrier is 1,
zero is 0.12 rad and ratio magnitude is 5.8; both ratio signs are exercised.
The noisy case adds uniform ±0.00015 rad noise and nearest 0.0002 rad quantization
using Python's half-even rounding. The hysteresis case adds a ±0.01 rad
directional bias. These are declared synthetic inputs, not inferred instrument
properties.

| Case | Expected result |
| --- | --- |
| Exact positive ratio | Accepted in the synthetic model; coefficients recovered |
| Exact negative ratio | Accepted in the synthetic model; negative ratio recovered |
| Negative ratio with noise and quantization | Accepted against declared fixture gates; uncertainty coverage remains conditional |
| Direction-dependent hysteresis | Rejected for directional bias/residual inconsistency |
| Collinear joint inputs | Rejected as rank deficient |
| Unpaired approach directions | Rejected with direction bias unassessed |
| Unknown output scale | Rejected; physical coefficients unidentifiable |
| Ratio near zero under the declared noise floor | Rejected with ambiguous sign |
| Wrapped output angles | Rejected for inconsistent linear observations |

The checked seed-42 study matches all nine expected outcomes. Tests additionally
recover 40 seeded offset/carrier/ratio combinations with unequal axis scales,
reject repeated/single-axis/contradictory inputs, verify covariance and exercise
CLI/schema failures. Canonical observation hashes bind each result to its
synthetic samples. Report metadata includes the seed, grids, generator parameters
and policy; it never reports physical calibration or commissioning.

`--input` accepts a bounded JSON object with exactly `schema_version`,
`evidence_class`, `coordinates`, `policy` and `observations`. The evidence and
coordinate values must match the module's constants; each observation has
`q2_rad`, `q3_rad`, `phi_rad` and `approach_direction`. Duplicate keys,
nonfinite values, malformed fields and more than 10,000 observations are
rejected. Exit 0 means the default study matched its expected cases or an input
fit passed its synthetic gates; exit 1 preserves a diagnostic report for a
rejected input fit; exit 2 means invalid input/output. `--output` creates a new
report and refuses to overwrite existing evidence.

## Measurement preparation without execution

[`thor-identification-worksheet.json`](../config/thor-identification-worksheet.json)
contains blank values for instrument identities, uncertainty, conditions,
unwrapping, source hashes and angle observations. Preconditions remain null,
including motor-energy disconnection, gravity restraint, owner inspection and
manual backdrive suitability. It is an **unexecuted unpowered worksheet**, not
an instruction to move or energize the mechanism. The software's synthetic gates
do not supply its missing physical acceptance limits or evidence.

Future observations need known coordinate/scale references and independently
excited axes, repeated bidirectional poses, raw records, instruments and
uncertainty. Unknown output scale, wrong/unverified belt routing, changed source
geometry, mixed unit conventions, wrapping, excessive hysteresis and failed
restraint/backdrive suitability invalidate the proposed identification model.
Physical records are deliberately not fed into this synthetic-only estimator.
