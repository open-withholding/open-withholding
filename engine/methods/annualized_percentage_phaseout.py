"""Reference implementation of /methods/annualized_percentage_phaseout.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.methods.common import clamp0, per_status
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    status = ctx.filing_status

    phaseout = per_status(
        params["deduction_phaseout"], status, context="annualized_percentage_phaseout"
    )
    maximum = D(phaseout["maximum"], context="params.deduction_phaseout.maximum")
    phase_start = D(phaseout["phase_start"], context="params.deduction_phaseout.phase_start")
    phase_rate = D(phaseout["phase_rate"], context="params.deduction_phaseout.phase_rate")
    exemption_amount = (
        D(params["exemption_amount"], context="params.exemption_amount")
        if params.get("exemption_amount") is not None
        else ZERO
    )
    table = per_status(ctx.bracket_tables, status, context="annualized_percentage_phaseout")

    # Step 2: annualize.
    annual_wages = ctx.taxable_wages * ctx.pay_periods

    # Step 3: phase the deduction out linearly above phase_start, floor at 0.
    deduction = maximum
    if annual_wages >= phase_start:
        deduction = clamp0(maximum - phase_rate * (annual_wages - phase_start))

    # Step 4: subtract deduction and exemptions, clamp.
    annual_net = clamp0(annual_wages - deduction - ctx.allowances * exemption_amount)

    # Step 5 (+ optional intermediate rounding, worked-examples permitting).
    annual_tax = tax_for(table, annual_net)
    if ctx.rounding.intermediate == "annual":
        annual_tax = ctx.rounding.apply_intermediate(annual_tax)

    # Steps 6-7: de-annualize, round once, add extra withholding.
    period_tax = annual_tax / ctx.pay_periods
    return ctx.rounding.apply(period_tax) + ctx.additional_withholding
