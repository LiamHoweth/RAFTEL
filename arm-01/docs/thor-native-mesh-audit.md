# Host audit of selected native cached-BRep meshes

This checkpoint independently checks eight STLs exported from selected pinned
saved BReps. It keeps them separate from the original upstream STL campaign.
The [host audit](../hardware/print-planning/thor-native-mesh-audit-v1.json)
records seven candidate geometry variants covering **11 selected installed
instances**, with the Art4 transmission column still blocked. These are
unqualified draft-inspection candidates; the scope is not the whole 65-print
assembly, a source-history repair or a fabrication release.

## Actual native input and host verification

The input is the [selected native capture](../hardware/cad/thor-native-solid-properties-v1.json)
from Run03, using FreeCAD **1.1.4**, observed OpenCascade **7.8.1**, and the
[eight-selection request](../hardware/print-planning/thor-native-export-inputs-v1.json).
The native launcher recorded completion in about **2.42 s**. Nine actual
primitive/unit/frame fixtures passed: maximum relative tensor error about
4.40e-15, COM error 8.88e-16 mm, and relative volume error 2.83e-16. No FreeCAD
documents were opened, recomputed or saved; original and isolated source bytes
remained unchanged. That native scope is selected cached geometry, not rebuilt
feature history or physical behavior.

The ordinary-Python host auditor launches **no native process**. It joins the
request snapshot, worker snapshot, original/copy source pins, launcher result,
native capture and every export's bytes/hash/facet count. The recorded native
capture raw SHA256 is
`c8498b9eee2f81a391d6813ef0513cfce2ab3b20d11f750a5daba3b18ccd854c`.
The host report retains runtime observations and their authentication boundary;
coherent supplied receipts alone are not independent proof that a native run
occurred. The actual Run03 and independent artifact review supply that evidence.

All eight exports contain finite binary-STL vertices and **29,642 triangles**
in total. Exact-vertex topology/winding analysis reuses the source-STL parser,
including vertex-link checks. There is no welding, automatic repair, reflection,
rescaling or placement application during the audit.

## Results and upstream comparison

| Native cached source | Triangles | Exact-vertex topology result | Selected installed quantity | Winding-volume proxy versus native volume |
| --- | --- | --- | --- | --- |
| BaseTop | 2,104 | Closed, consistently oriented | 1 | about −0.0430% |
| BaseBearingFix | 2,152 | Closed, consistently oriented | 1 | about −0.0510% |
| CommonBearingFix | 1,220 | Closed, consistently oriented | 4 | about −0.0658% |
| Art2BodyAWindow | 3,370 | Closed, consistently oriented | 1 | about −0.1486% |
| Art3TensionerBody | 804 | Closed, consistently oriented | 2 | about +0.0315% |
| Art4TransmissionColumn | 14,016 | **Three nonmanifold edges; blocked** | 1 | about −0.2337% |
| GripperFinger nominal | 2,988 | Closed, consistently oriented | 1 | about −0.0651% |
| Saved reflected GripperFinger | 2,988 | Closed, consistently oriented | 1 | about −0.0651% |

The fresh Art2 window and Art3 tensioner tessellations no longer have the exact
boundary defects observed in their preserved upstream STLs. This is a different
mesh derived from the saved native shape, **not a repair of CAD history or an
overwrite of those upstream files**. The native column tessellation still has
the same three nonmanifold edges and remains excluded from candidate packages.
Native BRep validity does not override the host mesh failure.

The native exports use the requested **0.1 mm absolute linear / 0.2 rad angular
deflection** inputs. Those are mesher settings, not demonstrated maximum surface
error or accepted part tolerances. Winding integrals remain diagnostic volume
proxies, especially for the blocked mesh; closed combinatorial topology does
not exclude geometric self-intersection.

The host compares mesh bounds with the native bounding box at a small
float32-serialization allowance, and checks a deliberately coarse 0.9–1.1
volume-ratio band for gross unit/scale mistakes. Neither numerical screen is a
surface-fidelity or manufacturing criterion. Curved native bounding boxes can
be looser than tessellated extrema; a difference is not assigned to shrinkage
or accepted as a measured surface deviation. Bidirectional native/mesh surface
distance and self-intersection checks remain unperformed.

## Frames and the actual reflected finger

Both native capture and mesh report retain
`saved_BRep_storage_frame_as_read_mm`, with no extra XML/object/link placement
applied. Raw Shape.Placement, native COM and bounds are recorded separately.
The installed/world App::Link transforms remain unknown to this export path;
COM and envelopes are not used to reconstruct them.

The reflected export comes from the actual saved
`AssemblyArt56::Unnamed1_GripperFinger_mirrored`, exact `PartShape52.brp` entry.
Every unindexed float32 vertex, including multiplicity, matches the nominal
export under `(x,y,z) → (−x,y,z)`. The two winding-integral volume proxies are
equal at about 12,584.8496 mm³; the cached BRep volumes are about
12,593.0426 mm³. This corroborates the reflected point geometry in the common
stored-source frame. It does not establish a triangle-by-triangle surface
bijection, installed mating transform, jaw fit or physical interchangeability.

Independent raw binary inspection corroborated all eight source hashes,
facet counts, positive winding integrals and edge-incidence findings. It also
confirmed the exact reflected vertex-multiset relation without importing the
production analyzer.

## Separate native-cached 3MF drafts

A separate queue under ignored `.work/print-planning/native-draft-plan-run03.json`
binds the native capture, launcher, request, host audit, original archive, exact
BRep entry, export SHA256, frame and tessellation settings. Its mesh origin is
`selected_saved_BRep_native_tessellation`; it is never silently represented as a
Git-tracked upstream STL. The original source plan and six first draft packages
remain preserved.

The generic Core composer accepts this explicit native origin separately from
the upstream-STL branch. It requires actual saved-mirror provenance for a
reflected variant, preserves the supplied source vertices/winding exactly and
uses only an identity-rotation draft bed translation. It performs **no new
reflection operation**. Variant quantities stay distinct, including one nominal
and one saved reflected finger. Native-cached provenance and all qualification
flags accompany the 3MF, with full upstream license text retained.

Eleven separate one-part drafts were prepared under
`.work/print-planning/projects-native-run03`: BaseTop ×1, BaseBearingFix ×1,
CommonBearingFix ×4, Art2BodyAWindow ×1, Art3TensionerBody ×2, and one of each
finger variant. Art4TransmissionColumn is not packaged. Package titles begin
`DRAFT_unqualified_NATIVE_CACHED` and explicitly name the variant. The saved
Kobra software-profile scenario is unchanged; actual nozzle, filament, support,
fit and strength are still unqualified.

Generic 3MF structural/coordinate roundtrips are separate from actual Anycubic
import. Opening, previewing or slicing would each require its own observed
result; none is inferred from archive creation. No printer/cloud communication,
G-code generation or print start occurs in these tools.

## Reproduction and test boundary

From an installed development environment in `arm-01`, with the preserved local
Run03 launcher receipt and export directory:

```powershell
python -m pytest tests/test_thor_native_mesh_audit.py tests/test_thor_draft_3mf.py
python tools/audit_thor_native_meshes.py --capture hardware/cad/thor-native-solid-properties-v1.json --launcher ../.work/native-solid-properties/run-03/launch-result.json --mesh-root ../.work/native-solid-properties/run-03/draft-stl --output new-native-mesh-audit.json --draft-plan new-native-draft-plan.json
python tools/thor_draft_3mf.py --plan new-native-draft-plan.json --mesh-root ../.work/native-solid-properties/run-03/draft-stl --license-file ../.work/print-planning/upstream/LICENSE --asset GripperFinger::Body --variant reflected --output DRAFT_unqualified_NATIVE_CACHED_reflected_finger.3mf --receipt new-native-3mf-receipt.json
```

The host tests use explicitly synthetic capture fixtures to check stale/missing
hashes, units/frame changes, incomplete fixtures, altered exports, wrong source
plans, topology/scale failures, variant/origin substitution and output
preservation. They validate software contracts; they do not authenticate or
replace the actual local FreeCAD run. Native and host artifacts remain separate
evidence classes throughout the handoff.
