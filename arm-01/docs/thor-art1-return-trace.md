# Copied Art1 parameter-return trace

`tools/probe_thor_art1_return_trace.py` extends the existing partial A6 radius
experiment with per-feature metrics and attachment/frame witnesses. It uses a
fresh exact-byte copy of `Art1Body-UNACCEPTED-through-all-v1.FCStd`, SHA-256
`6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd`.
The candidate remains unaccepted. Historical reports, including the observed
**0.0177205 mm³** failed nominal return, are preserved unchanged.

## Experiment and interpretation

The five ordered phases are restored cached nominal, requested-force nominal, radius
1.69 mm, radius 1.71 mm and returned nominal 1.7 mm. Only `Spreadsheet.B2`, whose
actual alias must remain `M3BoltBodyRadius`, changes in memory. Every forced
operation records a Boolean conversion of its native return value, rather than
interpreting process completion as a valid recompute. The worker never saves a
document or remaps a support.
The `restored_cached` phase is a post-open runtime observation. Restoring the
document can invoke native attachment behavior; it is not an untouched XML/BRep
or no-engine baseline.

Each phase retains all 90 restored object identities, own states, available own
and global placement matrices, expressions, actual schema-aware support targets,
attachment mode/offset, available sketch circle frames and native shape metrics.
The original 80-member Body order provides the feature sequence. Raw native
volume stays separate from volume derived from Solid subshapes; unbounded datum
geometry and missing volumetric centroids remain explicitly marked. These are
metric/frame witnesses, not surface-equivalence tests.

The existing five radius-dependent sketch constraint collections are recorded
both before and after each operation. Structural preservation excludes numeric
constraint values deliberately; the raw values remain available for separate
return comparisons. An unchanged datum during this particular radius perturbation
does not demonstrate that its attachment engine responds correctly to a moved
provider. The separate attachment-engine experiment owns that diagnostic.

The host analysis in `tools/thor_art1_return_analysis.py` evaluates the trace.
Keep cached-to-forced drift separate from forced-nominal-to-return drift and from
the historical pre-save comparison. The original migration thresholds remain
unchanged. A completed diagnostic can report a failed nominal return and never
sets migration acceptance or manufacturing release.

## Isolation and preservation

`--prepare` creates a new packet and does **not** launch FreeCAD. Root alone
reviews and executes `launch.json` through the serialized native queue. The
timeout is 300 seconds; the reserve is 50 GiB plus 512 MiB scratch. Remove all
inherited `RAFTEL_*`, `PYTHONPATH` and `PYTHONHOME` variables before applying the
packet's child-process environment.

The native worker requires an exact request hash, bounded strict UTF-8 JSON,
fixed copied-input/helper inventory, retained worker execution and unchanged
original/candidate/history bytes. It rejects symlink/reparse paths and competing
native opt-ins before helper imports. FreeCADCmd's actual embedded `FreeCAD`
module has no `__file__`; its runtime provenance uses the running Windows process
image obtained through `GetModuleFileNameW`, the pinned executable bytes and
observed FreeCAD version/configuration. Python's own executable string is retained
separately. The actual file-backed `Part.pyd` origin/hash is checked. No addon roots are
requested; this does not authenticate the entire runtime dependency bundle.

The actual user/system parameter, home, data and temp paths must match all five
dedicated paths exactly before opening the copy. Preexisting documents are
rejected. Cleanup closes only documents created in this dedicated process,
retains cleanup errors, then repeats snapshot and protected-input hash checks.
The preserved packet/report/logs remain local under `.work/swarm/a02_return/`.
Root separately verifies whole-input and addon preservation around native runs.

## Validation status

Twenty-five host guard tests pass with Ruff lint/format checks. These cover request
encoding/bounds/duplicates/nonfinite values, exact pins, overwrite prevention,
reserve enforcement, protected/snapshot/runtime tampering and conflicting
pre-import flags, embedded-module provenance and prior-attempt preservation.
These tests do not establish native execution.

Root executed run-001 in **2.5917 seconds**. It stopped before opening CAD or
capturing phases because the original provenance implementation assumed
`FreeCAD.__file__` existed. The failed report, request, snapshots, logs and global
preservation ledger remain unchanged. The console returned code 0 and retried the
failed script, which the fresh-report guard rejected. Process exit alone therefore
does not establish diagnostic completion. The revised worker returns its final
status checkpoint without throwing solely because the diagnostic failed.

Root executed fresh run-002 in **114.9911252 seconds**. Its five phases each
captured all **90 objects**, with all 450 own-state observations `Up-to-date`.
No document was saved; zero documents remained after cleanup. All packet inputs,
previous-attempt artifacts, originals, compatible CAD and addon files in Root's
741-file outer ledger remained hash-identical. The report is a completed
diagnostic, with migration acceptance still false.

| Phase | Actual B2 radius, mm | Body volume, mm³ | Captured recompute Boolean |
| --- | ---: | ---: | --- |
| Restored cached | 1.7 | 298644.44396778283 | Not requested |
| Requested-force nominal | 1.7 | 298644.44396778283 | False |
| Minus 0.01 mm | 1.69 | 298655.6435215032 | True |
| Plus 0.01 mm | 1.71 | 298633.15337228857 | True |
| Returned nominal | 1.7 | 298644.4262472596 | True |

The returned Body differs from this run's nominal by
**−0.01772052323212847 mm³**, again failing the unchanged `1e-6 mm³` gate.
`Pocket005` is the earliest ordered bounded feature with observed return metric
drift. Returned `HoleAxis_5` and `HoleAxis_6` own-frame errors are approximately
`6.75016e-12` and `4.33982e-11`, exceeding the unchanged `1e-12` matrix gate.
This localizes observations without identifying a geometric root cause.

The 12 original expression pairs across 11 owners, actual candidate target lists,
attachment modes and offsets remain preserved through all phases. The original
source and current candidate already differ in 14 of 24 external datum matrices
at the strict `1e-12` threshold; that failed baseline remains visible separately
from this parameter-return experiment. Stable target names/indices and expressions
do not prove geometric attachment semantics.

The literal `nominal_forced` phase key describes the request, not an observed
whole-history rebuild. At pinned FreeCAD commit
`4fd3bf320d9566a27e60069fc8387448aaa3a094`, `Document.recompute` returns an integer
attempted-feature count; `force=True` bypasses `SkipRecompute` and does not mark
all features for execution. The Boolean conversion means nominal `False` proves
zero attempted features, while later `True` proves a nonzero attempted count whose
exact value was not retained. Counts also do not prove successful feature
execution. Cached nominal geometry, own states and dependent observed metrics
are retained as separate evidence. Future captures should retain the raw integer.

Native stderr also retains seven `InertialCS` warnings that second/third inertia
axes are undefined for an axisymmetric inertia tensor. Neither an `Up-to-date`
state nor diagnostic completion waives these warnings or the failed gates.

The [tracked trace and attempt bindings](../hardware/cad/thor-art1-return-trace-v1.json)
retain full per-feature measurements, the failed first attempt, actual execution
hashes and completed host analysis. The final analysis authenticates all source
expression values directly from the pinned archive and separates an unchanged
null construction shape from metric drift. All five phase identity/control checks
pass. Cached-to-requested-force nominal metrics are unchanged; each comparison
against the returned nominal retains **84 strict numerical failures**. The host
CLI therefore exits 1 with a completed diagnostic report, preserving those failed
gates. Full surface equivalence, complete dependency closure,
repaired source history and fabrication remain unestablished.
