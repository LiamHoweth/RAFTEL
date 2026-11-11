# Bounded negative-common followup

This prepares one diagnostic for the [partial three-pose wrist run](thor-wrist-pose-desktop.md). That run stopped because the positive-Y pinion's Boolean `common` returned negative signed volume at q5=−20°, q6=−15°, intended `s=+1`. The negative magnitude and intermediate topology were not captured. They remain unknown in the preserved original evidence.

`tools/probe_thor_wrist_failure_pair.py` reads the same pinned saved BReps and applies exactly that declared copied-shape pose. The plate folds −20° about common native +Y, then rolls −15° about the carried +Z line through `(0,0,556)` mm. The positive-Y pinion rotates +10° about common +Y. It computes **one** `common`, without changing operand order, reversing/healing geometry, recomputing source history or saving CAD. The worker launches no process by itself.

Before the Boolean, both saved and rigidly posed inputs record signed volume, orientation, shape/solid/shell/face counts and native validity. Source and posed input volumes must remain positive and validity checks must pass. After `common`, the raw signed volume, aggregate orientation and each solid's signed volume/orientation are checkpointed **before** the separate potentially expensive validity call. Native validity is then recorded as a boolean, including `false`. A negative result remains negative; no absolute-value or material interpretation is applied.

The execution can complete its diagnostic measurements while the result remains unsuitable as a geometric material intersection. `diagnostic_outcome` explicitly states whether the negative signed volume reproduced. `geometric_intersection_accepted`, exact conjugate-mesh qualification, physical calibration and fabrication release remain false in both cases. A nonnegative followup does not overwrite or invalidate the earlier failed run.

Only a separately approved native slot may execute this probe. Use a fresh isolated root, pinned portable FreeCAD 1.1.4/addons and **180-second maximum outer process timeout**. Snapshot this worker, `probe_thor_wrist_pose_desktop.py` and `audit_freecad_assembly.py` together. The worker reuses the existing source-hash/disk/output/isolation guards and atomic ownership-preserving report writer. All 57 source inputs are hashed before and after; no open document or source save is permitted to escape cleanup.

```text
RAFTEL_RUN_WRIST_FAILURE_PAIR=1
RAFTEL_WRIST_FAILURE_SOURCE=/path/to/compatible/copied/freecad-src/Assembly.FCStd
RAFTEL_WRIST_FAILURE_REPORT=/path/to/fresh-run/new-report.json
RAFTEL_WRIST_FAILURE_ISOLATION_ROOT=/path/to/fresh-run
```

Use explicit task-local FreeCAD user/system preferences, data/home/temp paths, pinned addon roots, empty stdin and a hidden process. Preserve launcher, module-origin, executable, script and source-byte receipts. A timeout or failed validity call leaves the signed-value checkpoint available and must not become a completed capture.

Pure tests use small synthetic shape objects and do not exercise FreeCAD:

```powershell
python -m pytest tests/test_thor_wrist_failure_pair.py
```

## Executed result

The separately approved run completed in **43.32 seconds**, with one Boolean operation, no worker errors and zero open documents before and after. The [receipt](../hardware/cad/thor-wrist-failure-pair.json) binds the [unaltered raw capture](../hardware/cad/thor-wrist-failure-pair-capture-v1.json) and [unaltered launcher metadata](../hardware/cad/thor-wrist-failure-pair-runner-v1.json). Original operands and the exact declared pose were retained. All 57 original source files, all 57 compatible-copy inputs, script snapshots, pinned addons and launcher bytes remained unchanged.

Both saved and posed inputs are `Forward` solids with native `isValid=True` and positive volumes. Plate volume is approximately 42883.5006808 mm³; positive-Y pinion volume is 7716.7800706 mm³. Source restore states are `Up-to-date`, recorded separately from the cached-BRep geometry mode.

The negative result **reproduced**:

| Native observation | Value |
| --- | --- |
| Aggregate signed `common.Volume` | −0.5552516265803887 mm³ |
| `ShapeType` / `Orientation` | `Compound` / `Forward` |
| Native `isValid` | `True` |
| Solids / shells / faces | 3 / 3 / 11 |
| Reported solid 1 volume/orientation | +0.10539411058939224 mm³ / `Forward` |
| Reported solid 2 volume/orientation | +0.0007651983078344402 mm³ / `Forward` |
| Reported solid 3 volume/orientation | +0.00014976424489836237 mm³ / `Forward` |

Pure arithmetic gives a sum of reported solid volumes of **+0.10630907314212505 mm³**, while aggregate minus that sum is **−0.6615606997225137 mm³**. These are a recorded discrepancy and a derived comparison. The sum is not substituted for aggregate volume and neither value is accepted as a material penetration estimate. Native validity and the captured `Forward` flags do not resolve the discrepancy or qualify the gear mesh.

Per-solid face/shell counts, actual `isSame` constituent membership and standalone-face/shell disposition were **not captured**. The temporary common BRep was **not exported**; the retained run contains JSON/log/config/script evidence but no resulting common BRep to inspect afterward. Total 11 faces/3 shells and three positive solid volumes alone cannot establish whether extra lower-dimensional geometry exists. Its presence remains unknown.

## Pinned primary-source audit and remaining explanation gate

The [source audit](../hardware/cad/thor-wrist-failure-pair-source-audit-v1.json) records immutable source revisions/blob identities and observed packaged-DLL metadata. At the reported FreeCAD build commit, [`TopoShapePy::getVolume`](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapePyImp.cpp#L2848) calls the two-argument `BRepGProp::VolumeProperties` and returns the resulting mass property.

Packaged `TKBRep.dll` and `TKTopAlgo.dll` expose Windows version metadata **7.8.1**; their bytes are hashed in the audit. OCCT tag `V7_8_1` resolves to commit `bd2a789f15235755ce4d1a3b07379a2e062fdc2e`. Its [header](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.hxx#L177) gives `OnlyClosed=false` by default and warns that suitable coherent, boundary-free volume geometry is a caller condition. Its [implementation](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.cxx#L309) filters closed shells only when that option is enabled; the default route integrates faces in the whole shape.

This verifies a source-supported **possible** mechanism for aggregate properties being affected by open or mixed-dimensional constituents. It does not establish that this common contains such constituents, identify the failing face contributions or prove the cause of the observed negative aggregate. Exact DLL-to-source build correspondence and the loaded OCCT DLL path were not independently demonstrated; this is version-matched pinned-source inspection with that explicit boundary. No additional native process was launched for this source audit.

The smallest next native investigation requires a new separately approved slot: retain the exact resulting common BRep, capture per-solid face/shell counts and `isSame` membership, and identify any constituents outside those solids before interpreting volume. Preserve the original signed aggregate and all raw constituents. Do not apply `abs`, replace the aggregate with the solid sum or heal/reverse geometry to obtain an accepted result. Earlier positive aggregate values also remain native mass-property observations until their applicable constituent/closure requirements are checked. Exact mesh/contact and fabrication gates remain closed.

The completion checker binds full source/code/runtime/frame identities and ordered operands; it accepts complete diagnostic observations of a negative or invalid common while keeping material acceptance false. Conflicting generic/other-worker opt-in flags are rejected before helper imports. The approved run used frozen snapshots; its raw evidence is unchanged. No further native experiment is authorized or implied by this handoff.
