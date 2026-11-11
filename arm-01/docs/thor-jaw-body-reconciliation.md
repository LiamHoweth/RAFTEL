# Thor jaw body and pivot reconciliation

The new [jaw ownership ledger](../hardware/cad/thor-jaw-body-ledger.json) accounts for all **66 installed Art56 geometry leaves and 66 existing mass records**. It supports two deliberately separate configurations: the exact saved COMs, and an explicitly normalized ideal parallelogram scenario. It does not close the saved native linkage, repair gear contact or qualify physical motion.

The initial desktop jaw audit used Python to read seven hash-verified native source ZIP/XML archives at [Thor revision 286b081](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src). FreeCAD was unavailable at that initial checkpoint; the later [Windows native foundation](thor-windows-native-foundation.md) is separate evidence and does not turn these jaw metadata calculations into a native linkage solve. Twelve pivot/tip/hole locations were independently recalculated from their saved placements and checked against the [prior native gripper capture](../hardware/cad/thor-gripper-kinematics.json). This is **source metadata arithmetic**, not a new CAD feature rebuild, native contact simulation or physical measurement. Original CAD and earlier reports remain unchanged.

## Frames and configurations

`GripperBot` Body-local coordinates use metres and radians in the evaluator. Its source XY jaw plane maps through the exact saved placement into native assembly-world axes. The ledger records `native_from_gripper_bot`, with the explicit direction `p_native = T_native_from_bot * p_bot`. It composes `Assembly::AssemblyArt56.Placement` and `AssemblyArt56::GripperBot_GripperBot.Placement`, with both Model group frames verified to be identity.

The bot's saved orientation is slightly offset from nominal axes. Its local +X direction in native coordinates is approximately `(0.002721133, -0.999996298, 0)`, local +Y is native +Z, and local +Z is approximately `(-0.999996298, -0.002721133, 0)`. Its origin is approximately `(0.017149937, 0.000046667, 0.6125)` m. Use the recorded full matrix rather than these rounded values. These are native CAD coordinates; use the established `(x_ros,y_ros,z_ros)=(y_native,-x_native,z_native)` conversion before applying nominal ROS-frame arm transforms.

`jaw_body_states(ledger, mode="saved")` returns every saved native COM exactly with zero jaw derivative. It rejects a supplied jaw coordinate because the saved assembly has no solved common closing coordinate. The existing frozen-jaw studies continue to describe this configuration.

`jaw_body_states(ledger, q, mode="ideal")` uses the existing [IdealThorGripper](../src/raftel_arm01/kinematics/thor_gripper.py) coordinate, with `0 <= q < pi/2`. This is a mathematical study interval. The function returns each existing mass-record ID mapped to a `JawBodyState(position_m, derivative_m_rad)` in native assembly-world coordinates at zero arm pose. It stores no mass and adds no purchased asset. An upstream arm/wrist load evaluator must carry both positions and derivatives through its explicit transforms.

## Saved-to-ideal changes are part of the scenario

The saved active pivot has local X `-14.515` mm; the ideal model uses `-14.5` mm. The active arm, horn and its three screws therefore receive an explicit **+0.015 mm local X shift** in the ideal scenario. Their saved closing phase of approximately **0.279637283 degrees** is removed. The passive driven arm's saved phase of **0.25 degrees** is separately removed. Auxiliary phases are numerically zero. These changes are recorded per moving body and in `ideal_zero_normalizations`; ideal `q=0` is not the saved assembly.

For side `s=-1` left and `s=+1` right, a rotating record uses

```text
p_bot(q) = ideal_pivot + Rz(s * (q - saved_closing_phase)) * (saved_COM - saved_pivot)
dp_bot/dq = s * ez cross (p_bot - ideal_pivot)
```

Finger bodies and their retained fasteners translate by `(s*0.035*(cos(q)-1), 0.035*sin(q), 0)` m while keeping their saved orientation. The common translation reuses `IdealThorGripper`; it is not inferred from a commanded servo angle.

The active source pivot/tip have different axial Z coordinates because the datum is at a different place along the same rotation-axis line. Rotation about +Z preserves each COM's axial height; those axial differences are not added to the planar loop-error figures. The prior saved driven-axis residuals remain approximately **0.17144 mm left and 0.15272 mm right**. This overlay does not claim those residuals disappear in saved CAD. Moving the ideal active pivot relative to the saved servo support is a conditional alignment proposal; a mechanically realizable repair still needs a copied native assembly and joint-stack inspection.

## Exact ownership

The complete ledger preserves full instance paths, including repeated leaves and nested groups. Names below refer to `AssemblyArt56` objects at the pinned revision.

| Motion in the ideal jaw scenario | Existing records | Basis and remaining assumption |
| --- | --- | --- |
| Left finger translation | `Unnamed1_GripperFinger`, `Screw022`, `Screw023`, `Nut021`, `Nut022` | Saved finger and explicit HoleAxis attachments; retained fasteners are assumed to move with the finger. |
| Right finger translation | `GripperFinger_sym001/Unnamed1_GripperFinger_mirrored`, `Screw024`, `Screw025`, `Nut019`, `Nut020` | Saved mirrored finger and explicit attachments; the hidden source finger is not counted again. |
| Left active rotation | `GripperActiveArm_GripperActiveArm`, `ServomotorWheelHorn001/Clone041003009009001`, `Screw027`, `Screw028`, `Group003/Screw026` | Saved horn/arm/screw attachment chain; ideal phase and pivot normalization are explicit. Actual retention is unverified. |
| Right passive rotation | `Unnamed3_GripperPassiveArm` | Saved passive pivot/phase; equal/opposite ideal gear increments are conditional. |
| Auxiliary rotations | `Unnamed2_GripperArm001` left, `Unnamed2_GripperArm` right | Saved `GripperBot` auxiliary pivots and 35 mm links. |
| No additional jaw COM motion | Remaining 48 records | Preserve their saved COM and existing v2 wrist class. This includes gripper top/base, fixed-pivot fasteners, all wrist internals and the whole servo COM proxy. |

Fasteners attached to the fixed gripper top/base are modeled as fixed under jaw motion. A pin's axis attachment does not by itself establish which physical race or shank rotates; actual retention and tiny eccentric terms remain unverified. The whole **55 g servo asset** remains one mass record at `.../Servomotor001`, while its native leaf is `.../Servomotor001/AssemblyArt56::Compound002`. The horn remains its already separate mass record. The balanced-internal-COM approximation avoids fabricating a servo rotor mass. All seven arm motor masses remain **2.120 kg**; neither an additional rotor mass nor a replacement motor COM is introduced.

The overlay leaves all 452 geometry leaves outside Art56 to the existing model. The whole corrected inventory remains 518 leaves/517 mass records. A complete conditional load scenario must conserve these identities rather than append jaw bodies to already counted frozen bodies.

## Reproduction and validation

Run from `arm-01` after installing the project development environment:

```powershell
python tools/thor_jaw_reconciliation.py --check-ledger hardware/cad/thor-jaw-body-ledger.json
python -m pytest tests/test_thor_jaw_bodies.py tests/test_thor_gripper.py
```

To regenerate from a local copy of the seven pinned source archives, use a **new** output path:

```powershell
python tools/thor_jaw_reconciliation.py --source-dir C:\path\to\pinned\freecad-src --output C:\path\to\new-jaw-ledger.json
```

Generation verifies the source hashes, checks twelve saved points against the prior capture, and preserves exact native COMs and v2 wrist membership. Runtime validation checks declared artifact bindings and COM/ownership coverage against canonical inventory/membership hashes; it rejects stale inputs, missing/duplicated leaves, changed saved COMs, invalid transforms, nonfinite coordinates and incompatible membership. It does not independently reauthenticate the saved frame or pivot assignments; regeneration from the pinned source performs that source check. The CLI additionally rejects duplicate JSON keys and nonfinite JSON values and reports malformed/missing evidence as a clean argument error. The CLI does not open network or hardware connections, recompute CAD, save sources or overwrite evidence.

Focused checks independently verify native-to-ROS COM mapping, all existing mass-record IDs, the servo and arm-motor totals, finger displacement, rigid-link radius conservation, all 66 COM derivatives over seeded poses and a mass-weighted potential/virtual-work comparison under arbitrary gravity orientation. Those checks verify declared analytical motion only. No mesh interference, native multi-pose contact, physical jaw stroke, servo polarity, gripping force, thermal duty or fabrication release is established.

## Offline repair specification and capture predicates

The new [repair specification](../hardware/cad/thor-jaw-repair-specification.json) binds the pinned sources and exact ideal-body ledger. It is a **proposed numerical validation procedure**, not a native repair result. `tools/thor_jaw_acceptance.py` checks a supplied multi-pose capture against its declared geometry. The chosen numerical targets (1 micrometre positions/loop closure, 1e-7 rad link phase, 1e-8 axis/normal vector error) diagnose reproduction of the ideal model; they are not physical fit, clearance or safety tolerances.

The candidate sampling targets are ideal `q=0`, `pi/6` and `pi/3`. These three study points do not establish a usable stroke. At each pose, the capture must identify both sides and provide six points in the common GripperBot-local SI frame: driven/auxiliary base pivots, driven/auxiliary link tips, and the two corresponding finger-hole axes. It must also provide four unit pivot-axis directions and each identified finger-plane point/unit normal. Predicates check nominal XY pivots, projected loop-axis coincidence, 35 mm link lengths, the constant finger pivot vector, equal/opposite driven-link phases, opposing constant finger normals and the conditional `70*cos(q)` mm plane separation. Axial distances along a common revolute line are deliberately excluded from planar loop errors; fixed-pin stack engagement and axial retention stay unresolved.

Capture structure:

```text
schema_version: 1
evidence_class: native_selected_geometry | synthetic_fixture
configuration: ideal_derived_candidate | saved_original
source_revision, original_source_sha256: exact specification bindings
jaw_body_ledger_canonical_sha256: exact specification binding
coordinate_frame: "GripperBot source Body local XYZ, metres"
provenance: generator/runtime/version, candidate document hashes,
            recompute_mode and save_reopen_verified for native declarations
poses: [{q_rad, sides: {left: {...}, right: {...}}}]
per-side fields: driven_pivot_m, auxiliary_pivot_m, driven_tip_m,
                 auxiliary_tip_m, finger_driven_hole_m, finger_auxiliary_hole_m,
                 axis_units: {driven_base, auxiliary_base, finger_driven, finger_auxiliary},
                 contact_plane: {point_m, normal_unit}
```

A `saved_original` capture has exactly one pose with `q_rad=null`. It diagnoses residuals without relabeling the saved geometry as ideal zero. The historical source points produce the expected approximately 0.17144/0.15272 mm driven-loop residuals and 0.015 mm active-pivot mismatch in this checker. Candidate captures require all three study points; duplicate poses, missing side/axis fields, stale hashes, wrong frames, nonfinite values and nonunit directions are rejected or explicitly fail completion.

```powershell
python tools/thor_jaw_acceptance.py --capture C:\path\to\new-capture.json --output C:\path\to\new-jaw-predicate-report.json
python -m pytest tests/test_thor_jaw_acceptance.py
```

The command writes a new report and returns 0 only when all required declared geometry predicates pass; it returns 1 for a valid diagnostic capture that fails those predicates and 2 for malformed inputs. `input_evidence_class` is preserved. `native_rebuild_metadata_complete` indicates that supplied metadata declares forced selected-feature rebuild and save/reopen checks; it does not authenticate execution. **Every output keeps `native_verification_complete=false`, `contact_qualified=false`, `retention_qualified=false`, `usable_opening_m=null`, `physical_calibration_qualified=false` and `fabrication_released=false`.** Finger-plane geometry does not demonstrate gear/body contact, actual pad engagement, force retention or absence of interference. Even a supplied native capture requires independent source/runtime inspection; synthetic fixtures never become native evidence.

Tests construct three ideal poses independently, reject pivot/loop/normal/aperture/phase counterexamples, replay the unsolved historical planar points, exercise provenance and malformed-input failures, and show that declared native metadata cannot authenticate a run. No new native capture or accepted copied-CAD repair was produced on this host.

## Native acceptance still required

1. In copied CAD, reconcile the active axis/support offset, driven phases, both closed loops and equal/opposite gear motion. Record changed dimensions and semantic supports; preserve upstream source and static evidence.
2. Check multiple saved and proposed jaw poses with independent contact-plane, pivot-axis and interference probes. Include fixed-pivot stack/fastener retention, source wrist gearing and all travel stops.
3. Replace conditional COM/retention/servo assumptions with measured evidence only through an explicitly revisioned scenario. Physical calibration and unpowered inspection remain separate from any later authorized commissioning.

Thor source attribution and derivative obligations remain governed by the pinned reference records in [references.json](../hardware/cad/references.json) and [CAD reuse policy](cad-reuse.md). This ledger is metadata/analysis, not an exported part or a change to RAFTEL's company-wide licensing.
