# Independent adaptive OCCT metric study

The optional binding capability is available, but the Art1 discrepancy remains
unresolved. A separate OCCT distributor reproduces the earlier FreeCAD default
properties exactly and produces materially different Gauss–Kronrod integrals.
The source/candidate difference persists and changes across requested accuracies.
This establishes algorithm sensitivity, not exact geometry equality or a complete
explanation of the original discrepancy. Every migration, physical and fabrication
gate remains false.

[The study record](../hardware/cad/thor-adaptive-metric-study-v1.json) retains
acquisition/source receipts, the actual captures and runner metadata, original raw
file hashes/paths, failed protocol history, module identities and numerical rows.
[The worker](../tools/probe_thor_adaptive_properties.py) is optional tooling: no
repository requirement, main runtime dependency, global installation or CAD source
change was made.

## Capability, acquisition and isolation

The inspected FreeCAD commit is
`4fd3bf320d9566a27e60069fc8387448aaa3a094`. Its
[Shape volume getter](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapePyImp.cpp#L2848)
uses the default `BRepGProp::VolumeProperties` overload. Inspection of the
[main Part module registrations](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/AppPartPy.cpp)
found no adaptive GProp entry point. No FreeCAD binding or C++ ABI was modified.

Published PyPI releases supplied these CPython 3.11 / Windows x64 wheels:

| Distribution | Wheel bytes | SHA-256 |
| --- | ---: | --- |
| [cadquery-ocp 7.8.1.1.post1](https://pypi.org/project/cadquery-ocp/7.8.1.1.post1/) | 51,475,561 | `bfb110012766fa23e72c23eace00a791d9e7f86fc630694ef72d5e6b333df3aa` |
| [VTK 9.3.1](https://pypi.org/project/vtk/9.3.1/) | 52,526,922 | `59cc043f611e3eca2870cc50f27e67852a182857de322415e942bdc133594acd` |

All **104,002,483 downloaded bytes** match published PyPI sizes/digests. Every
wheel RECORD entry was checked before safe extraction: 932 files, 376,525,292
expanded bytes, entirely inside ignored `.work/adaptive-metrics`. The OCP initializer
requires `vtk.libs`; VTK's DLL payload was therefore retained. No VTK renderer or
Python visualization workflow was used, and transitive plotting packages were not
installed. No pip installer, SDK, whole CAD stack or global preferences were changed.

OCP's [pinned source tag](https://github.com/CadQuery/OCP/tree/d3fe8a125c5911a5d1cecd17007218f390d6fbae)
contains the [adaptive/GK API declarations](https://github.com/CadQuery/OCP/blob/d3fe8a125c5911a5d1cecd17007218f390d6fbae/opencascade/BRepGProp.hxx)
and [OCCT 7.8.1 version header](https://github.com/CadQuery/OCP/blob/d3fe8a125c5911a5d1cecd17007218f390d6fbae/opencascade/Standard_Version.hxx).
The actual Python binding reports 7.8.1.1; the actual loaded TKernel file resource
reports 7.8.1. Before and after the successful study, **46 TK DLLs** were observed
at the extracted wheel paths and matched their exact hashes. Any TK DLL resolved
from FreeCAD's adjacent `bin` directory would have rejected the experiment.

The FreeCAD and wheel TKernel binaries have **different hashes**. Matching version
numbers do not establish identical patches, compiler options or builds. PyPI build
attestations were not verified. This remains an independent-distributor kernel
observation; it is not a same-binary FreeCAD rebuild or equivalence certificate.

The process used the existing portable Python 3.11 executable with **`-I -S -B`**,
fresh child-only profile/app/temp paths, a minimal System32 PATH and no inherited
CAD-worker flags. A read-only, explicitly addressed System32 PowerShell process
module inventory recorded loaded filenames, resource versions and hashes. No
ctypes or C++ ABI calls were used. FreeCAD and Part were not imported; no CAD
document was opened, recomputed or saved. At least 50 GiB remained reserved.

Wrapper Apache-2.0, OCCT LGPL-2.1/special-exception/commercial-alternative notices,
VTK BSD and Thor attribution remain distinct. Wheel files and headers retain their
original notices in local scratch. No binary redistribution or repository-wide
license choice is made here.

## Controls and failed protocol history

Six analytic cases cover a 2×3×4 box and radius-2/height-5 cylinder, each at its
original placement, translated, and rotated/translated. Closed-form volume,
centroid and centroidal geometric tensor expectations are computed independently.
The same thresholds are retained throughout: relative volume `<1e-10`, centroid
error `<1e-9 mm`, and relative tensor error `<1e-9`.

Run01 failed before complex input measurement. Its last retained cases are the
three box cases; a capture-observability defect lost the first failing cylinder
method row. That exact old method/residual remains unknown and is not retrofilled.

Run02 retained all six cases × three methods. Exactly three rows fail: regular
adaptive Gauss cylinder tensors have relative errors about `7.74542e-8` for base
and translated cases, and `6.24093e-8` after rotation/translation. Volume and
centroid checks pass, while the returned mass-error estimate is about `2.12e-16`.
The [regular adaptive API](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.hxx#L199)
describes a mass/volume integration estimate. That estimate does not bound tensor
error. No tolerance was relaxed; the original 18-row gate remains failed.

Run03 is an explicitly different **protocol version 2**. It retains all 18
control rows and the original failed gate, but permits only default and GK methods
on complex inputs after **all 12 corresponding volume/centroid/tensor checks**
pass the unchanged thresholds. Regular Gauss is explicitly rejected for complex
tensor scope. Both older failures and their exact code/request/log snapshots remain
unchanged. This is algorithm-specific validation, not retroactive acceptance.

## Actual Art1 comparison

The two raw inputs are original cached Body BReps, with no added placements:

- Original archive `8afa16c8…`, member `PartShape.brp`, BRep SHA
  `d0ed3dcd293f814b6db11e0e29a22e89a6aa4fe6c8d9f8e5c08e508baec2b9db`.
- Explicitly **unaccepted** once-saved candidate archive `6b8e6ad3…`, member
  `Body.Shape.brp`, BRep SHA
  `190d3f1560664eea784ae7edabed8442768d7c65ce4a8c040e1b9f3f5529016c`.

Run03 ran from **22:49:14–22:49:28 UTC**, taking **14.030 seconds**. Originals,
archive/BRep copies, worker/request/launcher, interpreter, PowerShell and all
extracted package bytes remained unchanged. The API used `OnlyClosed=False`,
`SkipShared=False`; GK additionally used span integration plus centroid/tensor
flags. The original default and three GK rows are retained for each Body.

| Method / requested epsilon | Source volume, mm³ | Candidate volume, mm³ | Candidate − source, mm³ |
| --- | ---: | ---: | ---: |
| Default | 298648.100446804 | 298644.443967783 | −3.656479021 |
| GK / `1e-4` | 298673.866389097 | 298673.838414517 | −0.027974580 |
| GK / `1e-6` | 298663.112504455 | 298662.186121685 | −0.926382769 |
| GK / `1e-8` | 298663.492035459 | 298662.485084966 | −1.006950493 |

Default volume, centroid and tensor values exactly reproduce the earlier FreeCAD
metric-semantics capture despite the different distributor binary. GK changes
the integrals substantially, while the source/candidate difference persists and
changes with requested accuracy. The sequence is not a proof of equal limiting
values or a complete quadrature-only explanation.

Returned GK relative estimates at the finest request are approximately
`2.41304e-8 / 2.50968e-8`, numerically above `1e-8`. The API distinguishes requested
per-face integration tolerance from its returned whole-computation estimate.
Neither is an independently certified geometry or inertia error bound. No surface
distance, topology meaning, physical material or manufacturing tolerance follows
from these estimates.

The earlier datum discrepancies, 53-reference semantic audit, unresolved geometry
differences and failed radius roundtrip remain open. This study does not change
the accepted static snapshot, source CAD, load ledger, print settings or release
status. A bounded integration/reference-frame study may refine the numerical
explanation; continuous surface comparison and mechanical acceptance remain
separate work.

## Separate self-generated wrist Common diagnostic

Run05 is a separate **protocol version 3**, executed **23:01:39–23:01:55 UTC**
in **15.677 seconds**. Run04 was prepared only and never executed. Run05 did not
remeasure either Art1 Body. It reads one immutable, self-generated Boolean Common
BRep from the root wrist-topology capture: **900,661 bytes**, SHA-256
`f6a8a4f48a7c13f75fbde9a6e57aefb26fce268fc52d43278c589d934fea0678`.
This is explicitly **not an upstream Git Body**. Its copied source capture/hash
records 57 runtime-source archives: 56 original siblings plus the compatible/static
Art1 wrapper. The separate preserved-original 57-archive map, including original
Art1 `8afa16c8…`, is bound through that capture's
`launch_context.contract_sha256` to the retained contract's
`original_source_sha256_before` map. The direct runtime map is not relabeled as
the original-source map. The context also binds pose `q5=-20°`, `q6=-15°`, rotor
`10°`, candidate sign/side `+1`, and the `native_CAD_world_mm` frame.

The same six analytic fixtures and unchanged default/GK checks pass before this
measurement. All 18 rows and the rejected regular-Gauss tensor cases remain
recorded. All originals, copied BReps/context, packages, scripts and runtime
identities remained unchanged, and the before/after TK inventories stayed pinned.

| Integration context | Whole Common signed volume, mm³ | Sum of three Solid volumes, mm³ |
| --- | ---: | ---: |
| Default, `OnlyClosed=False` | −0.555251626579 | +0.106309073143 |
| Default, `OnlyClosed=True` | +0.106309073143 | +0.106309073143 |
| GK, requested `1e-8`, `OnlyClosed=False` | +0.237115898415 | +0.237115865417 |

The closed-only default values agree within `1.39e-17 mm³`; the GK aggregate/sum
difference is approximately `3.30e-8 mm³`, with returned aggregate estimate
`2.70458e-8`. No absolute values, healing, shape reversal or orientation changes
were applied. Individual default Solid values are unchanged by `OnlyClosed`.

All 11 global faces map to Solid-owner contexts with both `IsSame` and `IsEqual`
including orientation/location; the three Solid face counts are **3 / 4 / 4**.
No owner-orientation mismatch was observed. This adds that comparison to the
earlier containment evidence; it does not establish outward-normal correctness or
exact intersection geometry.

The [OCCT implementation](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.cxx#L310)
processes closed shells separately when `OnlyClosed=True`, while the other route
processes the aggregate. Therefore this option also changes integration grouping
and reference context; it is not merely a test for unattached faces. The observed
results support a numerical grouping/integration investigation. They do **not**
qualify overlap, establish a physical penetration volume or accept a geometry
repair. The original negative result and all failed runs remain intact.

The published tool additionally hard-pins this exact accepted context for future
protocol-3 reuse. The executed snapshot used its independently authenticated
request/context pins; that snapshot and its raw capture remain unchanged.
