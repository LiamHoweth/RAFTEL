# Durable implementation notes

- Start with AGENTS.md and nextSteps.md. The latter owns current status and next actions.
- ARM-01's installed CLI is `raftel-sort`; defaults are packaged in `src/raftel_arm01/defaults.json`. Runtime uses Python standard library only. No hardware backend or real-motion flag exists.
- The sorter checks abstract points against an envelope; it has no IK, collision checker, camera, or physics. Mock and analytical results cannot validate physical performance.
- Liam selected Thor as the first existing CAD study baseline and explicitly allowed eight actuators (seven arm motors plus one gripper). Six independent arm axes and parallel-gripper requirement remain. Study permission does not approve fabrication/purchases.
- CAD provenance is pinned in `arm-01/hardware/cad/references.json`. Keep upstream originals separate from modifications. Thor assembly references sibling native documents; a top-level file alone is insufficient.
- `tools/engineering_analysis.py` is an assumed lightweight-servo sensitivity model, not a CAD-derived Thor model. Replace assumptions only with traceable geometry/mass evidence; retain the distinction in reports.
- `kinematics/thor_drive.py` implements nominal continuous Thor-ROS joint/channel algebra only; no joint geometry, physical rotor angles, calibrated limits, serial output or hardware calls.
