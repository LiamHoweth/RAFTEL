# Mac development workflow

Run commands in the repository root. `make` shows the available commands; no
shell profile edits or global Python package installation are required.

```sh
make setup       # First install, or restore the pinned development dependencies
make demo        # Ten synthetic objects, mock backend
make benchmark   # Ten seeded logical evaluation layouts
make analysis    # Assumed-load and nominal spatial-kinematics diagnostics
make verify      # Full portable CI checks, engineering CLIs and offline wheel smoke
```

The development environment is `arm-01/.venv`. To use the CLIs directly:

```sh
source arm-01/.venv/bin/activate
raftel-sort --help
raftel-evaluate --help
```

Use `arm-01/.venv/bin/python` as the interpreter in your editor. Runtime uses the
standard library; pytest/Ruff and the build backend use the repository's pinned
versions. `make setup` and wheel building may access the package index. Installed
sorter/evaluation commands and offline engineering studies need no network,
camera, GPU or robotics middleware. The wheel smoke check installs with
`--no-index --no-deps` into a temporary environment and verifies all packaged
modules, defaults and both CLIs' success/failure/invalid-input behavior.

Each verification run retains evidence and a wheel in a fresh directory under
`.work/verification/`. The temporary wheel-test environment is removed on success;
its verification JSON remains. Failed-run evidence is retained for diagnosis.
The reusable development environment stays installed. Generated outputs, local
native paths and virtual environments are ignored by Git.

## Native Thor CAD

This Mac reuses the existing isolated FreeCAD installation and study inputs under
`/Users/howeth/Documents/Codex/2026-11-11/se/work/`. No application download,
global workbench installation, security changes or source CAD edits are needed.
Local paths are recorded in the ignored `.raftel-local.mk`:

```make
FREECAD := /absolute/path/to/FreeCAD.app/Contents/Resources/bin/freecadcmd
THOR_ASSEMBLY := /absolute/path/to/Thor-compatible-copy/freecad-src/Assembly.FCStd
FASTENERS := /absolute/path/to/FreeCAD_FastenersWB
GEARS := /absolute/path/to/freecad.gears-legacy003
```

The verified baseline uses Thor `286b081fe6f056d87c379b884781ef77ff6a0159`,
Fasteners `fddd07af422b7d3a69098b32333711c5eeae184c` and historical Gears
`ffe86c85e8061546a3fbaa598993d8e1be2b0de2`. FreeCAD is the existing signed ARM64
1.1.4 bundle. Do not register the current Gears root alongside the legacy root.

```sh
make native-audit
```

This calls the existing bounded runner with separate preferences, `changed`
recomputation, shape scope `none`, and a fresh report/log directory under
`.work/native/`. It reads the compatible copy without saving. The compatible
Art1 body is an exact static snapshot; original parametric history remains a
separate unresolved study. Inspect report completion, object states and native
diagnostics; exit status alone is insufficient. Run native studies serially and
retain at least 50 GiB free before large builds/native work.

## Scope

The [architecture](../arm-01/docs/architecture.md) and
[current next steps](../nextSteps.md) define the implemented workflow. ROS 2 Jazzy,
MoveIt 2, camera calibration/OpenCV, LeRobot, a physics environment, a hardware
driver and printer operation require their own concrete integration tasks and
acceptance evidence. They are not dependencies of this workflow. The current
sorter remains logical-only; native CAD and offline mathematics do not establish
physical motion, collision clearance, fabrication readiness or hardware safety.

See [the Mac setup receipt](mac-setup-2026-11-12.md) for executed results.
