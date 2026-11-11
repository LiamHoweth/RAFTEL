# Thor-first cost study — partial listings, not a purchase BOM

**Observed:** 2026-11-11. **Decision:** investigate Thor's existing CAD with eight actuators permitted. **Purchasing status:** Researching; nothing approved, ordered or tested. This bounded study identifies current listings and missing costs. It does not replace the provisional [BOM](bom.md) or qualify parts for the pinned assembly.

The [official Thor BOM](http://thor.angel-lm.com/documentation/bom/) links to the three StepperOnline models below, Arduino Mega, generic A4988 drivers, an MG995 servo and [Thor ControlPCB fabrication files](https://www.pcbway.com/project/shareproject/Thor_ControlPCB.html). The [electronics guide](http://thor.angel-lm.com/documentation/electronics/) describes the custom controller and another board option. Official site content was retrieved over HTTP because HTTPS access failed. The selected CAD baseline remains [Thor revision 286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159); website BOM and source revision consistency still need reconciliation.

## Current manufacturer/distributor listing prices

All figures in this table are **USD**, displayed for the indicated quantity on the observation date. They are public listing prices, not checkout quotations or delivered prices. No cart or order was created. Taxes, international shipping, duties, stock reservations and price changes are excluded.

| Item and source | Qty | Listed unit USD | Extended USD | Basis and unresolved fit |
|---|---:|---:|---:|---|
| [StepperOnline 17HS15-0404S](https://www.omc-stepperonline.com/nema-17-bipolar-1-8deg-40ncm-56-6oz-in-0-4a-12v-42x42x39mm-4-wires-17hs15-0404s) | 1 | 9.80 | 9.80 | Official BOM link; current listing says 39 mm motor body, whereas Thor's summary says 40 mm. CAD clearance, shaft fit and winding/drive behavior unverified. |
| [StepperOnline 17HS13-0404S-PG5](https://www.omc-stepperonline.com/nema-17-stepper-motor-bipolar-l-33mm-w-gear-ratio-5-1-planetary-gearbox-17hs13-0404s-pg5) | 3 | 26.91 | 80.73 | Official BOM link; 5:1 geared model. Current listing labels 34 mm motor body while URL retains “33mm”; match full drawing, gearbox and shaft rather than URL wording. |
| [StepperOnline 17HS13-0404S1](https://www.omc-stepperonline.com/nema-17-bipolar-1-8deg-26ncm-36-8oz-in-0-4a-12v-42x42x34mm-4-wires-17hs13-0404s1) | 3 | 8.48 | 25.44 | Official BOM link; 34 mm model; mounting, shaft and cable routing remain unchecked against assembled CAD. |
| **Seven arm-motor listing subtotal** | **7** | | **115.97** | Six arm axes; quantity includes coupled shoulder drive. No dynamic/continuous-duty qualification inferred. |
| [Arduino official US store A000067 Mega 2560 Rev3](https://store-usa.arduino.cc/products/arduino-mega-2560-rev3) | 1 | 34.93 sale | 34.93 | Observed sale versus $49.90 regular. This alone is not the complete Thor controller. Firmware/pin map and shield revision untested. |
| [Pololu A4988 carrier #1182](https://www.pololu.com/product/1182) | 8 | 8.41 at 5+ tier | 67.28 | Genuine priced carrier candidate instead of upstream generic driver link. Thor BOM lists eight; seven arm channels are required and use of the eighth needs reconciliation. Headers require soldering. Physical pin orientation, current-setting method and board clearance unverified. |
| **Motors + Mega + carrier listing subtotal** | | | **218.18** | **Excludes ControlPCB, shield components and remaining system costs.** With regular Mega price: $233.15. |
| [DigiKey / Soldered 555095, MG995 180° reference](https://www.digikey.com/en/products/detail/soldered-electronics/555095/29271419) | 1 | 26.32 | 26.32 | Distributor listing reference, not proof this matches the upstream linked unit. Exact servo provenance, voltage/current, horn fit and gripper performance require qualification. |
| **Partial priced hardware subtotal** | | | **244.50** | **Not a complete controller or complete arm.** With regular Mega price: $259.47. |
| Thor ControlPCB + component assembly | 1 set | Unknown | Unknown | Shared fabrication project is not a current assembled-board quotation. Include PCB minimum order, components, assembly and shipping. |

Motor prices use the displayed base/China-warehouse figures. StepperOnline also showed US-warehouse surcharges of $3.94 for the base motor, $6.75 per geared motor, and $3.91 per small motor: **$35.92 extra** for this motor mix if that fulfillment were available. The geared motor's US stock was shown as backorder; do not assume local delivery. Region selection and fulfillment must be confirmed in a future approved quote.

These are exact **listing identifiers**, a useful improvement over generic “NEMA17,” but not “compatibility verified” parts. Published holding torque is not a running torque curve or thermal-duty demonstration. A4988 chip-family matching alone does not establish that a particular carrier is a safe drop-in for a given shield revision. The Pololu manufacturer page also warns about supply transients and powered motor disconnection; an eventual electrical design must follow the selected driver's actual documentation.

The MG995 label is only a servo reference. It does **not** establish that Thor's jaw geometry provides the parallel-gripper behavior ARM-01 requires. Keep that mechanical requirement open and do not silently budget a different gripper as interchangeable.

## Missing costs and planning sensitivity

The following ranges are **engineering allowances created for this study, not supplier quotations, not upper bounds, and not verified complete counts**. They show why the partial priced subtotal cannot establish a $500 complete build. They assume access to an existing computer, printer, tools and basic assembly capability; buying those is excluded.

| Missing category | Low allowance USD | High allowance USD | Work needed |
|---|---:|---:|---|
| ControlPCB fabrication, board components and assembly consumables | 30 | 80 | Reconcile exact revision and obtain a fully itemized quote; Mega and carrier prices above are excluded here to avoid duplication. |
| Bearings, fasteners, belts, pulleys, couplers and minor mechanical parts | 50 | 120 | Reconcile upstream counts to pinned CAD and exact shaft/seat dimensions. |
| Printed material, support waste and reprints | 30 | 90 | Slice original parts with chosen material/settings; record grams, print time and actual per-kg cost. |
| Enclosed motor supply, gripper regulation and supporting power components | 50 | 100 | Determine exact motor/driver topology, loads and protection; no C001 supply arithmetic reused. |
| Removable metal mount, rated attachment, gravity restraint and independent stop hardware | 80 | 160 | Bench measurements, load study and reviewed protective circuit needed. |
| Wiring, rated connectors/fuses, sensors, cooling and enclosure | 35 | 80 | Reconcile missing upstream items, cooling needs and conductor/connector ratings. |
| Camera, rigid support, bins and calibration materials | 0 | 80 | Low case assumes all suitable items already owned and verified; inventory pending. |
| Contingency, shipping, duties and taxes | 40 | 100 | Obtain destination-specific quotations; actual charges may exceed this allowance. |
| **Additional planning allowance** | **315** | **810** | **Not an orderable list.** |

Using the observed-sale partial subtotal: **$244.50 + $315–810 ≈ $560–1,055**. Using the regular Mega price instead adds $14.97. The original $500 goal is therefore **not demonstrated** by the current study; the upper $725 planning range remains possible only under favorable verified component, reuse and fabrication assumptions. This is sensitivity arithmetic, not a probability forecast or a commitment that the low case can be built safely.

The earlier seven-C001 $501 comparison in `bom.md` is a different architecture and is not part of this total. Do not combine both budgets or transfer servo voltage/current assumptions to Thor.

## Next bounded research actions

1. Reconcile the exact ControlPCB revision, carrier pin/current-setting details, motor-channel map and firmware; quote the remaining controller components or the documented alternative as a **separate complete option**, without counting both.
2. Compare manufacturer motor drawings with the working native CAD assembly; confirm shafts, hole patterns, gearbox envelope and cable clearances before marking any compatibility verified.
3. Slice the original parts, inventory reusable equipment, and price the remaining mechanical/power/mount/stop items. Only then publish a complete candidate BOM for Liam's purchasing review.

Validation performed: upstream BOM hyperlinks extracted; public listing currencies/quantity tiers read; line extensions and subtotal arithmetic checked. No checkout, fabrication quote, motor-driver compatibility test, physical assembly or thermal test was performed.
