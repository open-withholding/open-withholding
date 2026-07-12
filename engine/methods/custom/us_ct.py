"""Reference implementation of /methods/custom/us_ct.md (v1).

Step numbers in comments reference the normative spec. Only control flow
lives here; every constant comes from the parameter file."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import parse_table, tax_for
from engine.errors import InputError
from engine.methods.common import clamp0
from engine.money import ZERO, D


def _range_lookup(rows: list[dict], salary: Decimal, *, context: str) -> Decimal:
    """TPG-211 range tables: last row with more_than < salary (EXCLUSIVE
    lower bound — a boundary salary belongs to the row below). Below the
    first row's range, the value is 0."""
    value = ZERO
    for row in rows:
        if D(row["more_than"], context=f"{context}.more_than") < salary:
            value = D(row["value"], context=f"{context}.value")
        else:
            break
    return value


def compute(ctx) -> Decimal:
    code = ctx.filing_status
    codes = ctx.params["codes"]
    if code not in codes:
        raise InputError(
            f"custom/us_ct: filing_status must be a CT-W4 withholding code, "
            f"one of {sorted(codes)}; got {code!r}"
        )
    tables = codes[code]

    # Steps 1-3: annualized salary.
    salary = ctx.taxable_wages * ctx.pay_periods
    if salary <= ZERO:
        return ctx.additional_withholding

    # Steps 4-6: exemption (range lookup on salary), taxable income.
    exempt = _range_lookup(tables["exemptions"], salary, context="exemptions")
    taxable = salary - exempt
    if taxable <= ZERO:
        return ctx.additional_withholding

    # Step 7: initial tax (ordinary bracket convention, printed bases).
    bracket_rows = parse_table(tables["brackets"], context=f"codes.{code}.brackets")
    initial = tax_for(bracket_rows, taxable)

    # Steps 8-10: add-back and recapture, both looked up on SALARY.
    addback = _range_lookup(tables["add_back"], salary, context="add_back")
    recap = _range_lookup(tables["recapture"], salary, context="recapture")
    total = initial + addback + recap

    # Steps 11-12: personal tax credit decimal.
    decimal_amount = _range_lookup(tables["credits"], salary, context="credits")
    tax = total * (Decimal("1") - decimal_amount)

    # Steps 13-16.
    period = ctx.rounding.apply(tax / ctx.pay_periods)
    return clamp0(period + ctx.additional_withholding)
