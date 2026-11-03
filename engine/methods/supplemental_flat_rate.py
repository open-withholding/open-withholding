"""Reference implementation of /methods/supplemental.md — `supplemental_flat_rate` (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.money import D, ZERO


def compute(ctx) -> Decimal:
    params = ctx.params
    rate = D(params["rate"], context="params.rate")
    taxable = ctx.taxable_wages
    ytd = D((ctx.ytd or {}).get("supplemental_wages", "0"), context="ytd.supplemental_wages")
    threshold = params.get("excess_threshold")
    if threshold is not None:
        threshold = D(threshold, context="params.excess_threshold")
        excess_rate = D(params["excess_rate"], context="params.excess_rate")
        below = max(ZERO, min(taxable, threshold - ytd))
        above = taxable - below
        return ctx.rounding.apply(below * rate + above * excess_rate)
    return ctx.rounding.apply(taxable * rate)
