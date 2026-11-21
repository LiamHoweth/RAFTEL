"""Shared validation for inputs to the logical task and its reporting tools."""

from math import isfinite
from numbers import Real


def finite(value: object, field: str = "value") -> float:
    message = f"{field} must be a finite real number"
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(message)
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(message) from exc
    if not isfinite(number):
        raise ValueError(message)
    return number


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate keys at every object level while decoding JSON."""
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f"duplicate JSON key: {key}")
        record[key] = value
    return record
