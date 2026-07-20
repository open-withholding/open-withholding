"""Reference implementation of /methods/fica.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    ss = ctx.params["social_security"]
    medicare = ctx.params["medicare"]
    wages = ctx.taxable_wages
    ytd = ctx.ytd or {}
    ytd_ss = D(ytd.get("social_security_wages", "0"), context="ytd.social_security_wages")
    ytd_med = D(ytd.get("medicare_wages", "0"), context="ytd.medicare_wages")

    # Step 1: Social Security up to the annual wage base.
    wage_base = D(ss["wage_base"], context="social_security.wage_base")
    ss_taxable = min(wages, clamp0(wage_base - ytd_ss))
    ss_tax = ctx.rounding.apply(ss_taxable * D(ss["employee_rate"],
                                               context="social_security.employee_rate"))

    # Step 2: Medicare on every taxable dollar.
    medicare_tax = ctx.rounding.apply(wages * D(medicare["employee_rate"],
                                                context="medicare.employee_rate"))

    # Step 3: Additional Medicare on the portion above the annual threshold.
    threshold = D(medicare["additional_threshold"], context="medicare.additional_threshold")
    addl_taxable = clamp0(wages + ytd_med - max(threshold, ytd_med))
    addl_tax = ctx.rounding.apply(
        addl_taxable * D(medicare["additional_employee_rate"],
                         context="medicare.additional_employee_rate")
    )

    # Step 4.
    return ss_tax + medicare_tax + addl_tax
