# Stepped-bore coupon dimension-study drafts

Three independent test-piece meshes are prepared for later fit planning. They
are **not extracted nominal Thor parts**, verified native exports or released
print jobs. No Anycubic import, slicing, G-code, printer connection or physical
measurement was performed by this tool. Existing source/native meshes and
installed arm quantities remain unchanged.

[The recipe and checks](../hardware/print-planning/thor-fit-coupons-v1.json) bind
the source interface capture and saved-profile audit by canonical JSON SHA-256.
The saved software profile is context only; no nozzle, spool, support or process
setting is selected here. The existing upstream/native 3MF composer deliberately
accepts authenticated part variants; these synthetic coupons are not mislabeled
as one of those assets. This lane produces STL plus a receipt, not a fabricated
source-part 3MF provenance record.

## Source dimensions versus independent coupon choices

The source is the preserved cached `BaseBot::Body002` capture at Thor revision
`286b081fe6f056d87c379b884781ef77ff6a0159`, source file SHA-256
`c637feec821a886c80c8622cf316de02c05f06d90ff49af9df9b0a0cdff00e5a`.
The same existing source-face crosschecks used by the
[base drawing](../hardware/drawings/thor-base-interface-v1.svg) validate the
dimensions before mesh generation.
The supported capture schema/class, exact pinned BaseBot file/object/hash/frame
and all eight referenced face IDs are required. JSON decoding rejects duplicate
keys and nonfinite constants. Saved-profile context also requires a supported
software-audit schema/class, matching profile selectors and the existing pinned
machine-profile checks; hashing arbitrary input does not make it profile evidence.

| Dimension | Value | Evidence / meaning |
| --- | ---: | --- |
| Nominal lower bore | Ø6 mm | Source cylindrical faces 6/9/11/13 |
| Lower bore depth | 5 mm | Source interval z=0 to 5 mm |
| Upper relief | Ø14 mm | Source relief faces 63/64/69/70 |
| Coupon outer diameter | Ø22 mm | Independent test-piece choice, not the source base outline |
| Coupon upper recess depth | 5 mm | Independent test-piece choice; source relief top is nonplanar |
| Coupon total height | 10 mm | Source lower depth plus assumed upper depth |

The source base's original outer shape, load paths and nonplanar relief top are
not reproduced. This is a simple concentric stepped annulus for isolating a
dimension/process question. It does not test source-part strength, bolt preload,
washer access, mount behavior or an actual fit class.

The default grid changes the **lower bore diameter**, not its radius or the
entire part scale. The relief stays Ø14 mm. The zero-offset piece retains source
nominal dimensions as a reference; it still has the independent coupon outer
shape and upper depth.

| Draft filename suffix | Diameter offset, mm | Target bore vertex diameter, mm | Digital minimum across flats, mm |
| --- | ---: | ---: | ---: |
| `coupon_01.stl` | −0.1 | 5.9 | 5.896840 |
| `coupon_02.stl` | 0 | 6.0 | 5.996786 |
| `coupon_03.stl` | +0.1 | 6.1 | 6.096733 |

Full filenames begin `DRAFT_dimension_study_bolt_`. These offsets are an
illustrative study grid, **not selected shrink compensation or accepted fit
allowances**. Actual target fastener/drawing, process behavior and required
clearance must be supplied before judging a printed result. The API bounds
offsets to ±0.5 mm and requires at least 1 mm radial outer wall solely to keep this
small study's parameter domain explicit; those are not structural design limits.

## Digital geometry checks

The coupon frame uses mm, z=0 at the lower annulus and +Z along the bore.
STL itself encodes no unit. The default circles have 96 segments; vertices are
rounded to a declared 0.000001 mm numerical grid before binary-float STL output.
That grid is a serialization choice, not claimed manufacturing precision.

Each default mesh has 576 exact shared vertices and 1,152 triangles. The existing
STL analyzer checks one connected component, nonzero positive signed volume,
no boundary/nonmanifold edges or vertices, consistent winding and no degenerate
or duplicate facets. Independent tests check all six surface-strip normal
directions and the polygon-prism volume formula. Bounds are 22 × 22 × 10 mm.

The hole boundaries are inscribed polygons. Their across-flats opening is
slightly smaller than the nominal circle; the receipt measures exported vertex
and across-flats diameters explicitly. This digital facet error must not be
confused with physical shrinkage or silently absorbed into a fit allowance.
No general self-intersection scan, source-solid equivalence or print acceptance
is claimed by these checks.

The simple source-Z-up pose is an orientation candidate: it has a flat annular
underside and an exposed upward step ledge. Actual bed adhesion, process settings,
dimensional behavior and support choices still require the real printer/material
workflow. The mesh does not encode a machine profile.

## Files and reproduction

Current generated meshes, receipt and attribution README are local under:

```text
.work/print-planning/fit-coupons/run-003/
```

Earlier runs 001/002 are preserved. Run 003 adds the blank measurement template
without changing the run-002 STL bytes; its receipt matches the current tracked
recipe. The recipe is sufficient to reproduce the meshes without native CAD,
internet or a slicer.

From `arm-01`, choose unused output paths:

```powershell
python tools/thor_fit_coupons.py --output-dir ../.work/print-planning/fit-coupons/repro-004 --report ../.work/print-planning/fit-coupons-repro-004.json
python -m pytest tests/test_thor_fit_coupons.py
```

For an alternative explicit grid, repeat `--bore-offset-mm`, including zero;
`--segments` accepts multiples of four from 32 to 512. Bounds, volume and topology
are checked again for each generated mesh. Existing output directories/reports
are refused, binary STLs use exclusive creation and text uses UTF-8/LF. A failure
can leave partial **new** output; a nonzero run is incomplete, and no existing
evidence is deleted or replaced.

Keep `receipt.json` and `README_DRAFT.txt` with the STLs. The binary header also
identifies DRAFT/mm and AngelLM/Thor CC-BY-SA-4.0 dimension attribution. The receipt
retains the pinned source/license links and identifies independent shape/offset
changes. No company-wide RAFTEL license is selected.

## Measurement and remaining gates

The recipe includes a blank `coupon_measurement_template`: specimen/mesh ID,
actual profile/filament evidence, instrument/resolution, measured X/Y bore and
relief dimensions, cleaned coupon mass, target drawing, required fit and
acceptance all remain unknown. Mesh dimensions use mm; later measurement fields
use explicitly named SI units. Coupon mass is **not installed arm mass** and
must not replace an installed-part ledger entry or be multiplied by arm quantity.

A bearing-seat coupon remains blocked because the bound interface capture does
not select an actual bearing-seat face/target fit. Axis-line evidence does not
supply the required bearing variant, seat dimension or interference allowance.
The actual part/drawing and a source-linked seat capture are the next inputs.

Before any separately authorized physical work, confirm the installed nozzle,
actual spool/process and target component; define the fit acceptance requirement
and measurement method. Later results must record specimen identity, dimensions
in multiple directions, instrument resolution and conditions. This draft package
does not authorize fabrication, prove a fit or permit motion.
