"""Exact decimal arithmetic and the envelope rounding rule.

Data files carry numbers as decimal strings; nothing in the engine may pass
through a binary float.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
)

from engine.errors import DataError

ZERO = Decimal("0")
CENT = Decimal("0.01")

_MODES = {
    "nearest": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "up": ROUND_CEILING,
    "down": ROUND_FLOOR,
}


def D(value: object, *, context: str = "value") -> Decimal:
    """Parse an exact decimal. Strings and ints only — floats are rejected
    because they already lost exactness upstream."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or isinstance(value, float):
        raise DataError(f"{context}: {value!r} is not an exact decimal; use a quoted string")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise DataError(f"{context}: cannot parse {value!r} as a decimal") from exc
    raise DataError(f"{context}: cannot parse {value!r} as a decimal")


@dataclass(frozen=True)
class Rounding:
    """The envelope `rounding` block. Default: round to the cent, half up,
    no intermediate rounding."""

    to: Decimal = CENT
    mode: str = "nearest"
    intermediate: str = "none"  # none | annual

    @classmethod
    def from_dict(cls, raw: dict | None) -> "Rounding":
        if raw is None:
            return cls()
        to = D(raw["to"], context="rounding.to")
        if to <= ZERO:
            raise DataError(f"rounding.to must be positive, got {to}")
        mode = raw["mode"]
        if mode not in _MODES:
            raise DataError(f"rounding.mode {mode!r} not one of {sorted(_MODES)}")
        intermediate = raw.get("intermediate", "none")
        if intermediate not in ("none", "annual"):
            raise DataError(f"rounding.intermediate {intermediate!r} not one of ['annual', 'none']")
        return cls(to=to, mode=mode, intermediate=intermediate)

    def apply(self, amount: Decimal) -> Decimal:
        """Round to the nearest multiple of `to` using `mode`."""
        multiples = (amount / self.to).to_integral_value(rounding=_MODES[self.mode])
        return (multiples * self.to).quantize(CENT)
