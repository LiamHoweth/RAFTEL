# Thor static-load analysis

**Evidence class:** analytical model, not a physical payload rating. This study uses Thor-specific geometry and explicit mass/COM evidence where available. It does not import the upstream URDF's placeholder 1 kg link masses or identity inertias. A native CAD solid centroid is a uniform-volume centroid, not necessarily the physical centre of mass of a motor, printed part, fan, bearing assembly or servo.

## Manufacturer mass and actuator evidence

Primary listings checked 2026-11-11:

| Upstream-linked model | Quantity | Listed individual mass | Holding-torque information | Limits on interpretation |
|---|---:|---:|---|---|
| [17HS15-0404S](https://www.omc-stepperonline.com/nema-17-bipolar-1-8deg-40ncm-56-6oz-in-0-4a-12v-42x42x39mm-4-wires-17hs15-0404s) | 1 | 0.290 kg | 0.40 N·m, 0.4 A/phase | Holding torque is not moving/continuous-duty torque. The motor is installed in the stationary base. |
| [17HS13-0404S-PG5](https://www.omc-stepperonline.com/nema-17-stepper-motor-bipolar-l-33mm-w-gear-ratio-5-1-planetary-gearbox-17hs13-0404s-pg5) | 3 | 0.380 kg | Bare-motor holding 0.25 N·m; gearbox ratio 5.18:1, claimed efficiency 90%; gearbox permissible 3 N·m and momentary 5 N·m | Gearbox capacity is not torque the motor can produce. A "5:1" product label must not silently become an exact calibration constant. |
| [17HS13-0404S1](https://www.omc-stepperonline.com/nema-17-bipolar-1-8deg-26ncm-36-8oz-in-0-4a-12v-42x42x34mm-4-wires-17hs13-0404s1) | 3 | 0.230 kg | 0.26 N·m, 0.4 A/phase | Actual drive voltage/current, speed, winding temperature and transmission losses require separate qualification. |

The seven listed motors alone sum to **2.120 kg**, before structure, gripper, bearings, fasteners, wiring and protective equipment. These are supplier-listed masses, not weighed RAFTEL parts. Drawing revisions and exact part fit must still be reconciled with the pinned CAD.

Manufacturer drawings: [base motor](https://files.omc-stepperonline.com/17HS15-0404S_Full_Datasheet.pdf), [geared motor](https://files.omc-stepperonline.com/17HS13-0404S-PG5_Full_Datasheet.pdf), [34 mm motor](https://files.omc-stepperonline.com/17HS13-0404S1_Full_Datasheet.pdf). The accessible full-datasheet PDFs contain dimensions/electrical/holding information, not a complete validated torque-speed/thermal model for the chosen Thor drive. Public pages advertise torque curves; a curve from a different supply, driver, current, gearbox or revision must not be transferred silently.

## CAD-derived mass and load results

The frozen [mounted-geometry ledger](../hardware/cad/thor-mounted-geometry.json) contains **516 installed positive-solid leaves**, with 14 hidden procedural inputs excluded; all selected solid shapes passed native topology validity. Seven motor assets receive manufacturer-listed masses once per complete asset. Their CAD solid centroids are still uniform-volume COM proxies. This model also includes explicit unmeasured masses for fans, controller, switches and servo, and declared density assumptions for printed and metal parts. The servo horn is a separate polymer-density item, not a second 55 g servo.

[The reproducible snapshot](../config/thor-load-snapshot.json) includes the complete per-instance mass-assignment ledger for the 50% scenario. [The load-study report](../hardware/cad/thor-load-study.json) contains three material-fraction cases, four hypothetical poses and 0/100/200 g payload sweeps, plus force/moment reactions and conditional wrist bounds.

| Assumed effective whole-part PLA solid fraction | Modeled mass including stationary base | Shoulder holding magnitude, 200 g horizontal case | Elbow holding magnitude, same case |
|---:|---:|---:|---:|
| 0.35 | 5.002 kg | 5.235 N·m | 2.157 N·m |
| 0.50 | 5.650 kg | 5.828 N·m | 2.342 N·m |
| 1.00 | 7.811 kg | 7.805 N·m | 2.960 N·m |

These are **conditional analytical estimates**, not measured masses, worst-case physical bounds, safe payloads or standard slicer infill percentages. External wiring, future mount/protection changes and physical COM/material errors remain outside the model. The 50% case assigns approximately 1.714 kg to the base and 3.935 kg to the arm above it. In its shoulder-horizontal/200 g case, the ideal base support reaction is approximately 57.37 N upward and 5.27 N·m of opposing moment about the model-origin X axis; this does not size a clamp or attachment.

Native bearing/shaft cylinders corroborate all six unsigned axis lines. The CAD-to-source-model rotation is **Rz(-π/2)**: `(x_ROS,y_ROS,z_ROS) = (y_CAD,-x_CAD,z_CAD)`. Without that conversion the pitch loads would use the wrong axes. Joint signs, hard stops, collision feasibility and physical zero remain uncalibrated. q1–q4 carrying groups are assigned from the root subassembly hierarchy; that rigid-link interpretation is an explicit modeling assumption. The study keeps q5=q6=0 and reports **null** exact q5/q6 self/total torques because their internal moving subsets are unresolved. Nonzero articulation of an unresolved joint is rejected.

For the actual CAD mass sweeps the payload study point is `(0,0,0.7025242557054092)` m, on the two fingers' distal plane and nominal arm axis. This is **not** the upstream URDF's 0.6875 m midpoint, not a calibrated TCP, and not the measured COM of an object. The 200 g shoulder-horizontal payload contribution alone is about 0.982 N·m; all self-mass contributions remain included in the table above. Object overhang can increase the demand.

At q5=q6=0, the 50% mass case yields a triangle-inequality bound on **modeled wrist-group self-mass contributions** of about 0.1352 N·m for joint 5 and 0.0465 N·m for joint 6. It deliberately includes every modeled Art56 mass whether or not that part truly moves with the joint. Payload at the axis-centered study point contributes up to 0.2874 N·m about joint 5 and zero about the roll axis; a 25 or 50 mm radial object-COM offset adds up to 0.0490 or 0.0981 N·m at 200 g. These are conditional model-contribution bounds, not guarantees covering omitted mass, other wrist-fold geometries, dynamic loads or hardware capability. The report keeps those distinctions explicit instead of substituting wrist zeros for unknown loads.

Reproduce the static study without FreeCAD, after installing the Python package:

```sh
python tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --output /path/to/new-cad-load-study.json
python tools/thor_load_analysis.py config/thor-load-snapshot.json --output /path/to/new-upright-report.json
```

The builder records a canonical input-inventory SHA-256 and every assigned mass. The supplied native inventory is sufficient to reproduce the calculation without reopening CAD. New output paths are required, preserving prior evidence.

## Available materials: PLA, PETG and ABS

Liam confirmed the ability to print **PLA, PETG and ABS**. Actual filament brands, formulations, measured density and structural suitability remain unconfirmed. The original PLA fraction sweep and snapshot remain unchanged for traceability. The [separate material comparison](../hardware/cad/thor-material-comparison.json) holds geometry, 50% whole-part solid fraction, pose, motor/hardware/horn masses and payload constant, changing only the printed-material reference density:

| Reference filament / specific source | Density used | Modeled mass | Shoulder / elbow holding magnitude, horizontal 200 g case |
|---|---:|---:|---:|
| [Prusament PLA TDS](https://prusament.com/wp-content/uploads/2022/10/PLA_Prusament_TDS_2021_10_EN.pdf) | 1240 kg/m³ | 5.650 kg | 5.828 / 2.342 N·m |
| [Prusament PETG TDS v1.1, 2022-02-16](https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf) | 1270 kg/m³ | 5.702 kg | 5.876 / 2.357 N·m |
| [Polymaker PolyLite ABS TDS EN v5.5](https://polymaker.com.cn/wp-content/uploads/lana-downloads/PolyLite-ABS_TDS_EN_V5.5.pdf) | 1040 kg/m³ | 5.301 kg | 5.509 / 2.243 N·m |

These are exact reference-product density scenarios, **not generic material specifications or Liam's actual filament**. Other official PolyLite ABS documents, including the older [PIS v1.2](https://polymaker.com/wp-content/tech-docs/PolyLite_ABS_PIS_EN_V1.2.pdf), list 1120 kg/m³; do not mix editions or assume a family name determines density. The CLI accepts an explicit positive finite density plus its source/estimate provenance when the actual material becomes known.

```sh
python tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --compare-materials --output /path/to/new-material-comparison.json
python tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --material PETG --output /path/to/new-PETG-fraction-study.json
python tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --material ABS --material-density-kg-m3 1120 --material-density-source "explicit alternative datasheet/estimate reference" --output /path/to/new-custom-density-study.json
```

Lower modeled mass does not establish a better structural material. Stiffness, creep under sustained load, layer orientation, bearing/shaft fits, thermal exposure and shrinkage/warping need material-specific coupons, fit checks and loaded tests. Material availability does not approve the mount, motor selection, fabrication or operation.

## Conditional wrist COM trajectories

The original snapshot, load study and material comparison remain unchanged baselines. A [separate wrist report](../hardware/cad/thor-wrist-load-study.json) now evaluates the traced [516-leaf membership ledger](../hardware/cad/thor-wrist-membership.json), its [mechanism evidence](thor-wrist-mechanism.md) and the [COM Jacobian model](thor-wrist-model.md). The ledger distinguishes 47 tool/roll leaves, seven fold-carrier leaves, ten side-rotor leaves, two bearing COM approximations and 450 upstream leaves. The same 515 mass records and seven motor masses are conserved; a purchased asset spanning multiple motion classes is rejected rather than arbitrarily divided.

The tool chain folds then rolls about the carried roll axis. Side rotors spin about their own common fold-axis line with declared angles `q5 ± 2*q6`; they do not follow a simple downstream rigid-body set. The report evaluates both unresolved bevel-handedness alternatives at four poses, including nonzero fold/roll, for all three reference materials at 50% whole-part fraction. Each final COM is carried through q1–q4 before evaluating proximal moments. Wrist contributions use `external generalized gravity torque = sum(m_i*g · dCOM_i/dq)`; holding has the opposite sign.

These outputs are **conditional modeled COM contributions**, not complete wrist holding demands. Art4 motor internals and traveling belts remain undecomposed, bearing race motion/inertia is not represented, jaws are frozen, and physical signs/limits are uncalibrated. Full q5/q6 arm and holding torques therefore remain **null**, including in the new report. The new contribution field must not be substituted for those null totals.

For an illustrative PLA pose with q2=90°, q5=45°, q6=30° and other coordinates zero, the two sign alternatives yield modeled q5 gravity contributions about +0.08316/+0.08306 N·m and q6 contributions about −0.007392/−0.007235 N·m. These are arm COM contributions only; payload moments remain separate. The same model with 200 g payload gives shoulder/elbow holding magnitudes about 5.696/2.210 N·m. These pose-specific conditional values do not qualify the arm or a motor. Material density sources are carried into every case; actual filament properties remain unknown.

```sh
python tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json --wrist-membership hardware/cad/thor-wrist-membership.json --output /path/to/new-wrist-load-study.json
```

The CLI checks the inventory file SHA-256 against the membership's source digest. The report records canonical membership and inventory hashes. Tests conserve mass and manufacturer motor totals, reject duplicate/mixed-class assignments, preserve the zero-wrist proximal baseline and compare all six generalized COM moments against finite differences of potential energy for both handedness branches.

The [separate elbow transmission analysis](thor-elbow-loads.md) consumes the unchanged baseline q2/q3 loads and explicitly maps the remote motor's carrier coupling into shoulder reaction and shaft effort. Its [mechanism evidence](thor-elbow-mechanism.md) keeps the smooth-drum pitch radius, routing sign and load-sharing assumptions visible. A source controller channel effort is not automatically a physical motor torque.

## Installed mass belongs to the carrying link

All three geared-motor installed links occur in `AssemblyArt1::Model`, upstream of the shoulder pitch coordinate. Thor remotely transmits elbow motion; do not place an elbow motor at the elbow simply because it drives that joint. `AssemblyArt3` contains one installed 34 mm stepper, and `AssemblyArt4` contains two. Motor roles and carried mass are different concepts.

Use paths beginning at the master `Assembly::Model` and recurse only through its installed assembly members. Library objects/prototypes can coexist in the same document. Repeated source-body names may represent legitimate repeated instances, but each **instance path** must be counted once. Do not sum a compound plus all its children, or a PartDesign body plus its feature history.

## Calculation and input contract

`tools/thor_load_analysis.py` evaluates a single explicit world-frame snapshot:

```text
external gravity torque at joint j = a_j · Σ[(c_i - o_j) × (m_i g)]
ideal holding torque = -external gravity torque
```

Here `a_j` is a unit revolute axis, `o_j` is a point on that axis, `c_i` is a downstream body's COM, and gravity is `(0,0,-9.80665)` m/s². Only bodies downstream of the joint enter its sum. All positions are metres and all masses kilograms. The snapshot requires six distinct joint axes, unique mounted-instance paths, a declared frame, mass/COM provenance, explicit complete/partial coverage and named omissions. Invalid/duplicate inputs fail before calculation.

Run from `arm-01` with a traceable generated snapshot:

```sh
python tools/thor_load_analysis.py /path/to/snapshot.json --output /path/to/new-report.json
```

The output reports arm gravity torque and payload increments separately for 0, 100 and 200 g at the supplied tool point. It preserves incomplete coverage and source evidence. A partial mass model is not a guaranteed lower or upper torque bound: omitted masses can add signed moments or cancel existing ones. A favorable upright pose is not a worst-case load result. No output qualifies an actuator, and no input here authorizes motion.

## Pose sweep and supplemental payload check

`articulate_snapshot()` rotates a supplied zero-pose COM/axis snapshot through a declared proximal-to-distal joint tree. It uses explicit downstream membership and Rodrigues rotations, preserves the input, and rotates later joint axes and the tool point with the chain. This does not resolve a wrong CAD-to-model frame or unknown attachment: zero pose, axis lines, link membership and source version must be reconciled first. A pose sweep is analytical sensitivity, not proof that any pose is collision-free or within physical stops.

A self-contained supplemental command tests the pinned **nominal upstream URDF** geometry without pretending its placeholder inertias are real:

```sh
python tools/thor_load_analysis.py --nominal-payload-increments
```

For a hypothetical 90° shoulder pose and 200 g payload at that source model's gripper midpoint, the incremental holding-torque magnitudes are approximately **0.9522 N·m at joint 2**, **0.6384 N·m at joint 3**, and **0.2579 N·m at joint 5**. The source shoulder-to-tool moment arm is 485.5 mm in that pose. These numbers explicitly exclude **all robot self mass**, do not reconcile the physical TCP, and must never size an actuator. They are useful as an independent payload-increment check when full CAD mass scenarios are added. The program also reports upright, elbow-horizontal and shoulder/elbow 45° examples, each marked unverified for physical pose feasibility.

## Printed mass scenarios

For a declared material, estimate `mass = CAD volume × material density × effective whole-part solid fraction`. Convert mm³ to m³ explicitly. [Prusament's PLA technical sheet](https://prusament.com/wp-content/uploads/2022/10/PLA_Prusament_TDS_2021_10_EN.pdf) lists typical density 1.24 g/cm³ (1240 kg/m³); that can support a **declared PLA sensitivity scenario**, not a claim that Liam owns or will use that filament.

Effective whole-part solid fraction includes perimeter walls, skins, infill and internal geometry. A slicer's "20% infill" setting is not a 20% whole-part solid fraction. Uniform-density COM is only a proxy when fill is distributed unevenly. Replace scenarios with slicer mass estimates, weighed components and measured assembly COM as those become available. Do not call scenario variation a statistical confidence interval or a guaranteed physical bound.

## Coupled drives and capacity gate

The nominal continuous channel convention has a virtual-work dual implemented as `nominal_channel_efforts()`. It returns generalized efforts conjugate to the source's GRBL coordinate values, **not motor shaft torques**. The caller must explicitly choose shoulder load sharing. Equal commanded coordinates do not guarantee equal load, and no default 50/50 physical split is assumed. Wrist sum/difference effort mapping must also be combined with actual transmissions, efficiencies, friction and preload before assessing shafts or motors.

Before a payload limit can be released, resolve full carried mass, joint/transmission geometry, physical stops, gearbox/belt/printed-gear capacity, both shoulder drive paths, moving torque-speed curves under the selected driver/supply, thermal duty, acceleration, cable forces, backlash and structural deflection. Use physical stop/holding-loss safeguards during eventual supervised validation. The 3 N·m gearbox number and advertised holding torques cannot close these gates by themselves.

## Verification of the calculation

Focused tests independently check a known 0.2 kg × 0.35 m moment, finite differences of gravitational potential, zero gravity torque about a vertical axis, downstream membership, metre/mm³ conversion, whole-asset motor deduplication, servo-horn classification, explicit unknown wrist membership, coupled-drive virtual work with unequal shoulder sharing, nonfinite input, duplicate instances and explicit mass coverage. These establish algebra/input handling, not physical robot performance.
