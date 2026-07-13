"""Reference implementation of /methods/deduction_constant_percentage.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )
    periods_map = params["periods_per_year"]
    if frequency not in periods_map:
        raise InputError(
            f"deduction_constant_percentage: no printed deduction-constant table "
            f"for pay frequency {frequency!r}; available: {sorted(periods_map)}"
        )
    periods = D(periods_map[frequency], context=f"params.periods_per_year.{frequency}")

    annuals = params["exemptions"]
    counts = ctx.exemptions or {}
    unknown = sorted(set(counts) - set(annuals))
    if unknown:
        raise InputError(
            f"deduction_constant_percentage: exemption kind(s) {unknown} not in "
            f"params.exemptions; available: {sorted(annuals)}"
        )

    # Step 2: one constant per kind, each independently rounded (the printed
    # example adds Table B twice — line 6 and line 7 round separately).
    total_constant = ZERO
    for kind, count in counts.items():
        if count <= 0:
            continue
        annual = D(annuals[kind], context=f"params.exemptions.{kind}")
        total_constant += ctx.rounding.apply(count * annual / periods)

    # Steps 3-4.
    taxable = clamp0(ctx.taxable_wages - total_constant)
    return ctx.rounding.apply(taxable * D(params["rate"], context="params.rate")) + (
        ctx.additional_withholding
    )
