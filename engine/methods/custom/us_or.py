"""Reference implementation of /methods/custom/us_or.md (v1)."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.methods.common import clamp0
from engine.money import ZERO, D


def _inclusive_lookup(rows: list[dict], key: str, amount: Decimal, *, context: str):
    row = None
    for candidate in rows:
        if D(candidate[key], context=f"{context}.{key}") <= amount:
            row = candidate
        else:
            break
    if row is None:
        raise InputError(f"custom/us_or: no {context} row covers {amount}")
    return row


def compute(ctx) -> Decimal:
    # Status-group selection (spec: FAQ 4 — higher-single-rate elects single).
    if ctx.filing_status == "single" and ctx.allowances < 3:
        group_key = "single_under_3"
    elif ctx.filing_status in ("single", "married"):
        group_key = "married_or_single_3plus"
    else:
        raise InputError(
            f"custom/us_or: filing_status must be single or married, got {ctx.filing_status!r}"
        )
    group = ctx.params["status_groups"][group_key]
    # Phase-out and allowance-zeroing key on the UNDERLYING status alone
    # (the doc prints both [S] and [M] ladders inside the married bracket
    # group; FAQ 4 + Example 3).
    status = ctx.params["statuses"][ctx.filing_status]

    if ctx.period_federal_income_withholding is None:
        raise InputError(
            "custom/us_or requires period_federal_income_withholding in the input "
            "record (Oregon subtracts actual federal income tax withheld; FICA is "
            "not included)"
        )

    # Step 1: annual wages.
    wages = ctx.taxable_wages * ctx.pay_periods

    # Step 2: capped federal subtraction (inclusive-lower phase-out rows).
    cap_row = _inclusive_lookup(
        status["fed_subtraction_phaseout"], "at_least", wages, context="fed_subtraction_phaseout"
    )
    fed_sub = min(
        ctx.period_federal_income_withholding * ctx.pay_periods,
        D(cap_row["cap"], context="fed_subtraction_phaseout.cap"),
    )

    # Step 3: BASE.
    base = clamp0(wages - fed_sub - D(group["standard_deduction"], context="standard_deduction"))

    # Step 4: wage tier, then printed formula row on BASE.
    tier = _inclusive_lookup(group["wage_tiers"], "wages_at_least", wages, context="wage_tiers")
    row = _inclusive_lookup(tier["formulas"], "at_least", base, context="formulas")
    wh = (
        D(row["base"], context="formulas.base")
        + (base - D(row["excess_over"], context="formulas.excess_over"))
        * D(row["rate"], context="formulas.rate")
    )

    # Worksheet line 8 rounds the total tax from rates (annual, whole
    # dollar via intermediate rounding) BEFORE the credit.
    wh = ctx.rounding.apply_intermediate(wh)

    # Step 5: allowance credit, zeroed at high wages by STATUS, clamp (FAQ 10).
    allowances = (
        0
        if wages > D(status["allowance_zero_above"], context="allowance_zero_above")
        else ctx.allowances
    )
    wh = clamp0(
        wh - D(ctx.params["credit_per_allowance"], context="credit_per_allowance") * allowances
    )

    # Step 6.
    return ctx.rounding.apply(wh / ctx.pay_periods) + ctx.additional_withholding
