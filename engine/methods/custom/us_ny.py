"""Reference implementation of /methods/custom/us_ny.md (v2).

One method, three publications (identical Method II structure):
  NYS-50-T-NYS  state      Method II + Method III
  NYS-50-T-NYC  US-NY-NYC  Method II only (no Method III printed);
                           residents only
  NYS-50-T-Y    US-NY-YONKERS  residents: state computation x surcharge_rate
                           (16.75%); nonresidents: Method VIII annualized
                           earnings tax (0.50% after an annualized exclusion)

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import D, ZERO

# Page 23 conversion: these frequencies compute at monthly and scale back.
_CONVERSIONS = {"quarterly": 3, "semiannually": 6}


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )

    # Nonresidents: a locality taxes them under its own rule or not at all.
    if ctx.resident is False:
        nonresident = params.get("nonresident_earnings_tax")
        if not nonresident:
            return ZERO  # NYC: no nonresident withholding (earnings tax repealed)
        return _nonresident_earnings_tax(ctx, nonresident, frequency)

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

    # Step 2: Method III applies at the table's printed per-period cutover —
    # where the publication prints one (NYC prints no Method III).
    periods = PAY_PERIODS_PER_YEAR[calc_freq]
    cutovers = params.get("method_iii_cutover")
    if cutovers is not None and net >= D(cutovers[calc_freq][status],
                                         context=f"method_iii_cutover.{calc_freq}.{status}"):
        annualized = net * periods
        bands = params["method_iii"][status]
        rate = D(bands[0]["rate"], context=f"method_iii.{status}[0].rate")
        for band in bands:
            if annualized >= D(band["over"], context=f"method_iii.{status}.over"):
                rate = D(band["rate"], context=f"method_iii.{status}.rate")
        raw = annualized * rate / periods
    else:
        table = ctx.bracket_tables[f"{calc_freq}.{status}"]
        raw = tax_for(table, net)

    # Step 2b: Yonkers resident surcharge — a percentage of the state
    # computation, applied to the EXACT (unrounded) amount; one final
    # rounding reproduces all eight printed examples.
    surcharge = params.get("surcharge_rate")
    if surcharge is not None:
        raw = raw * D(surcharge, context="surcharge_rate")
    tax = ctx.rounding.apply(raw)

    # Step 3: scale back to the actual period, never negative.
    return clamp0(tax * factor) + ctx.additional_withholding


def _nonresident_earnings_tax(ctx, nr: dict, frequency: str | None) -> Decimal:
    """Yonkers Method VIII (NYS-50-T-Y p.25): annualize by Table P, subtract
    the annualized exclusion for the band (exclusive lower bound: 'over X
    but not over Y'), apply the flat rate, divide back. Line 1 (annualized
    pay below the no-withholding floor) withholds nothing. Method VII's
    per-period tables are this computation with the exclusion pre-divided;
    the printed examples agree to the cent under both."""
    factors = nr["annual_factors"]
    if frequency not in factors:
        raise InputError(
            f"custom/us_ny: nonresident earnings tax prints annual factors only for "
            f"{sorted(factors)}; got pay frequency {frequency!r}"
        )
    periods = D(factors[frequency], context=f"nonresident_earnings_tax.annual_factors.{frequency}")
    annualized = ctx.taxable_wages * periods
    exclusion = None
    for row in nr["exclusions"]:
        if annualized > D(row["over"], context="nonresident_earnings_tax.exclusions.over"):
            exclusion = row["exclusion"]
    if exclusion is None:
        return clamp0(ZERO) + ctx.additional_withholding  # line 1: no tax withheld
    rate = D(nr["rate"], context="nonresident_earnings_tax.rate")
    annual_tax = (annualized - D(exclusion, context="nonresident_earnings_tax.exclusions.exclusion")) * rate
    return clamp0(ctx.rounding.apply(annual_tax / periods)) + ctx.additional_withholding
