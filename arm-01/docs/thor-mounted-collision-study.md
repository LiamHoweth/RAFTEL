# Saved-zero mounted numerical box pairs

This separate K4 input study constructs **518 numerical AABB proxies at saved
zero**, evaluates all **133,903 unordered pairs**, and retains every selected
overlap candidate plus every candidate found only by the comparison metric.
It establishes no physical collision, intended-contact decision, conservative
source enclosure, nonzero-pose binding or collision-free path. All proxy
enclosure statuses remain `unknown`; physical clearance and swept-path fields
remain null. No CAD/native process, runtime sorter integration or motion occurs.

The earlier [generic K4 study](thor-collision-proxies.md) is preserved unchanged
with its original pre-acquisition coverage scope. The new dataset advances
saved-zero numerical inputs while its enclosure and motion gates remain open.

## Pinned inputs and coordinates

[The mounted native capture](../hardware/cad/thor-native-mounted-bounds-v1.json)
is frozen at SHA-256
`d223ce7cb2bb9813b24640be2dc783b1054381624061b23951cf71e9bf067fe4`.
It binds all 518 identities to
[the existing inventory](../hardware/cad/thor-mounted-geometry-v2.json), whose
raw SHA-256 is checked again. The capture's source revision, evidence class,
schema, frame, five coordinate fixtures, no-recompute scope, exact identity
coverage, status, preservation flags and per-row source-object/root bindings
must match the declared contract. The existing generic box implementation is
bound by its own raw SHA-256.

The source is **restored cached saved-zero geometry**. The native run performed
no recomputation and ended with **1,147 Up-to-date / 1,854 Touched** state tokens.
Its 57 original CAD files, copied inputs and 589 addon files remained unchanged.
Successful coordinate fixtures and source preservation do not establish a rebuilt
or physically qualified geometry baseline. See [the capture contract](thor-native-mounted-bounds.md).

`world_optimal_bounds_m` already contains
`[[xmin,ymin,zmin],[xmax,ymax,zmax]]` in **metres**, in the native master-document
saved-zero frame with the complete Model ancestor chain. The native worker
already converted millimetres to metres exactly once and already applied the
appropriate ancestor placement to a copied Shape. This tool applies **no further
rescaling, own/object/ancestor placement or articulation**. It does not substitute
ROS, bench, camera or TCP coordinates.

The fixed, hash-bound policy selects the actual captured
`optimalBoundingBox(False, True)` result: triangulation disabled, shape-tolerance
expansion enabled. The default `BoundBox` result is retained independently.
This is an explicit diagnostic metric choice, not proof that either box encloses
the entire source or physical part. No inflation margin is invented and no
metric is chosen to certify clearance. The maximum observed coordinate-extremum
difference between the two methods is **28.411775 mm**; source representation,
cache and numerical metric differences remain relevant gates.

## Pair results and complete retention

[The resulting study](../hardware/cad/thor-mounted-collision-study-v1.json) records
the following counts at numerical tolerance **1e-12 m**:

| Numerical pair category | Count |
| --- | ---: |
| All unordered pairs | 133,903 |
| Selected optimal-bound overlap/contact candidates | 1,647 |
| Default-bound overlap/contact candidates | 1,692 |
| Candidates in both methods | 1,647 |
| Candidates only in selected optimal bounds | 0 |
| Candidates only in default bounds | 45 |
| No candidate under either numerical method | 132,211 |

All 1,647 selected candidates have interior overlap under this numerical policy;
the generic algorithm also retains tangent/within-tolerance cases. Of these,
1,372 pairs share a root-subassembly label and 275 cross two such labels. Every
pair is evaluated regardless of that metadata. Assembly labels are not a newly
verified rigid-motion or intended-contact classification.

The broad phase compares each interval directly on world X/Y/Z. For axis `i`,
the signed gap is `max(b_min[i]-a_max[i], a_min[i]-b_max[i])`; a positive gap
larger than the numerical tolerance separates those numerical boxes. Every
selected candidate is also checked using the frozen generic `AABB`/OBB SAT
implementation. The actual capture has **zero confirmation disagreements**.
Obvious interval-separated pairs do not incur a redundant SAT call.
At an exact numerical boundary, centre/half-width arithmetic can round differently
from endpoint comparisons. Such disagreements are counted and retained with both
results; they never silently remove an endpoint-policy candidate.

Every selected candidate and all 45 default-only candidates retain **both
methods' three raw interval gaps**, without exclusions. Pair indices resolve to
a registry sorted by exact source `instance_id`; that registry retains both
bounds, their extrema differences, object/root identities and unknown enclosure
status. Sixteen nearest separated numerical witnesses are also retained. These
projection gaps are not exact Euclidean distances, penetration depths or physical
clearances. An omitted pair means only that the selected numerical boxes do not
overlap under this one saved-zero calculation.

There are **no automatic adjacent-joint, motor, bearing, gear or fastener
exclusions**. The intended-contact audit remains incomplete. Bounding boxes
discard holes and surface shape, and many saved assembly interactions may be
intentional. A candidate is a request for more geometric/contact evidence,
not a demonstrated physical collision. The 45 metric-sensitive pairs remain
visible rather than being silently cleared by the selected method.

## Validation and reproduction

The focused tests cover known tangent/intersecting/separated boxes, comparison-
metric counterexamples, complete pair retention and no automatic exclusions.
Negative fixtures reject changed raw hashes, unsupported schema/source/frame/
unit contracts, missing/duplicate/foreign identities, wrong source/root bindings,
qualification promotion, failed/missing native fixtures, erased Touched states,
recompute claims, nonfinite/reversed/missing bounds and changed pair policies.
The actual tracked report reproduces and binds the fixed policy hash.

From `arm-01`, write to a new evidence path:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_thor_mounted_collision_study.py
.\.venv\Scripts\python.exe tools\thor_mounted_collision_study.py `
  --output ..\.work\mounted-collision-study-repeat.json
```

Next work must audit true shape/proxy enclosure and numerical margins, intended
contact pairs and per-body rigid articulation at nonzero configurations. Bench,
bin, tool, held-object, cable and other obstacle geometry remains missing from
this calculation. Discrete saved-zero boxes do not establish swept volumes,
calibration, physical clearance or permission to move or manufacture the robot.
