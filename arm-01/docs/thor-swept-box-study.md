# Conditional linear swept boxes

This T2 preparation primitive evaluates a **fixed-orientation axis-aligned box
under explicitly declared linear translation against static axis-aligned boxes**.
It returns the closed parameter interval where the supplied numerical proxies
overlap or touch. It does not validate a robot trajectory, establish physical
clearance, infer motion from joint endpoints or complete the T2 gate.

[The small reproducible study](../hardware/cad/thor-swept-box-study-v1.json)
contains seven explicitly synthetic fixtures and raw hashes of the reused box
math and swept-box implementation. No Thor or workstation geometry is invented,
articulated or passed into the study. Robot swept clearance and physical
collision-free fields remain null; no runtime sorter or hardware integration
is added.

## Why endpoint checks are insufficient

The hand-counted witness moves a cube of half-width **0.25 m** from centre
`(-2,0,0)` to `(2,0,0)` against a static cube of half-width **0.5 m** at the origin.
These are arbitrary fixture dimensions, not Thor dimensions. Both endpoint boxes
are separated from the obstacle. During the declared translation, the moving
centre is `x(u)=-2+4u`. The expanded obstacle's X slab is `[-0.75,0.75]`, giving
the overlap/contact interval **[5/16, 11/16]**. Endpoint-only acceptance would
miss this interval entirely.

Other retained cases cover stationary separation, stationary overlap, face
grazing, starting inside then exiting, contact only at the final endpoint, and
an instantaneous zero-width point crossing. Tangency is included, including a
singleton interval such as `[0.5,0.5]`.

## Model, coordinates and API

`kinematics.thor_swept_boxes` reuses the existing `BoxProxy`, `AABB`, proper SE(3)
validation and geometry services. Dimensions are metres. Both moving endpoints
must have the same identity, expression-frame ID, half extents and exact fixed
rotation. That rotation and each obstacle rotation must be an exact proper
signed permutation, so their faces remain aligned with world X/Y/Z. Arbitrary
rotations, near-axis rotations, orientation changes, resizing, frame mismatches
and a joint-path assumption are rejected rather than approximated silently.
Shared frame IDs express a caller declaration, not authenticated registration
to a real or source coordinate system.

The caller must supply the exact `LINEAR_TRANSLATION_ASSUMPTION` token and
nonempty motion evidence. The token declares the model; the implementation cannot
authenticate an actual physical motion from endpoints. The normalized parameter
`u` lies in **[0,1]**, with `centre(u)=(1-u)*start+u*end`. No duration, joint
trajectory, controller timing or physical velocity is inferred.

For each axis, the static obstacle interval is Minkowski-expanded by the moving
box's world half-width. The implementation analytically clips the moving centre
line against each expanded closed slab, handles zero-displacement axes directly,
and intersects the three parameter intervals. This is a slab calculation, without
sampled or endpoint-only acceptance. Negative displacement and reversed endpoints
are supported. A stationary coordinate inside its slab permits the whole `[0,1]`;
one outside makes that axis infeasible.

```python
from raftel_arm01.kinematics.thor_swept_boxes import (
    LINEAR_TRANSLATION_ASSUMPTION,
    sweep_linear_translation,
)

result = sweep_linear_translation(
    moving_start,
    moving_end,
    static_obstacle,
    assumption=LINEAR_TRANSLATION_ASSUMPTION,
    motion_evidence="Explicit synthetic fixed-orientation linear path",
    numerical_tolerance_m=0.0,
)
# The result concerns only the supplied declared proxy model.
assert result.physical_collision_free is None
```

`sweep_against_static_boxes` returns every per-obstacle result within a declared
obstacle budget. IDs must be unique and no contact exclusions are invented.
An empty collection establishes no obstacle or physical scene coverage.

## Numerical policy and unsupported paths

The default numerical padding is **0 m**. A supplied finite nonnegative padding
explicitly dilates every slab in metres; it is not a manufacturing allowance,
calibrated safety margin or evidence that the proxy encloses a source body.
Calculations use floating-point arithmetic, not certified interval arithmetic.
The analytic model should not be interpreted as an exact-arithmetic physical
clearance proof. Unrepresentable deltas/radius sums, positive widths lost at large
centre coordinates and strictly interior crossings rounded to parameter 0 or 1
reject cleanly rather than silently substituting a point or endpoint interval.

The existing [518-body saved-zero study](thor-mounted-collision-study.md) supplies
one cached numerical scene, with unknown enclosure and no dynamic body bindings.
It does not authorize moving those boxes. The existing [joint quintic paths](thor-offline-trajectories.md)
describe joint coordinates; a joint quintic does not imply that a body centre
moves along a straight line or that its orientation stays fixed. Joint rotation,
curved motion, changing extents, moving obstacles, jaw/gear articulation and
inferred source-body dynamics are unsupported here. No automatic conversion from
joint endpoints or sampled FK is provided.

Full T2 remains gated on audited shape enclosures and motion bindings, intended
contacts, complete obstacle/held-object/cable geometry, IK branch continuity and
appropriate swept checks for the actual articulated paths. This generic fixture
does not clear an approach, grasp, retreat, transport or release operation.

## Validation and reproduction

The focused tests compare 750 deterministic randomized cases against an
independent `Fraction` inequality-clipping oracle, treating input floats as exact
dyadic rationals. They also cover the hand-computed midpath witness, stationary
and tangent cases, zero-width shapes, disjoint per-axis parameter intervals,
negative velocity/reversed endpoints, proper signed-permutation orientations,
explicit padding, rejected unsupported assumptions/frames/rotations, numeric
failure bounds, obstacle budgets, exact report reproduction and preserved outputs.
Independent review uses a separately implemented rational oracle.

From `arm-01`, write to a new evidence path:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_thor_swept_boxes.py
.\.venv\Scripts\python.exe tools\thor_swept_box_study.py `
  --output ..\.work\swept-box-study-repeat.json
```
