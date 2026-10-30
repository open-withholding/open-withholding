"""Reference implementation of /methods/resident_nonresident_flat_rate.md (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.money import D


def compute(ctx) -> Decimal:
    key = "nonresident_rate" if ctx.resident is False else "resident_rate"
    rate = D(ctx.params[key], context=f"params.{key}")
    return ctx.rounding.apply(ctx.taxable_wages * rate) + ctx.additional_withholding
