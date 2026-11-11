# Conditional rigid-interface reaction study

The [offline solver](../src/raftel_arm01/engineering/mount_reactions.py) allocates a
complete force/moment wrench among declared reaction channels. The
[reproducible study](../hardware/cad/thor-mount-reaction-study-v1.json) reuses
preserved v2 gravity wrenches and source mount locations, with explicit hypothetical
contact/force-allocation assumptions. It is the equilibrium component of F5, not
a selected clamp, plate detail, strength calculation or fabrication release.

## Input and allocation contract

`Wrench` requires force in N, moment in N·m, a reference point in m and a common
coordinate-frame name. A `ReactionChannel` requires a proper rigid
`common_from_support` transform with translation in m, a local unit direction,
positive relative allocation weight, an allowed sign and provenance. Its point
of application is the support-frame origin. All channels must explicitly use the
wrench frame. A 3D point contact is represented by three independently declared
channels; those constraints are assumptions until the real interface supports
them. The model accepts at most 128 channels.

For channel force scalar `f_i`, common-frame direction `u_i` and displacement
`r_i` from the wrench reference:

```text
A_i = [ u_i ]       A f + external_wrench = 0
      [ r_i × u_i ]
```

A redundant support layout has many equilibrium allocations. The implemented
choice explicitly minimizes `norm(f_i / sqrt(relative_weight_i))`. With diagonal
positive weights `W`, the candidate is:

```text
f = W Aᵀ (A W Aᵀ)⁻¹ (−external_wrench)
```

These weights are **not measured stiffness or preload**. A common scaling of all
weights leaves the candidate unchanged. Different relative weights can change
individual reactions while preserving the same total wrench. No equal split of
weight or moment among clamps is inferred from the number of holes.

Moment rows and moment demand are divided by an explicit characteristic length
for the numerical solve/rank diagnostic. Reported forces, moments and residuals
retain their SI units. The solver rejects an incomplete six-component support
map, even when one special vertical load could be balanced. It also checks the
complete original-SI force and moment residuals after solving. No horizontal
force or torsional demand is silently discarded.

`SingularSupportLayout` retains the numerical rank and **complete unsolved
external wrench**. Four coplanar normal-only supports have rank 3; two fully
constrained point contacts have rank 5. Actual finite clamp patches may transmit
additional moments, but that capability must be modeled from evidence rather
than being assumed by a point-support calculation.

Allowed signs are checked on the chosen candidate. If its minimum-force-norm
allocation violates a one-sided channel, the result says:

```text
unknown_chosen_candidate_invalid_other_allocations_not_checked
```

This is not a proof that no constrained equilibrium exists. Tests exhibit a
full-rank bilateral layout plus one additional nonnegative channel: the minimum
assigns a negative force to that extra channel, while a different valid allocation
sets it to zero and balances the full wrench through the bilateral supports. No
inequality-constrained optimizer, contact selection or preload solution is claimed.

## Source-linked scenarios

The study binds three files by exact SHA-256: the revisioned frame configuration,
[source fabrication capture](../hardware/cad/thor-fabrication-interfaces.json) and
[preserved v2 load study](../hardware/cad/thor-wrist-load-study-v2.json). It uses the
source-selected ideal positive wrist phase, PLA reference density and 50% effective
whole-part solid-fraction scenario, with jaws frozen at their saved pose. It does
not replace that study or turn its assumptions into physical capacity.

Two upright/horizontal-shoulder cases use the existing **0.2 kg payload** wrenches.
The total modeled downward force is approximately **57.4152 N**. Force and moment
are rotated together from nominal `base_link` into the native-source zero-frame
scenario with the shared revisioned frame graph. The BaseBot `LCS_Bot` identity
is treated as coincident with native assembly zero in this declared source
scenario; there is no measured bench registration. The actual bench transform
remains `null`.

Each gravity case is allocated to two hypothetical layouts:

| Layout | Declared point locations and constraints |
| --- | --- |
| Source bore points | The four asymmetric source XY centers, z=0, with three bilateral force directions at each point |
| Proposed adapter corners | Four points inset 25 mm from the existing 300 × 320 mm proposal, with three bilateral force directions each; inset and constraints are study assumptions, not selected clamp pads |

The reported chosen vertical reactions illustrate why a weight-only split is
insufficient:

| Pose | Assumed layout | Chosen vertical reaction range, N |
| --- | --- | ---: |
| Upright | Source bore points | −3.9874 to +32.7091 |
| Horizontal shoulder | Source bore points | −6.8162 to +35.5097 |
| Upright | Proposed corner points | +7.4174 to +21.2903 |
| Horizontal shoulder | Proposed corner points | +9.5095 to +19.1981 |

These values describe the explicit bilateral minimum-force allocation only.
Negative force means the chosen channel acts opposite its local positive
direction. Actual bolt tension, contact pressure, clamp preload and load sharing
require contact/compliance evidence. Positive chosen reactions do not establish
that an actual clamp/desk interface can provide them.

Two additional **synthetic** wrenches include horizontal force and torsion; they
test complete equilibrium but are not measured or prescribed proof loads. The
study also records deliberate rank-3 normal-only and rank-5 two-point model
rejections, retaining all components of the synthetic request.

## Reproduction and external cases

From `arm-01` after the normal editable installation:

```powershell
New-Item -ItemType Directory -Path ../.work/mount-repro-001
python tools/thor_mount_reactions.py --output ../.work/mount-repro-001/mount-study.json
python -m pytest tests/test_mount_reactions.py
```

The tool needs no FreeCAD, serial connection or internet. If a bound input changes,
create and review a new report rather than silently reusing old reactions. Choose
a previously unused run-directory name. Output paths are resolved, checked against
inputs/existing entries and created exclusively with UTF-8/LF lines. A later
creation race also fails without truncating old evidence. An I/O failure may leave
partial new output; a nonzero exit remains an incomplete run. The tool never
creates meshes, G-code or hardware commands.

For a supplied scenario, use `--case-file case.json --output reaction-result.json`.
The case must have integer `schema_version=1`,
`evidence_class="conditional_mount_input"`, explicit SI units
`{"force":"N","moment":"N*m","length":"m"}`, `wrench` fields matching `Wrench`,
a `channels` array matching `ReactionChannel`, and:

```json
{
  "allocation": {
    "method": "minimum_weighted_force_norm",
    "evidence": "State the chosen allocation assumption and its provenance",
    "characteristic_length_m": 0.1
  }
}
```

Unknown frame relationships must be resolved or kept as explicitly conditional
inputs; the parser does not fill them in. Singular cases exit nonzero and emit an
incomplete-model diagnostic without writing a successful result. Malformed units,
nonfinite numbers, improper transforms, duplicate IDs and missing provenance fail.

Tests independently check arbitrary six-component balance and virtual work across
60 seeded cases, a known centered load, pure torsion, weighted-allocation
stationarity/optimality along a balanced null-space fixture, common-weight scaling,
coordinate/reference covariance, sign-constraint ambiguity and rejected layouts.
Source hole coordinates and nominal-to-native wrench rotation are separately
crosschecked against the preserved inputs. These establish declared mathematical
behavior, not native or physical performance.

## Unresolved mount gate

The 300 × 320 mm adapter remains a proposal. Grade/thickness, actual bench
dimensions/material, clamp positions/contact area, preload/contact availability,
friction/slip, fastener strength/pullout, desktop crushing, printed-base bearing
and creep, plate bending, cable/dynamic demand and independent gravity restraint
remain open. An accepted physical interface requires those inputs and separate
inspection/testing. No strength margin, household safety or fabrication/hardware
permission follows from equilibrium alone.
