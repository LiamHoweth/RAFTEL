# Thor initial native CAD validation — historical partial result

Follow-up: the [compatible assembly baseline](thor-assembly-compatibility.md) now restores and recalculates using pinned addons and a static Art1 snapshot. The initial failed attempt below is preserved as historical evidence.

Checked 2026-11-11 against Thor `286b081fe6f056d87c379b884781ef77ff6a0159`, in an isolated working copy. **The complete assembly is not validated. No CAD changes were saved, and no physical operation occurred.**

## Runtime and provenance

The [official FreeCAD 1.1.4 ARM64 DMG](https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/FreeCAD_1.1.4-macOS-arm64-py311.dmg) was downloaded and its SHA-256 matched the published value:

`071343b4abb70492b75c973f41eaf1d2528f9b9c7ea018d22a4f46ae14d27ac0`

The bundle passed `codesign --verify --deep --strict`. Its local standalone console reports `1.1.4R20260928`. It runs under the workspace's `work/tools/FreeCAD.app`, without a system-wide installation, global settings changes, or additional workbenches installed. Separate user/system configuration files were used. Direct startup from the mounted image stalled; the copied local runtime works. The runtime is an active project tool, excluded from the repository.

## Results

| Check | Result | Evidence limit |
|---|---|---|
| 57 native source containers, SHA-256s, dependencies | Reproduced the committed inventory; 33 filename-case mismatches | Container/XML inspection only |
| Complete `Assembly.FCStd` import/recompute attempt | Timed out after 180 seconds; process terminated without saving | Complete import/recompute and assembly usability are **not** established |
| Whole-assembly diagnostic log | `module not permitted: FastenersCmd`; failed thickness features, including `BRep_API: command not done` | Determine exact addon/proxy trust and CAD/kernel compatibility; do not assume all failures have one cause |
| Original `BaseTop.fcstd` native import and forced recompute | Completed; 17 document objects; body Up-to-date, one valid solid | One part only; not a mount strength, print-fit, joint, or whole-arm validation |
| BaseTop body bounding box | Approximately 150 × 150 × 27.5 mm | Axis-aligned geometry of this original part; **not** verified mounting-hole dimensions or robot reach |
| BaseTop body volume | Approximately 222,336.23 mm³ | CAD solid volume; printed mass depends on material, infill, walls and actual fabrication |
| Source preservation | Original checkout clean; BaseTop working-copy bytes unchanged | No native source save/export performed |

Reports: [native summary](../hardware/cad/thor-native-audit-summary.json), [BaseTop object report](../hardware/cad/thor-base-top-native-audit.json), and [historical container inventory](../hardware/cad/thor-baseline-inspection.json). The historical inventory predates the native check; its earlier “no FreeCAD available” limitation is not the final runtime state.

## Reproduce a part audit

Use a separate source working copy and a **new** report path. The optional script requires FreeCAD's console, not the standard Python environment. From `arm-01`, substitute actual local paths:

```sh
export RAFTEL_RUN_FREECAD_AUDIT=1
export RAFTEL_FREECAD_ASSEMBLY=/path/to/working-copy/freecad-src/BaseTop.fcstd
export RAFTEL_FREECAD_REPORT=/path/to/work/new-part-report.json
/path/to/freecadcmd -u /path/to/work/task-user.cfg -s /path/to/work/task-system.cfg tools/audit_freecad_assembly.py
```

FreeCAD executes startup files under its own module name, so the explicit opt-in environment flag invokes the script's main routine. Reports refuse existing output paths and non-JSON destinations. The script closes only documents it opened, never calls save, and preserves existing evidence. A process exit code alone is insufficient: inspect the generated report, object states and console diagnostics. Apply a bounded process timeout to complete-assembly experiments; this script does not claim to control runaway native features.

## Next compatibility gate

1. Inventory the assembly's exact Python proxies/workbench dependencies, verify their upstream code and supported versions, and reproduce the intended document-loading permissions in an isolated configuration. Do not disable global document protections or install arbitrary modules.
2. Identify the exact documents/features producing thickness failures; compare their cached geometry, original FreeCAD 0.19 provenance and supported runtime/kernel behavior. Preserve an unchanged baseline before a compatibility-only working copy is made.
3. Re-run the complete assembly with incremental per-document diagnostics and a realistic bounded timeout. Distinguish successful restore, successful forced recompute and geometric validity.
4. Only after the model gate closes, extract joint axes, transforms, masses and mounting interfaces. BaseTop bounds are not a released adapter drawing, and the original geometry should not be scaled to meet a target.
