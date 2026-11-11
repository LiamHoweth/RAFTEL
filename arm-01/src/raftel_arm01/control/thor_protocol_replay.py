"""Bounded in-memory GRBL coordinate/step diagnostics, with no transport API.

Only G0/G90/G91/G92/G92.1 and seven Thor axis words are modeled. This is not a
firmware emulator: timing, acceleration, limits, homing, EEPROM and hardware
feedback are absent. Accepted targets and synthetic completed step counts are
separate, including when acknowledgments are lost. AVR float32 arithmetic and
lround's half-away-from-zero rule model the audited scalar planner path.
"""

from __future__ import annotations

import math
import re
import struct
from collections.abc import Sequence
from dataclasses import dataclass, replace
from numbers import Real

from .thor_source_conversion import GRBL_AXES

GRBL_REVISION = "1f6437a77e3abcb652d3f8ce718faf7e041ae6ff"
EVIDENCE_CLASS = "synthetic_protocol_replay_not_measured_pose"
SOURCE_DEFAULT_STEPS_PER_DEGREE = (44.5, 270.0, 270.0, 265.0, 20.0, 250.0, 250.0)
_WORD = re.compile(r"([A-Z])([+-]?(?:\d+(?:\.\d*)?|\.\d+))", re.ASCII)
_MAX_STEP = 2**31 - 1


def _finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("finite numeric inputs are required")
    try:
        value = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("finite numeric inputs are required") from error
    if not math.isfinite(value):
        raise ValueError("finite numeric inputs are required")
    return value


def _f32(value: float) -> float:
    try:
        return _finite(struct.unpack("<f", struct.pack("<f", _finite(value)))[0])
    except (OverflowError, struct.error) as error:
        raise ValueError("value exceeds finite float32 diagnostic range") from error


def _vector(values: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(values, Sequence) or isinstance(values, str | bytes) or len(values) != 7:
        raise ValueError("expected seven complete channel values")
    return tuple(_f32(value) for value in values)


def scalar_steps(target_deg: float, steps_per_degree: float) -> int:
    """Audited AVR scalar math within the conservative symmetric int32 subset."""
    scale = _f32(steps_per_degree)
    if scale <= 0:
        raise ValueError("steps_per_degree must be positive")
    product = _f32(_f32(target_deg) * scale)
    result = math.floor(product + 0.5) if product >= 0 else math.ceil(product - 0.5)
    if abs(result) > _MAX_STEP:
        raise ValueError("target exceeds signed 32-bit step diagnostic range")
    return result


def source_decimal(text: str) -> float:
    """Audited read_float digit accumulation with AVR float32 multiplications.

    Only eight digits are accumulated, including leading zeros. Later integer
    digits change the exponent; later fractional digits are discarded. Limit
    the total digits to 64 so the source's int8 exponent cannot overflow. This
    keeps the supported path defined instead of hiding parser truncation behind
    Python's decimal conversion. Scientific notation remains unsupported.
    """
    if not isinstance(text, str) or not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text, re.ASCII
    ):
        raise ValueError("malformed decimal source word")
    negative = text.startswith("-")
    text = text.lstrip("+-")
    if sum(char.isdigit() for char in text) > 64:
        raise ValueError("decimal exceeds bounded defined-exponent diagnostic subset")
    integer, exponent, digits, decimal = 0, 0, 0, False
    for char in text:
        if char == ".":
            decimal = True
        else:
            digits += 1
            if digits <= 8:
                integer = integer * 10 + int(char)
                if decimal:
                    exponent -= 1
            elif not decimal:
                exponent += 1
    value = _f32(integer)
    if value != 0:
        while exponent <= -2:
            value = _f32(value * _f32(0.01))
            exponent += 2
        if exponent < 0:
            value = _f32(value * _f32(0.1))
        elif exponent > 0:
            for _ in range(exponent):
                value = _f32(value * _f32(10.0))
    return -value if negative else value


@dataclass(frozen=True)
class ReplayReceipt:
    sequence: int
    diagnostic_line: str
    parser_target_deg: tuple[float, ...]
    planned_steps: tuple[int, ...]
    motion_word_present: bool
    acknowledged: bool = False
    completed_in_simulation: bool = False
    invalidated_by_reset: bool = False
    evidence_class: str = EVIDENCE_CLASS


@dataclass(frozen=True)
class SyntheticStatus:
    """Complete diagnostic state. It is never evidence from an encoder."""

    sequence: int
    timestamp_s: float
    completed_steps: tuple[int, ...]
    pending_commands: int
    evidence_class: str = EVIDENCE_CLASS


def _parse(line: str) -> tuple[list[str], dict[int, float]]:
    if not isinstance(line, str) or not line or len(line) > 256:
        raise ValueError("a diagnostic line must contain 1..256 characters")
    line = line.removesuffix("\r\n").removesuffix("\n")
    compact = line.replace(" ", "")
    words = list(_WORD.finditer(compact))
    if not words or "".join(match[0] for match in words) != compact:
        raise ValueError("malformed or unsupported diagnostic words")
    gcodes: list[str] = []
    values: dict[int, float] = {}
    groups: set[str] = set()
    for match in words:
        letter, text = match.groups()
        if letter == "G":
            # Match supported numeric values but reject obscure noncanonical codes.
            code_value = float(text)
            code = {0.0: "G0", 90.0: "G90", 91.0: "G91", 92.0: "G92", 92.1: "G92.1"}.get(code_value)
            if code is None:
                raise ValueError("unsupported diagnostic G code")
            group = "distance" if code in {"G90", "G91"} else "motion_or_offset"
            if group in groups:
                raise ValueError("duplicate or conflicting G modal group")
            groups.add(group)
            gcodes.append(code)
        elif letter in GRBL_AXES:
            index = GRBL_AXES.index(letter)
            if index in values:
                raise ValueError("duplicate channel word")
            values[index] = source_decimal(text)
        else:
            raise ValueError(f"unsupported diagnostic word {letter}")
    if not gcodes and not values:
        raise ValueError("empty diagnostic line")
    return gcodes, values


class DiagnosticReplay:
    """Small source-coordinate replay, independent of mock arm/task control.

    Construction establishes an explicit synthetic origin, G90, zero G92 and
    a supplied work offset. A reset invalidates that knowledge and latches a
    fault; create a new replay with explicit synthetic starting conditions.
    No methods connect, emit, arm, home or recover physical equipment.
    """

    def __init__(
        self,
        *,
        steps_per_degree: Sequence[float] = SOURCE_DEFAULT_STEPS_PER_DEGREE,
        work_offset_deg: Sequence[float] = (0,) * 7,
        max_commands: int = 10_000,
        max_pending: int = 128,
    ) -> None:
        self.scales = _vector(steps_per_degree)
        if any(scale <= 0 for scale in self.scales):
            raise ValueError("all scalar step scales must be positive")
        self.work_offset_deg = _vector(work_offset_deg)
        for bound in (max_commands, max_pending):
            if type(bound) is not int or not 1 <= bound <= 100_000:
                raise ValueError("replay bounds must be integers within 1..100000")
        self.max_commands, self.max_pending = max_commands, max_pending
        self.absolute = True
        self.g92_offset_deg = (0.0,) * 7
        self.parser_target_deg = (0.0,) * 7
        self.completed_steps = (0,) * 7
        self.receipts: list[ReplayReceipt] = []
        self._pending: list[int] = []
        self.fault: str | None = None
        self._status_sequence = 0
        self._last_status_sequence = -1
        self._last_status_timestamp = -math.inf

    def _ready(self) -> None:
        if self.fault is not None:
            raise ValueError(f"replay fault is latched: {self.fault}")

    def submit(self, line: str, *, acknowledgment_received: bool = True) -> ReplayReceipt:
        """Accept a diagnostic line atomically; acknowledgment is not completion.

        Axis-only lines use the modeled G0 modal state. All accepted lines,
        including mode/offset changes, are ordered in the synthetic queue.
        acknowledgment_received is per-line synthetic ground truth, not an
        attribution algorithm for an untagged GRBL ok stream. When replaying
        a stream, submit unacknowledged lines and call acknowledge in FIFO order.
        Re-submitting an unacknowledged G91 line applies it twice, as the source
        has no command ID deduplication. The fixture exposes that ambiguity.
        """
        self._ready()
        if type(acknowledgment_received) is not bool:
            raise ValueError("acknowledgment_received must be boolean")
        if len(self.receipts) >= self.max_commands or len(self._pending) >= self.max_pending:
            raise ValueError("bounded replay capacity exceeded")
        gcodes, values = _parse(line)
        absolute = self.absolute
        if "G90" in gcodes:
            absolute = True
        if "G91" in gcodes:
            absolute = False
        target = list(self.parser_target_deg)
        offsets = list(self.g92_offset_deg)
        if "G92" in gcodes:
            if not values:
                raise ValueError("G92 requires at least one channel")
            for index, value in values.items():
                offsets[index] = _f32(_f32(target[index] - self.work_offset_deg[index]) - value)
        elif "G92.1" in gcodes:
            if values:
                raise ValueError("G92.1 must not include channel words in this diagnostic subset")
            offsets = [0.0] * 7
        else:
            for index, value in values.items():
                if absolute:
                    target[index] = _f32(value + _f32(self.work_offset_deg[index] + offsets[index]))
                else:
                    target[index] = _f32(value + target[index])
        planned = tuple(scalar_steps(target[i], self.scales[i]) for i in range(7))
        prior = self.receipts[-1].planned_steps if self.receipts else self.completed_steps
        if any(abs(planned[i] - prior[i]) > _MAX_STEP for i in range(7)):
            raise ValueError("step delta exceeds signed 32-bit diagnostic range")
        receipt = ReplayReceipt(
            len(self.receipts), line, tuple(target), planned, bool(values and "G92" not in gcodes)
        )
        receipt = replace(receipt, acknowledged=acknowledgment_received)
        self.absolute, self.g92_offset_deg = absolute, tuple(offsets)
        self.parser_target_deg = tuple(target)
        self.receipts.append(receipt)
        self._pending.append(receipt.sequence)
        return receipt

    def acknowledge(self, sequence: int) -> ReplayReceipt:
        """Record an acknowledgment only for the first unacknowledged line."""
        self._ready()
        unacked = [r.sequence for r in self.receipts if not r.acknowledged]
        if type(sequence) is not int or not unacked or sequence != unacked[0]:
            raise ValueError("acknowledgment is duplicate, missing or out of order")
        receipt = replace(self.receipts[sequence], acknowledged=True)
        self.receipts[sequence] = receipt
        return receipt

    def complete_next(self) -> ReplayReceipt:
        """Advance only the oldest accepted line in the synthetic execution."""
        self._ready()
        if not self._pending:
            raise ValueError("no pending diagnostic command")
        sequence = self._pending.pop(0)
        receipt = replace(self.receipts[sequence], completed_in_simulation=True)
        self.receipts[sequence] = receipt
        self.completed_steps = receipt.planned_steps
        return receipt

    def status(self, timestamp_s: float) -> SyntheticStatus:
        """Return command-derived synthetic step state, never a measured pose."""
        self._ready()
        timestamp = _finite(timestamp_s)
        if timestamp < 0:
            raise ValueError("timestamp must be nonnegative")
        status = SyntheticStatus(
            self._status_sequence, timestamp, self.completed_steps, len(self._pending)
        )
        self._status_sequence += 1
        return status

    def observe_status(self, status: SyntheticStatus, *, now_s: float, max_age_s: float) -> None:
        """Validate complete fresh ordered synthetic status and latch ambiguity.

        Faults cannot be cleared by another status, acknowledgments, or submit.
        B/C disagreement is evaluated in source channel degrees using their
        individual scales, so unequal scales are not confused with unequal
        modeled angles. This equality is numeric only, not a physical threshold.
        """
        self._ready()
        now, max_age = _finite(now_s), _finite(max_age_s)
        reason = None
        if now < 0 or max_age < 0:
            raise ValueError("now and maximum age must be nonnegative")
        if not isinstance(status, SyntheticStatus) or status.evidence_class != EVIDENCE_CLASS:
            reason = "non_synthetic_or_malformed_status"
        elif (
            type(status.sequence) is not int
            or status.sequence <= self._last_status_sequence
            or type(status.pending_commands) is not int
            or status.pending_commands < 0
            or status.pending_commands > self.max_pending
        ):
            reason = "out_of_order_or_malformed_status"
        elif (
            not isinstance(status.completed_steps, tuple)
            or len(status.completed_steps) != 7
            or any(type(v) is not int or abs(v) > _MAX_STEP for v in status.completed_steps)
        ):
            reason = "partial_or_malformed_status"
        else:
            try:
                timestamp = _finite(status.timestamp_s)
            except ValueError:
                reason = "malformed_status_timestamp"
            else:
                if (
                    timestamp < self._last_status_timestamp
                    or timestamp < 0
                    or timestamp > now
                    or now - timestamp > max_age
                ):
                    reason = "stale_or_future_status"
                elif not math.isclose(
                    status.completed_steps[1] / self.scales[1],
                    status.completed_steps[2] / self.scales[2],
                    rel_tol=0,
                    abs_tol=1e-9,
                ):
                    reason = "duplicate_shoulder_disagreement"
        if reason is not None:
            self.fault = reason
            raise ValueError(f"replay fault is latched: {reason}")
        self._last_status_sequence = status.sequence
        self._last_status_timestamp = status.timestamp_s

    def reset(self) -> None:
        """Invalidate accepted-but-uncompleted work; reset never verifies origin."""
        for sequence in self._pending:
            self.receipts[sequence] = replace(self.receipts[sequence], invalidated_by_reset=True)
        self._pending.clear()
        self.fault = "reset_invalidates_mode_offsets_and_position_knowledge"
