# Limited native nonzero pose and frame checks

The [retained native capture](../hardware/cad/thor-native-pose-frames.json) checks the existing compatible Thor assembly at **saved zero plus three nonzero analytical scenarios**. Existing native placement expressions, six unsigned cylinder-axis lines and the complete fold-frame transform agree with the pinned nominal ROS model for the tested first four coordinates. **q5 and q6 remain zero.** This is not full six-coordinate native FK, physical calibration, collision/contact, TCP or hardware validation.

The accepted matching-worker run started **2026-11-11 22:06:27 UTC** and completed in **158.49 seconds** using portable FreeCAD 1.1.4 / Open CASCADE 7.8.1. The frozen worker is SHA-256 `844eae394f3d6cec505bac5b01066ed8c2eb171254e871a2da2c7eb51d9cb261`; the request is `de9acb8a5a6ec99d8ef11d01dc5c67f09cb6ce4bc0552a775f65beaaeee4af6f`. The executable was checked against `1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d` before launch. Actual five preference/home/data/temp paths were checked before opening CAD. The process began with zero documents and closed all 53 documents it created without saving.

## What was changed in memory

The saved `Assembly::Variables` object contains **no custom angle variables**. The probe therefore creates no new joint variables and makes no claim that source controller commands drive these placements. It temporarily rotates the existing `AttachmentOffset` properties of four master `App::Link` objects, then asks the master document to evaluate its existing Assembly4 placement expressions.

| Source mathematical coordinate | Existing master link | Parent mating datum | Right-increment axis in saved offset frame |
| --- | --- | --- | --- |
| q1 | `AssemblyArt1` | `AssemblyBase::LCS_Art1003` | +Z |
| q2 | `AssemblyArt2` | `AssemblyArt1::LCS_Art2002` | +Z |
| q3 | `AssemblyArt3` | `AssemblyArt2::LCS_Model_1` | +Y |
| q4 | `AssemblyArt4` | `AssemblyArt3::LCS_Art4Fix` | +Z |

The operation is `saved_AttachmentOffset * Rotation(local_axis,q)`, with radians explicitly converted to the native rotation constructor's degrees. The saved offsets are not identities; their original rotations must remain in the chain. The chosen axes follow the pinned source datum/offset orientations and are checked against the native zero-axis lines before any nonzero pose. They map to native +Z/+Y/+Y/+Z, and then to source +Z/+X/+X/+Z under the documented CAD-to-ROS rotation. These are declared mathematical signs, not motor polarity or measured hardware signs.

The three scenarios, in source radians, are:

```text
base_rotation       (0.3,  0,    0,    0,   0, 0)
shoulder_rotation   (0,    0.25, 0,    0,   0, 0)
mixed_proximal      (0.2, -0.3,  0.25, 0.4, 0, 0)
```

Each pose records actual offset matrices, quaternions and unchanged source expression strings after master recomputation. All sixteen offset readbacks across zero/nonzero cases were independently checked. The original offsets were restored in memory before closing, with maximum reset matrix error zero. No CAD document, original source or copied FCStd file was saved. The 57-file compatible input remains the exact static Art1 wrapper SHA `142d754d3551352ffd2338d940cc3edecb9d272b2401f70aea9f89fea164c140` plus 56 pinned original files; this does not repair original Art1 procedural history.

## Independent references and observed refresh

Native geometry is not recreated from the nominal chain. The worker opens the copied compatible assembly, evaluates its saved mating-datum expressions, and reads existing native objects. Host-side nominal references reuse the existing FK; the actual pinned Xacro byte hash is checked before preparation. The source frame conversion remains `Rz(-pi/2)`, with positions converted from mm to m.

The complete fold frame is the existing master `AssemblyArt56` placement. At zero its native orientation is Rz(+pi/2) and its origin is z=556 mm. The source comparison is `FK(link_6) * TransZ(-0.0135 m)` with q5=q6=0. **13.5 mm comes directly from the pinned Xacro's joint-6 origin**, rather than being fitted to the native zero pose. This comparison does not identify a gripper/contact TCP.

All six observed cylinders retain their pinned object/face/radius identities. Shape coordinates already include each object's own placement; the probe applies only the master subassembly ancestor placement once. Every relevant native `Model` ancestor is required to be identity. Cylinder comparisons use unsigned directions and perpendicular distance to the expected line, allowing distinct points along one axis. The known joint-4 mating-plane versus source-axis-point offset and joint-6 bearing versus nominal-axis-point offset are therefore not silently treated as coincident frame origins.

To detect stale link geometry, each case also reads an actual raw first vertex from the master Art56 link's `Shape`. Its 6,129 vertices remain stable, and that raw vertex follows the measured parent-placement delta without applying the shape placement a second time. This supports observed link-geometry refresh for this marker. It is not a full surface-deviation or all-descendant geometry check.

Across the four cases, maximum recorded errors are approximately **1.214e-16 m fold position**, **8.545e-16 rad fold orientation**, **2.824e-16 m axis-line distance**, **2.235e-15 unsigned direction difference**, and **2.275e-13 mm marker refresh**. These floating-point residuals establish source/model consistency in the declared scenarios, not manufacturing tolerances or physical accuracy. Independent review parsed the Xacro directly and used a separate fixed-space screw/product-of-exponentials calculation, without production FK/frame helpers, to check all four fold matrices and 24 axis observations.

## States, preservation and evidence limits

The final capture includes all **3,001 object states across 53 documents**. **39 objects remain Touched**, with no Invalid/Error states. The worker recomputes the master placement expressions; it does not force every external feature history. Accordingly, this report makes no all-Up-to-date or whole-assembly feature-rebuild claim. The cached source geometry, explicit frame observations and pending states remain distinguishable.

All 57 retained compatible inputs and all copied inputs, worker/helper/request snapshots remained byte-identical before/after. Fasteners and historical Gears module origins and hashes match the previously pinned smoke evidence. The generic audit helper is itself retained by SHA-256; its isolation guard runs before opening the assembly. Rejected fresh-process guards preserve pre-existing documents, and cleanup closes only documents created by this worker. That failure path has a separate host regression test.

Run 01 remains an actual locally retained earlier capture. Its fresh process contained zero prior documents, so the subsequently found rejected-guard cleanup defect was not exercised. Run 02 repeats the numerical observations with the corrected worker and document-qualified state summaries. The publication keeps original native fields unchanged and appends an explicitly labeled **derived publication receipt** containing the raw native-report hash and actual launcher observations; launcher facts are not presented as additional native observations.

The existing [nominal frame/Jacobian/IK documentation](thor-spatial-kinematics.md) remains the software contract. This limited capture adds nonzero first-four-coordinate native evidence while leaving bench/camera registration, actual TCP, q5/q6 internal motion, stops, collision clearance, gear contact, physical zeros/signs and actuator/load acceptance unresolved. It sends no controller commands and provides no hardware-motion or fabrication authorization.

## Reproduction

Use `tools/probe_thor_pose_frames_desktop.py` from an immutable snapshot in the centrally coordinated native queue. Its host `prepare_contract(source_root,arm01_root,pinned_xacro)` verifies the 57 retained compatible inputs, the original source inventory, source placement expressions and Xacro byte pin, and creates the zero plus three-case request. A regenerated static wrapper with different bytes requires inspection and a newly versioned contract; do not overwrite this historical capture or silently substitute it.

Copy the entire compatible sibling tree into a fresh run directory; snapshot the worker, `audit_freecad_assembly.py`, request and module-origin pins. Select dedicated `-u`/`-s` files and existing run-local `FREECAD_USER_HOME`, `FREECAD_USER_DATA`, `FREECAD_USER_TEMP`; set `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1`. The worker opt-in is `RAFTEL_RUN_THOR_POSE_FRAMES=1`, with `RAFTEL_POSE_RUN_DIR` and `RAFTEL_POSE_ENVELOPE` pointing inside that run. Apply a bounded outer timeout, preserve checkpoints, check the complete result and close state, and authenticate original/copy/code hashes after exit. A successful process exit alone is not pose acceptance.
