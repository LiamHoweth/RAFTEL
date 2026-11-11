# Review-only value-word mask candidate

A new copied-source candidate repairs the **representation of value-word
bookkeeping** in pinned GRBL. It widens the local `value_words` to 32 bits and
uses a dedicated unsigned 32-bit mask helper. Original source and historical
build/audit evidence remain unchanged. The candidate has only been compiled
into relocatable objects; it is not promoted, linked, executed or released.

The [machine-readable report](../hardware/cad/thor-grbl-warning-candidate.json)
contains the complete one-file proposed diff, source hashes, comparison
diagnostics and static data checks. The [previous warning audit](thor-grbl-source-warnings.md)
establishes the source consumers and runtime limitations. This candidate does
not turn the [offline protocol replay](thor-controller-replay.md) into a tested
firmware parser.

## Chosen repair and intended behavior boundary

The existing source checks repeat value words and tracks unused words, but
defines 17 value-word indices (`WORD_F=0` through `WORD_Z=16`) in a 16-bit mask.
Its generic signed-int shift also reaches the AVR sign bit at index 15 and
exceeds the width at 16. These defects support a narrow representation repair
without deciding new M95, recovery, checksum or motion behavior.

Only copied `grbl/gcode.c` changes:

- Add `VALUE_WORD_MASK(n)`, defined as `(UINT32_C(1) << (n))`. The existing
  `grbl.h` already includes `<stdint.h>`.
- Change local `value_words` from `uint16_t` to `uint32_t`.
- Replace all 34 `bit(WORD_*)` occurrences, including existing commented examples,
  and the two direct `1<<WORD_*` expressions with that helper.
- Replace exactly three dynamic `bit(word_bit)` uses in the **value-word** path:
  duplicate detection, negative-value screening and recording a value word.

The four command-word dynamic-mask uses remain unchanged. So do global
`bit(n)`, the 16-bit `command_words`, M95, all seven `axis_words`/coordinate
assignments, target/motion dispatch, spindle and EEPROM code. A full diff and
all 72 copied-file hashes verify that scope.

The representation contract is explicit: every index 0–16 must have a distinct,
representable bit; repeat Y/Z checks must detect a bit already present; clearing
axis words must preserve unrelated value words. Lower indices 0–14 retain their
defined mathematical masks. Since baseline signed shifts at 15/16 lack portable
defined C semantics, the candidate is **not described as binary-compatible
behavior for those undefined expressions**. It implements the source's apparent
duplicate/unused-word bookkeeping intent, subject to further parser review.

This does not establish that Z motion previously failed or now succeeds. The
separate `axis_words` target path is unchanged. It also does not prove every
complete command parser path is correct.

## Actual compile-only comparison

[`prepare_thor_grbl_warning_candidate.py`](../tools/prepare_thor_grbl_warning_candidate.py)
verifies the clean pinned 72-file source tree and official compiler archive,
creates separate baseline/candidate copies and changes only candidate
`grbl/gcode.c`. Both copies retain upstream notices.

| Artifact/input | SHA-256 |
| --- | --- |
| Baseline gcode.c | `fd6be78b5b6c2258f7aefee5913a1968989ed19f91383b08a16cc3a10cf07321` |
| Candidate gcode.c | `356263ac806d995fe4c0e1deff5e6af86620f7956f163c8522c8db92865f7d9f` |
| Baseline default/strict object | `daebdaa9f4823dbb032d457b24c4696ef31cc81fd39b5de49420c05f9eb02c20` |
| Candidate default/strict object | `f611b775b84dfe1ffb06f6fcc97b4130ba6ab7477e56b92c2dcfcdcb2ad3d6dc` |

The baseline object is byte-identical to `gcode.o` from the preceding successful
C7 build. This binds the comparison to the existing baseline rather than to a
newly invented source. Default and stricter-diagnostic objects agree within
each variant; the stricter flag changes diagnostics, not the captured code.

The verified Arduino AVR GCC 7.3.0 toolchain compiles `gcode.c` using the
existing target/optimization flags, once normally and once with
`-Wshift-overflow=2`. Dependency-output options are unnecessary for these
standalone object comparisons. No linker runs.

| Translation unit | Default diagnostics | Stricter diagnostics |
| --- | --- | --- |
| Baseline gcode.c | Width-overflow warning plus maybe-uninitialized `word_bit` | Adds signed sign-bit shift warning |
| Candidate gcode.c | Only maybe-uninitialized `word_bit` | Only maybe-uninitialized `word_bit` |

The M95 warning is deliberately retained. Spindle/EEPROM sources are unchanged
and were not recompiled here; their earlier warnings remain unresolved. This
is not a claim that a full candidate firmware has only one warning.

The candidate object file is 21,028 bytes versus 20,852 baseline bytes. These
are relocatable file sizes, **not linked flash usage**. A wider local may affect
instructions, stack and timing; none is qualified by this file-size delta.
The earlier 31,640-byte linked baseline image is not a candidate memory result.

## Static expression checks and negative cases

A fifth compiler invocation produces a separate relocatable static-data probe
using the exact candidate helper and pinned header constants. Python reads its
named ELF data sections; no instructions execute. Twenty-two captured values
establish:

- All 17 distinct masks, including Y=`0x8000` and Z=`0x10000`.
- Existing Y and Z masks each satisfy the repeat-word bit predicate.
- Y and Z masks do not overlap.
- Removing all seven axis-word masks from all 17 bits leaves `0x3ff`, preserving
  the ten non-axis value words.
- Clearing Y leaves an unrelated Z mask intact.

The probe emits no warnings even under the stricter shift diagnostics. These
are compiled expression/property checks, **not end-to-end parser execution**.
Portable tests additionally check 100 seeded selective-clear cases and reject
invalid indices, stale source bytes, missing transformation anchors, duplicate
header indices and source/compiler output overlap. They verify tooling and
the proposed contract, separately from the native compiler capture.

## Minimal proposals for the other warnings

The six original compiler warnings span four source concerns. Only the mask
candidate is prepared; the others remain explicit proposals:

| Concern | Precise next proposal | Why no patch is accepted here |
| --- | --- | --- |
| M95 unassigned/stale `word_bit` | Specify an M95 modal-group and execution-order contract before assigning the bit or changing the branch | Initializing it arbitrarily could hide the warning while leaving stale/conflicting command semantics; homing currently occurs before the later modal check |
| Implicit/conflicting spindle return type | A signature-only proposal adds `void` to match the header | It would not repair the separate empty recovery function or define recovery behavior |
| Empty spindle recovery body | Specify recovery-state behavior separately from normal `spindle_run`, including future independently reviewed stop/restart requirements | No physical recovery semantics are qualified by this task |
| Two EEPROM logical-shift warnings | Choose an explicit checksum recurrence for both read/write paths and a storage-version/old-record policy | Replacing `||` with `|` blindly can break compatibility and assumes an intended algorithm not established by source |

Those proposals are not implementation claims or an operational workaround.
Actual installed firmware/settings, full-parser behavior, memory/timing,
feedback/calibration, motor-energy isolation and physical commissioning remain
separate unresolved gates.

## Reproduction and preservation

From `arm-01`, using the retained local inputs and a new scratch directory:

```powershell
python tools/prepare_thor_grbl_warning_candidate.py --source ../.work/controller/grbl-source/upstream --toolchain-archive ../.work/controller/toolchain/avr-gcc-7.3.0-atmel3.6.1-arduino7-i686-w64-mingw32.zip --toolchain-root ../.work/controller/grbl-build-03/toolchain --output-dir ../.work/controller/grbl-warning-candidate-next
python -m pytest tests/test_thor_grbl_warning_candidate.py
```

The tool refuses existing/source/compiler-overlapping output, preserves the
50 GiB reserve, verifies raw source/compiler bytes before and after, and records
all five compiler-only calls. It downloads/installs nothing. Compiler searches
and temporary files reuse the child-only isolation from C7. Generated text and
reports use explicit LF. Original source, historical evidence and compiler files
are unchanged. No binary, source copy or toolchain is committed.

The complete proposed diff is in the tracked JSON report and retained scratch
`candidate.patch`; the copied source remains review-only. It is derived from
upstream GPL-3.0-or-later source with its notices preserved. No company-wide
license is selected and no firmware binary is distributed. Independent review
of this candidate's exact diff and evidence precedes any decision to promote it;
runtime and hardware acceptance would still require separate work.
