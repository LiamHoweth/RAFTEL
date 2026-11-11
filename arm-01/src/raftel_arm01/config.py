"""Strict configuration loading; no motor addresses or hardware backend."""

import json
from dataclasses import dataclass
from importlib.resources import files
from math import isfinite
from pathlib import Path

from raftel_arm01.models import Bin, Position
from raftel_arm01.safety.envelope import Envelope


@dataclass(frozen=True)
class Config:
    bins: tuple[Bin, ...]
    envelope: Envelope
    clearance_m: float
    max_attempts: int

    def __post_init__(self) -> None:
        if any(not isinstance(b.category, str) or not b.category.strip() for b in self.bins):
            raise ValueError("bin categories must be nonempty strings")
        if len(self.bins) != 3 or len({b.category for b in self.bins}) != 3:
            raise ValueError("exactly three distinct sorting categories required")
        if any(not b.category for b in self.bins):
            raise ValueError("bin category cannot be empty")
        if not isfinite(self.clearance_m) or self.clearance_m <= 0:
            raise ValueError("clearance must be finite and positive")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be integer 1..5")
        for b in self.bins:
            self.envelope.validate(b.position)
            self.envelope.validate(b.position.above(self.clearance_m))


def load_config(path: Path | None = None) -> Config:
    raw = path.read_text() if path else files("raftel_arm01").joinpath("defaults.json").read_text()
    data = json.loads(raw)
    if set(data) != {"frame", "bins", "envelope", "clearance_m", "max_attempts"}:
        raise ValueError("unexpected or missing configuration fields")
    if data["frame"] != "arm_base":
        raise ValueError("only the arm_base coordinate frame is supported")
    bins = tuple(
        Bin(category=b["category"], position=Position(**b["position"])) for b in data["bins"]
    )
    return Config(bins, Envelope(**data["envelope"]), data["clearance_m"], data["max_attempts"])
