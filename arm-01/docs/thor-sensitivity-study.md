# Bounded conditional load sensitivity

The [separate sensitivity report](../hardware/cad/thor-sensitivity-study-v1.json) evaluates **1,620 explicit analytical cases** from the [hash-bound scenario](../config/thor-scenario-v1.json). It retains the original frozen reports and the [twelve-case saved-versus-ideal jaw study](thor-scenario-analysis.md). This is a deterministic Cartesian grid with complete enumeration of the requested cases, not a search of calibrated travel, a certified worst case, an uncertainty distribution or a capacity margin.

The documented reference grid holds the source-supported ideal wrist phase `s=+1` and the same geometry/membership assumptions, while varying:

| Input | Declared study values | Evidence boundary |
| --- | --- | --- |
| Printed material reference | PLA 1240, PETG 1270, ABS 1040 kg/m³ | Exact prior reference-product density scenarios; not actual filament identification or qualification |
| Effective whole-part fraction | 0.35, 0.50, 1.00 | Earlier load-study sensitivity values; not slicer infill or measured per-part fractions |
| Arm pose | Upright, shoulder-horizontal, shoulder-horizontal with fold 45°/roll 30°, mixed pose | Bound scenario poses, without verified stops, interference or collision feasibility |
| Jaw configuration | Independent saved pose; ideal q=0 and q=60° | Explicit mathematical body overlay, not repaired native loops or usable physical stroke |
| Payload mass | 0, 0.1, 0.2 kg | Prior sensitivity scenarios, without payload or retention qualification |
| Payload COM offset | Zero; +25/+50 mm along nominal zero-frame X or Y | Explicit lateral directions in the roll-tool attachment, not measured object COM |

The payload point stays fixed relative to the roll tool, independent of jaw angle. No contact, object movement, gripping force or servo torque is inferred. The base study point and every value/source are serialized in the report's complete `request` object. Custom requests must provide explicit units, values and evidence rather than receiving implicit physical ranges. The implementation caps a run at **4,096 cases** and rejects duplicate values, missing evidence, nonfinite inputs, unknown fields and inconsistent saved/ideal jaw coordinates before analysis.

## Reproduction

Run from `arm-01` after installing the package:

```powershell
python tools/thor_sensitivity_study.py config/thor-scenario-v1.json --documented-reference-study --output /path/to/new-sensitivity.json
python tools/thor_sensitivity_study.py config/thor-scenario-v1.json --request /path/to/explicit-request.json --output /path/to/new-custom-sensitivity.json
```

Choose a fresh output path; existing files are refused. The CLI requires either the explicit documented-reference flag or a request file. To repeat a retained report exactly, save its `request` object as the request JSON and use the same bound manifest/input files. No native CAD, network, hardware or optional integration is accessed.

The tool reuses the existing mass overlay, wrist articulation and gravity calculations. It computes each material/fraction/body pose once, then applies the linear payload contribution for each mass/offset. Tests independently rebuild reported witnesses using full snapshots with changed payload points, validating the offset-carry optimization against the original calculation path. Each material/fraction scenario retains 517 mass records and all seven whole motors totaling 2.120 kg; jaw motion does not add, remove or reweight records.

## What the selected grid shows

Within these requested cases, sampled absolute conditional holding maxima are approximately **7.928 N·m shoulder**, **3.009 N·m elbow**, **0.489 N·m wrist fold** and **0.101 N·m wrist roll**. The report names the full material/fraction/arm/jaw/payload/overhang witness for every coordinate. The ideal jaw coordinate's sampled maximum is about **0.01405 N·m**, conjugate to mathematical closing q; it is not an MG995 shaft torque or a gripping-force requirement. Original full physical wrist holding values remain unknown.

The report also ranks missing measurements by the largest sampled signed holding spread when changing **one declared parameter while holding all other parameters fixed**. In this particular grid:

| Varied input | Largest sampled holding spread | Corresponding missing evidence |
| --- | ---: | --- |
| Effective whole-part fraction | 2.638 N·m | Actual per-part sliced/model mass and weighed mass |
| Payload mass | 0.982 N·m | Actual object mass |
| Material reference density | 0.735 N·m | Actual filament product/density and printed masses |
| Payload COM direction/offset | 0.134 N·m | Actual grasped-object COM/overhang |
| Saved/ideal jaw configuration | 0.0122 N·m | Realizable pivot/phase alignment, closure coordinate and ownership |

This ranking is a model-sensitivity summary, **not physical risk priority, statistical confidence, measurement tolerances or an uncertainty bound**. Its order changes with the declared sample choices. A small modeled gravity effect does not reduce the need to resolve gear interference, jaw loop closure, stops, contact, structural strength or actual calibration. Native source editability and physical safety gates remain independent of these numerical rankings.

The study omits accelerations, friction, efficiency, cable forces, impacts, rotor/internal inertia, actual belt redistribution and moving actuator thermal/torque-speed capacity. It establishes neither structural nor motor margins and releases no payload, fabrication or operation. Follow the [scenario evidence gates](thor-scenario-analysis.md) before attempting a more complete demand model.
