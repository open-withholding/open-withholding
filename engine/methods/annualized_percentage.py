"""Reference implementation of /methods/annualized_percentage.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.methods.common import clamp0, per_status
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    status = ctx.filing_status

    standard_deduction = ZERO
    if params.get("standard_deduction"):
        standard_deduction = D(
            per_status(params["standard_deduction"], status, context="annualized_percentage"),
            context="params.standard_deduction",
        )
    allowance_amount = (
        D(params["allowance_amount"], context="params.allowance_amount")
        if params.get("allowance_amount") is not None
        else ZERO
    )
    secondary_allowance_amount = (
        D(params["secondary_allowance_amount"], context="params.secondary_allowance_amount")
        if params.get("secondary_allowance_amount") is not None
        else ZERO
    )
    credit_per_allowance = (
        D(params["credit_per_allowance"], context="params.credit_per_allowance")
        if params.get("credit_per_allowance") is not None
        else None
    )
    table = per_status(ctx.bracket_tables, status, context="annualized_percentage")

    # Steps 2-3: annualize, subtract deductions and allowances, clamp.
    annual_wages = ctx.taxable_wages * ctx.pay_periods
    percent_deduction = ZERO
    pd = params.get("percent_deduction")
    if pd is not None:
        # v1.2: percentage-of-wages deduction with a cap, optionally gated on
        # claiming at least one allowance (South Carolina WH-1603F).
        claiming = (ctx.allowances + ctx.secondary_allowances) > 0
        if claiming or not pd.get("requires_allowances", False):
            percent_deduction = min(
                annual_wages * D(pd["rate"], context="percent_deduction.rate"),
                D(pd["cap"], context="percent_deduction.cap"),
            )
    annual_taxable = clamp0(
        annual_wages
        - standard_deduction
        - percent_deduction
        - ctx.allowances * allowance_amount
        - ctx.secondary_allowances * secondary_allowance_amount
    )

    # Step 4 (+ optional intermediate rounding, worked-examples permitting).
    annual_tax = tax_for(table, annual_taxable)
    if ctx.rounding.intermediate == "annual":
        annual_tax = ctx.rounding.apply_intermediate(annual_tax)

    # Step 5: per-allowance credits.
    if credit_per_allowance is not None:
        annual_tax = clamp0(annual_tax - ctx.allowances * credit_per_allowance)

    # Steps 6-7: de-annualize, round once, add extra withholding.
    period_tax = annual_tax / ctx.pay_periods
    return ctx.rounding.apply(period_tax) + ctx.additional_withholding
