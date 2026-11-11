# Thor compatible assembly baseline

The geometry-analysis baseline now restores and recalculates in FreeCAD 1.1.4. It uses pinned upstream Thor CAD, normal addon registration and **one explicitly static Art1Body compatibility snapshot**. The untouched original parametric files remain available separately. This is an operational CAD baseline for analysis, not a hardware validation or a claim that the original Art1 feature history has been repaired.

## Reproducible environment

| Component | Exact baseline |
|---|---|
| Thor source | `286b081fe6f056d87c379b884781ef77ff6a0159` |
| FreeCAD | `1.1.4R20260928`, ARM64; [runtime provenance](thor-native-validation.md) |
| Fasteners | `fddd07af422b7d3a69098b32333711c5eeae184c` |
| Gears | `ffe86c85e8061546a3fbaa598993d8e1be2b0de2`, saved-schema-compatible version0.0.3 |
| Art1 replacement | Exact original cached final solid and all24 named datum frames, produced by [snapshot recipe](thor-feature-compatibility.md) |

Current Gears is retained only as a diagnostic comparison because its migration fails on the old saved schema. Addons are registered with FreeCAD's standard `-M` option; global trust settings are unchanged. See [dependency evidence](thor-dependency-compatibility.md).

## Whole-assembly native result

The dedicated compatibility copy restored all **53 referenced documents**. A separate `changed` recompute audit completed, recalculating **2,129 features** and reporting **all3,001 objects Up-to-date**, with no Invalid/Touched states or caught audit errors. The native log contained no dependency, migration or feature errors; missing optional icon resources are cosmetic diagnostics.

[Compact validation report](../hardware/cad/thor-compatible-assembly-validation.json) records the mode, source and addon pins, counts and raw-report hash. This result is changed-feature recalculation, **not a forced rebuild of every original procedural feature or topology validation of all history objects**. Separate [feature tests](thor-feature-compatibility.md) validate the static Art1 snapshot after save/reopen/forced recompute. Its saved Body BRep and all datum placements match the candidate used in the whole assembly; ZIP metadata can produce different file hashes for independently saved equivalent documents.

The installed geometry inventory subsequently examines physical source shapes and mounted instances. A successful CAD restore/recompute alone does not establish correct part counting, material mass, kinematic limits, collision clearance or load capacity.

## Reproduce the working copy

1. Acquire the exact Thor revision with complete `freecad-src` siblings and retain its license. Keep that source checkout unchanged; copy the source directory into a separate working area.
2. Run `tools/prepare_thor_compatibility.py` in the isolated native console against the pinned original Art1 file, creating a **new** native snapshot and report. Adopt it only when `validated_static_snapshot` is true. Replace only the Art1 file in the dedicated working copy.
3. Obtain the two pinned addon sources. Do not register the current and historical Gears roots together.
4. Inspect/resolve case-sensitive sibling links without rewriting CAD:

```sh
python tools/resolve_thor_case_aliases.py /path/to/working-copy/freecad-src \
  --inventory hardware/cad/thor-baseline-inspection.json --apply
```

On this Mac all33 spelling variants already resolve through the filesystem, so no symlinks were created. On a case-sensitive filesystem the helper creates relative sibling aliases and refuses conflicting files; CI exercises that behavior. This does not claim a native Linux FreeCAD run.

5. From `arm-01`, run the bounded native audit with a fresh output path:

```sh
python tools/run_freecad_audit.py \
  --freecad /path/to/freecadcmd \
  --source /path/to/working-copy/freecad-src/Assembly.FCStd \
  --report /path/to/work/new-assembly-audit.json \
  --module-path /path/to/FreeCAD_FastenersWB \
  --module-path /path/to/freecad.gears-legacy003 \
  --recompute changed --shape-scope none --timeout 480
```

The runner uses separate user/system configuration files and retains stdout, stderr, native logs and timeout metadata in a sibling `.run` directory. Audit checkpoints are written atomically before opening and at stage boundaries; object checkpoints are throttled to avoid repeatedly writing multi-megabyte history inventories. A timeout leaves a partial report. Process exit0 is insufficient: require report status complete, inspect object states and native errors, and retain the declared mode.

For shape extraction use scoped `--object Document::Object` selectors with `--shape-scope all`, or terminal scope. Metadata is distinct from material or mass assumptions. The audited file count53 is the referenced assembly set, not all57 native source files in the repository.

## Remaining limitations

- The original Art1 procedural model still fails current-kernel Thickness and external-sketch constraints; use the preserved original for that separate migration task. The compatibility solid is editable as static geometry, without its original feature history.
- Native cached geometry, recalculated geometry and measured physical geometry are different evidence classes. Report which supplies each calculation.
- Axis signs, motor calibration, coupled limits, gripper behavior, hardware feedback and physical loads remain unverified. No physical motion backend was added.
