"""Reference implementation of /methods/city_flat_rate.md (v1).

Michigan Uniform City Income Tax Ordinance cities (Act 284 of 1964): a
resident rate and a nonresident rate (statutorily half the resident rate)
applied to wages after an annual per-exemption deduction, annualized and
divided back. The LocalElection's `resident` flag selects the rate; the
exemption count is the local election's `allowances` when given, else the
parent state's.
"""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.methods.common import clamp0
from engine.money import D


def compute(ctx) -> Decimal:
    params = ctx.params
    if ctx.resident is None:
        raise InputError("city_flat_rate: a LocalElection with `resident` is required (city files only)")
    rate = D(params["resident_rate" if ctx.resident else "nonresident_rate"],
             context="params.resident_rate/nonresident_rate")
    exemption = D(params["exemption_amount"], context="params.exemption_amount")

    annual_wages = ctx.taxable_wages * ctx.pay_periods
    annual_taxable = clamp0(annual_wages - exemption * ctx.allowances)
    annual_tax = annual_taxable * rate
    if ctx.rounding.intermediate == "annual":
        annual_tax = ctx.rounding.apply_intermediate(annual_tax)
    return ctx.rounding.apply(annual_tax / ctx.pay_periods) + ctx.additional_withholding
