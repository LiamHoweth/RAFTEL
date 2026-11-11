# Collision-proxy mathematics and binding gates

K4 is **partially implemented**: reusable AABB/OBB intersection mathematics,
explicit pair policies, synthetic counterexamples and a hash-bound source
coverage audit exist. No mounted Thor collision proxies, conservative enclosure,
robot collision-free pose, physical clearance or swept path is established.
The logical sorter does not use this module.

[The study](../hardware/cad/thor-collision-study-v1.json) binds the exact input
bytes for the 518-leaf mounted inventory, revised wrist membership, frame
manifest, native metric-semantics source audit and relevant implementations.
Inventory/membership revisions, source revision, evidence classes and frames
are checked before reporting coverage. Wrist membership must cover exactly the
same 518 installed identities and bind the inventory's raw SHA-256.

## Why robot proxy coverage remains zero

The current mounted inventory records solid volume, zero-world COM, source
identity and grouping assumptions. It contains no per-leaf full-shape bounds or
source-to-installed full-shape transform ledger. COM and volume cannot recover
an object's shape or orientation. The existing nominal joint chain and limited
proximal native pose checks do not supply all installed shape transforms.

The wrist membership classifies all 518 leaves, but its `MotionStep` chains are
an explicit COM model. Bearing compound classes describe COM behavior without
separating race/cage rigid motion. Uniform circulating belts retain fixed spatial
COM despite material motion. Ideal coupled rotor/jaw declarations remain
conditional. Treating each of these as an ordinary rigid link would introduce
unsupported geometry motion. See [the wrist model](thor-wrist-model.md).

Saved source boxes also do not establish the required enclosure contract here.
Default bounds can depend on surface representation and triangulation/cache
state, and this lane has not independently bounded their numerical enclosure
error. Mesh extrema enclose sampled vertices, which does not establish enclosure
of the full source or physical solid. No source box is labeled conservative and
no inflation margin is invented. See [native metric semantics](thor-native-metric-semantics.md).

The report therefore records **0 verified mounted proxy bindings**, no robot
collision witnesses, and an empty robot pair-exclusion manifest whose audit is
explicitly incomplete. That empty list is not a claim that intended contacts are
absent. Bearings, gears, belts, jaws and other intended contacts need exact pair
identities, reasons and independent evidence before exclusions are applied.
There is no blanket rule skipping adjacent joints.

## API and numerical meaning

`kinematics.thor_collision` uses metres and the existing `thor_frames` validation,
composition and point transforms. An `AABB` stores minimum/maximum coordinates.
`BoxProxy` stores half extents, an explicit expression-frame ID, a proper
`frame_from_box` SE(3) transform and evidence. Enclosure status permits only
`unknown` or `synthetic_exact_box`; neither certifies physical geometry coverage.
Missing or mismatched expression-frame IDs are rejected. A shared supplied ID
does not authenticate registration to a real or source frame. A caller must
provide a declared known transform through `transform_proxy`; missing extrinsics
never become identity.

`intersect_boxes(a, b)` tests the 15 candidate separating directions: three axes
from each box plus nine pairwise edge cross products. Each nonzero axis is
normalized before comparing the projected centre separation with both projected
half widths. Exactly zero cross products add no direction and are skipped;
small nonzero cross products are retained. The maximum signed projection gap
and its unit-axis witness are reported. This quantity is not an exact Euclidean
clearance or penetration depth.

- A gap greater than the explicit numerical tolerance reports `no_proxy_overlap`.
- Other cases report `proxy_overlap_or_contact`, with an interior-overlap or
  within-numerical-tolerance classification. Exact tangency is retained.
- The default tolerance is `1e-12 m`, a numerical comparison choice, not a
  calibrated physical margin. Arithmetic is floating point, without certified
  interval error bounds. Nonfinite/unrepresentable calculations reject rather
  than returning a clearance result.

`screen_proxies` evaluates all declared pairs within an explicit pair-count
budget. `PairExclusion` requires exact distinct identities, a reason and evidence;
unknown and duplicate pairs fail. Even an excluded pair retains its raw geometric
intersection result, making the policy reviewable. No adjacency exclusions are
created automatically. Output always retains `physical_collision_free: null`
and incomplete source/obstacle/swept coverage.

```python
from raftel_arm01.kinematics.thor_collision import AABB, intersect_boxes

# Explicit mathematical fixtures; these dimensions do not describe Thor.
a = AABB((-1, -1, -1), (1, 1, 1)).proxy("cube_a", "fixture", "Synthetic cube")
b = AABB((1, -1, -1), (3, 1, 1)).proxy("cube_b", "fixture", "Tangent fixture")
result = intersect_boxes(a, b)
assert result.relation == "proxy_overlap_or_contact"
assert result.physical_clearance_established is False
```

## Validation and next binding work

The focused suite covers overlapping/tangent/separated AABBs, zero-width boxes,
an OBB pair separated despite overlapping AABBs, and a counterexample requiring
an edge-cross-edge separating axis while all six face directions overlap. It
also covers near-parallel axes, very small/large scales, clean overflow rejection,
pair symmetry, global rigid-frame covariance, exact exclusion policies, pair
budgets, malformed source semantics, input hashes and preserved outputs.

The report's contact/separation scene and nominal-FK cube example are explicitly
synthetic. Their dimensions, obstacle and contact policy are not source-derived
Thor or workstation geometry. The FK example exercises a known mathematical
transform only, without asserting a mounted-body binding.

From `arm-01`, write to a new evidence path:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_thor_collision.py
.\.venv\Scripts\python.exe tools\thor_collision_study.py `
  --output ..\.work\collision-study-repeat.json
```

Next binding work must obtain per-leaf geometry/transform evidence, establish
enclosure and rigid ownership at declared poses, and audit intended contact pairs.
Measured bench/bin/tool/held-object/wiring geometry and common frames are separate
inputs. Discrete proxy tests must then be extended to intersample/swept coverage;
clear endpoints cannot establish an entire path. Source/numerical results cannot
replace physical calibration, contact validation or motion commissioning.
