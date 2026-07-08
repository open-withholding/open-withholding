"""Reference implementation of /methods/flat_rate.md (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.money import D


def compute(ctx) -> Decimal:
    rate = D(ctx.params["rate"], context="params.rate")
    return ctx.rounding.apply(ctx.taxable_wages * rate) + ctx.additional_withholding
