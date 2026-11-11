# Local slicer draft planning and upstream mesh audit

This checkpoint prepares local print-planning material for the installed
Anycubic Slicer Next. It audits **pinned upstream STLs**, rather than exporting
RAFTEL's accepted native final solids. It creates a separate standard mesh-only
3MF fallback for inspection; Anycubic import must be observed before calling it
an interoperable local project. Nothing here releases manufacturing, starts a
print, uploads to a service or generates G-code.

## Source, units and quantity reconciliation

The source is [AngelLM/Thor revision
286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159).
The complete recursive Git tree capture is pinned by its SHA/immutable URL and
canonical JSON SHA256
`a58151d5204ff5f00fbbc907b11f285cf00774507ee0708be82feea3571848f4`.
Each acquired source file is checked against its Git blob ID and size, then
recorded with SHA256. Downloads remain under ignored `.work/print-planning`;
original CAD and historical captures remain unchanged.

[The draft plan](../hardware/print-planning/thor-draft-plan-v1.json) reconciles
the existing [printable ledger](../hardware/cad/thor-printable-assets-v1.json):

| Scope | Count and disposition |
| --- | --- |
| Upstream nominal `stl/` files | 49 audited |
| Named source assets in the installed ledger | 46 |
| Installed printed leaves | 65 |
| Geometry variants | 47, including one distinct reflected finger |
| Nominal source candidates | 64 installed instances |
| Topology-blocked nominal instances | 4 |
| Missing reflected native export | 1 instance |
| Candidates for further draft planning | 60, all still unqualified |
| Separate `mods/` meshes | 23 listed, unselected and not substituted |
| Upstream 3MF files | None in the pinned tree |

Three nominal files are source-only extras outside the installed ledger:
`Art1OptoFix.stl`, `Art4BearingPlug.stl` and `Art56Interface.stl`. They are audited
but receive no installed print quantity or draft plate. The nominal
`GripperFinger.stl` supplies only the single nominal finger candidate; it cannot
replace the separate reflected finger. No reflection is fabricated from an
unreconciled STL-to-native transform.

STL itself has no unit field. Coordinates are **explicitly interpreted as mm**
for comparison with the preserved native captures. That is a documented unit
interpretation, not a unit declaration encoded in the source file or physical
dimensional acceptance.

## Mesh validation and remaining fidelity gaps

`tools/thor_slicer_plan.py` reads bounded binary or ASCII STL inputs, rejects
truncated/empty/nonfinite data and validates triangle grammar. Exact-size binary
STL takes precedence over an ASCII-looking `solid` header. It computes bounds,
surface area and a translation-stable signed-volume integral. Normals are
checked as warnings; winding comes from the actual vertices.

The topology checks include edge incidence, consistent winding, duplicate/zero
area facets and each vertex's incident-face link. The latter rejects two closed
shells meeting only at a vertex even if every edge has two incident triangles.
Vertices match **exactly**; no tolerance weld, repair or smoothing is performed.
Self-intersections are not checked. A closed topological mesh and its winding
integral do not by themselves prove an embedded solid, printability or native
geometry equivalence.

| Source file | Exact-vertex finding | Installed instances blocked |
| --- | --- | --- |
| `Art2BodyAWindow.stl` | 504 boundary edges | 1 |
| `Art3TensionerBody.stl` | 6 boundary edges | 2 |
| `Art4TransmissionColumn.stl` | 3 nonmanifold edges, 4 nonmanifold vertices | 1 |

The other 46 upstream files pass the implemented closed/winding/link checks,
including the three source-only extras. Independent raw binary inspection
corroborated all 49 bounds and edge-incidence results; the closed-mesh signed
volume calculations agree within 2.33e-9 mm³.

For the 46 installed source assets, absolute signed mesh-volume proxies differ
from captured native volumes by less than 0.688%. **Bounds can differ much more**:

| Asset | Upstream STL XYZ extent mm | Captured native XYZ envelope mm |
| --- | --- | --- |
| Art56GearPlate | about 77.157 × 77.141 × 51 | about 138.553 × 138.524 × 52.7 |
| BaseBot | about 175 × 199.999 × 65.5 | about 202.452 × 254.903 × 65.5 |
| Art1Body | 150 × 150 × about 161.489 | about 162.359 × 162.359 × 161.561 |

These differences remain unresolved. Loose curved-surface bounds, tessellation,
frames or actual geometry differences require native extrema/distance evidence;
this audit does not choose a cause. Similar volume is insufficient to accept a
source mesh as the exact native final solid. The original Art1 parametric
history remains unrepaired, and the failed Intersection workaround is not an
accepted source. The draft 3MF composer explicitly excludes Art1Body while its
exact-final-solid gate remains unresolved.

## Saved profile scenario and conservative draft placement

The separate [local profile audit](../hardware/print-planning/local-profile-audit.json) records installed
Anycubic Slicer Next **2.0.0.3** and last-saved software selectors: Kobra 3 Max
0.4 nozzle, its 0.20 mm Standard process and Anycubic PLA in six slots. These
are software observations; actual nozzle, spool, bed surface and live unsaved
GUI state remain unconfirmed.

The planner independently reconciles the allowlisted machine outline and its
four-point exclusion groups: outline 426 × 420 mm, 3 mm X-edge strips, and a
provisional inner rectangle X=3..423, Y=0..420 mm. It uses a conservative
500 mm height from the user-confirmed nominal machine dimensions, rather than
consuming the profile's extra 1 mm. The exact machine-profile raw SHA256 and
inherited process/filament hashes remain in the plan. Changed or unfamiliar
geometry/keepout fields fail rather than silently adopting a different printer.

For nonblocked nominal candidates, the queue proposes **one part per draft
plate**, repeated according to the installed quantity. A centered translation
puts the interpreted source minimum Z at zero, retaining source STL Z-up as an
explicitly **unselected orientation candidate**. A 10 mm XY numerical margin
allows space around the interpreted bounding box; actual supports/brims,
contact stability, clearance and layer-load suitability remain separate checks.
No support strategy or structural process is selected by an AABB fit.

The saved process's 0.20 mm layers, two walls, 15% sparse infill, disabled
supports and auto-brim are not approved Thor settings. Infill percentage is
not a whole-part solid mass fraction. The source orientation/inspection prompts
and fit-coupon dependencies remain attached to each group. Actual filament,
nozzle and fit observations are required before process-dependent decisions.

## Standard mesh-only 3MF fallback

The installed CLI exposed no usable help/export result in the bounded profile
audit, so a separate format fallback was authorized. `tools/thor_draft_3mf.py`
creates a **generic 3MF Core mesh package**, not an Anycubic-native project or
toolpath. Its format reference is [3MF Core Specification v1.4.0, revision
997b385e06f3181cf9aae0c578e0b45ccd48ccb2](https://github.com/3MFConsortium/spec_core/blob/997b385e06f3181cf9aae0c578e0b45ccd48ccb2/3MF%20Core%20Specification.md),
SHA256 `4db7a7a13e7f757c6afc1a9ad731b56d8d068b1a766025692ff757d0f7f16940`,
accessed 2026-11-11. Checks cover §3.3 transforms, §3.4 model/metadata, §4.1 meshes
and Appendix C package types/relationships. They are structural subset checks,
not a certification of complete 3MF conformance or slicer compatibility.

The package has only `[Content_Types].xml`, `_rels/.rels` and
`3D/3dmodel.model`. It specifies `unit="millimeter"`, zero-based triangle indices,
one nominal object and one build item. Vertex coordinates use round-trippable
17-digit decimals; source vertex values, facet order and winding are preserved.
The 12-value row-vector build transform has identity rotation and translation
in its last three values, per the format convention. No scale, reflection,
automatic repair, process configuration, machine command or external resource
is added.

Raw source hashes, discrete topology and packaged vertex/index/winding values
remain exact. Recomputed derived mesh diagnostics allow only 1e-12 finite-float
roundoff for Windows/Linux reproduction; this is not a geometry or manufacturing
tolerance. Negative fixtures reject meaningful diagnostic or count changes.

Each draft includes a `DRAFT_unqualified` title, full upstream CC-BY-SA license
text, source/revision/mesh/profile hashes, the quantity/copy index and explicit
remaining gates. Custom provenance metadata uses a declared QName namespace.
Source-attribution and ShareAlike obligations remain; no company-wide RAFTEL
license is selected. Existing output paths are never overwritten.

Six initial local draft packages were prepared under ignored
`.work/print-planning/projects`: BaseTop ×1, BaseBearingFix ×1 and
CommonBearingFix ×4 as separate one-part plates. The source-only extras, three
topology failures, reflected finger and Art1Body were not packaged. Matching
JSON receipts record package hashes and exact mesh/index/winding roundtrips.
These are format/geometry checks until the integration owner observes import
in the installed application. No slicing or physical print is claimed here.

## Reproduction and next checks

From the installed development environment in `arm-01`, with separately
acquired pinned sources and tree capture:

```powershell
python -m pytest tests/test_thor_slicer_plan.py tests/test_thor_draft_3mf.py
python tools/thor_slicer_plan.py --tree /path/to/pinned-tree.json --upstream-root /path/to/pinned-downloads --profile-audit hardware/print-planning/local-profile-audit.json --output new-draft-plan.json
python tools/thor_draft_3mf.py --plan new-draft-plan.json --upstream-root /path/to/pinned-downloads --asset BaseTop::Body --output DRAFT_unqualified_BaseTop.3mf --receipt new-3mf-receipt.json
```

Next, observe the saved-profile and draft geometry in Anycubic, inspect stable
contact faces and likely support access, and retain the unresolved mesh/native
differences and physical-input gates. Do not treat successful import, automatic
mesh repair, a slicer estimate or a zero CLI exit as fabrication acceptance.
