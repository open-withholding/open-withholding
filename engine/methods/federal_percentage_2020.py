"""Reference implementation of /methods/federal_percentage_2020.md (v1).

Line numbers in comments reference Pub 15-T Worksheet 1A."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.methods.common import clamp0, per_status
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    w4 = ctx.federal
    if w4 is None:
        raise InputError("federal_percentage_2020 requires the input's federal block")
    if w4.w4_version != 2020:
        raise InputError(
            f"federal_percentage_2020 handles 2020+ W-4s only; input has {w4.w4_version!r}"
        )

    # Step 1 — Adjusted Annual Wage Amount (lines 1c..1i).
    annual_wages = ctx.taxable_wages * ctx.pay_periods
    total = annual_wages + w4.step4a_other_income
    if w4.step2_checkbox:
        adjustment = ZERO
        variant = "step2_checkbox"
    else:
        adjustment = D(
            per_status(
                ctx.params["wage_adjustment"], w4.filing_status, context="federal_percentage_2020"
            ),
            context="params.wage_adjustment",
        )
        variant = "standard"
    aawa = clamp0(total - w4.step4b_deductions - adjustment)

    # Step 2 — tentative withholding (lines 2a..2h).
    key = f"{variant}.{w4.filing_status}"
    if key not in ctx.bracket_tables:
        raise InputError(
            f"federal_percentage_2020: no bracket table {key!r}; "
            f"available: {sorted(ctx.bracket_tables)}"
        )
    annual_tentative = tax_for(ctx.bracket_tables[key], aawa)
    if ctx.rounding.intermediate == "annual":
        annual_tentative = ctx.rounding.apply_intermediate(annual_tentative)
    tentative_period = annual_tentative / ctx.pay_periods

    # Step 3 — credits (lines 3a..3c).
    after_credits = clamp0(tentative_period - w4.step3_credits / ctx.pay_periods)

    # Step 4 — extra withholding (line 4a).
    return ctx.rounding.apply(after_credits) + w4.step4c_extra
