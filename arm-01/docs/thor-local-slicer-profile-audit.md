# Local Anycubic Slicer Next profile audit

The [allowlisted audit record](../hardware/print-planning/local-profile-audit.json) captures the installed software and last-saved printer/process/filament selection on this Windows host. It contains no account identifiers, credentials, privacy settings, full application configuration, unrelated project names or custom G-code. Original profiles and the configured power/security policies were not edited.

**Installed application:** `C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe`, Windows PE file/product version **2.0.0.3**. The record includes executable/DLL SHA-256 values. This is an installed-version observation, without an online/latest-version claim.

The last-saved selectors identify:

| Selector | Saved profile |
| --- | --- |
| Machine | `Anycubic Kobra 3 Max 0.4 nozzle` |
| Process | `0.20mm Standard @Anycubic Kobra 3 Max 0.4 nozzle` |
| Six filament slots | `Anycubic PLA @Anycubic Kobra 3 Max 0.4 nozzle` |
| Bed type | Application code `4`; its meaning was not independently mapped in this audit |

These are **saved software settings**, not verification of the installed nozzle, loaded filament, physical build surface or current unsaved GUI scene. Actual hardware/material confirmations remain null. The selected machine is the non-V2 Kobra 3 Max profile; separate V2 profiles are present but were not substituted.

## Source paths and inherited fields

The selected cached profiles reside below `%APPDATA%\AnycubicSlicerNext\system\Anycubic`; matching bundled files reside below `%PROGRAMFILES%\AnycubicSlicerNext\resources\profiles\Anycubic`. The audit stores each exact relative JSON path, raw file SHA-256, version label and inheritance chain. Cached and bundled bytes match for all six relevant files:

1. `machine/Anycubic Kobra 3 Max 0.4 nozzle.json`, version `1.3.2512.26`, no inherited machine profile.
2. `process/0.20mm Standard @Anycubic Kobra 3 Max 0.4 nozzle.json`, version `1.3.2507.10`, inheriting `process/fdm_process_common.json`.
3. `filament/Anycubic PLA @Anycubic Kobra 3 Max 0.4 nozzle.json`, version `1.3.2505.16`, inheriting `filament/Anycubic PLA @acbase.json` and then `filament/fdm_filament_common.json`.

No user profile with the same selected basename was found. The audit retains only relevant resolved geometry, nozzle, layer, wall, infill, support/brim and filament fields; it does not export arbitrary profile contents.

The machine profile defines a **426 × 420 mm outline and 501 mm height**, with explicit bed-exclusion points. The points describe 3 mm strips at each X edge, alongside repeated points forming degenerate Y-edge groups. A provisional rectangular interpretation is **X=3..423 mm, Y=0..420 mm**, giving 420 × 420 mm inside the strips. The raw allowlisted points remain in the JSON so a downstream planner can inspect them independently. Confirm exclusion interpretation and actual placement in the slicer before accepting a plate layout.

The extra profile dimensions do not supersede Liam's confirmed nominal **420 × 420 × 500 mm** machine dimensions. Offline draft planning should retain a conservative 500 mm height and explicit margins for brims, supports and placement rather than consuming the 1 mm profile extension as measured hardware clearance.

The selected process specifies **0.20 mm layers/first layer, two wall loops, 15% 3D-honeycomb sparse infill, supports disabled and automatic brim with 5 mm configured width**. These are defaults, not approved settings for Thor load-bearing parts. Fifteen percent infill is not a 0.15 effective whole-part mass fraction.

The PLA profile specifies **1.75 mm filament**, density **1.24 g/cm³**, **210°C nozzle / 220°C first layer**, **65°C hot/textured plate**, and maximum volumetric speed **13 mm³/s**. These profile numbers do not identify the actual spool or qualify printed strength, fit, creep, flow or temperature suitability.

## CLI capability result

Read-only binary inspection found CLI action tokens including `export_3mf`, `export_stl`, `info`, `load_settings`, `load_filaments`, `outputdir`, `help` and `datadir`. Tokens alone are not a validated command-line contract.

Two `--help --datadir <isolated repository scratch>` invocations were attempted: a hidden redirected process and a PTY invocation. Both exited zero; the first emitted a `StaticPrintConfigs` initialization trace only and the second exposed no help text. No action-specific help, model import, 3MF export or slicing result was observed. Therefore **working CLI export/preview remains unverified**. A zero exit code is not export or slicing success.

No `--slice`, G-code generation, printer connection, cloud action, upload or print was requested. A mesh-only standard 3MF composition can be prepared as a separately reviewed offline-format fallback, coordinated by the integration owner. Opening and visually checking that draft in the installed application is a separate evidence step; this audit did not automate the GUI.
