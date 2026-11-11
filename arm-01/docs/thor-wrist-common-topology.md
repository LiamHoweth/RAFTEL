# Wrist common topology ownership diagnostic

This prepares one bounded followup to the [signed-volume discrepancy](thor-wrist-failure-pair.md). That capture observed a valid `Forward` Compound with aggregate signed volume −0.5552516266 mm³ and three `Forward` solids whose reported volumes sum to +0.1063090731 mm³. It did not retain constituent ownership or the resulting BRep, so open/mixed faces and quadrature/reference effects remain hypotheses.

`tools/probe_thor_wrist_common_topology.py` reuses the accepted one-pair source, frame, runtime, input-metric and identity guards. It computes the same single `plate.common(positive_Y_pinion)`, at q5=−20°, q6=−15°, intended `s=+1`, pinion angle +10°. Source cached shapes and declared ideal copied-shape articulation remain explicit. It never changes operand order, repairs/reverses shapes, substitutes `abs` or a solid sum, recomputes source history, or saves a source document.

The new observations are:

- Every common face: local index, native orientation, surface type, area and exact owning solid/shell indices.
- Every common shell: face count, matching common-face indices, owning solids and native `isClosed()` state when supported; unavailable/error states remain unknown.
- Every common solid: signed volume/orientation, raw face/shell counts and matching common-face/shell indices.
- Explicit common faces and shells that match no solid constituent. Matching uses `TopoShape.isSame` topology/location identity, with no geometric proximity fallback.

The raw common is exported **once** into a private run-local directory, then retained byte-for-byte at a new `.work` BRep path with SHA-256 and byte count. Export writes only the computed diagnostic shape. It is not a CAD-document save, altered design asset or manufacturing release. Existing paths are rejected and no previous native report/debug shape is overwritten. The exact BRep permits later independent inspection without pretending that the earlier capture retained it.

Raw child counts and matching common-index sets are not assumed equal: repeated native occurrences can share an `isSame` identity. Each solid/shell therefore records every local face/shell occurrence and its matching common indices. Completion requires count/occurrence cardinality, reciprocal memberships and shell→solid→face containment to agree. This preserves legitimate repeated occurrences while rejecting missing or contradictory hierarchy. Debug metadata must identify the unaltered common at `common-debug.brep` inside the isolated root and within the 128 MiB retention bound.

The report first preserves signed shape metrics, then validity and ownership. Exact membership is an observation; the negative aggregate's cause remains unproven. Even if unowned faces exist, explaining their numerical contributions requires a separate controlled integration study. Physical mesh/contact, calibrated accuracy and fabrication remain unqualified.

Only Root may schedule the native slot. Use a fresh isolated run, pinned executable/addons, empty stdin, hidden process, actual configuration-path verification and an **180-second maximum** process timeout. Snapshot this worker plus the accepted failure-pair, wrist-pose and assembly-audit helpers. Conflicting opt-in flags are rejected before helper imports. No native process launches through the default script entry point.

```text
RAFTEL_RUN_WRIST_COMMON_TOPOLOGY=1
RAFTEL_WRIST_TOPOLOGY_SOURCE=/path/to/compatible/copied/freecad-src/Assembly.FCStd
RAFTEL_WRIST_TOPOLOGY_REPORT=/path/to/fresh-run/report.json
RAFTEL_WRIST_TOPOLOGY_ISOLATION_ROOT=/path/to/fresh-run
```

The completion check extends the accepted one-pair measurement contract using independent full source/code pins. It checks topology coverage, reciprocal ownership and raw-export metadata while preserving negative/invalid results and all no-acceptance fields. Original/copy input hashes and zero open-document counts remain required.

Pure tests exercise exact identity versus location/orientation, synthetic owned/unowned faces and shells, unknown closure queries, exclusive no-overwrite debug retention, inherited-flag guards and contract tampering. A failed final write can leave a partial newly created debug file; its missing completion/pin must not be accepted. These tests do not run CAD:

```powershell
python -m pytest tests/test_thor_wrist_common_topology.py
```

## Actual scheduled result

The approved isolated run completed in **41.29 seconds**, with one common and one raw-BRep export. [The tracked native capture](../hardware/cad/thor-wrist-common-topology-v1.json) is byte-identical to `.work/native-wrist-common-topology-02/probe.json` (SHA-256 `5141144ed1d338b0b083254a168c481772c9c2aa13a89eac8d6a7c9e7e0243ad`). Worker errors are empty, strict completion passed and open-document counts are zero before and after. Original/copy CAD inputs, snapshots, addons and launcher bytes remained unchanged according to the retained independent launch receipt.

The negative aggregate reproduced at **−0.5552516265803887 mm³**. Actual ownership observations are:

| Solid | Owned common faces | Raw face/shell counts | Native solid/shell closure |
| --- | --- | --- | --- |
| 1 | 1, 2, 3 | 3 / 1 | Both `isClosed=True` |
| 2 | 4, 5, 6, 7 | 4 / 1 | Both `isClosed=True` |
| 3 | 8, 9, 10, 11 | 4 / 1 | Both `isClosed=True` |

Every one of the eleven common faces belongs to exactly one of these solids and its shell. All three common shells belong to solids. There are **no unowned common faces or shells** in this capture. Face surfaces comprise one cone, seven B-spline surfaces, two cylinders and one plane; face 11 is `Reversed`, the other face orientations are `Forward`. The complete per-face areas, occurrence mappings and ownership are retained in the native capture.

`isSame` ignores orientation while comparing topology/location. Common-level face orientations therefore do not authenticate orientations in each owning solid/shell context or explain the signed integration result; those context-specific orientations were not captured.

This does **not support the standalone/free-face explanation** for this exact common. The three positive reported solid volumes remain distinct from its negative aggregate, and the reason remains unproven. Native topological validity and closure observations are preserved without turning either volume into accepted material or physical contact evidence.

The exact unaltered common BRep is retained at:

```text
.work/native-wrist-common-topology-02/common-debug.brep
900661 bytes
SHA-256 f6a8a4f48a7c13f75fbde9a6e57aefb26fce268fc52d43278c589d934fea0678
```

This is a local diagnostic artifact, not a tracked manufacturing export. Its byte pin permits a later independently scheduled OCP/OCCT integration study without recomputing the Boolean or altering source CAD.

The already pinned [OCCT implementation](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.cxx#L224) chooses `roughBaryCenter(S)` as its integration reference. Grouping the input as a compound versus separate solids can therefore change that reference. The same source uses a nonadaptive branch for the default `Eps=1.0` path. These facts motivate a controlled reference/quadrature comparison on the retained BRep; they do not prove the numerical cause. Exact binary/source correspondence remains bounded as documented in the [previous source audit](thor-wrist-failure-pair.md).

No healing, orientation reversal, `abs`, solid-sum replacement, additional Boolean or physical acceptance was performed. Further kernel comparisons require a new explicit serialized slot and must retain original signed metrics and BRep bytes.
