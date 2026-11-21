# License readiness

RAFTEL's original work is publicly visible on GitHub. Liam Howeth has yet to
select a distribution license for it. GitHub provides viewing and forking under
its terms. General permission to reuse RAFTEL's original work requires an
applicable license or other permission from the rights holder.
[GitHub's licensing guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

## Audit scope

On 2026-11-21, the file inventory covered all 422 tracked blobs at baseline
`9917163` and paths in fetched Git history. The audit also reviewed the Python
distribution configuration and the project's pinned notice inventory. Every
baseline blob decoded as UTF-8. The baseline contains Python, Markdown, JSON,
development configuration and two Thor-derived SVG interface drawings. The
tracked-path review found no native CAD, STEP/STL/BRep/3MF geometry files,
firmware binaries, toolchain bundles, or upstream source trees. GitHub showed
zero releases when checked. Native source copies, generic print drafts and
compile outputs documented by past runs were kept in local work areas. The
source-derived text, diff and diagrams already in Git still need a rights and
notice review before a broader release.
[GitHub releases](https://github.com/LiamHoweth/RAFTEL/releases) ·
[CAD reference manifest](../arm-01/hardware/cad/references.json) ·
[Desktop notice inventory](../arm-01/docs/desktop-third-party-notices.md)

| Candidate scope | Material and review needed |
| --- | --- |
| Original software | BenchSort's task logic, mock backend, synthetic scenes, evaluation and independently authored tests, tools and configuration are candidates after rights-holder confirmation. Review any copied expression, fixture, code fragment, or sample separately. The Python wheel currently packages the Thor study modules too. |
| Original documentation and data | RAFTEL-authored prose, experiment protocols, original figures and synthetic datasets are candidates where RAFTEL controls the rights. Check cited excerpts, third-party figures and source-derived evidence individually, including in daily reading notes. |
| Thor CAD and derived evidence | The pinned Thor README and root license declare CC-BY-SA-4.0. The notice inventory recorded `All rights reserved` in all 57 original native documents. The existing [base](../arm-01/hardware/drawings/thor-base-interface-v1.svg) and [tool](../arm-01/hardware/drawings/thor-tool-interface-v1.svg) drawings credit Thor and describe annotations or proposed changes. Review which notices apply to those drawings, extracted geometry/frames and exact CAD/mesh exports, and seek upstream clarification for the saved-document discrepancy. [Pinned Thor README](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/README.md) · [Pinned Thor license](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/LICENSE) |
| Thor ROS and Asgard | Their pinned root licenses declare CC-BY-SA-4.0, and the Thor-ROS controller package manifest declares Apache-2.0. Review the scope of those declarations before redistributing a port or copied code. Prioritize the arithmetic and string transcription in [`thor_source_conversion.py`](../arm-01/src/raftel_arm01/control/thor_source_conversion.py) and related fixtures for file-level review. [Thor-ROS license](https://github.com/AngelLM/Thor/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/LICENSE) · [Controller manifest](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/package.xml) · [Asgard license](https://github.com/AngelLM/Asgard/blob/30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6/LICENSE) |
| Thor GRBL | The [tracked warning-candidate report](../arm-01/hardware/cad/thor-grbl-warning-candidate.json) includes a unified diff with upstream source context. Exclude the diff from any permissive RAFTEL grant. Check notice and source-distribution obligations for the diff and related tools. If conveying compiled firmware under the applicable GPL terms, provide Corresponding Source by a permitted method and include applicable notices. [Pinned GRBL notice and license](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/COPYING) |
| CAD and compiler tooling | Keep using separate upstream installs. Fasteners and historical Gears have GPL and file-specific LGPL declarations. The FreeCAD, AVR and optional CAD diagnostic distributions carry additional component notices. Inventory the exact components and obligations if bundling any tooling. [Desktop notices](../arm-01/docs/desktop-third-party-notices.md) · [Optional CAD tooling notes](../arm-01/docs/thor-adaptive-metric-study.md) |
| Other hardware references and vendor artifacts | SO-ARM100 and the six-axis SO-101 variant have Apache-2.0 roots. PAROL6's pinned public hardware uses CERN-OHL-S-2.0, and firmware and libraries have separate terms. Its seller restricts sharing purchased STEP files without permission. The pinned Annin AR4 terms restrict software use and design redistribution. Keep restricted CAD out of a release unless the rights holder grants the required permissions. Review vendor assets separately when packaging slicer inputs or outputs. [CAD reference and license pins](../arm-01/hardware/cad/references.json) · [PAROL6 STEP terms](https://source-robotics.com/products/parol6-step-files) · [Pinned Annin AR4 terms](https://github.com/Annin-Robotics/ar4-hmi/blob/214558c2beb474695d6c083856c354d3f6d4790f/LICENSE.txt) |

For material shared under CC BY-SA 4.0, retain applicable supplied credits and
notices, identify the source and license, and indicate changes. Shared
adaptations must use a permitted ShareAlike license. Technical format changes
allowed under §2(a)(4) can preserve the original material without producing an
adaptation. Preserve original notices and source revision or hashes in
provenance records. Review artifacts in their distribution format, since a CAD
export or rendered figure can carry material from multiple sources.
[CC BY-SA 4.0 legal code, §§2–3](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en)

## Recommendation for owner review

| Option | Fit for cleared RAFTEL software and accompanying docs |
| --- | --- |
| Apache-2.0 | Recommended for the first scoped release. It permits broad reuse and includes an explicit contributor patent grant with termination conditions. Distributions include the license, identify modifications, and retain applicable notices, including relevant attributions from a distributed `NOTICE` file. [Apache Software Foundation](https://www.apache.org/licenses/LICENSE-2.0) · [OSI approval](https://opensource.org/license/apache-2.0) |
| MIT | A shorter permissive option if simplicity is the priority. Retain the copyright and permission notices in copies or substantial portions. Its text has no express patent clause. [OSI license text](https://opensource.org/license/mit) |

The owner could use CC BY 4.0 for independently authored, standalone research
documentation and the software license for accompanying manuals and examples.
If RAFTEL develops and releases independently authored hardware design files,
choose a CERN-OHL v2 variant that matches the intended level of reciprocity and
ship the editable source needed to modify the design. Rights covering an
upstream adaptation follow the review for that material. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en) ·
[CERN-OHL variants](https://ohwr.org/licences/)

## Owner decision checklist

- [ ] Confirm authorization from relevant rights holders for the original files
  to be licensed. Review commit history, contributor permissions and imported
  material before treating authorship or ownership as settled.
- [ ] Select the release scope and license in writing. Document what the
  software grant covers and explicitly identify separately licensed or
  excluded material. Decide whether standalone docs or future original
  hardware will have their own grants.
- [ ] Resolve the CAD and controller notice discrepancies for each intended
  derived item. Retain its source revision, creators, applicable license text,
  notices and change record. Review the tracked GRBL diff and the need for
  separate notices or distribution changes. Obtain permission or omit material
  whose redistribution rights remain unclear.
- [ ] In an approved licensing change, add the selected license text and clear
  file or directory scope, applicable third-party notices, contributor terms
  and consistent README/package metadata. Mark modifications as required.
- [ ] Inspect the actual wheel, source archive and any proposed CAD, firmware
  or tooling bundle against that scope. Confirm the correct license and notice
  files ship with each artifact and keep local-only items out of distribution.
