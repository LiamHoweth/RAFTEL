# Preliminary BenchSort workstation

**Planning geometry only; not a validated physical layout.** Liam permits eight actuators and selected Thor as the first existing-CAD study. Desk target remains 800 × 600 mm; Thor-specific footprint, base height, mass, horizontal reach and tool approach clearance have not yet been extracted or validated. Its upstream stretched-height figure must not be treated as horizontal reach.

The earlier 350–450 mm ARM-01 reach target is a planning requirement, not a measured Thor property. At that reach, a rear-mounted arm cannot cover the full desk: a point 600 mm forward is outside even a 450 mm sphere before height, joint limits and tool orientation. Preserve the restricted working regions below as provisional examples; revise them from the selected Thor model rather than stretching links to fit the desk.

Use right-handed `bench` coordinates: x to the operator's right, y forward from the rear edge, z up. Proposed base origin is `(0, 0.05, 0)` m relative to the rear-center edge; actual shoulder height remains a CAD-dependent transform. Desk bounds are x ±0.4 m, y 0–0.6 m. Record `bench → arm_base → tool`, `bench → camera`, and bin transforms in calibration; never substitute arbitrary table points for measured frames.

## Candidate regions

| Item | Preliminary bench location | Unverified constraints |
|---|---|---|
| Arm base | Rear-center at y≈0.05 m | Retain rear clamp clearance and cable bend radius; ensure desk edge is structurally adequate |
| Source objects | x≈−0.12 to +0.12 m, y≈0.18–0.28 m | Verify full grasp/retreat path and object height, not just center-point distance |
| Left bin | Center approximately (−0.22, 0.15) m | Low walls and tool clearance; collision model must include walls |
| Center bin | Center approximately (0, 0.34) m | Reach at release height may constrain opening size and approach |
| Right bin | Center approximately (+0.22, 0.15) m | Cable and wrist clearance; avoid source-region overlap |
| Camera | Rigid overhead support, optical axis toward working regions | All source/bin markers visible with no unstable arm-mounted reference |
| Power/distribution | Rear or side, outside all swept volumes | Ventilation, splash avoidance, enclosed terminals and source-proximate protection |
| Physical emergency stop | Operator's near side outside arm reach | Accessible without crossing the robot, unobstructed even with bins present |

The positions are a physical planning example, not the logical demo's validated robot coordinates. Map them only after arm geometry and calibration are established. Select low-wall containers around 80–100 mm wide provisionally; dimensions remain open until geometry checks. Keep the frontmost desk strip free for operator access and separation, not object collection.

## Mounting and load path

Use a removable metal base plate or reinforced interface whose bolts match the selected Thor upstream base, preserving the original arm-side geometry during baseline study. A separate adapter can preserve the proven arm geometry and permit future chassis migration. Transfer forces through the plate, clamp/bolts and bench structure; do not assume printed plastic clamp threads, thin desktop veneer or furniture trim are structural anchors. Two separated clamps may resist rotation better than a single clamp, but exact ratings, spacing, desk thickness and load distribution require verification.

For the selected Thor pose/payload, calculate actual arm and payload overturning moment, horizontal inertial load and cable forces. Include seven arm motors, transmissions, printed structure, gripper and cables; do not reuse the lightweight C001 reference mass model as a Thor load rating. Derive clamp reactions/bolt forces from the actual lever arms; include dynamic allowance and pullout/slip checks. A removable design is not considered secure merely because it fits. Complete the mechanical analysis and a restrained physical proof/deflection test before motor operation. No fabricated mount CAD is supplied in this milestone.

## Camera and calibration

Attach the camera to a rigid support separate from flexible printed links. Provide diffuse steady illumination and a reproducible, dimensioned calibration target across the grasp plane. Calibrate intrinsics/distortion and bench extrinsics; include held-out points and report position error. A planar homography applies only to the calibrated plane and is not general 3D pose estimation. Object height and occlusion need their own handling before arbitrary household items are attempted.

## Cable and operational preparation

Route stepper, sensor and gripper cables along links with strain relief and joint service loops; keep them clear of exposed belts and pulleys as well as all joint travel; secure host/power cables behind the workstation. Avoid cable drag on bins and source objects. Keep a guarded gravity-collapse/drop zone clear. No camera support, supply or emergency-stop cable may become a collision obstacle or compromise the removable mount.

Liam's next measurements: usable desk dimensions; rear/underside access; tabletop thickness/material; clamp pad area; nearby obstructions; desired bin dimensions; camera mount height/view; existing supply/camera/printer availability. These measurements precede purchasing or drilling.
