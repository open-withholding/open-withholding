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
    no intermediate rounding.

    `intermediate_to` lets the intermediate (annualized) rounding use a
    different granularity than the final rounding — Virginia's worksheet
    rounds the annual tax to whole dollars, then divides to a cents result."""

    to: Decimal = CENT
    mode: str = "nearest"
    intermediate: str = "none"  # none | annual
    intermediate_to: Decimal | None = None  # defaults to `to`

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
        intermediate_to = None
        if raw.get("intermediate_to") is not None:
            intermediate_to = D(raw["intermediate_to"], context="rounding.intermediate_to")
            if intermediate_to <= ZERO:
                raise DataError(f"rounding.intermediate_to must be positive, got {intermediate_to}")
        return cls(to=to, mode=mode, intermediate=intermediate, intermediate_to=intermediate_to)

    def _round(self, amount: Decimal, granularity: Decimal) -> Decimal:
        multiples = (amount / granularity).to_integral_value(rounding=_MODES[self.mode])
        return (multiples * granularity).quantize(CENT)

    def apply(self, amount: Decimal) -> Decimal:
        """Round to the nearest multiple of `to` using `mode`."""
        return self._round(amount, self.to)

    def apply_intermediate(self, amount: Decimal) -> Decimal:
        """Round an intermediate (annualized) amount, at `intermediate_to`
        granularity when set, else `to`."""
        return self._round(amount, self.intermediate_to or self.to)
