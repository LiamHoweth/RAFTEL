# Hash-bound Thor scenarios and ideal-jaw gravity

The [versioned manifest](../config/thor-scenario-v1.json) binds the revised 518-leaf geometry inventory, wrist membership, moving-mass evidence and [jaw body ledger](../hardware/cad/thor-jaw-body-ledger.json) to exact file SHA-256 values. It declares source revisions, SI units, nominal ROS frame, density/fraction assumptions, two belt masses, payload point and twelve named pose/jaw cases. This is **conditional analytical evidence**, with no native recompute, hardware backend, actuator rating or fabrication release.

The [separate study](../hardware/cad/thor-scenario-study-v1.json) preserves the original frozen-jaw studies unchanged. Its four saved configurations have no solved common jaw coordinate. Eight additional cases evaluate the explicit ideal jaw overlay at mathematical closing angles 0° and 60°, for the same four arm poses and fixed 200 g payload point. These are sample configurations, not validated physical travel, contact, retention or collision-free poses. Each sampled extremum names its witness case and remains a sampled value.

## Reproduce and detect stale inputs

After installing the package, run from `arm-01`:

```powershell
python tools/thor_scenario_analysis.py config/thor-scenario-v1.json --output /path/to/new-report.json
```

Choose a fresh output path; the CLI refuses to overwrite an evidence file. `--project-root` allows a separately retained copy of the bound input tree. No FreeCAD, ROS, network or camera is needed. The report's public Python API also verifies bound files internally before generating results.

Input SHA-256 values hash **raw file bytes**. A newline-only edit therefore makes a binding stale. The report's separate canonical manifest SHA-256 hashes normalized validated JSON, independent of indentation. Duplicate JSON keys, nonfinite values, path escapes, missing inputs, changed source revisions, mismatched inventory/membership hashes, omitted belt overrides and unknown required provenance fail explicitly. Rebinding a derived input requires reviewing the changed evidence and creating an appropriate scenario revision; replacing a digest alone does not qualify the changed model.

The scenario builder reuses `tools/thor_load_analysis.py` for mass classification, purchased-asset consolidation, wrist articulation and arm gravity. It checks 517 mass records and seven complete motor assets totaling 2.120 kg before applying jaw motion. The `mass_record_identity_sha256` hashes the complete ID-to-mass map; it is invariant under the jaw overlay. The current 50% effective whole-part PLA reference scenario remains **5.6547224855756 kg** including stationary base, with all material and COM assignments unmeasured. Whole-part fraction is not slicer infill percentage.

## Coordinate and jaw-body contract

`engineering/jaw_loads.py` consumes the [source-audited jaw map](thor-jaw-body-reconciliation.md). Its native zero-arm COM states convert to the nominal load frame using `(x,y,z)_ROS=(y,-x,z)_CAD`, replacing COM coordinates only. Ten translating and eight rotating jaw records remain part of the roll tool. The other 48 Art56 records retain their saved jaw-relative COM, while their existing wrist classes still determine fold/roll motion. The upstream 451 mass records retain their existing values and motion declarations. No body is added, removed, reweighted or split; the 55 g whole-servo allowance and separate horn record remain distinct.

Ideal q=0 is intentionally different from the saved assembly: driven phases are normalized and the active pivot shifts 15 micrometres toward the symmetric model. This is an explicit conditional alignment proposal, not a native realizability or repaired-loop claim. In saved mode, the exact saved COMs remain and the common jaw effort stays **null**, rather than reporting a fictitious measured zero.

For the ideal overlay, the jaw COM derivative rotates through the existing proximal-first wrist motion and the q1–q4 nominal arm orientation. Gravity gives:

```text
external jaw generalized gravity effort = sum(m_i * gravity dot dCOM_i/dqjaw)
ideal jaw holding effort = -external effort
```

This effort is conjugate to the mathematical closing coordinate, **not an MG995 shaft torque, servo current or grip force**. The payload study point stays fixed relative to `roll_tool`, independent of jaw angle. It models no object movement, pad contact or load transfer as jaws close. The existing full physical wrist holding fields remain null; separate conditional modeled fields retain all prior balance, uniform-belt and bearing-COM assumptions.

For example, in the selected shoulder-horizontal pose, ideal closure from q=0 to 60° changes modeled shoulder holding magnitude by approximately **0.006995 N·m** while preserving total mass. That difference depends on the declared jaw ownership, source COM proxies and density/allowance scenarios. It does not establish useful stroke or safe payload.

## Inertia preparation and open gates

`engineering/inertia.py` supplies uniform box/cylinder fixtures, centroidal tensor validation, proper frame transforms and mass/COM aggregation with parallel-axis terms. It rejects nonsymmetric, indefinite and physically impossible principal-moment combinations, including at microscopic SI scales. An unknown constituent tensor propagates to an unknown aggregate tensor. A known purchased mass or a uniform whole-part print fraction is never silently promoted to measured internal inertia.

Native cached-solid extraction now supplies source-bound centroidal **geometric** tensors on this Windows host. The [selected-eight capture](../hardware/cad/thor-native-solid-properties-v1.json) and [matching normalized-validator replay](../hardware/cad/thor-native-solid-properties-normalized-v1.json) establish native primitive semantics and preserve identical selected geometry. The separate [full printed-asset capture](../hardware/print-planning/thor-full-print-export-native-v1.json) covers 47 cached geometry variants representing 65 installed printed instances. The [native property notes](thor-native-solid-properties.md) explain storage frames, units, validation and preservation.

M3 remains partial because these are separate saved-BRep storage-frame tensors, without verified cross-asset transforms into installed body frames or a whole-arm dynamic model. This scenario report does not consume or aggregate those native tensors. Physical density, nonuniform-print distribution and purchased internal inertia remain unknown; geometric extraction does not close those gates. The tested generic algebra can integrate appropriately transformed, evidence-bound inputs once those contracts are established.

The most useful follow-on measurements are:

1. Reconcile the jaw pivot/phase and fastener retention choices in a copied native assembly, then independently verify loop closure and interference across proposed positions. The ideal overlay cannot close this gate.
2. Obtain actual printed-part/whole-asset masses and COMs, filament density and per-part slicer data. Replace explicit assumptions with evidence-bearing measurements while conserving each installed asset once.
3. Supply physical stops, calibrated signs/zeros, belt pitch/traction and matching moving torque-speed/thermal data before turning modeled efforts into actuator or structure capacity claims.

Focused tests compare all six arm plus ideal-jaw gravity efforts against independent finite differences of whole-ledger gravitational potential, including payload and both wrist phase alternatives. Separate tests check transformed COM derivatives, all mass IDs and motor totals, stale provenance, negative CLI cases, primitive inertia, geometric scaling, energy quadratic forms, frame covariance and unknown-property propagation. These establish the declared mathematical model and input handling only.
