"""Reference implementation of /methods/custom/us_ca.md (v1).

Step numbers in comments reference the normative spec (which mirrors the
printed Method B steps 1-5)."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import ZERO, D


def _column(status: str | None, regular_allowances: int) -> str:
    """Tables 1 and 3 column key: married splits on the REGULAR count."""
    if status == "married":
        return "married_allowances_0_1" if regular_allowances <= 1 else "married_allowances_2_plus"
    if status in ("single", "head_of_household"):
        return status
    raise InputError(
        f"custom/us_ca: filing_status must be single, married, or "
        f"head_of_household, got {status!r}"
    )


def _count_lookup(values: list, count: int, *, context: str) -> Decimal:
    """Tables 2 and 4: printed rows for low counts; beyond the table the
    footnotes say one-allowance amount x count."""
    if count <= 0:
        return ZERO
    if count <= len(values):
        return D(values[count - 1], context=f"{context}[{count}]")
    return D(values[0], context=f"{context}[1]") * count


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )
    if frequency not in params["low_income_exemption"]:
        raise InputError(
            f"custom/us_ca: no printed tables for pay frequency {frequency!r}; "
            f"available: {sorted(params['low_income_exemption'])}"
        )
    column = _column(ctx.filing_status, ctx.allowances)

    # Step 1: low-income exemption cliff on GROSS wages (<=, per the text).
    threshold = D(params["low_income_exemption"][frequency][column],
                  context=f"low_income_exemption.{frequency}.{column}")
    if ctx.taxable_wages <= threshold:
        return ctx.additional_withholding

    # Step 2: estimated-deduction allowances reduce wages (Table 2).
    wages = ctx.taxable_wages - _count_lookup(
        params["estimated_deduction"][frequency], ctx.secondary_allowances,
        context=f"estimated_deduction.{frequency}",
    )

    # Step 3: standard deduction (Table 3).
    sd = D(params["standard_deduction"][frequency][column],
           context=f"standard_deduction.{frequency}.{column}")
    taxable = clamp0(wages - sd)

    # Step 4: Tables 5-28 (printed bases authoritative).
    table = ctx.bracket_tables[f"{frequency}.{ctx.filing_status}"]
    tax = ctx.rounding.apply(tax_for(table, taxable))

    # Step 5: exemption allowance credit (Table 4) — REGULAR allowances only.
    credit = _count_lookup(
        params["exemption_allowance"][frequency], ctx.allowances,
        context=f"exemption_allowance.{frequency}",
    )
    return clamp0(tax - credit) + ctx.additional_withholding
