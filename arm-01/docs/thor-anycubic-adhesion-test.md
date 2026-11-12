# Single-retainer adhesion diagnostic — November 12, 2026

The owner reports parts detaching and sometimes becoming spaghetti. The exact
failed files, actual temperatures and first-layer photographs have not been
observed, so the root cause and any causal role of the earlier 55°C draft remain
unknown. The later owner screenshots do confirm loading the eight-part project
in Prepare with its PLA/0.4 and Textured PEI selectors; they do not show the
physical surface or a successful first layer. A warning-free slice was not
physical adhesion validation.

A separate one-retainer diagnostic is delivered at
`C:\Users\howet\Desktop\RAFTEL Prints\2026-11-12 Adhesion Test\ADHESION_TEST_ONE_RETAINER_60C.3mf`,
with matching native G-code, instructions, preserved original source and notices.
Open as a project. Estimated **5m45s / 1.16 g**. The original eight-part and
optional fit files remain unchanged; the retainer is already one of those eight
installed identities and must not be counted twice.

Changes from the 55°C fit draft: **60°C bed**, **20 mm/s first-layer outline and
infill** instead of 45, **8 mm forced outer brim** instead of auto/5 mm configured.
Nozzle remains 220°C first / 210°C later, 0.20 mm layers, first-layer part cooling
off. No manual Z-offset correction or geometry edit was made. These are a
diagnostic starting point; filament brand/range and actual surface remain
unverified. Anycubic's [Kobra 3 Max adhesion guide](https://wiki.anycubic.com/zh/fdm-3d-printer/kobra-3-max/model-non-stick-printing-platform)
recommends cleaning, brim adjustment and leveling; its
[general print-quality guide](https://wiki.anycubic.com/en/fdm-3d-printer/common/print-quality)
recommends a slower first layer and lists a 55–65°C PLA bed range.

Before testing, the owner should clean the cooled removable sheet with water
and detergent, rinse/dry completely, reinstall it flat, preheat and enable/run
leveling with the sheet installed. Observe the first layer; if it releases,
stop the test and photograph it before guessing at nozzle-height adjustments.
Pause full-batch attempts until a small print holds and the failure is understood.

The [receipt](../hardware/print-planning/thor-anycubic-adhesion-test-v1.json)
records actual isolated native export/slicing, matching embedded/external G-code
and MD5, zero mesh-repair counters, unchanged placed mesh against the previously
reviewed fit job, and **2,247 first-layer extrusion moves at no more than 20 mm/s**.
Source/runtime/configuration preservation passes. No printer action was sent.

Warning `1000C001` remains present because the unchanged slicer threshold flags
bed temperatures at/above the declared 60°C vitrification value. It was retained,
not disabled or raised. The project is not warning-free and must not be reported
as such. Saved-process/toolpath checks do not establish physical adhesion, fit,
material suitability or strength. Native launch/review records are under
`.work/anycubic-desktop-planning/session-2026-11-12-adhesion-01/`.
