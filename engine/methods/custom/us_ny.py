"""Reference implementation of /methods/custom/us_ny.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import D

# Page 23 conversion: these frequencies compute at monthly and scale back.
_CONVERSIONS = {"quarterly": 3, "semiannually": 6}


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )

    # Step 0: conversion rule for periods without printed tables.
    factor = _CONVERSIONS.get(frequency, 1)
    calc_freq = "monthly" if factor > 1 else frequency
    if calc_freq not in params["deduction"]:
        raise InputError(
            f"custom/us_ny: no printed tables for pay frequency {frequency!r}; "
            f"available: {sorted(params['deduction'])} plus {sorted(_CONVERSIONS)}"
        )
    status = ctx.filing_status
    if status not in params["deduction"][calc_freq]:
        raise InputError(
            f"custom/us_ny: filing_status must be one of "
            f"{sorted(params['deduction'][calc_freq])}, got {status!r}"
        )
    wages = ctx.taxable_wages / factor

    # Step 1: net wages after the Table B + n x Table C allowance.
    deduction = D(params["deduction"][calc_freq][status],
                  context=f"deduction.{calc_freq}.{status}")
    exemption = D(params["exemption_value"][calc_freq],
                  context=f"exemption_value.{calc_freq}")
    net = clamp0(wages - deduction - ctx.allowances * exemption)

    # Step 2: Method III applies at the table's printed per-period cutover.
    cutover = D(params["method_iii_cutover"][calc_freq][status],
                context=f"method_iii_cutover.{calc_freq}.{status}")
    periods = PAY_PERIODS_PER_YEAR[calc_freq]
    if net >= cutover:
        annualized = net * periods
        bands = params["method_iii"][status]
        rate = D(bands[0]["rate"], context=f"method_iii.{status}[0].rate")
        for band in bands:
            if annualized >= D(band["over"], context=f"method_iii.{status}.over"):
                rate = D(band["rate"], context=f"method_iii.{status}.rate")
        tax = ctx.rounding.apply(annualized * rate / periods)
    else:
        table = ctx.bracket_tables[f"{calc_freq}.{status}"]
        tax = ctx.rounding.apply(tax_for(table, net))

    # Step 3: scale back to the actual period, never negative.
    return clamp0(tax * factor) + ctx.additional_withholding
