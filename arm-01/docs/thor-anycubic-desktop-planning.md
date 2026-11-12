# Anycubic desktop inspection plan

The installed Anycubic Slicer Next was opened during this desktop run. Window
capture timed out while the desktop was unavailable; **no model import,
rendered plate, native project save or slice has yet been observed**. Liam
expects to return around 00:10 UTC November 12. The live session remains pending
an awake/unlocked desktop. This record will distinguish actual observations
from the prepared inputs below.

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

## Live-session procedure and evidence

1. Re-select the actual returned slicer window and obtain a fresh visible
   capture. Stop if the desktop remains locked or capture/input fails.
2. Import the first generic model as geometry. Check units, object count,
   dimensions, bed position and any repair warning. A repair warning remains
   evidence; do not silently replace the retained source geometry.
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
