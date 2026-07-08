"""Reference implementation of /methods/flat_rate_with_annual_allowance.md (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.methods.common import clamp0, per_status
from engine.money import D


def compute(ctx) -> Decimal:
    rate = D(ctx.params["rate"], context="params.rate")
    status_params = per_status(
        ctx.params["filing_status"], ctx.filing_status, context="flat_rate_with_annual_allowance"
    )
    allowance = D(status_params["annual_allowance"], context="params.annual_allowance")

    annual_wages = ctx.taxable_wages * ctx.pay_periods
    annual_taxable = clamp0(annual_wages - allowance)
    annual_tax = annual_taxable * rate
    if ctx.rounding.intermediate == "annual":
        annual_tax = ctx.rounding.apply(annual_tax)
    period_tax = annual_tax / ctx.pay_periods
    return ctx.rounding.apply(period_tax) + ctx.additional_withholding
