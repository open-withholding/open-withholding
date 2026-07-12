"""Reference implementation of /methods/custom/us_al.md (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import parse_table, tax_for
from engine.errors import InputError
from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    statuses = ctx.params["statuses"]
    if ctx.filing_status not in statuses:
        raise InputError(
            f"custom/us_al: filing_status must be an A-4 claim code, one of "
            f"{sorted(statuses)}; got {ctx.filing_status!r}"
        )
    status = statuses[ctx.filing_status]
    if ctx.period_federal_income_withholding is None:
        raise InputError(
            "custom/us_al requires period_federal_income_withholding in the input "
            "record (Alabama deducts annualized actual federal withholding)"
        )

    # Step 1: annual gross income.
    gi = ctx.taxable_wages * ctx.pay_periods

    # Step 2A: stepped standard deduction (inclusive-lower printed rows).
    sd = ZERO
    for row in status["standard_deduction"]:
        if D(row["at_least"], context="standard_deduction.at_least") <= gi:
            sd = D(row["amount"], context="standard_deduction.amount")
        else:
            break

    # Step 2B: annualized federal withholding, uncapped.
    fed = ctx.period_federal_income_withholding * ctx.pay_periods

    # Step 2C: personal exemption.
    pe = D(status["personal_exemption"], context="personal_exemption")

    # Step 2D: income-tiered per-dependent amount (exclusive-lower rows).
    per_dep = ZERO
    for row in ctx.params["dependent_tiers"]:
        if D(row["more_than"], context="dependent_tiers.more_than") < gi:
            per_dep = D(row["value"], context="dependent_tiers.value")
        else:
            break
    dep = ctx.allowances * per_dep

    # Steps 3-5.
    taxable = clamp0(gi - sd - fed - pe - dep)
    table = parse_table(status["brackets"], context=f"statuses.{ctx.filing_status}.brackets")
    tax = tax_for(table, taxable)
    return ctx.rounding.apply(tax / ctx.pay_periods) + ctx.additional_withholding
