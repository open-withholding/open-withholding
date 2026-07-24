"""Reference implementation of /methods/futa.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    ytd = ctx.ytd or {}

    # Step 1: net rate for a full-credit employer, plus any credit
    # reduction for the state whose UI program the employer pays into.
    rate = D(params["rate"], context="futa.rate")
    credit = D(params["max_credit"], context="futa.max_credit")
    reductions = params.get("credit_reductions") or {}
    reduction = ZERO
    if ctx.sui_jurisdiction and ctx.sui_jurisdiction in reductions:
        reduction = D(reductions[ctx.sui_jurisdiction],
                      context=f"futa.credit_reductions.{ctx.sui_jurisdiction}")
    effective = rate - credit + reduction

    # Step 2: cap against the annual wage base.
    wage_base = D(params["wage_base"], context="futa.wage_base")
    ytd_futa = D(ytd.get("futa_wages", "0"), context="ytd.futa_wages")
    taxable = min(ctx.taxable_wages, clamp0(wage_base - ytd_futa))

    # Step 3.
    return ctx.rounding.apply(taxable * effective)
