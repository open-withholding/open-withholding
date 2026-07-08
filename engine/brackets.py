"""Bracket tables: parse, validate, and evaluate.

Rows carry `over` (lower bound) only; upper bounds are implied by the next
row. A precomputed `base` per row is permitted by the schema but MUST match
the recomputed cumulative sum — a mismatch means a transcription error and
the file is rejected at load time.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.errors import DataError
from engine.money import ZERO, D


@dataclass(frozen=True)
class BracketRow:
    over: Decimal
    rate: Decimal
    base: Decimal  # cumulative tax on income below `over`


def parse_table(rows: list[dict], *, context: str = "brackets") -> tuple[BracketRow, ...]:
    if not rows:
        raise DataError(f"{context}: table is empty")
    parsed: list[BracketRow] = []
    cumulative = ZERO
    prev_over: Decimal | None = None
    prev_rate: Decimal | None = None
    for i, row in enumerate(rows):
        where = f"{context}[{i}]"
        over = D(row["over"], context=f"{where}.over")
        rate = D(row["rate"], context=f"{where}.rate")
        if i == 0:
            if over != ZERO:
                raise DataError(f"{where}: first row must have over == 0, got {over}")
        else:
            if over <= prev_over:
                raise DataError(
                    f"{where}: rows must be strictly ascending by `over` "
                    f"({over} follows {prev_over})"
                )
            cumulative += (over - prev_over) * prev_rate
        declared = row.get("base")
        if declared is not None:
            declared = D(declared, context=f"{where}.base")
            if declared != cumulative:
                raise DataError(
                    f"{where}: declared base {declared} != recomputed cumulative {cumulative}; "
                    f"transcription error"
                )
        parsed.append(BracketRow(over=over, rate=rate, base=cumulative))
        prev_over, prev_rate = over, rate
    return tuple(parsed)


def tax_for(table: tuple[BracketRow, ...], amount: Decimal) -> Decimal:
    """Cumulative tax on `amount`: base of the containing row plus the row's
    rate on the excess. `amount` must be >= 0 (callers clamp first)."""
    if amount < ZERO:
        raise DataError(f"bracket amount must be non-negative, got {amount}")
    row = table[0]
    for candidate in table:
        if candidate.over <= amount:
            row = candidate
        else:
            break
    return row.base + (amount - row.over) * row.rate
