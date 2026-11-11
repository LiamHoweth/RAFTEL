# Pinned GRBL AVR build feasibility

The unmodified pinned GRBL Thor source **cross-compiles on this Windows host**
with a small isolated official AVR toolchain. Two fresh build directories
produce byte-identical ELF and Intel HEX artifacts. This is build-feasibility
evidence only: six compiler warnings remain explicit source-correctness gates.
No firmware was executed, emulated, uploaded or flashed, and no hardware/serial
device was connected or inspected.

The [machine-readable capture](../hardware/cad/thor-grbl-build-feasibility.json)
binds all 72 source files, compiler archive, selected macros, flags, output
hashes, memory output, warning messages and two successful local captures.
Source/toolchain/binaries remain in ignored `.work/controller/` scratch, with
original notices retained. Only the diagnostic script, guard tests, report and
this document are tracked.

## Source, compiler and build recipe

| Input | Verified value |
| --- | --- |
| Source | [AngelLM/grbl](https://github.com/AngelLM/grbl/tree/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff), revision `1f6437a77e3abcb652d3f8ce718faf7e041ae6ff` |
| Source tree | `0748cdaf21d34b189ffb7fd926f6217040e2f952` |
| Toolchain | Official Arduino AVR GCC `7.3.0-atmel3.6.1-arduino7`, Windows `i686-mingw32` |
| Official archive | [Arduino compiler ZIP](https://downloads.arduino.cc/tools/avr-gcc-7.3.0-atmel3.6.1-arduino7-i686-w64-mingw32.zip), 52,519,412 bytes |
| Published archive SHA-256 | `a54f64755fff4cb792a1495e5defdd789902a2a3503982e81b898299cf39800e` |
| Artifact metadata | [Official Arduino package index](https://downloads.arduino.cc/packages/package_index.json), retrieved 2026-11-11; snapshot hash retained in the report |
| Target | ATmega2560, 16 MHz, seven axes, `DEFAULTS_THOR`, `CPU_MAP_ATMEGA2560`; `COREXY` absent |
| Confirmed ABI | `int` 16 bits, `long` 32 bits, `float` 32 bits, `double` 32 bits |

The checksum from the official index matches the downloaded archive's actual
bytes. The extracted toolchain has 1,628 files (219,613,639 uncompressed bytes
including archive members); byte hashes and file coverage are checked before
and after compilation. This is an explicitly pinned usable historical compiler,
not a claim that it is the latest compiler or the official release binary's
original toolchain.

The [upstream Makefile](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/Makefile)
provides the 17 C translation units and flags. The diagnostic script reproduces
its compile/link recipe directly:

```text
-Wall -Os -DF_CPU=16000000 -mmcu=atmega2560 -I.
-ffunction-sections -fdata-sections
```

Each source compiles with `-MMD -MP -c`; linking adds `-lm -Wl,--gc-sections`.
`avr-objcopy` selects `.text` and `.data` for Intel HEX, and `avr-size` inspects
the ELF. **No Makefile target is invoked**: that Makefile also contains upload,
fuse and bootloader targets, which are outside this task. The only directly
allowed native executables are `avr-gcc.exe`, `avr-objcopy.exe` and `avr-size.exe`.
The compiler's pinned assembler/linker/helper binaries run as normal compiler
subprocesses; no resulting AVR program runs.

## Actual build captures

| Output | SHA-256 | File size |
| --- | --- | --- |
| Diagnostic ELF | `32048673548dcbf94d1b6382da9ea296c7ee0011cd3de21734e873a1fc2ce68b` | 56,976 bytes |
| Diagnostic Intel HEX | `7f13139cbac7e25754cf93f43c7af42443f73fab9ae2c09931f4bc9713f79db4` | 89,007 bytes |

Build 02 completed at **2026-11-11 20:32:13 UTC**; build 03 completed at
**20:35:09 UTC** with the final child-only environment isolation and additional
ABI guards. Both artifact hashes agree exactly. A prior attempt stopped before
compilation because the strict version guard expected `avr-gcc` while the
official Windows compiler reports `avr-gcc.exe`; that failed directory is
preserved. No upstream source was changed to obtain a successful build.

The tool reports `.text=31,640`, `.data=0`, `.bss=2,075` bytes. Device memory
output gives a 31,640-byte program image (12.1% of the target's flash) and
2,075-byte static data allocation (25.3% of SRAM). This is not a stack-usage,
runtime heap/interrupt-stack or worst-case SRAM qualification, and says nothing
about electrical or motion safety. No capacity margin is released from it.

## Unresolved compiler/source-correctness gates

The six warnings are retained in the report and complete local build logs.
They must not be dismissed as harmless build noise:

1. **Axis-word mask width:**
   [`gcode.h:144`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.h#L144)
   defines `WORD_Z=16`.
   [`nuts_bolts.h:58`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/nuts_bolts.h#L58)
   defines `bit(n)` as `1 << n`, while this AVR ABI has a 16-bit signed `int`.
   The compiler warns on `bit(WORD_Z)` expanded at
   [`gcode.c:852`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L852).
   A shift by the operand width is not a valid C shift. The source's
   `uint16_t value_words` at line 97 also cannot represent bit 16; widening only
   the literal would not by itself establish a correct whole parser mask.
   Actual runtime effects remain untested and source repair is a separate task.
2. **Potentially uninitialized `word_bit`:** the compiler points to
   `gc_execute_line`, declaration at `gcode.c:105`, through the same `bit` macro.
   A full parser-control-flow review and regression fixtures are needed before
   classifying the warning or proposing a source revision.
3. **Spindle function signature:**
   [`spindle_control.c:118`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/spindle_control.c#L118)
   omits a return type on `spindle_set_state`, conflicting with the header's
   `void` declaration. Both implicit-int and conflicting-type warnings occur.
4. **EEPROM checksum expressions:**
   [`eeprom.c:133/144`](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/eeprom.c#L133)
   use logical OR in `(checksum << 1) || (checksum >> 7)`. The compiler warns
   about shifted expressions in boolean context. Changing that operator could
   affect stored-checksum compatibility; no change or EEPROM access was made.

The [source-coordinate replay](thor-controller-replay.md) tests a bounded
declared arithmetic/protocol subset. Successful cross-compilation does not
validate that the full pinned parser, planner, stepper or gripper behaves like
that subset at runtime. These warnings add unresolved gates; they do not
retroactively convert synthetic fixture results into firmware execution.
Installed firmware/settings and equivalence to an upstream prebuilt release
remain unknown.

## Reproduction and guard behavior

[`build_thor_grbl_diagnostic.py`](../tools/build_thor_grbl_diagnostic.py) performs
no downloads or global installation. Supply an already obtained exact checkout
and pinned official ZIP. Preserve source LF bytes when checking out on Windows
(`git -c core.autocrlf=false checkout --detach` in a newly created source copy);
the script rejects modified/untracked sources or any on-disk byte that differs
from its immutable Git blob. Do not use that command to replace a dirty checkout.

From `arm-01`, using the retained local inputs and a **new** output directory:

```powershell
python tools/build_thor_grbl_diagnostic.py --source ../.work/controller/grbl-source/upstream --toolchain-archive ../.work/controller/toolchain/avr-gcc-7.3.0-atmel3.6.1-arduino7-i686-w64-mingw32.zip --output-dir ../.work/controller/grbl-build-next
python -m pytest tests/test_build_thor_grbl_diagnostic.py
```

The script requires Windows for this pinned compiler artifact. It checks at
least 50 GiB free plus a bounded extraction allowance, verifies the source and
archive before creating a build, copies only tracked source files and notices,
rejects links/traversal/duplicate archive members, validates compiler file
coverage/hashes and checks the source remains unchanged afterward. It refuses
existing or source-overlapping output directories and deletes nothing.

Compiler search overrides are removed **only from child process environments**.
The child's PATH contains the verified toolchain and Windows System32, and
temporary files use a private build directory. Global environment, profiles,
drivers, power policy and devices remain untouched. Reports use explicit LF
newlines; source/notice bytes are preserved exactly. Binaries, compiler,
source copies and large logs are not committed.

Sixteen portable guard tests use synthetic files/process doubles to verify
input/hash/path/source/environment/disk boundaries. They do not run or simulate
firmware and are separate from the actual local AVR capture. Linux CI can run
those guard tests without acquiring the Windows compiler or native source.

The pinned upstream source retains its GPL-3.0-or-later headers and `COPYING`
notice (SHA-256 retained). The complete compiler archive and its notices remain
local. No binary distribution or RAFTEL company-wide license decision is made.
