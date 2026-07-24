"""Reference implementation of /methods/sui.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.methods.common import clamp0
from engine.money import D


def compute(ctx) -> Decimal:
    params = ctx.params
    ytd = ctx.ytd or {}

    # Step 1: the noticed experience rate is employer input, never data,
    # and must fall within the published schedule's range.
    rate = ctx.sui_experience_rate
    if rate is None:
        raise InputError(
            "sui: employer.sui_experience_rate is required — it comes from the "
            "state's annual rate notice (a new employer enters the published "
            f"new-employer rate, {params.get('new_employer_rate')!r})"
        )
    lo = D(params["rate_range"]["min"], context="sui.rate_range.min")
    hi = D(params["rate_range"]["max"], context="sui.rate_range.max")
    if not (lo <= rate <= hi):
        raise InputError(
            f"sui: experience rate {rate} is outside the published schedule "
            f"range {lo}..{hi} — check the rate notice's year and decimal form"
        )

    # Step 2: cap against the annual taxable wage base.
    ytd_sui = D(ytd.get("sui_wages", "0"), context="ytd.sui_wages")
    wage_base = D(params["wage_base"], context="sui.wage_base")
    taxable = min(ctx.taxable_wages, clamp0(wage_base - ytd_sui))
    tax = ctx.rounding.apply(taxable * rate)

    # Step 3: separately-published flat surtaxes, each with its own base.
    for surtax in params.get("surtaxes") or []:
        s_base = D(surtax["wage_base"], context=f"sui.surtaxes.{surtax['name']}.wage_base")
        s_taxable = min(ctx.taxable_wages, clamp0(s_base - ytd_sui))
        tax += ctx.rounding.apply(
            s_taxable * D(surtax["rate"], context=f"sui.surtaxes.{surtax['name']}.rate")
        )
    return tax
