# Saved Anycubic DRAFT package audit

`tools/audit_anycubic_draft_project.py PROJECT --output NEW_REPORT.json` inspects
a local 3MF package without extracting, changing it, invoking a slicer or
contacting a printer. Output creation is exclusive and uses UTF-8/LF. A failure
returns exit code 2 with a sanitized error, without including metadata values.

The report binds exact project bytes by SHA-256 and size. It lists declared
model units, resource object identifiers, vertex/triangle counts, component
references, build items and expanded mesh leaves. Build-item count and mesh-leaf
count are separate: one build object can contain several component meshes.
Nonprintable builds remain visible and have a separate printable-leaf count.
Object names, designer/title metadata, thumbnails, account details and arbitrary
settings are omitted. Companion tools compare geometry and observe allowlisted
process fields; this structural report does neither.

## Shared bounded reader

`ProjectArchive(Path | bytes)` is a context manager exposing `names`, `sha256`,
`size`, `read(name, *, max_bytes=MAX_MEMBER_BYTES)` and `safe_xml(name)`.
The process observer reuses this reader. `load_project(Path | bytes)` supplies
the mesh comparator with numeric vertex/index arrays, original vertex tokens,
the resolved component graph and mesh instances. Numeric transforms use 3MF's
twelve-coefficient row-vector convention. An instance's `transform_chain` and
`transform_tokens_chain` apply the leaf component first, then its ancestors,
then the build placement. All linked parts must have the same unit; mixed units
are rejected rather than silently converted. An absent model unit means
millimeter under the Core specification.

The supported geometry is Core mesh/component objects and Production extension
cross-part `path` references. Unknown required extensions fail. Optional color,
materials and vendor metadata are not interpreted; this is not a complete 3MF
conformance validator. The Core packaging conventions follow the already pinned
specification recorded by `tools/thor_draft_3mf.py`.
Production paths must be absolute and cross-part component references can appear
only in the root model. Referenced child builds are ignored, as required by the
[Production specification, chapters 2-3](https://github.com/3MFConsortium/spec_production/blob/master/3MF%20Production%20Extension.md)
(accessed November 12, 2026). This reader does not assert Production UUID or
per-model relationship conformance.

Limits are 128 MiB archive/member, 512 MiB total declared uncompressed data,
512 members, 1,000:1 compression ratio, 128 model parts, 500,000 aggregate
vertices plus triangles, 10,000 resources/references, 64 graph levels and
10,000 expanded leaves. XML is UTF-8 only, with at most 2,000,000 elements per
part and 64 element levels. DTD/entities, encrypted/unsupported ZIP members,
symlinks, path traversal, case-fold name collisions, encoded/ambiguous reference
paths, cycles, dangling references, duplicate resource IDs, duplicate geometry
containers, nonfinite geometry and singular transforms fail closed. No ZIP
member is executed. Independent review identified depth-cache and nested
namespace-shadowing cases; focused regression fixtures retain both failures.
Numeric tokens are decimal-only, at most 128 characters, with exponent magnitude
at most 324; nonzero underflow is rejected before companion exact-rational work.

## Evidence boundary

The prepared generic eight-copy source plate has been read successfully:
205,597 bytes, SHA-256
`68f4e0b621b3552b80e673125ab6eb98352e795b2bfa063ef9a7cc154f313bbb`,
eight build items and eight mesh leaves, with 7,524 vertices and 15,112
triangles. This is a reader check against the existing generic source plate,
not evidence that Anycubic saved or imported it. A fresh actual saved project
must be supplied and audited separately.

Host tests cover valid direct/cross-part/repeated instances, transform ordering,
privacy, caller-specific member bounds, hostile package/XML/graph cases and
exclusive output preservation. Native application save observation, source
geometry equivalence, software selectors, slicing and physical nozzle/material
confirmation remain explicit unknowns in the structural report. Manufacturing
release remains false.
