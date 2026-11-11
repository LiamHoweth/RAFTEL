# Thor Python proxy dependency compatibility

Checked 2026-11-11 with Thor revision `286b081fe6f056d87c379b884781ef77ff6a0159` and the portable FreeCAD `1.1.4R20260928` console. This document records dependency discovery and small native smoke tests. It does not establish complete assembly recomputation or physical performance.

## Cause and supported registration

The matching [FreeCAD restore implementation](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/App/PropertyPythonObject.cpp#L76) checks an unloaded Python proxy module's origin against registered module directories. A missing addon can therefore produce `module not permitted`, rather than simply a missing-module message.

[FreeCADInit.py](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/App/FreeCADInit.py#L101) includes command-line additional module paths in `FreeCAD.__ModDirs__`, and [Application.cpp](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/App/Application.cpp#L2218) exposes the standard `-M`/`--module-path` option. Registering the reviewed addon roots through that option restores the normal workbench mechanism. No global preferences, blanket trust rule, or source-document security bypass is needed. Do not register a broad Downloads/work directory or preload arbitrary modules to evade the restore check.

## Dependency inventory from original native XML

The 57 native archives were read without rewriting them. Stored Python proxy classes identify these dependencies:

| Stored module/class | Original documents using it | Dependency source |
|---|---|---|
| `FastenersCmd.FSScrewObject` | AssemblyBase, AssemblyArt1, AssemblyArt2, AssemblyArt3 | Fasteners Workbench |
| `freecad.gears.features.InvoluteGear` / `BevelGear` | Nine gear-bearing parts, including Art1Bot, Art1GearMotor, Art2BodyA, Art2MotorGear, Art4MotorGear, Art4TransmissionColumn, Art56GearPlate and both gripper arms | FreeCAD Gears |
| `pygears.involute_tooth.InvoluteTooth` / `pygears.bevel_tooth.BevelTooth` | Eight involute-tooth parts and the Art56 bevel gear plate | Bundled within the same FreeCAD Gears source checkout |
| `draftobjects.array.Array` / `draftobjects.wire.Wire` | Original arrays and a wire in the assembly/parts | FreeCAD's bundled Draft module |

A valid cached solid does not prove that its Python proxy restored. The initial runtime log also contained `No module named 'freecad.gears'` and blocked `pygears` imports, in addition to the previously summarized Fasteners messages.

## Pinned addon tooling

| Addon | Revision used | Observed package/source information | Local tooling location |
|---|---|---|---|
| [Fasteners Workbench](https://github.com/shaise/FreeCAD_FastenersWB/tree/fddd07af422b7d3a69098b32333711c5eeae184c) | `fddd07af422b7d3a69098b32333711c5eeae184c` | package version `0.5.67`; package license GPL-2.0-or-later; retain file-specific notices | `work/tools/addons/FreeCAD_FastenersWB` outside RAFTEL checkout |
| [FreeCAD Gears](https://github.com/looooo/freecad.gears/tree/83ec154b1925347622b61812f75d2ed51e956b9f) | `83ec154b1925347622b61812f75d2ed51e956b9f` | GPL-3.0-or-later source; includes its `pygears` package | `work/tools/addons/freecad.gears` outside RAFTEL checkout |

The two initial checkouts are detached at the listed revisions. The current Gears checkout is retained as a comparison; the version-matched baseline below is the recommended Thor route. Their source and license files remain outside the RAFTEL repository; no upstream addon source was vendored or installed into a global Python environment.

Gears' [features.py](https://github.com/looooo/freecad.gears/blob/83ec154b1925347622b61812f75d2ed51e956b9f/freecad/gears/features.py) explicitly retains compatibility reexports for the original stored class names. Its deprecation warning is expected; do not resave upstream originals merely to silence it. Its [project metadata](https://github.com/looooo/freecad.gears/blob/83ec154b1925347622b61812f75d2ed51e956b9f/pyproject.toml) lists NumPy, SciPy and SymPy. Import smoke tests found compatible runtime-bundled versions `1.26.4`, `1.16.3` and `1.14.0` respectively; no extra package installation was needed in this runtime.

## Match the original gear version before rebuilding

Thor's original Art1GearMotor XML records `freecad.gears-version` **0.0.3**. Importing it with current Gears restores a proxy but triggers `Property 'angular_backlash' not found` during its legacy migration. The current implementation attempts to set that expression while migrating the original `dw` property before the old object has the required new property. Thus successful module import is insufficient.

Use the official historical [Gears revision ffe86c85e8061546a3fbaa598993d8e1be2b0de2](https://github.com/looooo/freecad.gears/tree/ffe86c85e8061546a3fbaa598993d8e1be2b0de2), dated 2021-02-17, whose `pygears` version is 0.0.3. It is preserved in a separate detached working tree at `work/tools/addons/freecad.gears-legacy003`; no current addon files were overwritten. This matches the saved schema while avoiding speculative property migration or a geometry rewrite. Only **one** Gears root should be registered per run.

The original Art1GearMotor part then restored the original `freecad.gears.features.InvoluteGear` proxy without the migration exception. Forced recompute completed (return value 15); the gear feature reported Up-to-date with a valid shape and volume approximately `3561.245013 mm³`. A second original part, Art56GearPlate, also restored its BevelGear proxy and forcibly recomputed (return value 22), reporting Up-to-date with a valid shape and volume approximately `36223.090213 mm³`. These results verify those parts' dependency restoration/recompute routes, not the complete arm or geometric equivalence across every part. Ordinary FreeCAD Midplane deprecation warnings remain and do not justify editing upstream originals.

## Actual native smoke results

1. With Fasteners registered through `-M`, the official `FSScrewObject` implementation created and recomputed a synthetic ISO4762 M3 × 10 fastener. Its shape was valid, volume approximately `131.497464 mm³`; this is an isolated software fixture, not a qualified manufactured fastener.
2. A fresh console process reopened that task-created native fixture **without** the addon. The log reported blocked import; `obj.Proxy` was `NoneType`, even though its cached solid was valid and its document state said Up-to-date.
3. A second fresh process reopened the same unchanged fixture **with** the pinned addon registered. The proxy restored as `FSScrewObject`; forced recompute completed, the solid remained valid, and its volume matched. No blanket permission setting or pre-import was used on the restore path.
4. With Gears registered through `-M`, `freecad.gears.features`, `pygears.involute_tooth`, and `pygears.bevel_tooth` all imported from the pinned addon root. NumPy/SciPy/SymPy imports succeeded. This validates the dependency route, not every original Thor gear's rebuild.

Fasteners imports FreeCAD's GUI module even in the console path. The smoke emitted an absent optional `3DconnexionNavlib` warning; it did not prevent the successful recompute/report. No desktop UI session or robot hardware was controlled.

## Reproduce the isolated addon route

Use exact pinned checkouts and a separate native-CAD working copy. From `arm-01`, substitute actual paths:

```sh
export RAFTEL_RUN_FREECAD_AUDIT=1
export RAFTEL_FREECAD_ASSEMBLY=/path/to/working-copy/freecad-src/Assembly.FCStd
export RAFTEL_FREECAD_REPORT=/path/to/work/new-report.json
/path/to/freecadcmd \
  -u /path/to/work/task-user.cfg \
  -s /path/to/work/task-system.cfg \
  -M /path/to/work/tools/addons/FreeCAD_FastenersWB \
  -M /path/to/work/tools/addons/freecad.gears-legacy003 \
  tools/audit_freecad_assembly.py
```

Apply an external bounded timeout. Check proxy class/module restoration as well as document errors, feature state and geometric validity. A cached shape, Up-to-date label or zero process exit code alone cannot close the assembly compatibility gate. Keep addon restoration distinct from topology/kernel failures such as the original thickness feature; adding workbenches does not prove that those features rebuild correctly.
