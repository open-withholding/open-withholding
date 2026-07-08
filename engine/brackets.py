"""Bracket tables: parse, validate, and evaluate.

Rows carry `over` (lower bound) only; upper bounds are implied by the next
row. A printed `base` per row is AUTHORITATIVE when present — guides'
worked examples compute base + rate x excess from the printed column, so the
engine must too. The recomputed cumulative sum is a transcription check, with
a small tolerance: agencies round printed thresholds but derive the base
column from unrounded amounts (e.g. Pub 15-T 2026 halves the MFJ checkbox
table, printing threshold $108,938 for a true boundary of $108,937.50 and a
base of $20,512.00 where the printed-threshold sum gives $20,512.12).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.errors import DataError
from engine.money import ZERO, D

# Max |declared base - recomputed cumulative| before a file is rejected.
# Threshold rounding accounts for < ~$0.20 of drift; real transcription
# errors are typically dollars. Golden tests remain the backstop for
# sub-dollar mistakes in brackets that worked examples exercise.
BASE_TOLERANCE = Decimal("1.00")


@dataclass(frozen=True)
class BracketRow:
    over: Decimal
    rate: Decimal
    base: Decimal  # tax on income below `over`; printed value wins when declared


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
        base = cumulative
        declared = row.get("base")
        if declared is not None:
            declared = D(declared, context=f"{where}.base")
            if abs(declared - cumulative) > BASE_TOLERANCE:
                raise DataError(
                    f"{where}: declared base {declared} is {abs(declared - cumulative)} from "
                    f"the recomputed cumulative {cumulative} (tolerance {BASE_TOLERANCE}); "
                    f"transcription error"
                )
            base = declared  # printed value is what the guide's examples use
        parsed.append(BracketRow(over=over, rate=rate, base=base))
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
