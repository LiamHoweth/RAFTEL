# Copied Art1 attachment-engine diagnostic

The [worker](../tools/probe_thor_art1_attachment_engine.py) exercises native
`positionBySupport()` on fresh copies of the existing unaccepted ThroughAll
candidate. This is a separate experiment from the earlier public-getter audit.
No original document is opened, no CAD document is saved, no support is explicitly
assigned in the candidate and no candidate recompute is requested.

Before examining the candidate, synthetic fixtures must demonstrate a real
placement change after a deliberately wrong placement is assigned immediately
before the explicit engine call. FlatFace follows a translated/rotated provider
and returns to its nominal frame. A Deactivated control must retain its imposed
placement. Five ObjectXY phases compare actual engine output against independently
derived constant matrices: nominal, support translation, support rotation,
AttachmentOffset change and nominal return. Actual input frames, sentinel frames,
outputs and partial failure observations are retained.

For each of the source ledger's 53 dependent owners, the worker records the frame
saved locally before its call, the direct nominal engine result, a deliberate
translation challenge, the second direct engine result and restoration of the
saved frame. A method return
or unchanged public getter alone cannot pass the engine-effect predicate.
Deactivated owners remain explicit no-effect controls. A completed diagnostic can
include unavailable methods or individual engine errors; its counts must be read
before drawing any narrower execution conclusion. Placement restoration is an
explicit local cleanup operation, not proof of a rebuilt feature-history return.
The row named `saved` is the restored in-memory frame captured before this probe's
explicit call, not an independently decoded serialized XML Placement. Native
document restoration can itself invoke attachment calculation.

The [pinned FreeCAD implementation](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/AttachExtension.cpp)
confirms that
`positionBySupport()` runs native attachment calculation and writes Placement.
An `Attacher` property read alone returns an engine copy and does not execute it.
Native attachment can update persistent-reference shadow data, so the report
distinguishes no explicit support assignment from observed public target changes.
The internal resolver path is not instrumented by this experiment.

The guard requires the exact source/candidate hashes, an authenticated source XML
ledger, a fresh owned `.work/swarm/a01_engine/run-NN` packet, bounded UTF-8 request
JSON, retained worker/helper pins, actual runtime provenance and all five
isolated configuration paths. Reparse paths are rejected before reads; the outer
launcher checks fresh isolated directories before starting FreeCAD. It preserves
original CAD, pinned addons, historical receipts/workers, copied inputs and runtime
module/executable bytes before and after execution. Only owned documents close;
cleanup and preservation failures remain report failures. A 50 GiB reserve plus
512 MiB scratch and Root's serialized native slot are required.

FreeCADcmd embeds the `FreeCAD` module without `__file__`; the worker records this
fact and authenticates the actual Win32 process image plus `App.Version()`.
Python's `sys.executable` is retained separately as observed metadata.
`Part.__file__` is checked as a separate native extension. A pinned `FreeCAD.pyd`
file in the preserved runtime is not claimed as the origin of the embedded module.

## Actual run

Root executed fresh run-04 in **2.402573 seconds** with the pinned FreeCAD 1.1.4
console. All five independent ObjectXY phases passed; their maximum difference
from the constant oracle was 1.776e-15. FlatFace provider covariance differed by
1.110e-16 and nominal return was exact. The Deactivated control returned false,
made no engine placement change and retained the imposed challenge.

Of 53 source-dependent owners, **51 exposed and executed `positionBySupport()`**.
Every one overwrote the imposed 3.75 mm maximum translation component and returned
exactly to its first nominal engine matrix. The two `Mirrored` feature owners do
not expose that method and are explicitly excluded from the execution count.
All 53 locally saved frames were restored. No public attachment target change
was observed. `DatumPlane001` retained current `Pocket.Face6` and its -20 mm
AttachmentOffset; this is not a new remap of the original source selector.

The [versioned receipt](../hardware/cad/thor-art1-attachment-engine-v1.json) retains
every raw native field plus provenance. Raw report SHA-256 is
`5e49533ca489a0c7d384cd668dd4d617e0c9f2d15e36651bf35e828f07207409`.
All 8 retained and 838 protected files passed before/after checks, including 57
original CAD files, 589 pinned addon files and prior semantic-run evidence. Actual
process image, Part extension and all five isolated paths matched their pins.
Zero documents remained open. Final states were 37 Up-to-date and 53 Touched;
the probe did not rebuild features or certify their resulting shapes.
Six retained native InertialCS warnings state that second and third inertia axes
are undefined for a tensor with an axis of symmetry. Repeat placement recovery in
this run does not establish a unique inertial-frame orientation.

Independent actual fixture replay verified rigid-frame arithmetic, engine effects,
the negative control, return and unaltered raw-field curation. Host tests validate
guards and classification separately from this recorded native execution.
No repaired history, semantic attachment approval, migration acceptance, physical
calibration or fabrication release follows from this diagnostic.

Original Thor CAD remains attributed to AngelLM/Thor at revision
`286b081fe6f056d87c379b884781ef77ff6a0159`; existing license/NOTICE gates remain.
