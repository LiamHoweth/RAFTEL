# Desktop wrist pose diagnostic

`tools/probe_thor_wrist_pose_desktop.py` prepares a bounded native geometry experiment for W1. It reads the three pinned saved wrist gear solids from a compatible copied master, transforms shape copies through three declared wrist poses and computes native Boolean intersections/minimum distances. It performs no CAD feature-history recompute, assembly constraint solve, source save or hardware operation.

This is separate from the [historical quarter-degree handedness probe](thor-wrist-handedness.md). That probe found saved interference and supported intended ideal sign `s=+1`. This experiment tests larger bidirectional declared rotations and checks that a common fold preserves pair overlap. The results can expose a frame/articulation error or continued tooth interference. They cannot establish exact conjugate meshing, physical contact, backlash, retention or manufacturing acceptance.

## Bounded plan

| Pose | Declared fold q5 | Declared tool roll q6 | Geometry/configuration |
| --- | --- | --- | --- |
| `saved_zero` | 0° | 0° | Original saved BReps, with their recorded installed placements. |
| `positive_fold_roll` | +20° | +15° | Shape copies with intended `s=+1`; reversed `s=-1` is a diagnostic comparator. |
| `negative_fold_roll` | −20° | −15° | Shape copies with intended `s=+1`; reversed `s=-1` is a diagnostic comparator. |

The plate first folds about native +Y through `(0,0,556)` mm, then rolls about the carried +Z line. The side pinions rotate about that common +Y fold line with `alpha_negative_y=q5+s*2*q6` and `alpha_positive_y=q5-s*2*q6`. The point `(0,0,556)` lies on both nominal zero-pose axis lines; using it for the carried roll line is equivalent to carrying another point along that same line. The native gear pitch apices remain noncoincident and are not silently repaired.

For each rolled intended-sign pose, an unfolded same-roll comparison independently checks rigid-fold overlap invariance. The full plan has 10 gear-pair rows, four fold-invariance rows, 14 Boolean `common` operations and 10 minimum-distance operations. A nominal 1e-4 mm³ plus 1e-6-relative volume discrepancy target diagnoses numerical/frame consistency; it is not a manufacturing tolerance. A failed invariance check remains a reported result, rather than being hidden by an execution-completion flag.

The cooperative native-operation budget is at most 600 seconds. An isolated launcher must also impose a 600-second process timeout, because Python cannot interrupt a blocked OpenCascade operation. Each completed Boolean pair is checkpointed before the minimum-distance call, so a timeout can preserve useful overlap evidence even if distance computation stalls. No new operation starts after the cooperative deadline. If this bounded investigation stalls, retain its partial report and return to the ready software/evidence lanes.

## Execution contract

Only the integration owner schedules the native process. Do not launch concurrently with another whole-assembly/native worker. The default Python script exits without launching any process. Native execution requires `RAFTEL_RUN_WRIST_POSE_DESKTOP=1` and these explicit environment paths:

```text
RAFTEL_WRIST_POSE_SOURCE=/path/to/compatible/copied/freecad-src/Assembly.FCStd
RAFTEL_WRIST_POSE_REPORT=/path/to/fresh-isolated-run/new-report.json
RAFTEL_WRIST_POSE_ISOLATION_ROOT=/path/to/fresh-isolated-run
```

Use the pinned portable FreeCAD 1.1.4 executable and pinned Fasteners/Gears 0.0.3 addon roots from the native foundation. Snapshot this worker and `audit_freecad_assembly.py` together in the new run directory; the worker reuses its isolated-path check and ownership-preserving atomic `ReportWriter`. Pass fresh `-u`, `-s` and `--log-file` paths, task-local home/data/temp directories, `PYTHONNOUSERSITE=1`, empty stdin and a hidden native process. Verify the launch executable/addon/script pins and preserve stdout/stderr/timeout metadata independently of the worker report.

Before opening CAD, the worker verifies the immutable master/wrist/gear hashes, refuses existing output paths, requires all native configuration/data paths inside the run root and at least 50 GiB free. The master may reference the separately validated static Art1 compatibility snapshot; this diagnostic does not use Art1 history. It hashes every native sibling before and after and checks that selected source-object placements remain unchanged. It closes only documents opened by its isolated process. No source document is saved.

The source-shape mode is explicitly **saved cached BRep inspection**. Source `Up-to-date` states are recorded as restore metadata and do not establish a feature rebuild. The new native evidence consists of validity checks and actual native Boolean/distance operations on transformed copies. The nonzero poses are declared ideal rigid transformations; they are not a solved or saved native articulated assembly. Existing source/jaw loop defects and gear-profile mismatch remain unresolved.

## Completion and interpretation

The native report remains `in_progress` until all observations and source checks complete; errors or a timeout leave partial evidence. `report_is_complete` requires exact selected object/pair/pose coverage, finite native metrics, all source hashes unchanged, isolated runtime metadata and all no-release qualification fields. A zero process exit alone is insufficient. The report preserves any measured penetration volume and explicitly warns that zero minimum distance can also describe intersecting solids.

All results keep feature-history recompute, constraint solve, exact conjugate-mesh qualification, jaw-loop evaluation, physical calibration, contact-force/retention and fabrication release false. Jaw multi-pose closure is handled separately by the [offline repair specification](thor-jaw-body-reconciliation.md); this wrist gear experiment cannot close that gate.

Pure guard/contract tests run without FreeCAD:

```powershell
python -m pytest tests/test_thor_wrist_pose_desktop.py
ruff check tools/probe_thor_wrist_pose_desktop.py tests/test_thor_wrist_pose_desktop.py
```

## Executed desktop result: partial, failed closed

The scheduled native run finished in **266.66 seconds**, within its 600-second process budget. The process returned zero, but the worker explicitly recorded **`audit_status=failed`** after a native `common` result reported negative signed volume. The [partial evidence receipt](../hardware/cad/thor-wrist-pose-desktop.json) binds the [unaltered raw capture](../hardware/cad/thor-wrist-pose-desktop-capture-v1.json) and [unaltered launcher metadata](../hardware/cad/thor-wrist-pose-desktop-runner-v1.json). The raw failure is preserved; no missing row was completed analytically and no negative value was clamped or replaced by its absolute value.

Three selected source gear solids passed native validity checks. Seven of the ten pair rows and three of four rigid-fold comparisons completed. Eleven of the planned fourteen Boolean operations executed, including the common that failed its signed-volume guard. Every one of the 57 original source files, all 57 compatible-copy CAD inputs, worker snapshots and pinned addon files remained byte-identical. Actual runtime configuration paths and imported module origins are retained. The full portable runtime bundle was not independently rehashed per file during this launch; the executable hash and addon files were verified.

| Configuration | Side | Observed intersection mm³ |
| --- | --- | ---: |
| Saved zero | Negative Y | 0.1803033385 |
| Saved zero | Positive Y | 0.3073740820 |
| +20° fold, +15° roll, intended `s=+1` | Negative Y | 0.0757247857 |
| +20° fold, +15° roll, intended `s=+1` | Positive Y | 0.5753691219 |
| Same positive pose, reversed `s=-1` | Negative Y | 209.4784633659 |
| Same positive pose, reversed `s=-1` | Positive Y | 189.8804227938 |
| −20° fold, −15° roll, intended `s=+1` | Negative Y | 0.1421719489 |

The saved volumes reproduce the historical baseline. The positive-pose comparison is consistent with the earlier intended-sign evidence while still showing source penetration. The three observed rigid-fold volume discrepancies are at most **7.69e-9 mm³**, which supports the declared carried-axis composition for those checked pairs. None of these results repairs the saved teeth or verifies physical gear contact. The full bidirectional larger-pose diagnostic remains incomplete.

The failure occurred at the next pair in the fixed operation order: **q5=−20°, q6=−15°, `s=+1`, positive-Y pinion**, whose declared common-Y angle is +10°. The raw guard recorded only that the signed intersection volume was negative; its magnitude, intermediate result topology, solid orientations and validity were **not captured** before that guard stopped the run. Those values remain null/unknown in the receipt. The positive-side fold countercheck and both reversed-sign rows at the negative pose were not completed. The final in-memory selected-object placement comparison was also not reached: its raw default `false` means unverified, not an observed document mutation. The receipt records that check as unexecuted/unknown. File-byte preservation was independently observed for all original and compatible-copy CAD inputs.

Possible explanations include a Boolean orientation result, a numerical/tangency degeneracy or a source tooth/profile contact limitation at that configuration. Source-shape validity and unchanged input bytes do not identify which explanation applies. The three successful common-fold checks constrain a general transform error, but they do not validate the unobserved positive-side result. No hypothesis is accepted from the available capture.

The smallest next native investigation, after a separately scheduled slot, is the failing selected pair alone. Preserve signed `Volume`, solid count/orientations, shape validity and bounds **before** interpreting it; compare operand order and an unfolded same-roll pair in fresh evidence. Do not normalize a negative sign away or infer a material penetration magnitude without that evidence. No further native run was launched for this checkpoint.

After retaining the run's immutable script snapshots, the repository completion checker was hardened to reject malformed records, stale worker/helper pins, wrong schema/source/frame/runtime, incorrect pose coverage and numeric type coercions. Defaults bind current script bytes; historical captures need their independently retained launch pins. Future captures also record open-document counts before/after closing and checkpoint a negative signed volume before stopping. These changes do not backfill the original raw report. Exact launched scripts, addon/module checks, runtime logs and isolated preferences remain in `.work/native-wrist-pose-01` under the receipt's hashes.
