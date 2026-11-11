# Thor actuator feasibility checkpoint

**Status: not qualified for moving operation or a released payload.** This pass identifies exact motor evidence and the conditions still missing from an actuator comparison. It does not select a purchase, change drive settings or enable motion. Access date: 2026-11-11. The [machine-readable record](../hardware/cad/thor-actuator-capacity.json) separates supplier specifications, document conflicts, analytical demand and unavailable evidence.

## Exact models and published conditions

| Installed role | Exact manufacturer model | Electrical reference | Published static reference |
|---|---|---|---|
| Base, one | [17HS15-0404S](https://www.omc-stepperonline.com/nema-17-bipolar-1-8deg-40ncm-56-6oz-in-0-4a-12v-42x42x39mm-4-wires-17hs15-0404s) | 0.4 A/phase, 30 ohm, 58 mH | 0.40 N·m holding |
| Two shoulder branches and remote elbow, three | [17HS13-0404S-PG5](https://www.omc-stepperonline.com/nema-17-stepper-motor-bipolar-l-33mm-w-gear-ratio-5-1-planetary-gearbox-17hs13-0404s-pg5) | 0.4 A/phase, 27 ohm, 28.5 mH; nominal gearbox 5.18:1 | 0.25 N·m **without gearbox**; gearbox permissible 3 N·m, momentary 5 N·m |
| Forearm and wrist drives, three | [17HS13-0404S1](https://www.omc-stepperonline.com/nema-17-bipolar-1-8deg-26ncm-36-8oz-in-0-4a-12v-42x42x34mm-4-wires-17hs13-0404s1) | 0.4 A/phase, 30 ohm, 37 mH | 0.26 N·m holding |

These are listing/drawing references, not measurements of owned motors. No motor serial/revision or selected supply, carrier revision, current waveform, microstep mode, cooling, target speed/acceleration or duty schedule has been verified.

The current manufacturer drawings are [A0616 revision 0, date printed 8.1.2025](https://files.omc-stepperonline.com/17HS15-0404S_Full_Datasheet.pdf), [A0581 revision 0, date printed 2.27.2026](https://files.omc-stepperonline.com/17HS13-0404S1_Full_Datasheet.pdf), and [PG5 drawing, date printed 1.9.2023](https://files.omc-stepperonline.com/17HS13-0404S-PG5_Full_Datasheet.pdf). Each gives ambient −10 to 50°C, class B 130°C insulation and maximum temperature rise 80°C; the PG5 explicitly states standstill with two phases energized. These limits are not a permissible external printed-part temperature or a continuous-duty robot test. The base drawing additionally lists dynamic axial 10 N and radial 21 N at 20 mm shaft length. The PG5 lists shaft axial 50 N and radial 100 N without an extracted load-position condition. The S1 drawing's rotor inertia and weight fields are blank; do not fill them from another variant.

## Running torque evidence and unresolved conflict

The manufacturer [legacy PG5 torque-curve PDF](https://www.omc-stepperonline.com/download/17HS13-0404S-PG5_Torque_Curve.pdf) is text-readable through the web index and says maximum permissible torque **2 N·m**. That conflicts with the current product/drawing's **3 N·m**. Its extracted text identifies 200 microsteps and a speed axis, but does not supply reliable torque ordinates, current, voltage, driver or thermal test conditions. This pass could not inspect its graph: screenshot retrieval failed and direct PDF downloads returned HTTP 403. Therefore no curve was digitized, byte hash claimed or running margin calculated. This conflict requires manufacturer revision confirmation rather than choosing the larger number.

The current exact-model pages say torque curves exist but expose only full datasheets in their download sections. Direct manufacturer curve URLs for the base and S1 were not retrievable in this pass. Curves for similarly named HG/CG motors and mirrored S1 documents were deliberately excluded from capacity calculations. The full datasheets' life-test statements at 24 V/300 RPM do not specify available torque or qualify this arm's duty.

## Conditional demand comparison

The unchanged [elbow study](thor-elbow-loads.md) uses an unmeasured 37 mm effective-radius scenario, carrier coefficient +1, same-sense routing and a 50/50 shoulder split. Its baseline 200 g shoulder-horizontal demands are:

| Quantity | Ideal static demand magnitude |
|---|---:|
| Remote elbow rotor | 0.077803 N·m |
| Remote elbow gearbox output | 0.403019 N·m |
| Each shoulder rotor, only under assumed equal sharing | 0.087274 N·m |
| Each shoulder gearbox output, before printed 6:1 stage | 0.452081 N·m |
| One shoulder rotor supplying the whole residual, scenario only | 0.174549 N·m |
| Elbow belt tension difference | 63.306 N |

These demands may be listed beside supplier static quantities, but their ratios are **not running, thermal or safety margins**. Friction, acceleration, reflected inertia, cables and shoulder circulating preload are absent. Belt tension difference is not the radial shaft load, which also depends on span directions, mean tension, pulley overhang and support. Do not subtract 63.306 N from a 100 N shaft number to claim bearing reserve. Full wrist holding totals remain unresolved in the existing wrist report, so those motors cannot receive a complete feasibility result yet.

## Driver and capacity closure

The priced [Pololu A4988 carrier #1182](https://www.pololu.com/product/1182) is only a candidate. Its manufacturer specifies an 8–35 V motor supply, adjustable current, and `Imax=Vref/(8*Rcs)`. Full-step coil current is approximately 70% of the set limit; supply current is not coil current. Thus “0.4 A motor” and “0.4 A current-limit setting” do not automatically reproduce a two-phase holding specification. Confirm the actual carrier/sense resistors and phase peak/RMS waveform before comparing torque; no setting is prescribed here.

A reviewable moving-capacity result needs: exact purchased motor/gearbox revisions and reconciled permissible rating; full pull-out curves with supply/driver/current/microstep/test-temperature conditions; a declared joint speed/acceleration/duty envelope mapped through the coupled transmission; friction, compliance and inertia demands; gearbox speed/duty and shaft-load conditions; cooling and motor/driver temperatures; and printed gear/belt/clamp limits. A later supervised test plan must include loss-of-holding behavior and restraint, but no powered test is performed by this study. Until these inputs exist, moving torque, continuous duty and safe payload remain explicit unknowns.
