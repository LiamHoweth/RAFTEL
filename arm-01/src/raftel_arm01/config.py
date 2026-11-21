"""Strict configuration loading; no motor addresses or hardware backend."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from raftel_arm01._validation import finite, unique_object
from raftel_arm01.models import Bin, Position
from raftel_arm01.safety.envelope import Envelope


@dataclass(frozen=True)
class Config:
    bins: tuple[Bin, ...]
    envelope: Envelope
    clearance_m: float
    max_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.bins, Sequence) or not all(isinstance(b, Bin) for b in self.bins):
            raise ValueError("bins must be a sequence of Bin values")
        bins = tuple(self.bins)
        if len(bins) != 3 or len({b.category for b in bins}) != 3:
            raise ValueError("exactly three distinct sorting categories required")
        if len({b.position for b in bins}) != 3:
            raise ValueError("sorting bins must have distinct positions")
        if not isinstance(self.envelope, Envelope):
            raise ValueError("envelope must be an Envelope")
        if finite(self.clearance_m, "clearance in metres") <= 0:
            raise ValueError("clearance must be positive")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be integer 1..5")
        for b in bins:
            self.envelope.validate(b.position)
            self.envelope.validate(b.position.above(self.clearance_m))
        object.__setattr__(self, "bins", bins)

    def bin_at(self, position: Position) -> Bin | None:
        """Identify a logical bin by its exact position in arm_base."""
        return next((b for b in self.bins if b.position == position), None)


def _load_bin(data: object) -> Bin:
    if not isinstance(data, dict) or set(data) != {"category", "position"}:
        raise ValueError("sorting bin requires exactly category and position fields")
    position = data["position"]
    if not isinstance(position, dict) or set(position) != {"x", "y", "z"}:
        raise ValueError("bin position requires exactly x, y and z coordinates in metres")
    return Bin(data["category"], Position(**position))


def load_config(path: Path | None = None) -> Config:
    raw = (
        path.read_text(encoding="utf-8")
        if path
        else files("raftel_arm01").joinpath("defaults.json").read_text(encoding="utf-8")
    )
    try:
        data = json.loads(raw, object_pairs_hook=unique_object)
    except RecursionError as exc:
        raise ValueError("configuration JSON nesting limit exceeded") from exc
    if not isinstance(data, dict) or set(data) != {
        "frame",
        "bins",
        "envelope",
        "clearance_m",
        "max_attempts",
    }:
        raise ValueError("unexpected or missing configuration fields")
    if data["frame"] != "arm_base":
        raise ValueError("only the arm_base coordinate frame is supported")
    if not isinstance(data["bins"], list) or len(data["bins"]) != 3:
        raise ValueError("configuration must contain exactly three sorting bins")
    try:
        envelope = Envelope(**data["envelope"])
    except TypeError as exc:
        raise ValueError("configuration envelope has invalid fields") from exc
    return Config(
        tuple(_load_bin(row) for row in data["bins"]),
        envelope,
        data["clearance_m"],
        data["max_attempts"],
    )
