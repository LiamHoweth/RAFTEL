# Windows native CAD foundation

The desktop run now has an isolated FreeCAD 1.1.4 compatibility baseline. The
[receipt](../hardware/cad/thor-windows-native-foundation-v1.json) binds the official
archive/executable, exact source files, addon revisions, executed script snapshots
and local raw reports. Source CAD and historical reports remain unchanged.

## Observed result

- The portable runtime imported pinned Fasteners and historical Gears/pygears
  0.0.3 from their recorded source roots. Numerical libraries came from the
  portable runtime. The official archive and executable were checked; individual
  runtime DLLs were not exhaustively hashed.
- `prepare_thor_compatibility.py` read the original Art1 archive and wrote a new
  static saved-solid/datum wrapper in a copied tree. Its saved/reopened volume,
  bounds, single-solid validity and 24 datum matrices matched. Independent XML
  comparison also found zero datum-transform difference. This preserves the
  historical static compatibility route; it does not repair procedural Art1.
- `run_freecad_audit.py` restored and performed changed-only recomputation across
  53 documents. After all requested recomputations, all 3,001 loaded objects had
  `Up-to-date` states, no report errors remained, and all newly opened documents
  were closed. The final global state sweep avoids accepting a parent inspected
  before a later child recompute touched it.
- Five actual FreeCAD configuration/data/temp paths stayed inside each fresh run
  directory. Original source, executed worker and retained runner hashes matched
  before/after. All 57 original native files and 589 addon files still match their
  source receipts; 56 other working-copy native siblings are unchanged.

## Scope and reproduction

The assembly run used `recompute="changed"`, `shape_scope="none"` and no whole
shape validation. Up-to-date state is not proof of geometric correctness,
collision clearance, conjugate gears, physical calibration or printable parts.
The separate ThroughAll Art1 candidate was not substituted here and remains
unaccepted under its own failed roundtrip gates.

The local sources/runtime and logs live under `.work/native-foundation` and
`.work/cad/runtime`; they are deliberately untracked. Preserve them when resuming.
The receipt lists exact relative raw-evidence paths and hashes. To repeat, use
the verified `bin/freecadcmd.exe`, the two exact addon roots through `-M`, a fresh
source copy with a newly validated static wrapper, and a new JSON report path:

```python
from pathlib import Path
from tools.run_freecad_audit import run_audit

run_audit(
    Path("<verified portable bin/freecadcmd.exe>"),
    Path("<fresh compatibility source tree>/Assembly.FCStd"),
    Path("<new evidence path>.json"),
    module_paths=(Path("<pinned Fasteners root>"), Path("<pinned Gears root>")),
    recompute="changed", shape_scope="none", timeout_s=480,
)
```

Inspect report status, final object states, actual isolation paths, source/script
hashes and stderr together. Process exit zero alone is insufficient. Do not run
this concurrently with another native probe; the coordinator owns the queue.

Preparation attempt 01 stopped before launch because two executable paths matched
a broad search. Its failure evidence is preserved. Attempt 02 used the exact
verified executable. No global addon installation or preferences migration was
needed.
