# Reusing an existing mechanical design

Research checked 2026-11-11. **Decision direction: reuse existing CAD and reproduce a baseline before changing load-bearing geometry.** This document is an adoption plan, not a released mechanical design. Liam authorized eight actuators and selected **Thor as the first baseline to study** on 2026-11-11. A pinned Thor source checkout has been acquired outside this repository and all 57 native CAD containers inspected. No CAD has been imported into a CAD application, recomputed, fabricated, or physically validated. No upstream CAD assets are vendored here.

## What “proven” means for ARM-01

An upstream arm with build instructions, released parts, physical demonstrations and repeat builders is a stronger starting point than an attractive render. Those indicators establish an existing platform, not that its advertised payload, accuracy, duty cycle, or safety is established for RAFTEL. Our copy must still pass dimensional, electrical, thermal and manipulation tests. Every geometry or actuator change narrows how much upstream evidence transfers.

The six-independent-arm-axis requirement excludes the gripper. The seven-total-actuator target is a separate requirement. A six-axis design can use more than six arm motors, and a servo-operated jaw is not automatically a parallel gripper.

## Candidate comparison

| Candidate | Reusable source and physical evidence | Fit and principal limitation | Adoption position |
|---|---|---|---|
| Stock SO-101 | Component STEP, STEP assembly, STL and simulation descriptions. Upstream assembly guide, vendor kits and physical demonstration ecosystem. Apache-2.0. | Five arm joints plus gripper: fails six arm axes. The upstream URDF models a revolute moving jaw, so the stock tool does not implement parallel translation. No native feature-history CAD was identified. | Best inexpensive reference for fixtures, servo packaging and reproducible baseline experiments; cannot be labeled the final six-axis design. |
| SO-101 elbow-roll modification | Released STL assemblies/parts and LeRobot plugin; author links a physical demonstration. Apache-2.0. | Adds sixth arm joint and seventh actuator, but no STEP/native CAD or unit tests found in inspected tree. Geometry, stiffness, thermal loads and integration remain unverified by RAFTEL. | Research candidate only. Do not extend links or issue prints as a validated ARM-01 design. |
| PAROL6 | Six arm axes; public STL, build material and robot descriptions; manufacturer physical demonstration and kits. Current hardware license CERN-OHL-S-2.0; firmware GPL-3.0. | Upstream claims 408 mm reach and 5.5 kg arm mass. Full individual STEP parts are sold separately, without an assembly; seller prohibits sharing without permission. Only two mounting-plate STEP files found in inspected tree. Cost and mass are poor matches for the initial budget/mobile goal. | Strong six-axis reference if budget is increased; retain the original drivetrain instead of shrinking it blindly. |
| Thor | Six arm DoF, native FreeCAD, STEP, STL, gripper source, assembly documentation and upstream physical videos. CC-BY-SA-4.0. | Primary BOM has **seven arm stepper motors plus one MG995 gripper = eight actuators**. Upstream 625 mm stretched height is not horizontal reach. More print volume and assembly work than SO-101. | Selected first baseline for study after Liam allowed eight actuators; size, build effort and performance remain open. |
| Annin AR4 | Existing six-axis platform with official hardware documentation and physical examples. | Current custom license limits commercial use and redistribution. Not suitable for an assumed freely redistributable company derivative. | Study architecture only; do not vendor or derive production CAD without the necessary rights. |

Sources and exact inspected revisions appear below. The stock SO-101, its elbow-roll modification, Thor and PAROL6 are distinct baselines; do not combine their specifications into a fictitious single design.

## Recommendation for Liam's intended approach

Use existing editable CAD as the starting point, while keeping RAFTEL's software, mount interface, perception and evaluation its own. A custom arm designed from scratch is not the recommended first mechanical milestone.

There is no inspected candidate that simultaneously establishes all of: six arm axes, seven total actuators, approximately $500 complete workstation cost, editable CAD, a parallel gripper, and demonstrated 100–200 g continuous-duty operation at 350–450 mm. Preserve those gaps instead of claiming a match.

Liam's current decision is to **allow eight actuators and study Thor first**. Preserve its existing six-axis drivetrain and develop RAFTEL's mount, perception, sorting logic and evaluation around it. The study must re-cost the complete build, extract actual horizontal workspace/moving mass, verify gripper geometry and establish CAD compatibility before design release. Its published cost is an upstream claim, not a current delivered quotation.

SO-101 remains a lower-cost fallback only if its sixth-axis engineering work is acceptable. PAROL6 remains a more expensive comparison. No new custom arm or link extension is recommended for the initial baseline.

The baseline study is authorized; no purchase, fabrication release or powered operation is authorized by this decision.

## Exact CAD starting points

### SO-101 — accessible neutral solids

Pinned upstream: [SO-ARM100 at a758567c3978dfeefe282ede0500085a48fe8f78](https://github.com/TheRobotStudio/SO-ARM100/tree/a758567c3978dfeefe282ede0500085a48fe8f78).

- `STEP/SO101/SO101 Assembly.step` — assembly (about 20.5 MB in inspected tree).
- `STEP/SO101/Upper_arm_SO101.step` and `Under_arm_SO101.step` — link solids.
- `STEP/SO101/Base_SO101.step`, `Base_motor_holder_SO101.step` — base interfaces.
- `STEP/SO101/Wrist_Roll_Pitch_SO101.step` — wrist packaging.
- `STEP/SO101/Follower_Specific/Moving_Jaw_SO101.step` — moving jaw.
- `STEP/SO101/Seeedstudio_Mounting_Plate_SO101.step` — example controller plate.
- `Simulation/SO101/so101_new_calib.urdf` — reference description; not a seven-actuator model.

The upstream URDF was parsed: five arm revolute joints plus a separate `gripper` revolute joint connecting `gripper_link` to `moving_jaw_so101_v1_link` confirms the joint count and pivoted tool. Generic URDF effort limits are not actuator ratings. The controller mounting-plate STEP was streamed and inspected: ISO-10303-21 header, AP214 schema and `ADVANCED_BREP_SHAPE_REPRESENTATION`/solid entities were present. That verifies a solid-format file exists, not its dimensions or successful CAD import. STEP supports direct solid edits but usually does not preserve the original parametric sketches, features or assembly joints. Keep the upstream copy immutable and build adaptations in a separate working design.

### Thor — native parametric source

Pinned upstream: [Thor at 286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159).

- `freecad-src/Assembly.FCStd` and `AssemblyBase.FCStd`, `AssemblyArt1.FCStd` … `AssemblyArt56.FCStd`.
- `freecad-src/Art2BodyA.fcstd`, `Art56GearPlate.fcstd` — representative complex mechanical parts.
- `freecad-src/GripperTop.FCStd`, `GripperActiveArm.FCStd`, `GripperPassiveArm.FCStd` — gripper mechanism source.
- `step/` — corresponding neutral parts; `stl/` — print exports; `mods/` — separately inspect before use.

`Assembly.FCStd` and `BaseTop.fcstd` were streamed and ZIP/XML contents inspected. They identify FreeCAD 0.19; the top assembly references sibling assembly files through external links. Preserve the full directory layout and dependencies. **Opening only the small top assembly file is insufficient.** Neither a current FreeCAD recompute nor assembly-workbench compatibility was tested. Embedded document metadata says “All rights reserved,” while the repository explicitly applies CC-BY-SA-4.0 to all source files; record this discrepancy and resolve source provenance before publishing a derivative source package.

### Six-axis modification — mesh-only source currently found

Pinned upstream: [SO-101 variants at 4431247328acc333ab40fc4b202ffda1646660d0](https://github.com/rabhishek100/so101-6dof-and-extended-versions/tree/4431247328acc333ab40fc4b202ffda1646660d0).

`stl_files/so101_6dof/SO101_dof6_modified_links_mod.stl` and `SO101_dof6_assembled_mod.stl` are reference meshes. Do not treat an STL-to-solid conversion as recovered parametric CAD. The README's bus description says RS485, which conflicts with the proposed STS3215 TTL ecosystem; resolve using exact servo/controller electrical specifications before wiring. The author-provided video is evidence of a claimed physical implementation, not a measured ARM-01 load or reliability test.

## Controlled adaptation procedure

1. **Record provenance:** upstream repository, immutable commit, selected files, checksums, license/NOTICE text, downloaded date and changes. Retain original filenames in a read-only reference package; avoid adding unrelated vendor assets.
2. **Open and reproduce:** import the entire unmodified assembly in the appropriate CAD application. Resolve all external links, units and workbench dependencies. Save screenshots, import diagnostics and a geometry inventory. Do not change geometry while establishing the baseline.
3. **Extract engineering data:** count independently controllable joints and actuators; record joint origins/axes/limits, link lengths, tool transform, gripper jaw motion, fasteners, bearings and tolerances. Compute volumes using explicit material density; weigh representative prints and bought parts later.
4. **Build the virtual baseline:** derive a six-axis robot description from actual CAD, not invented dimensions. Test FK/IK, limits, singularities, swept collisions, reachable bin approaches, and floor reach with a hypothetical chassis. Simulation does not authorize physical motion.
5. **Adapt peripheral interfaces first:** removable metal base adapter, cable retention, electronics placement, overhead camera mount, replaceable fingertips and tool adapter. Leave gear ratios, bearing seats, link lengths and joint stack-ups unchanged initially. Account for every added gram downstream.
6. **Validate before release:** review worst-pose static/dynamic torque, thermal duty, mount loads and power-loss behavior. Validate critical-fit coupons before a full print. Commission only after secure mounting, independent emergency stop and guarded supervised procedures are established.
7. **Change one subsystem at a time:** preserve the original CAD and a tested reference configuration. Log dimensioned changes and test evidence. Re-run load, workspace and regression checks after each mechanical change.

## License handling

Before distributing borrowed or modified assets, preserve notices and review the license applicable to the exact revision and file. Apache-2.0 sources require their license and relevant notices, with changes identified. CC-BY-SA-4.0 adaptations require attribution, change indication and applicable ShareAlike terms when shared. CERN-OHL-S-2.0 has reciprocal Complete Source requirements on relevant distribution of sources/products; firmware carries separate terms. Company software does not inherit an asset's license merely because a robot is mentioned in documentation. Record actual component boundaries and obtain a focused license review before a commercial product release. No upstream design is rebranded as RAFTEL-original work.

## Evidence register

| Primary source | Inspected revision / date | Evidence and remaining uncertainty |
|---|---|---|
| [SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) and [LICENSE](https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/LICENSE) | `a758567c3978dfeefe282ede0500085a48fe8f78`; repository last pushed 2026-10-06 | Tree, STEP sample and source license inspected; no CAD application import or physical tests. |
| [SO-101 variants](https://github.com/rabhishek100/so101-6dof-and-extended-versions) | `4431247328acc333ab40fc4b202ffda1646660d0`; last pushed 2025-12-25 | Tree and README; physical demonstration link exists; geometry, claimed bus and contemporary LeRobot compatibility untested. |
| [Thor](https://github.com/AngelLM/Thor), [BOM](http://thor.angel-lm.com/documentation/bom/), [assembly](http://thor.angel-lm.com/documentation/assembly/), [electronics](http://thor.angel-lm.com/documentation/electronics/) | `286b081fe6f056d87c379b884781ef77ff6a0159`; last pushed 2025-05-09; website retrieved 2026-11-11 | Native file XML, STEP inventory, seven arm motors and separate gripper established. Website HTTPS failed in browser; HTTP content retrieved. Version consistency and current assembly recompute remain open. |
| [Thor ROS](https://github.com/AngelLM/Thor-ROS) | README accessed 2026-11-11; not integration-tested or pinned for use | Documents ROS 2 **Humble** and MoveIt 2; do not claim a tested Jazzy integration. |
| [PAROL6](https://github.com/Source-Robotics/PAROL6-Desktop-robot-arm), [license](https://github.com/Source-Robotics/PAROL6-Desktop-robot-arm/blob/e2169c163244d647739cc34fc5da15c24b042a61/LICENSE), [STEP listing](https://source-robotics.com/products/parol6-step-files) | `e2169c163244d647739cc34fc5da15c24b042a61`; last pushed 2026-11-10 | Hardware license changed 2026-11-04 per README; seller listing explicitly excludes whole-robot assembly and says STEP is not open source and must not be shared without permission. Its older GPL wording conflicts with the newer repository hardware license; purchased STEP terms remain separate. |
| [Annin AR4 license](https://github.com/Annin-Robotics/ar4-hmi/blob/214558c2beb474695d6c083856c354d3f6d4790f/LICENSE.txt) | `214558c2beb474695d6c083856c354d3f6d4790f`; accessed 2026-11-11 | Custom noncommercial terms and restrictions prevent assuming unrestricted company derivative rights. |

Arctos was screened through its [official GitHub organization](https://github.com/Arctos-Robotics). The full CAD storefront could not be retrieved (HTTP 406); no primary CAD license was verified, so it is not ranked as an adoptable design. Do not substitute a third-party summary for its actual commercial CAD terms.

## Acquired Thor baseline — source inspection result

The clean sparse checkout at `work/Thor-reference` beside the RAFTEL checkout is detached at `286b081fe6f056d87c379b884781ef77ff6a0159`. It retains the complete `freecad-src/` directory plus upstream root files, including LICENSE. Native source totals **57 files / 122,885,970 bytes**. All 57 ZIP containers and their `Document.xml` records parsed successfully. The checkout occupied approximately 246 MiB including Git objects when inspected; retain it as the baseline reference.

The complete machine-readable evidence, SHA-256 file inventory and saved assembly placements are in [thor-baseline-inspection.json](../hardware/cad/thor-baseline-inspection.json). A reproducible read-only inspector is [inspect_thor_reference.py](../tools/inspect_thor_reference.py). It does not import or execute CAD code.

**New compatibility issue:** 33 unique external-reference filenames use `.FCStd` while actual component files use `.fcstd`. Every reference has a case-insensitive match; no entirely absent native target was found. A case-insensitive Mac volume conceals this discrepancy, but a Linux case-sensitive checkout can expose broken links. Preserve the original source; test and repair link spelling only in a documented derivative working copy.

No FreeCAD app was found in `/Applications` or `~/Applications`, and neither `FreeCADCmd` nor `freecadcmd` was available on PATH. Consequently import, feature recompute, solid validity, mass properties and kinematics remain untested. Do not install software or report an application-level CAD check implicitly.

### Initial geometry inventory and adaptation surfaces

| Source | Observed source information | First adaptation / unresolved validation |
|---|---|---|
| `Assembly.FCStd` | Six linked subassemblies: Base, Art1, Art2, Art3, Art4, Art56. Saved placements included Art1 Z=79, Art2 Y=-68/Z=202, Art3 Z=443.5 and Art56 Z=556 in native FreeCAD length units. | These are stored component placements in one layout, **not verified joint centers, link lengths or reach**. Recompute and establish coordinate frames before deriving a robot description. |
| `BaseBot.fcstd`, `BaseTop.fcstd`, `AssemblyBase.FCStd` | Native base feature history and attachment coordinate systems are present. | First mechanical adaptation: external removable metal mounting adapter. Measure actual existing mounting surfaces and fastener pattern after CAD import; do not invent a plate pattern from feature lengths. |
| `BaseBoxBody.FCStd`, `BaseBoxCover.FCStd` | Separate native enclosure body and cover. | Controller tray, accessible connector/strain-relief arrangement and independent emergency-stop placement; preserve structural bearing support. |
| `Art56Interface.fcstd`, `GripperTop.FCStd`, `GripperBot.FCStd` | Separate wrist/tool and gripper source, including active/passive arm and finger components. | Determine tool flange, jaw trajectories/parallelism and tool mass; prefer a reversible adapter or replaceable fingertips over changing wrist gears. |

Specific native feature values were read, for example `GripperTop.Pad.Length=15` and `GripperBot.Pad.Length=19.8`. These are feature parameters rather than approved finished-part thicknesses, bearing fits or mounting dimensions. No manufacturing dimension is released from this XML inspection.
