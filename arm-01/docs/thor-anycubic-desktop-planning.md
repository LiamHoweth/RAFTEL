# Anycubic desktop inspection plan

**Latest checkpoint:** stopped for the night at the owner's request on
November 11 at approximately 21:15 America/Chicago. The owner confirmed the app
was visible and maximized, but fresh Sky capture still timed out and coordinate
input remained unavailable. Accessibility could read Home; keyboard Open
produced a picker, but filename entry, model import and native Save As were not
verified. Computer Use was stopped with Escape; no further UI input followed.
The final picker/scene state is unobserved and must be preserved on resume.
See the [swarm checkpoint](../../docs/arm01-swarm-checkpoint-2026-11-11.md).

The new [project auditor](thor-anycubic-project-audit.md) and source-to-saved
mesh/profile tools passed host/source review, but still need an actual freshly
saved Anycubic project. They do not turn the generic source draft into GUI
acceptance. No upload, printer start, physical fit or fabrication is approved.

## Earlier desktop observations

The installed Anycubic Slicer Next was opened during this desktop run. Window
capture timed out while the desktop was unavailable; **no model import,
rendered plate, native project save or slice has yet been observed**. At
23:10 UTC Liam estimated returning in about an hour; actual desktop-ready
confirmation remains pending. This record distinguishes actual observations
from the prepared inputs below.

At **01:07 UTC**, a fresh read-only inventory showed the slicer was no longer
running. Root reopened the already-installed app using its returned Sky app ID;
a new window appeared. Its first fresh screenshot request again failed with
`window capture timed out: timed out waiting on channel`. No model/project input
was sent after that launch, and UI attempts stopped. The app was left open;
its current scene remains unobserved. The error alone does not identify its
cause. No lock/authentication UI or power/security setting was operated.

## Prepared first inspections

The files are under the retained local directory
`.work/full-print-native-drafts/run-001/` in this checkout. Each generic 3MF has
one object, millimetre units, unchanged source-Z-up rotation and bottom placement
at z=0. Source origin, exact geometry, attribution and copy counts are retained.
Import one at a time initially; do not interpret another campaign's copy of the
same part as additional installed quantity.

| Order | Project filename | Recorded X × Y × Z, mm | Variant copy count | Inspect |
| --- | --- | --- | --- | --- |
| 1 | `DRAFT_full_native_print-39-commonbearingfix-body-nominal_01-of-04.3mf` | 30 × 15.780363083 × 4 | 1 of 4 | Scale, bed contact and bearing/fastener access |
| 2 | `DRAFT_full_native_print-34-basebearingfix-body-nominal_01-of-01.3mf` | 149.951110840 × 149.975555420 × 5 | 1 of 1 | Thin ring and hole access |
| 3 | `DRAFT_full_native_print-38-basetop-body-nominal_01-of-01.3mf` | 149.951110840 × 149.975555420 × 27.5 | 1 of 1 | Steps, overhangs and bores |
| 4 | `DRAFT_full_native_print-44-gripperfinger-body-nominal_01-of-01.3mf` | 18.5 × 60 × 15.5 | 1 of 1 | Pivot, contact face and layer direction |
| 5 | `DRAFT_full_native_print-45-assemblyart56-unnamed1_gripperfinger_mirrored-reflected_01-of-01.3mf` | 18.5 × 60 × 15.5 | 1 of 1 | Distinct saved handedness against the nominal finger |

The dimensions shown are rounded for reading. The queue receipt and model
coordinates retain original precision. These are inspection candidates; no
stable orientation, support strategy or physical fit is accepted by this list.

## Independently reviewed combined inspection plate

A separate local generic draft is ready at
`.work/anycubic-desktop-planning/plate-001/DRAFT_INSPECTION_eight_native_copies_source_Z_up.3mf`.
It contains the four CommonBearingFix copies, one BaseBearingFix, one BaseTop,
the nominal finger and the actual saved reflected finger: **eight existing
installed identities**, reused from the 61-project queue. This is another
representation of that subset, without eight additional parts in the inventory.
Its SHA-256 is
`68f4e0b621b3552b80e673125ab6eb98352e795b2bfa063ef9a7cc154f313bbb`.

The [curated artifact receipt](../hardware/print-planning/thor-anycubic-inspection-plate-v1.json)
binds the ignored raw receipt, separate one-off composer, original projects and
complete retained metadata/native provenance. The original production writer
and inspector have a one-object contract and were not used to claim validation
of this multiobject package. A separate reviewer parsed the actual OPC/Core
package and compared all **8 resources/build items, 7,524 vertices and 15,112
triangles**, including indices and winding, exactly against the eight sources.
All complete original metadata/license maps match. All 63 files in the original
queue directory remain byte-identical.

Only XY placement changes; identity rotation, source-Z-up and each original
bottom-to-z=0 correction remain. All 28 mesh-AABB pair distances and the minimum
margin inside the provisional X=3..423/Y=0..420 mm rectangle are **at least
20 mm**. Those are mesh-box inspection spacings, without qualified supports,
brims, purge or toolhead clearance, adhesion or stable contact. This is bounded
artifact verification, not full 3MF certification or observed slicer behavior.
The unchanged single-object projects and fallback receipt remain available.

## Live-session procedure and evidence

1. Re-select the actual returned slicer window and obtain a fresh visible
   capture. Stop if the desktop remains locked or capture/input fails. Observe
   and preserve any existing unsaved/recovered scene before loading a draft;
   do not assume the last home screen or an old window ID is current.
2. Import the first generic model as geometry. Check units, object count,
   dimensions, bed position and any repair warning. A repair warning remains
   evidence; do not silently replace the retained source geometry. After that
   scale check, inspect the combined draft for all eight distinct objects and
   its proposed placements; successful import is a separate observation.
3. Observe the current machine, nozzle, material and process selectors. The
   [saved audit](thor-local-slicer-profile-audit.md) is software evidence of
   Kobra 3 Max / 0.4 mm / PLA / 0.20 mm Standard, without physical confirmation.
4. Inspect bed contact, holes and unsupported surfaces; keep orientation and
   support choices provisional. Save only fresh `DRAFT_` projects beneath
   `.work/anycubic-desktop-planning/`, preserving the generic inputs and unrelated
   user projects.
5. An offline slice, if performed, is an assumed-process estimate. Record its
   actual settings, warnings, mass/time estimates and unresolved inputs. It does
   not qualify load-bearing parts or release fabrication.

No printer connection, upload, print start, motion, flashing or fabrication
release is part of this plan. Current 61 native-origin drafts, two separate
source-optodisk drafts, fit coupons and orientation studies remain distinct;
see the [evidence index](desktop-evidence-index.md).
