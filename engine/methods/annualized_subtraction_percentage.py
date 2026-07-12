"""Reference implementation of /methods/annualized_subtraction_percentage.md
(v1). Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    snap = params["midrange_snap"]
    bracket = D(snap["bracket_size"], context="midrange_snap.bracket_size")
    midpoint = D(snap["midpoint"], context="midrange_snap.midpoint")
    snap_below = D(snap["snap_below"], context="midrange_snap.snap_below")
    sd = D(params["standard_deduction"], context="params.standard_deduction")
    cpa = (
        D(params["credit_per_allowance"], context="params.credit_per_allowance")
        if params.get("credit_per_allowance") is not None
        else ZERO
    )

    # Steps 2-4: annualize, deduct, snap.
    annual = ctx.taxable_wages * ctx.pay_periods
    nti = clamp0(annual - sd)
    if nti < snap_below:
        nti = (nti / bracket).to_integral_value(rounding="ROUND_FLOOR") * bracket + midpoint

    # Step 5: printed rate-minus-subtraction row (last with from <= income).
    row = params["table"][0]
    for candidate in params["table"]:
        if D(candidate["from"], context="table.from") <= nti:
            row = candidate
        else:
            break
    rate = D(row["rate"], context="table.rate")
    subtract = D(row.get("subtract") or "0", context="table.subtract")
    gross_tax = clamp0(nti * rate - subtract)

    # Steps 6-8: round annual tax, credits, de-annualize.
    gross_tax = ctx.rounding.apply_intermediate(gross_tax)
    net_tax = clamp0(gross_tax - ctx.allowances * cpa)
    return ctx.rounding.apply(net_tax / ctx.pay_periods) + ctx.additional_withholding
