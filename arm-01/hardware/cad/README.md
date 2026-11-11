# Existing CAD adoption workspace

ARM-01 should begin from an existing physically demonstrated mechanism. The current files are a **source manifest and adoption procedure**, not manufacturing-ready CAD. See [CAD comparison and reuse plan](../../docs/cad-reuse.md) and [references.json](references.json).

No robot CAD binary has been copied into this repository. All references pin immutable upstream revisions. Source-tree inspection and selected file-content checks establish availability, not that the geometry opens correctly or meets ARM-01 requirements.

## Current shortlist

- **Thor:** strongest free native-editable six-axis candidate, using FreeCAD source plus neutral STEP/STL. Its seven arm motors and gripper total eight actuators, so Liam must explicitly relax the proposed seven-actuator target before adoption. Confirm actual workspace, build cost, mass, gripper jaw motion and assembly-version compatibility.
- **SO-101:** strongest inexpensive reuse reference with complete STEP geometry, but stock has only five arm axes. Its existing elbow-roll modification is a separate, unvalidated candidate with meshes and code, not released editable CAD. Do not represent it as a proven complete ARM-01 mechanism.
- **PAROL6:** established six-axis alternative with poor initial budget/mass fit. Purchased full robot STEP files have separate restrictions and contain individual parts, not an assembled robot. Public mounting-plate STEP files do not substitute for full mechanical source.

The baseline is **not frozen**. Do not issue prints, alter link lengths, or buy components from these references without the outstanding engineering decisions in `nextSteps.md`.

## How to adopt Thor in FreeCAD after selection

1. Acquire the exact revision in the manifest into a local reference checkout. Preserve the entire `freecad-src/` directory and the upstream license. `Assembly.FCStd` depends on `AssemblyBase.FCStd` and `AssemblyArt1` … `AssemblyArt56.FCStd`, which in turn depend on component files; downloading only the master assembly will leave missing references.
2. Keep that checkout unchanged. Start RAFTEL adaptations in a separate working folder/feature branch, with a provenance manifest recording source commit and modified parts. Keep binary working files outside Git until a deliberate CAD storage policy is selected.
3. Open the master assembly in FreeCAD. Inspected files originated in FreeCAD 0.19; establish and record the current version and necessary assembly workbench compatibility rather than assuming current FreeCAD can recompute it unchanged. Load all referenced documents; check the report view, missing objects, transforms, document units, and recompute errors.
4. Save an import/recompute report and dimensioned screenshots. Record solid counts, joint origins, axes and allowable travel, bearing fits, shaft dimensions, fasteners, tool center point, motor count and gripper mechanism. The current manifest does **not** supply verified dimensions.
5. Establish the original arm virtually and, later, physically under the safety plan before modifying its load-bearing structure. Initial RAFTEL changes should be the removable mount adapter, electronics tray, camera fixture, cable clips and replaceable tool/finger interfaces. Include their mass in load analysis.
6. Preserve the original drivetrain, link lengths, bearings and joint stack-ups until baseline tests pass. A shorter/longer link or extra motor makes a new mechanism requiring renewed load, stiffness, collision, thermal and calibration evidence.

For SO-101, import the pinned STEP assembly and components into the chosen CAD application instead. STEP provides editable neutral solids, usually without native feature history or recovered joint constraints. Do not treat STL conversion as equivalent to native CAD source.

## Before CAD is released for fabrication

- Reconcile license notices, provenance and any file-specific terms. Thor's embedded document metadata differs from its explicit repository license; record that discrepancy before redistribution.
- Validate six independent arm axes separately from actuator count; verify parallel jaw motion separately from motorized gripping.
- Extract a robot description from actual geometry and check FK/IK, joint limits, singularities, reachable tool orientations and swept collisions.
- Check complete downstream mass and worst-case loads against sustainable actuator capability, then assess mount loads, print material/anisotropy, tolerances, cable clearance, fastener retention and power-loss behavior.
- Obtain physical fit/thermal/load evidence and secure mounting with an independent emergency stop before enabling motion. A downloaded CAD model is not a safety approval.

Future adopted assets should retain exact upstream provenance and license notices. Keep unchanged reference assets separate from RAFTEL derivative files and document each change. Do not rebrand the original robot as a RAFTEL design.
