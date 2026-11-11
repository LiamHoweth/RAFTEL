# Wrist COM trajectory evaluator

[`thor_wrist.py`](../src/raftel_arm01/kinematics/thor_wrist.py) evaluates an explicitly declared center-of-mass trajectory. The [membership evidence](thor-wrist-mechanism.md) supplies the bodies and candidate mechanism relations; the evaluator does not infer those relations from a CAD attachment tree. It uses only the Python standard library and does not command hardware.

## Frame and chain contract

Every point, axis direction and axis origin in a call uses one common zero-pose frame. Positions are metres and angles radians. A `MotionStep` rotates by `q5_coefficient*q5 + q6_coefficient*q6`. Each step requires an evidence string; that string records a declaration's provenance, not physical verification.

**Steps are ordered from proximal to distal. Earlier steps carry later axis origins and directions.** A tool point following fold and roll therefore uses `[fold, roll]`, with both axes declared at the zero pose. This evaluates `T_fold(q5) * T_roll(q6) * p_zero`; it does not rotate first about a fixed world roll axis and then about an independently fixed fold axis. The implementation rotates the point while carrying the later axes, yielding the same product.

```python
fold = MotionStep((0, 0, 0.556), (0, 1, 0), 1, 0, "declared CAD fold axis")
roll = MotionStep((0, 0, 0.5775), (0, 0, 1), 0, 1, "declared carried roll axis")
state = point_state(com_zero_m, q5_rad, q6_rad, (fold, roll))
```

An empty sequence models a fixed COM. A side rotor uses a single fixed-axis step with both angle coefficients, rather than inheriting the carrier's roll axis. A rotor's angular phase can change while its COM stays fixed when that COM lies on the rotor axis. Bearings whose whole-asset COM motion is known can use a COM trajectory without asserting rigid ownership of internal races. These declarations cannot be used as full rigid-body inertia models.

## Derivatives and gravity

`point_state` returns `WristPointState(position_m, dq5_m_rad, dq6_m_rad)`. Each derivative is analytic, summing `coefficient * axis cross (COM - axis_origin)` over the active carried axes. Multiple steps can contribute to either generalized coordinate. This supports nested axes and differential phase without assigning every wrist mass to the same downstream rigid group.

`gravity_generalized_torque_nm(state, mass_kg, gravity_m_s2)` returns external generalized gravity efforts `tau_j = mass * gravity dot dCOM/dq_j`. Ideal static holding effort has the opposite sign. A caller composing this wrist frame with an upstream rigid transform must transform COM positions as points, and Jacobians and gravity as vectors. The result is invariant to a consistent rigid change of expression frame.

The result is a gravity effort conjugate to the declared q5/q6 coordinates. Actuator shaft torques need a separately justified transmission map. This module supplies no motor polarity, gear efficiency, friction, backlash, collision clearance, joint limits, printed-part strength, or operating approval.

## Verification

The focused tests cover known quarter turns, carried roll axes, fixed COMs despite coupled rotor phase, off-axis coupled COMs, centered finite-difference Jacobians at nonzero wrist angles, negative potential-energy gradients, virtual work, and rigid frame covariance. Invalid declarations and nonfinite results are rejected. These are mathematical verification cases, not evidence of a calibrated physical wrist.
