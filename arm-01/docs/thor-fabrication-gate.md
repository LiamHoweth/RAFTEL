# Thor fabrication interfaces and acceptance gate

The pinned source geometry supports a dimensioned **interface proposal and fit plan**. It does not release a printable arm, mount or interchangeable tool. [Machine-readable dimensions](../hardware/cad/thor-fabrication-interfaces.json) record source-file hashes, cached native face indices, cylinder axes, datum matrices and 46 printed-source envelopes. Native FreeCAD 1.1.4 read these shapes without recomputing or saving the originals. The printed-envelope pass used the already pinned Fasteners and Gears 0.0.3 addons. Original Art1 history remains unresolved; its cached solid and compatible static snapshot are different evidence lanes.

## Bench-side interface

Use the **BaseBot source frame**, with `LCS_Bot=(0,0,0) mm` and source z=0 at the nominal underside plane. The final installed asset is `BaseBot::Body002`, not the earlier Body or its auxiliary Body001. Its envelope is x −75 to +127.4517 mm, y ±127.4517 mm, z 0–65.5 mm: **202.4517 × 254.9034 × 65.5 mm**. Preserve source axis orientation when mapping this into the workstation's separately defined bench frame.

| Hole | Source x, y in mm | Saved geometry |
|---|---:|---|
| A | 0, +86 | Ø6 bore, z=0–5 mm; Ø14 recess above z=5 |
| B | +74.478185, +43 | Same |
| C | 0, −86 | Same |
| D | +74.478185, −43 | Same |

The four centers lie on an 86 mm radius; `74.478185=86 cos(30°)` and `43=86 sin(30°)`. This is an **asymmetric four-point pattern**, not a square or a complete six-hole circle. Bore faces 6/9/11/13 and recess faces 63/64/69/70 supply the dimensions. The recess tops intersect nonplanar surfaces, so a single assumed recess depth would be misleading. Ø6 does not by itself select a bolt, fit class, washer or clamp preload. Verify head/washer access through the Ø14 relief and retention below the base.

The proposal is a separate **metal adapter blank 300 × 320 mm**, source-frame outline x −100 to +200 mm and y −160 to +160 mm. It preserves the four arm-side locations and original underside plane. Grade, thickness `t`, finished clearance holes, underside retention and clamp ears remain parameters; no structural thickness or clamp rating is selected. The blank leaves at least 25 mm geometric margin around the source base envelope, which is layout room rather than evidence of adequate edge distance or clamp-pad area. Cable/connector and tool access can require a larger outline.

Use two separated, independently retained bench clamps or a verified bolted bench interface as the candidate load path. Their positions, pad area and spacing must come from Liam's actual bench dimensions, underside access and clamp data. Do not infer clamp reactions by splitting the arm weight equally. Compute the full wrench at the plate, then resolve clamp/bolt reactions using the measured lever arms and check slip, pullout, local desktop crushing, plate bending and printed-base bearing/creep. Include loss-of-power gravity collapse and cable loads in the later test plan. The existing [workstation proposal](workstation.md) remains provisional.

## Wrist/tool interface

The source interface is **a cylindrical socket with radial retention**, not an axial three-bolt flange. In the Art56GearPlate source frame:

- Male cylindrical surface: **Ø30 mm**, z −42.5 to −5 mm. The gripper end is z=−42.5 mm.
- Three radial **Ø3.4 mm** hole lines intersect the plane z=−38 mm, **4.5 mm from that end**, at 120° spacing. Their common axis-line origin is `(0,0,−38) mm`; directions are `(0,−1,0)` and `(±√3/2,0.5,0)`. HoleAxis datum origins at radius 12.5 mm are points along radial bores, not axial bolt positions.
- GripperBot and GripperTop form the matching **Ø31 mm** socket. The nominal diametral difference is 1 mm; this is saved CAD clearance, not measured print fit, repeatability or a recommendation to add another 1 mm allowance.

Keep the saved mounting expression: `plate.Placement * plate.LCS_Gripper * AttachmentOffset * gripper.LCS_GripperBot^-1`. The pinned assembly's offset includes **+1 mm local z and a 180° tilt**. Preserve that transform when designing an adapter; aligning only the two cylinder axes loses axial and angular registration. The report retains both datum matrices and exact attachment data. Mechanical retention, actual fastener engagement, insertion depth, access and angular registration still require a fit inspection. This is not a standard or qualified quick-release tool interface.

For the initial design, retain this source coupling and make a separate sacrificial socket/hole coupon before changing the bevel plate or jaw carrier. A later passive adapter must declare its mass, COM and tool transform and update the load inventory. Keep the parallel-jaw decision separate: see the [gripper study](thor-gripper-kinematics.md); socket fit does not prove jaw motion or grip force.

## Build-volume and slicing plan

Liam's [Kobra 3 Max record](../hardware/fabrication.md) supplies a nominal **420 × 420 × 500 mm** volume and PLA/PETG/ABS availability. Exact installed nozzle, usable machine area, profiles and filament formulations remain unknown. All **46 unique printed source shapes** selected by the existing mass ledger fit that nominal volume in their saved source-axis bounding boxes. The ledger has 65 installed printed leaves, with repeated assets and one mirrored finger; the mirrored finger uses the original finger geometry and was not reopened as an independent assembly envelope. This check includes the cached original Art1 solid but does not make its history editable.

The largest source envelopes are:

| Source part | Saved x × y × z envelope, mm |
|---|---:|
| Art2BodyA / Art2BodyB | 139.656 × 299.656 × 32 |
| Art2BodyBCover | 120 × 280 × 7 |
| Art2SideCover | 120 × 280 × 2 |
| BaseBot | 202.452 × 254.903 × 65.5 |

These are source-shape envelopes only. Supports, brim, skirt, machine keepouts, chosen orientation, shrinkage and export tessellation are excluded. No part has been sliced and no G-code was generated. Do not uniformly rescale the arm to compensate for fits: that changes gears, bearings, axes and fastener patterns together.

For each actual filament/profile candidate, record the slicer/version, exported machine/material profile, nozzle, layer height, line width, wall/skin counts, infill type, orientation, supports and ambient process. Start with source underside/major planar faces on the bed as **orientation candidates**, then inspect overhangs and whether critical loads separate layers. Compare another orientation where pivot bosses, gear teeth or collar retention make layer direction important. Do not select PLA, PETG or ABS structurally from density alone; ABS also needs the actual thermal setup/profile to be demonstrated.

Use this staged plan after fabrication is explicitly approved:

1. Export only final installed printable solids from the compatible copy; retain source revision, object name, export units and mesh settings. Check manifoldness and dimensions against this report. Do not export history features/prototypes twice.
2. Slice small source-derived coupons first: the Ø30/31 socket with radial retention, Ø6/14 base hole/recess, representative bearing seat, and gear/pivot features. If comparing compensation offsets, label each offset rather than silently editing the original design. Keep the unmodified nominal coupon as the reference.
3. Before accepting a fit, choose and record the required clearance/interference and retention behavior using the actual bearing/shaft/fastener drawing and intended assembly method. Measure multiple locations and X/Y/Z directions; record instrument resolution. Pass only if the documented fit assembles without forcing or cracks, retains the intended component, and repeats after removal. No numerical fit tolerance is claimed before those requirements are selected.
4. Export per-part slicer mass with walls/skins/infill separated where available, support/purge mass separate, and component orientation. Compare slicer mass to a cleaned, weighed printed coupon/part using a recorded scale resolution. Record discrepancies and rerun mass/COM sensitivity when they materially affect demand; the original 50% whole-part factor is not an infill setting.
5. Dry-fit the unpowered interface, check hole alignment, axial seating, radial fastener access, remount registration and full cable/tool keepouts. A repeatability target must be allocated from the later manipulation accuracy budget before declaring a pass.
6. Only after the mount calculations and material/fit evidence close, prepare a restrained proof/deflection/creep test with an explicit load case, acceptance limit and stop criteria. No powered motion follows automatically from a successful print or dry fit.

## Remaining evidence gate

Liam's bench dimensions, thickness/material and clamp access determine the adapter's final outline, thickness and clamp geometry. His actual profiles and filaments determine slicing and fit. The final source-editability decision remains governed by the [Art1 editability gate](thor-art1-editability-gate.md) and [compatibility baseline](thor-assembly-compatibility.md): preserve the upstream original, keep the exact static analysis snapshot separate, and validate a bounded procedural migration before relying on edited Art1 history. None of those missing measurements prevents this dimensioned proposal, but they prevent a manufacturing or load-rated release.
