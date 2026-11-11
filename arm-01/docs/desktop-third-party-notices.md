# Desktop third-party notice observations

This source audit records the exact desktop-run pins and differing declarations.
It does not determine legal applicability, choose RAFTEL's company license or
approve external distribution. Original source, historical evidence and local
toolchains remain unchanged. No CAD, third-party source tree, runtime, compiler
or firmware binary is added to Git by this audit.

The [machine-readable observation snapshot](../hardware/cad/desktop-third-party-provenance-v1.json)
contains exact file hashes and evidence lines. The
[read-only reproducer](../tools/audit_third_party_provenance.py) verifies selected
notice bytes against their pinned Git blobs, examines all 57 original native
document license properties, and checks the presently retained draft metadata.
The 540 Fasteners and 49 historical Gears Git-tree entries are counted; this is
not a claim that every non-code asset has an individually reviewed notice.

## Repository and file declarations

| Source pin | Observed repository/package declaration | Separately observed file or saved-document declaration |
| --- | --- | --- |
| [Thor `286b081`](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159) | Root `LICENSE` and README declare CC-BY-SA-4.0; license SHA-256 `7abe19ec9bb73b36141b999b861d24ad855e808bafe0f81e84cce28556f6c297`. | All 57 original `Document.xml` property sets say `All rights reserved` and link to the Wikipedia page with that name. These saved values are preserved, not replaced by the repository declaration. |
| [Fasteners `fddd07a`](https://github.com/shaise/FreeCAD_FastenersWB/tree/fddd07af422b7d3a69098b32333711c5eeae184c) | Root `LICENSE` is GPL version 2 text; `package.xml:8` says `GPL-2.0-or-later`; README says `GPLv2`. | `FastenersCmd.py:9–12` declares GPL version 2 or later. `screw_maker.py:68–71` declares LGPL version 2 or later. Observed credits include Shai Seger, Ulrich Brammer and Andrey Bekhterev. |
| [Historical Gears `ffe86c8`](https://github.com/looooo/freecad.gears/tree/ffe86c85e8061546a3fbaa598993d8e1be2b0de2) | Root `LICENSE` is GPL version 3 text; README states GNU GPL v3.0. This is the saved-schema-compatible `pygears` 0.0.3 pin. | `freecad/gears/features.py:4–7` and `pygears/__init__.py:4–7` declare LGPL version 2 or later. Project setup identifies maintainer `looooo`; the audit does not flatten these file declarations into the root declaration. |
| [Thor GRBL `1f6437a`](https://github.com/AngelLM/grbl/tree/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff) | Root `COPYING` contains the GRBL copyright notice and GPL version 3 text. | `grbl/main.c` declares GPL version 3 or later and credits Sungeun K. Jeon and Simen Svale Skogsrud. Diagnostic ELF/HEX files remain local ignored scratch; no binary release is approved. |
| [Thor ROS `e11a56b`](https://github.com/AngelLM/Thor-ROS/tree/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952) | Root `LICENSE` is CC-BY-SA-4.0, with the same `7abe19ec…` hash as Thor. | [`thor_controller/package.xml`](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/package.xml) declares Apache-2.0; exact SHA-256 is `217edb7be38806babd71e178a89eb71ca1df1278621bc9e1e386f177df79bbf6`. Root and package declarations remain separate observations. |
| [Asgard `30bf2f8`](https://github.com/AngelLM/Asgard/tree/30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6) | Root `LICENSE` is CC-BY-SA-4.0, also with the `7abe19ec…` hash. | This is a reference-source notice observation; this audit does not import or operate the application. |

The three small Thor ROS/Asgard notice documents were retrieved from immutable
public raw URLs on 2026-11-11 and retained only under `.work/third-party/`.
Their full pinned URLs and hashes are in the machine-readable snapshot.

## Local runtime and build tools

The portable FreeCAD **1.1.4 Windows x86-64 / Python 3.11** release archive is
pinned to SHA-256
`4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d`.
Its bundled `doc/LICENSE.html` says LGPL2+ and includes the Library GPL version 2
text. `doc/ThirdPartyLibraries.html` is retained as a separate component-notice
index. That index is not a verified complete runtime dependency/license SBOM.
This audit binds the existing native receipt to the official release metadata;
it does not rehash the 418 MB archive or claim a new signature validation.

The Arduino-distributed AVR toolchain **7.3.0-atmel3.6.1-arduino7** archive is
pinned to SHA-256
`a54f64755fff4cb792a1495e5defdd789902a2a3503982e81b898299cf39800e`.
This audit rechecks those archive bytes. Selected contained notices differ:

- GCC's `avr/lib/gcc/avr/7.3.0/include/stddef.h` declares GPL version 3 or later
  with GCC Runtime Library Exception version 3.1.
- `avr/avr/include/stdio.h` carries avr-libc copyright and a three-clause
  source/binary redistribution notice.
- No archive member name matches the audit's standalone notice-name search
  (`license`, `licence`, `copying`, `copyright`, `notice`). This does **not** mean
  the archive or its components lack licenses: the selected headers demonstrate
  embedded notices. A complete toolchain redistribution review remains open.

Compiler execution, native source compatibility and local installation are
separate evidence classes. No runtime/toolchain redistribution is approved by
recording these observations.

## Generic 3MF draft attribution

The snapshot checks **17 retained generic 3MF drafts**: six published-STL drafts
and eleven selected saved-BRep native tessellation drafts. This is an observed
file set, not the total printable-asset count or a released print package.

For every observed draft, the audit verifies the retained full upstream license
text against Thor's exact license hash, a pinned Thor source URL/revision,
the `AngelLM and Thor contributors` designer attribution, an explicit change
statement, and `manufacturing_release=false`. It records the archive hash and
keeps native versus published-STL mesh origins distinct. The existing composer
also binds these metadata fields during its own draft validation.

These checks do not establish mesh fidelity, completeness, slicing, orientation,
process settings, fit or printed performance. They do not resolve the native
document metadata difference or determine license applicability to generated
geometry.

## Reproduction and unresolved gates

From the repository root, with the retained source roots and public notice
captures present:

```powershell
arm-01\.venv\Scripts\python.exe arm-01\tools\audit_third_party_provenance.py --output .work\third-party\new-observation.json
arm-01\.venv\Scripts\python.exe -m pytest arm-01\tests\test_third_party_provenance.py
```

Output creation is exclusive; existing evidence is not overwritten. The tool
uses no network and executes no source/CAD/firmware. A later draft, receipt or
source revision yields a new snapshot, not a silent update to this one.

Receipt schemas, source/evidence classes and runtime/toolchain pins are checked
before their metadata is used. JSON rejects duplicate keys and nonfinite values.
The toolchain archive path must remain in its exact normalized scratch location,
including after symlink resolution. Synthetic guard fixtures cover these input
failures without reading unrelated files or installing malformed packages.

Validation: 45 focused synthetic guard tests and scoped Ruff lint/format pass.
Independent re-review repeated the prior negative probes before any outside-root
read and reproduced the complete frozen observation snapshot. It accepted this
notice/metadata observation scope with no remaining blocker; no legal
applicability or release decision was made.

Before an external derivative/export distribution is approved, the remaining
review must identify its exact files, preserve applicable source/author notices
and change records, resolve the differing declarations for that distribution,
and inventory any redistributed third-party runtime/toolchain components.
Those decisions remain null in the report. No company-wide license, physical
fabrication or manufacturing release is selected here.
