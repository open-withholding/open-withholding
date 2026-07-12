"""Reference implementation of /methods/custom/us_ma.md (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import parse_table, tax_for
from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import ZERO, D


def _freq_value(mapping: dict, frequency: str, *, context: str) -> Decimal:
    if frequency not in mapping:
        raise InputError(
            f"custom/us_ma: no printed {context} value for pay frequency "
            f"{frequency!r}; available: {sorted(mapping)}"
        )
    return D(mapping[frequency], context=context)


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )

    # Step 0: low-income floor (claiming >= 1 exemption).
    if ctx.allowances >= 1 and ctx.taxable_wages < _freq_value(
        params["low_income_floor"], frequency, context="low_income_floor"
    ):
        return ctx.additional_withholding

    if ctx.period_fica_withholding is None:
        raise InputError(
            "custom/us_ma requires period_fica_withholding in the input record "
            "(Circular M step 1 subtracts actual FICA/Medicare/retirement "
            "withholdings; pass \"0\" if none)"
        )

    # Step 1: retirement subtraction under the cumulative annual cap.
    used = ctx.ytd.get("retirement_deduction_used", ZERO)
    remaining = clamp0(D(params["retirement_deduction_cap"], context="cap") - used)
    w = ctx.taxable_wages - min(ctx.period_fica_withholding, remaining)

    # Step 2: exemption factor (nonlinear: n=1 special-cased).
    factors = params["exemption_factors"].get(frequency)
    if factors is None:
        raise InputError(
            f"custom/us_ma: no printed exemption factors for {frequency!r}"
        )
    if ctx.allowances == 1:
        w -= D(factors["claiming_one"], context="exemption_factors.claiming_one")
    elif ctx.allowances > 1:
        w -= (
            D(factors["per_exemption"], context="exemption_factors.per_exemption")
            * ctx.allowances
            + D(factors["plus"], context="exemption_factors.plus")
        )
    w = clamp0(w)

    # Steps 3-5: annualize, bracket tax (surtax tier), de-annualize.
    table = parse_table(params["brackets"], context="params.brackets")
    period = tax_for(table, w * ctx.pay_periods) / ctx.pay_periods

    # Steps 6-7: per-period tax subtractions.
    if ctx.filing_status == "head_of_household":
        period -= _freq_value(params["hoh_tax_value"], frequency, context="hoh_tax_value")
    if ctx.secondary_allowances:
        period -= (
            _freq_value(params["blindness_tax_value"], frequency, context="blindness_tax_value")
            * ctx.secondary_allowances
        )

    # Step 8.
    return ctx.rounding.apply(clamp0(period)) + ctx.additional_withholding
