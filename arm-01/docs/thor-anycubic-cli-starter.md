# Anycubic PLA starter projects — November 12, 2026

The owner confirmed an awake/unlocked desktop, loaded PLA and a 0.4 mm nozzle.
Fresh Sky captures still timed out after window reselection and a JavaScript
kernel reset. Live GUI import/Preview remains unobserved. The installed
**Anycubic Slicer Next 2.0.0.3** nevertheless has a working offline CLI: actual
project export and slicing succeeded with isolated data directories and copied
profiles. This supersedes the earlier *unverified* CLI-capability result without
changing its historical observations.

## Delivered files

Folder: `C:\Users\howet\Desktop\RAFTEL Prints\2026-11-12 Starter\Sliced PLA 0.4\`.

| Job | Native project | Native estimate | Quantity |
| --- | --- | --- | --- |
| Main starter | `STARTER_8_PARTS_PLA_04mm.3mf` plus matching G-code/sidecar | 10 h 48 m 43 s; 211.14 g | Four common bearing retainers, base bearing ring, base top, nominal finger and distinct reflected finger |
| Optional fit check | `Optional fit check/OPTIONAL_FIT_CHECK_1_RETAINER_PLA_04mm.3mf` plus matching G-code/sidecar | 4 m 10 s; 0.98 g | One of those same retainers, not a ninth required part |

Open the native file **as a project**, preserving its saved settings. Review
Preview before printing. If the optional printed retainer is kept, remove one
common retainer from the main project and re-slice to avoid duplicating it.
No printer was connected, uploaded to or started. The source generic packages
remain separate; the delivered folder also retains the original eight-copy
source and its attribution/metadata. Large native projects and G-code remain
local, not in Git.

## Saved process and actual warnings

The saved machine is the non-V2 Kobra 3 Max / 0.4 mm profile. These are prototype
fit settings: PLA; 0.20 mm layers; four walls; 40% gyroid; five top/bottom layers;
automatic tree support from the build plate; automatic brim; by-layer printing;
one filament. The selected surface is **Textured PEI Plate**, assumed from the
saved code-4 selection, not physically inspected. Actual filament brand remains
unknown. No dimensional compensation was added.

The final files specify **55°C bed**, **220°C first-layer / 210°C later nozzle**.
Both actual final warning lists are empty. Original 65°C and trial 60°C outputs
retain warning `1000C001`; their warnings were not removed from the files.
The unchanged PLA vitrification field is 60°C. The pinned upstream
[warning implementation](https://github.com/ANYCUBIC-3D/AnycubicSlicerNext/blob/6103ed8b511609658d00d0538cc7f0609cdb57da/src/libslic3r/GCode/GCodeProcessor.cpp#L5037)
checks `highest_bed_temp >= vitrification_temperature`, explaining why 60°C
still warned. The selected bed temperatures were lowered; the warning threshold
was not changed. This software-source reference does not establish an exact
public-source match for the installed binary.

## Actual verification and limits

The [curated receipt](../hardware/print-planning/thor-anycubic-cli-starter-v1.json)
pins both outputs, seven retained native invocations, copied profile/source
records and the desktop delivery. Native elapsed time totals **86.2885324 s**.
Runtime, source packages, all six bundled profile files and the bound global
configuration remained hash-identical across their respective execution ledgers.
Original CAD/history were not opened or modified.

The source-to-native semantic join uses `source_object_id`, native parent
resource ID and root build; XML object order changes between exports. All eight
source identities, **7,524 vertices / 15,112 triangle indices and winding**,
including the distinct reflected finger, survive. All mesh-repair counters are
zero. The 55°C and 60°C native saved geometry agree exactly after this join.

**Exact equality to the generic source does not pass.** Native coordinate
recentering/serialization produces a maximum placed-coordinate residual of
**1.003137207e-6 mm**. An exploratory fixed 1e-6 diagnostic was exceeded and is
explicitly retained. A separate numerical diagnostic uses one float32 ULP at
each saved local coordinate range plus 1e-7 mm translation serialization budget;
all eight rows are within that budget. This does not waive an existing CAD
migration gate, prove continuous-surface equivalence or establish physical fit.

Embedded G-code equals the external files and recorded MD5s. Eight actual
object definitions/start identities have positive extrusion moves; all linear
deposition endpoints stay inside the provisional bed. No deposition arcs occur.
The main footprint is X=23.21..342.741 / Y=20.21..259.779 mm, Z=0.2..27.6 mm.
The fit job is rotated only in XY and measures 15.78036308 × 30 × 4 mm.
Opaque vendor start/end macros and hardware behavior were not validated.

**81 focused host tests pass**, and an independent read-only specialist accepted
the actual outputs, source joins, settings, warnings, hashes and footprints.
Native GUI rendering, physical fit, PLA creep/strength, calibrated flow,
structural/load-bearing qualification and fabrication release remain separate.

## Reproduction route

Retained run arguments are under
`.work/anycubic-desktop-planning/session-2026-11-12-02/`. Use the installed EXE
with a fresh `--datadir`, copied flattened `--load-settings` machine/process,
copied `--load-filaments`, `--slice 0`, `--ensure-on-bed`, a **bare filename**
for `--export-3mf`, and a separate `--outputdir`. Main uses `--arrange 0` to
retain the reviewed layout; the fit check uses `--arrange 1`.
No DLL ABI wrapper or GUI automation bypass was used. Inspect actual output;
an exit-zero `--help` result alone still proves neither export nor slicing.
