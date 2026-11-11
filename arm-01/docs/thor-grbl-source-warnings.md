# What the pinned GRBL warnings establish

The [successful AVR cross-build](thor-grbl-build-feasibility.md) produced six
warnings. This follow-up traces their source consumers and adds static
relocatable-object probes. It establishes specific source defects and limited
compiler encodings, while keeping complete firmware/runtime and physical
behavior unresolved. Original source, compatible copies and earlier build
captures remain unchanged. No source patch was accepted.

The [audit report](../hardware/cad/thor-grbl-warning-audit.json) binds source
hashes to GRBL revision `1f6437a77e3abcb652d3f8ce718faf7e041ae6ff` and records
the facts, explicit nonclaims, source lines and object-data capture.
[`audit_thor_grbl_warnings.py`](../tools/audit_thor_grbl_warnings.py) reproduces
the pinned audit; it is not a general C analyzer or firmware emulator.

## Axis bookkeeping has a width defect; Z has a separate target path

The pinned source defines [`WORD_Z=16`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.h#L144),
uses `uint16_t value_words` at
[`gcode.c:97`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L97),
and defines `bit(n)` using signed integer literal 1 at
[`nuts_bolts.h:58`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/nuts_bolts.h#L58).
The captured AVR ABI has 16-bit `int`. Shifting by 16 exceeds that operand's
width, and 16-bit storage cannot retain bit 16 even if only the literal is
widened. The relevant C rules distinguish invalid shift counts, signed result
representability and unsigned conversion; see WG14
[N1570 §6.5.7](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf).

`value_words` supports duplicate-word checks (`gcode.c:378`), value tracking
(384) and unused-word cleanup/checks (851–853). It is **not the only carrier of
the Z target**:

1. [`gcode.c:373`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L373)
   assigns the Z number to `gc_block.values.xyz[G_AXIS]` and sets `axis_words`
   bit 6. This axis-index bit fits its 8-bit mask.
2. `axis_words` establishes implicit motion at lines 421–422 and selects which
   coordinates retain/update their targets at
   [620–633](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L620).
3. The G0 execution branch passes the coordinate array to
   [`mc_line` at 989](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L989).

Therefore the bookkeeping defect does **not** establish that Z motion always
fails. Undefined source operations also prevent treating one compiler's
encoding as a portable full-parser prediction. Duplicate/unused-word behavior,
the complete optimized parser and any installed firmware remain unvalidated.

The adjacent `WORD_Y=15` reaches the signed `int` sign bit. The ordinary build's
absence of a warning is not proof of portable defined C behavior. GCC 7.3's
[versioned warning documentation](https://gcc.gnu.org/onlinedocs/gcc-7.3.0/gcc/Warning-Options.html)
explains that default shift-overflow level 1 omits this sign-bit case and level
2 diagnoses it. A separate probe confirms that distinction. It does not
establish a Y motion failure either.

## The maybe-uninitialized warning has a concrete M95 path

The local `word_bit` is declared without initialization at
[`gcode.c:105`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L105).
Most supported command/value cases assign it. The
[`M95 branch at 315–332`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L315)
does not.

On its homing-enabled branch, M95 invokes homing-related functions and then
breaks out of the command switch. If those calls return, the following modal
mask at line 339 reads `word_bit`. When M95 was the first parsed word, there
was no earlier assignment; after other words it can reuse their stale bit.
The homing-disabled branch returns early instead. `sys.abort` only skips
idle/stepper cleanup inside this branch; it does not itself return before the
modal-mask read. This source control-flow witness is narrower and stronger
than assuming every parser path is affected.

The pinned defaults enable homing, but actual installed settings are unknown.
**No M95, homing, parser command or hardware action was executed.** M95 is also
outside the supported G0/G90/G91/G92 diagnostic replay subset. Correct
initialization/modal assignment and execution ordering require a separate
reviewed source change and tests; this audit proposes no operational workaround.

## Spindle signature and empty recovery path are separate issues

[`spindle_control.c:118`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/spindle_control.c#L118)
defines `spindle_set_state` without a return type while its header declares
`void`. The compiler reports both implicit-int and conflicting-type warnings.
The function body is empty in this source.

Its sole textual call site is the protocol's
[`re-energize spindle branch at 309`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/protocol.c#L309).
Ordinary speed/modal changes use `spindle_run` at
[`gcode.c:876/888`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L876),
which has a different nonempty PWM/control body. Thus it is incorrect to call
all M3/S control empty from this warning. The empty recovery function and type
mismatch remain source-correctness gates; actual servo behavior, recovery and
safe motor-energy handling were not tested or accepted.

## The EEPROM warning is a defined but weak recurrence

Both checksum loops at
[`eeprom.c:130–150`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/eeprom.c#L130)
use logical OR in the shifted-state expression. For the unsigned 8-bit checksum
promoted to the captured 16-bit `int`, that expression is 0 when the previous
checksum is zero and 1 otherwise. The update is consequently:

```text
c_next = (int(c != 0) + next_byte) modulo 256
```

The two-byte records `[1,42]` and `[2,42]` both produce 43. A pure expression
fixture and independently compiled constant data agree. This proves a concrete
collision; it does not characterize every error pattern or actual EEPROM
contents. It also does not establish that a bitwise rotate was the author's
intended replacement.

The settings layer uses these routines for startup lines, build information,
coordinate records and global settings. Both writer and reader currently use
the same recurrence, so they agree on existing valid records. Changing one side
alone, or changing both without a reviewed storage-version/migration policy,
can break compatibility. No EEPROM was read or written.

## What the static probes observed

The verified compiler from the prior build compiled **separate probe code**
into two ELF32 `EM_AVR`, `ET_REL` objects. Nothing was linked into a runnable
firmware image. Python reads named `.rodata` sections as bytes. The second
compile adds only `-Wshift-overflow=2`; recorded section data remain equal.

| Isolated expression/data | Observed encoding | Evidence boundary |
| --- | --- | --- |
| Signed `1<<16` assigned to uint16 | `0000` | This compiler's encoding of undefined C; not runtime semantics |
| Signed `1<<15` assigned to uint16 | `0080` | This compiler's encoding; stricter diagnostic warns |
| Unsigned `1U<<15` | `0080` | Defined unsigned expression; same bytes do not validate signed expression |
| Wide uint32 bit 16 | `00000100` | 65,536 is representable in the wide type |
| Wide bit 16 converted to uint16 | `0000` | Storage conversion loses the seventeenth bit |
| Axis-index `1<<6` in uint8 | `40` | A separate representable axis-presence mask |
| Logical-OR versus bitwise-OR shifted state 2 | `01` versus `04` | The operators compute different defined expressions |
| Checksum fixtures `[1,42]` and `[2,42]` | `2b` and `2b` | Concrete modeled collision; no EEPROM execution |

These encodings do not execute instructions or resolve all effects of undefined
source constructs in the complete optimizer/control flow. The original six
build warnings remain the historical result; the stronger probe adds a
diagnostic for the adjacent sign-bit case without modifying that build report.

## Reproduction and remaining work

From `arm-01`, the source-only audit needs no compiler or network:

```powershell
python tools/audit_thor_grbl_warnings.py --source ../.work/controller/grbl-source/upstream --output-dir ../.work/controller/grbl-warning-source-next
python -m pytest tests/test_thor_grbl_warnings.py
```

To add static probes on the Windows host, provide the existing verified ZIP and
extracted runtime:

```powershell
python tools/audit_thor_grbl_warnings.py --source ../.work/controller/grbl-source/upstream --output-dir ../.work/controller/grbl-warning-probes-next --toolchain-archive ../.work/controller/toolchain/avr-gcc-7.3.0-atmel3.6.1-arduino7-i686-w64-mingw32.zip --toolchain-root ../.work/controller/grbl-build-03/toolchain
```

Outputs must be new and separate from both source and compiler. A guard rejects
compiler-tree overlap before creating anything. Source/blob hashes, compiler
archive/file hashes, available disk reserve and source preservation are checked.
Reports and generated probe text use explicit LF. Compiler searches/temporary
files use the existing child-only isolation. No binaries, source copies or
toolchain files are committed. Sixteen portable tests cover ELF data guards,
expression fixtures, source/report bindings and preservation boundaries; these
are distinct from the captured native compiler invocation.

The next source work is a separately reviewed revision with a consistently wide
word mask and unsigned shifts, explicit M95 modal/control semantics, compatible
spindle recovery implementation and a deliberate checksum/storage policy.
Such changes require isolated compile/parser fixtures and independent review
before they can replace this pinned baseline. Installed firmware, real feedback,
hardware stop/energy isolation, calibration and physical commissioning remain
separate unresolved gates. No repair, release or hardware action follows from
this audit.
