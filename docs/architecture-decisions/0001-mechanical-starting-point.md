# ADR 0001 — Study the existing Thor arm first; gate physical fabrication

- Date: 2026-11-11
- Status: **Thor selected as the first CAD study baseline**; physical fabrication, purchasing and hardware operation remain unapproved
- Scope: ARM-01 BenchSort, six independent arm axes plus one motorized parallel gripper

## Problem

Liam wants a robot based on existing, demonstrated mechanical CAD that RAFTEL can adapt. The proposed $500 target ($350–725 planning range), 350–450 mm reach, 100–200 g payload and six arm axes must be considered together. Liam explicitly decided to allow eight actuators and study Thor first on 2026-11-11. This replaces the original seven-total-actuator target for the initial study; no budget increase or physical build was approved. None of the inspected candidates is verified to satisfy the remaining targets together. A working upstream arm does not validate a changed load path, longer links, different motor, mount, tool, or duty cycle.

## Decision

Adopt a **reuse-first, baseline-then-adapt** engineering process. Do not start a custom arm or describe an extra SO-101 joint as already validated. Keep the robot-independent software progressing while the physical design remains gated.

Use **Thor at revision `286b081fe6f056d87c379b884781ef77ff6a0159` as the first CAD study baseline**, following Liam's explicit selection. It provides existing demonstrated six-axis mechanics with freely published native FreeCAD, STEP and STL files. Its seven arm steppers plus one gripper actuator are accepted for this study. Preserve the original assembly and trace each motor/transmission before adapting it.

**PAROL6 is the backup reference**, conditional on a substantially larger budget, mobile mass acceptance and acceptable editable-CAD rights. SO-101 remains useful background; adding its sixth arm axis is an experimental redesign and is not the selected starting point. The gripper never counts as one of the six spatial arm axes.

The initial adaptations should concern a detachable mount, camera/marker fixtures, cable guards, task tooling and software. Preserve upstream link lengths, motor placement and transmissions until the original assembly is understood. Any added arm axis, motor replacement, link scaling or substantial gripper mass change creates a new mechanical validation milestone.

## Alternatives and evidence

| Option | Advantages | Why not freeze now? |
|---|---|---|
| A — SO-101 plus an extra axis | Low-cost ecosystem, STEP/STL, mature stock assembly and LeRobot support; permissive Apache-2.0 | Stock has five arm axes. The published [elbow-roll modification](https://github.com/rabhishek100/so101-6dof-and-extended-versions/tree/4431247328acc333ab40fc4b202ffda1646660d0) supplies STL/plugins, but no bundled tests/native CAD; bus documentation conflicts need resolution. Added distal mass worsens shoulder/elbow load. |
| B — PAROL6 | Six arm axes; upstream 408 mm reach claim; documented full arm with stepper transmissions and robot models | [Source](https://github.com/Source-Robotics/PAROL6-Desktop-robot-arm/tree/e2169c163244d647739cc34fc5da15c24b042a61) claims 5.5 kg arm. [Partial kit](https://source-robotics.com/products/parol6-partial-kit) observed at €1,188.81 excludes steppers, gearboxes and power supply. [Editable STEP](https://source-robotics.com/products/parol6-step-files) is a separate restricted-sharing product (€27.37 observed), not an unrestricted source assembly. Currency, tax and shipping are not converted or included. |
| B — Thor | Six axes; native FreeCAD plus STEP/STL; working upstream assemblies; affordable upstream cost claim | [BOM](http://thor.angel-lm.com/documentation/bom/) lists seven arm steppers plus gripper, so eight total. [Source](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159) reports 625 mm stretched height, not reach; reported cost/payload are not RAFTEL verified. Requires fresh load, workspace and total BOM studies. |
| B — Annin AR4 | Existing six-axis mechanical/control ecosystem | [Design license](https://github.com/Annin-Robotics/ar4-hmi/blob/214558c2beb474695d6c083856c354d3f6d4790f/LICENSE.txt) restricts commercial use and design-file redistribution; unsuitable as a direct manufacturing foundation absent separate rights. |
| C — Custom six-axis arm from reusable components | Full control of geometry, mounting and eventual manufacturability | Greatest CAD, transmission, bearing, stiffness and controls validation burden; conflicts with preference to preserve a demonstrated mechanism. Reserve for evidence that existing baselines cannot meet revised priorities. |

## Assumptions and open checks

1. Existing development computer and printer/tool access can reduce prototype cost; availability is not confirmed.
2. Supplier payload claims apply to particular configurations and poses. Recompute gravity load including every downstream component and compare with sustainable actuator output before selecting motors; [analysis](../../arm-01/docs/mechanical-analysis.md) uses assumptions, not measured CAD properties.
3. Jaw kinematics must satisfy the **parallel gripper** requirement. Do not assume a pivoting stock jaw or any advertised gripper is equivalent. A replacement tool changes load and calibration.
4. CAD source licenses and distribution/manufacturing rights must be tracked by asset and revision. No company-wide license has been selected; paid STEP sharing restrictions cannot be bypassed by a repository license.
5. A rear-mounted 350–450 mm arm cannot cover an entire 800 × 600 mm desk. Keep source and bins within the eventual collision-free workspace.
6. Mobile floor reach and chassis clearance need joint-constrained kinematics and mass/tipping analysis; desktop reach is insufficient evidence.

## Definition of the mechanical selection gate

- Import the complete pinned Thor source assembly with its linked sibling FreeCAD files; confirm it opens and resolves part references. A downloaded archive or parsed file is not an opened/verified CAD assembly.
- Extract joint axes, link dimensions, and mass/center-of-gravity estimates with material-density assumptions; reproduce the workspace for the source region, all three bins, and future floor-reach cases.
- Produce a fresh Thor-specific priced BOM against the existing $500 target/$350–725 planning range, including the parallel gripper, mount, camera, protection and eight actuator channels. Record any budget conflict instead of assuming an increase.
- Resolve footprint/mass and derivative-source obligations before a fabrication recommendation; eight-actuator allowance and Thor-first study selection are already decided.
- Record exact upstream revision, editable source paths, license and attribution; keep the original baseline separable from RAFTEL modifications.
- Inspect assembly axes, link lengths, joint limits, transmission ratios, part mass estimates, bearing support and cable paths in CAD.
- Produce a complete priced BOM with exact motor/controller/supply suffixes and a compatible lightweight parallel gripper.
- Reproduce FK/workspace and torque studies; identify unreachable bins/floor poses and collision risks.
- Review mount load transfer, power isolation and gravity-fall provisions before fabrication or energizing.

See the [CAD reuse workflow](../../arm-01/docs/cad-reuse.md) for practical import/adaptation steps and [research](../../arm-01/docs/research.md) for maintenance and integration status. A static file import is not mechanical verification.

## Revisit criteria

Revisit when accurate CAD masses or thermal tests invalidate actuator margins, the Thor CAD study fails the workspace or gripper requirements, total cost exceeds the existing planning range, CAD rights obstruct manufacturing, or mobile mass/reach conflicts emerge. Only physical evidence can establish that RAFTEL's final assembly works.
