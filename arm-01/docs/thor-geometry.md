# Thor geometry — source model, CAD cross-check and mounted instances

This study uses Thor native CAD `286b081fe6f056d87c379b884781ef77ff6a0159` and [Thor-ROS description `e11a56b5aa0d89f0b68a3ea7bd084eab4a050952`](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_urdf/urdf/thor.urdf.xacro). It separates three evidence classes:

1. **Saved native metadata:** pinned placements, linked assemblies and mating coordinate systems read from original XML, without executing CAD.
2. **Restored native geometry:** mounted-instance volumes and centroids read through the compatible FreeCAD environment. These may use cached shapes; successful restore does not establish successful feature recompute.
3. **Nominal source kinematics:** a mathematical transcription of the pinned upstream ROS origins/axes. It is not a calibrated ARM-01 model, released collision model, or permission for motion.

The native six zero-pose axis lines are now corroborated with analytic cylinder geometry, while their physical signs, limits and dynamic behavior remain unverified.

No source mass/inertia or effort values are adopted as engineering ratings. The ROS file's default mass of 1 kg on every link and identity inertias are placeholders.

## Exact upstream six-joint chain

The source uses zero joint-origin RPY, these translations relative to the previous moving link, and radians for joint coordinates:

| Joint | Parent → child | Origin translation m | Axis in joint frame | Zero-pose origin in base_link m |
|---|---|---|---|---|
| 1 | base_link → link_1 | (0, 0, 0.099) | +Z | (0, 0, 0.099) |
| 2 | link_1 → link_2 | (0, 0, 0.103) | +X | (0, 0, 0.202) |
| 3 | link_2 → link_3 | (0, 0, 0.160) | +X | (0, 0, 0.362) |
| 4 | link_3 → link_4 | (0, 0, 0.0895) | +Z | (0, 0, 0.4515) |
| 5 | link_4 → link_5 | (0, 0, 0.1045) | +X | (0, 0, 0.556) |
| 6 | link_5 → link_6 | (0, 0, 0.0135) | +Z | (0, 0, 0.5695) |

The source then adds fixed +Z offsets of 0.043 m to `gripper_base` and 0.075 m to `gripper_mid_point`. Thus its all-zero midpoint is at z = 0.6875 m. **That is a model's zero-pose height, not radial reach or a verified CAD grasp point.** The source's different mesh/link frame conventions and the actual native gripper geometry must be reconciled before adopting this TCP for ARM-01.

The original source byte SHA-256 is `19b83e26f86aae15fda5c21418f768d0e3ed1b0d1daa6d149abd9b45ceccd8b9`. The extracted geometry and selected native hashes are recorded in [thor-saved-geometry.json](../hardware/cad/thor-saved-geometry.json).

`src/raftel_arm01/kinematics/thor_model.py` implements this nominal FK without dependencies. `chain(q)` returns six world-frame axis lines and the `link_6` transform. `forward_kinematics(q, target)` also supports the source gripper base and midpoint. It accepts six finite angles, but deliberately does not claim physical joint limits, collision checking, inverse kinematics or motion safety. Independent planar/yaw cases and rotation-orthonormality tests verify the implementation rather than only comparing it with itself.

## Native mating-coordinate cross-check

Original master/subassembly placements and selected LCS coordinates produce:

| Source native coordinate system | Saved assembly-world position m | Interpretation |
|---|---|---|
| AssemblyBase `LCS_Art1003` | (0, 0, 0.079) | Art1 assembly mounting datum; a point on the nominal base yaw axis line, not proof that z = 0.079 is the URDF origin |
| AssemblyArt1 `LCS_Art2002` | (0, 0, 0.202) | Shoulder mating point; matches nominal joint-2 point |
| AssemblyArt2 `LCS_Art1` | (0, 0, 0.202) | Opposite side of the same shoulder mating interface |
| AssemblyArt2 `LCS_Model_1` | (0, 0, 0.362) | Elbow mating point; matches nominal joint-3 point |
| AssemblyArt3 `LCS_Art2Fix` | (0, 0, 0.362) | Opposite side of the elbow mating interface |
| AssemblyArt3 `LCS_Art4Fix` / Art4 `LCS_Art3Fix` | (0, 0, 0.4445) | Coaxial yaw interface; differs from nominal joint-4 origin by 7 mm **along** its proposed Z axis |
| AssemblyArt4 `LCS_Art56Fix` / Art56 `LCS_Art4Fix` | (0, 0, 0.556) | Wrist interface; matches nominal joint-5 point |

For example, Art2's saved assembly origin is `(0, -0.068, 0.202)` m, with a half-turn around `(0, 1, 1)`. Transforming its local mating point `(0, 0.160, 0.068)` gives `(0, 0, 0.362)` m. Art3's assembly origin at z = 0.4435 m is therefore **not** the elbow joint origin. Reusing assembly origins as joints would introduce a large link-length error.

Points along the same revolute axis describe the same mathematical axis line, so a 7 mm displacement along a proposed Z line is not by itself a kinematic mismatch. However, matching heights or mating points does **not** establish axis directions, signs, physical zero, TCP or cable/joint limits. The later native cylindrical-face probe below corroborates all six **unsigned zero-pose axis lines** and resolves the base-frame rotation. Command signs, TCP/contact calibration, travel limits and controlled articulation remain separate gates.

## Native cylindrical-axis evidence and frame reconciliation

The optional `tools/probe_thor_axes_freecad.py` was run against the compatible working copy in FreeCAD 1.1.4, without recompute or saving. A translated synthetic cylinder first confirmed that the native Surface center/axis data include the face's own transformed placement. Selected bearing/shaft cylindrical faces then established:

| Joint | Native evidence | Native unsigned axis line |
|---|---|---|
| 1 | AssemblyBase Bearing_16014zz001, 35 mm radius cylinder | Z through x = y = 0 |
| 2 | AssemblyArt2 Bearing_625ZZ002, 2.5 mm bore radius | Y through x = 0, z = 0.202 m |
| 3 | AssemblyArt2 Bearing_625ZZ001, 2.5 mm bore radius | Y through x = 0, z = 0.362 m |
| 4 | AssemblyArt4 Art4TransmissionColumn, 10 mm radius cylinder | Z through x = y = 0 |
| 5 | AssemblyArt4 Bearing_625ZZ001, 2.5 mm bore radius | Y through x = 0, z = 0.556 m |
| 6 | AssemblyArt56 Bearing_625ZZ001, 2.5 mm bore radius | Z through x = y = 0 at the studied wrist pose |

The native pitch-axis directions are **Y**, whereas the upstream ROS pitch axes are **X**. The source's arm mesh visual origins explicitly use `Rz(-PI/2)`. Applying that fixed native-CAD-to-source-base rotation gives:

```text
x_source =  y_native
 y_source = -x_native
z_source =  z_native
```

All six source zero-pose axis lines agree with the measured native cylinder lines under this frame conversion. Native line points can differ along an axis: for example, the wrist bearing's cylinder point is at z = 0.5775 m while nominal joint 6 is at 0.5695 m, but both lie on the same Z line. The [axis evidence report](../hardware/cad/thor-axis-evidence.json) records object IDs, native face indices, radii, line-distance residuals and unsigned collinearity. These are source-geometry checks, not physical calibration. A cylinder surface's signed axis orientation does not establish positive motor/joint command direction.

**Do not rotate native CAD centroids using nominal ROS FK without this frame conversion.** That error would move the masses about the wrong horizontal axis despite matching all zero-pose heights.

## Native gripper boundary and an explicit load proxy

The actual two visible finger solids were transformed through their installed instance placements. Both occupy z = 0.6410–0.7025242557 m in the studied native zero pose. Their opposing Y bounds are approximately +34.979…+55.040 mm and −55.040…−34.979 mm. The mirrored finger's hidden original construction link is not a third physical finger.

For load sensitivity, an explicitly defined geometric proxy is the intersection of the wrist roll axis with the most-distal finger bounding plane: **(0, 0, 0.7025242557) m**. It is not a measured contact point, grasp success guarantee, object COM or calibrated TCP. Object size and off-center grasps require additional payload-offset scenarios.

This proxy is 15.024 mm distal to the upstream ROS model's zero-pose midpoint at 0.6875 m. Its shoulder-axis distance is approximately 0.500524 m, so the original 350–450 mm useful-reach target should be treated as a task-region goal rather than scaling Thor's existing links. Subtracting the native Art1 mounting datum at 0.079 m gives 0.623524 m, close to the upstream 625 mm stretched-height description; that is a possible reference-height reconciliation, not proof of the author's exact dimensional convention.

## Mounted-instance extraction rules

`tools/extract_thor_geometry.py` reads the pinned native archives, the source Xacro as XML (without executing Xacro/Python), and optionally a native audit report. Its installed-instance walker starts at `Assembly::Model` and follows actual group/link membership:

- Expand installed `App::Part`/Model groups and links to part groups.
- Count `PartDesign::Body` once; do not count every sketch, feature, body tip or CSG dependency as another physical part.
- Preserve separate App::Link instance paths for repeated parts such as the three geared motors sharing one prototype.
- Exclude hidden procedural inputs when their final mirrored, arrayed or compounded output is installed in the same part group; retain an explicit exclusion ledger. For example, a compound switch shape already includes its six original sub-solids, and a bearing array already includes its source sphere.
- Deduplicate editor-only group aliases: the native Model also lists `Group003`, which refers to nuts/screws already present directly. Counting both would inflate volume and mass.
- Ignore explicitly recognized datum/reference/sketch objects and observed zero-solid geometry. Every other terminal requires a native shape observation, including directly installed `PartDesign::Pad` features outside a Body. Unknown terminal types fail closed instead of silently disappearing; terminal-type counts make the exclusions reviewable.
- Preserve bought-asset ancestry in each instance path so a whole motor's manufacturer mass is not added again to its CAD leaf density estimate.

Native synthetic fixtures established that raw `Shape` centroids include the object's own placement, but exclude ancestor App::Part transforms. App::Link with `LinkTransform=False` replaces the linked source's placement; `True` retains it. The extractor consequently applies only ancestor transforms to a raw instance centroid, and its explicitly labeled source-shape fallback reproduces the verified link transform rule. Applying both raw instance placement and leaf placement would double-transform a part.

Subassembly membership supports an initial mass-group map: Art1 is downstream of joint 1, Art2 of joints 1–2, Art3 of 1–3, and Art4 of 1–4. Art56 wrist internals need further separation between the fold and roll links. In particular, all three geared motors reside in Art1's native assembly, including the remote elbow drive; a motor's driven joint does not identify where its mass is carried. This grouping is a model assumption until articulation is verified; q6 body membership remains explicitly unresolved.

## Reproduce saved metadata extraction

From `arm-01`, with the pinned upstream Xacro saved locally:

```sh
python tools/extract_thor_geometry.py /path/to/Thor-reference/freecad-src \
  --urdf /path/to/pinned/thor.urdf.xacro \
  --inventory hardware/cad/thor-baseline-inspection.json > /path/to/work/saved-geometry.json
```

Add `--native-report /path/to/native-audit.json` to extract restored mounted-leaf data. Reports include the source hashes, pin match, frame/validation class, missing records, geometry errors, and unresolved mass/calibration flags. If metadata and selected shapes were captured separately, add `--shape-report /path/to/filtered-shapes.json` with the complete metadata file as `--native-report`; repeat `--shape-report` for independent supplements such as the wrist-belt capture. Runtime/master identity is checked; retaining unchanged source manifests between runs is the caller’s responsibility. Partial audit data are useful diagnostics but cannot establish complete installed mass coverage.

## Restored mounted geometry result

The historical [516-leaf inventory](../hardware/cad/thor-mounted-geometry.json) omitted **two installed closed wrist belts**. Its old missing-geometry guard only recognized `Part::` and `App::Link`, so `AssemblyArt4::Pad046`, a `PartDesign::Pad` installed through two belt-group links, was silently skipped. Zero reported errors in that historical result therefore did not prove complete installed-leaf coverage. The original inventory and reports are retained unchanged for provenance.

Use the corrected [518-leaf inventory v2](../hardware/cad/thor-mounted-geometry-v2.json) for current work. All 516 prior rows remain exactly unchanged; two explicit belt instance paths and their volume/COM observations are added. A [supplemental native capture](../hardware/cad/thor-wrist-belt-native-validation.json) validates the cached source belt as one positive-volume solid, instanced twice, with volume 2013.9894452343387 mm³ per belt. Its recorded state is `Touched`, mode is `none`, and no original source is saved; this is cached shape/topology evidence, not a feature-history recompute.

The corrected walker accounts for every reachable installed terminal type, explicitly excludes datum/sketch/Assembly4 Variables records, and fails closed on missing shape inventory for all other terminal types. The retained traversal has 518 physical solid leaves, one observed zero-solid wire/reference, 226 nonphysical support records and the same fourteen excluded hidden procedural inputs. An independent metadata traversal found no other omitted solid terminal. See [completeness correction and reproduction](thor-geometry-completeness.md) for precise scope and hashes.

These are restored source-CAD shapes, not independently measured manufactured parts or proof that the source CAD includes every real wire, fastener or accessory. Material, printed fill, purchased-part masses, belt construction and physical assembly remain separate evidence. See the load study's current per-instance ledger before using any mass result.

## Remaining geometry gates

1. Preserve the successful compatibility and six-axis evidence; reproduce full geometry extraction if CAD is changed.
2. Calibrate positive joint directions and a reproducible physical zero, then verify travel/cable/collision limits.
3. Establish gripper contact/TCP calibration and jaw motion; the native boundary proxy is only an explicit analytical scenario.
4. Split wrist fold/roll moving bodies, verify signs/zeros and coupled feasible limits, then check trajectories against full geometry.
5. Attach measured or explicitly estimated component masses/COMs to mounted instances. Volumes and centroids are geometry; material, print process, bought components and omitted hardware determine mass confidence.
