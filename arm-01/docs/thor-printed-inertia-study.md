# Authenticated printed-copy tensor frames

The [native frame capture](../hardware/cad/thor-printed-tensor-frames-v1.json) authenticates all **47 saved-BRep geometry variants against 65 distinct installed printed copies** in the copied saved-zero assembly. The [derived study](../hardware/cad/thor-printed-inertia-study-v1.json) integrates that printed subset under an explicitly assumed **uniform solid density of 1240 kg/m³**. This is a conditional geometric reference, without measured printed-part inertia, nonuniform wall/infill distribution, purchased internals or whole-arm dynamics. Those physical quantities remain null. No CAD design was repaired, manufacturing qualified or fabrication released.

## Actual native observations

One independently approved FreeCAD 1.1.4 console process ran from **2026-11-11 23:41:32 UTC to 23:43:14 UTC**, taking **101.968 seconds**. Its worker SHA-256 was `4dc06fbe2f5e864e0312f3860eac4521c1230a080468df7e0733e4d4b682ab3e`; executable SHA-256 remained `1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d`. Prepared runs 01/02 were never launched. The retained Run03 snapshot and raw capture remain separate from the published artifact's explicitly identified host-added launcher provenance.

The five actual preference/home/data/temp paths matched their dedicated expected paths. Open-document counts were zero before and after; all 53 restored documents' actual `FileName` values resolved inside the private source directory and matched its archive hashes. The 518-leaf walker reproduced the pinned complete identity set. The source assembly was not explicitly recomputed or saved; only the separate synthetic coordinate fixture was recomputed. Final native states were **1147 Up-to-date and 1854 Touched**, with no Invalid/Error objects observed. These are cached-state observations, without a feature-history rebuild claim.

All 57 original archives, 57 compatible-parent archives, their 114 private copies, 589 add-on files and the retained script/request/input snapshots remained byte-identical before and after. The compatibility tree uses the separately accepted static Art1 wrapper `142d754d…` plus 56 original siblings; the independent original-source BRep tree preserves the original Art1 archive. Source tensor metrics were required to exactly reproduce the [six earlier batches](../hardware/print-planning/thor-full-print-export-native-v1.json). Earlier selected-eight, normalized-validator and full-47 evidence was preserved.

## Frame authentication without COM fitting

For each variant, the worker reads its hash-pinned saved BRep, retaining its own raw placement `P_source`. It obtains the installed object's actual raw `Shape.Placement`, `P_installed`, and independently walks the assembly ancestor chain `A`. The candidate mapping is:

```text
p_installed_raw = P_installed * inverse(P_source) * p_source_raw
p_master = A * P_installed * inverse(P_source) * p_source_raw
```

Raw shape coordinates already include their own placement, so no XML or object placement is applied twice. Each matrix must contain a proper rigid rotation. Native object/link identity must name the exact selected source object; source and installed vertex/edge/face/solid counts must agree. The reflected finger uses its **actual saved mirroring BRep** as a separate variant, without an additional assumed reflection.

Every ordered native vertex was checked: **8612 installed vertex observations**, with at least three noncollinear anchors per copy. Maximum vertex residual was **1.947e-13 mm**, below the declared **1e-7 mm** numerical acceptance threshold. Independent native installed-solid metrics also checked volume, transformed COM and rotated centroidal tensor; maximum relative residuals were **1.648e-15 volume** and **1.051e-14 tensor**, with **2.298e-13 mm COM** error. Their declared gates were 1e-9 relative volume, 1e-8 relative tensor and 1e-7 mm COM. World COMs matched the earlier mounted capture within **2.511e-16 m**, against a 1e-9 m check.

These observations authenticate cached-source identities and placement frames. Ordered markers and moment agreement are not a continuous-surface deviation certificate. Default native GProps integration remains numerical, with no certified error bound; the close residuals do not supply that missing bound. Failed marker, source-identity, covariance or preservation checks remain diagnostic unknowns. The host tool refuses to aggregate incomplete 65-instance coverage as a complete subset.

## Conditional uniform-solid result

Geometric tensor units convert from mm⁵ to m⁵ with `1e-15`, then multiply by the declared density. Rotations act on centroidal tensors; translations change their COMs, and the existing parallel-axis algebra aggregates them in one native master saved-zero frame. Every printed instance is counted once, including repeated source copies and the saved reflected finger. Density is an explicit solid-model assumption, not slicer infill or a measured print distribution.

The installed printed volume is **0.003485323122867904 m³**. At the declared 1240 kg/m³ reference density, the subset mass is **4.3218006723562015 kg**, with COM **(-0.01718382371637, -0.000284997238493107, 0.23423980985378312) m**. Its conditional centroidal tensor in native master axes is:

```text
kg*m^2
[ 0.155007153274,  0.000067849644, -0.014672599738 ]
[ 0.000067849644,  0.162042117216,  0.000391693852 ]
[-0.014672599738,  0.000391693852,  0.025420010010 ]
```

The report also records all 65 component properties and six subassembly aggregates in that same frame. It does not merge these solid-reference tensors into the existing gravity mass ledger or infer inertia for motors, fasteners, belts or payloads. Physical printed and whole-arm inertia remain unknown; calibrated motion, actual densities/distributions and purchased internal properties are separate gates.

## Reproduce and review

From `arm-01`, after installing the package:

```powershell
python tools/thor_printed_inertia_study.py hardware/cad/thor-printed-tensor-frames-v1.json --output /path/to/new-study.json
```

The output path must be fresh. The host builder verifies all eleven bound evidence files, exact source tensor bindings, complete identities, actual placement composition, vertex checks, prior mounted COMs and SI conversions before integrating the reference subset. A different density must be caller-declared with `--uniform-solid-density-kg-m3`; it remains an assumption.

Native reproduction requires a fresh copied tree, retained worker/helper/input snapshots, pinned add-on origins, isolated runtime preferences, 50 GiB reserve, one explicitly coordinated native slot and the private request contract. No source recompute, CAD save, hardware motion, flashing, G-code, printing or upload is part of this tool. Host tests independently check a 65-box closed-form tensor and reduced-mass/parallel-axis result, reject identity/frame/unit mutations, preserve unknown partial coverage and replay the retained actual evidence.
