"""Reference implementation of /methods/per_period_credit_phaseout.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0, per_status
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )
    per_freq = params["schedules"].get(frequency)
    if per_freq is None:
        raise InputError(
            f"per_period_credit_phaseout: no printed schedule for pay frequency "
            f"{frequency!r}; available: {sorted(params['schedules'])}"
        )
    schedule = per_status(per_freq, ctx.filing_status, context="per_period_credit_phaseout")

    rate = D(params["rate"], context="params.rate")
    phase_rate = D(params["phase_rate"], context="params.phase_rate")
    base = D(schedule["base_allowance"], context="schedules.base_allowance")
    phase_start = D(schedule["phase_start"], context="schedules.phase_start")

    # Steps 2-4: worksheet lines, each rounded per the envelope rule.
    tentative = ctx.rounding.apply(ctx.taxable_wages * rate)
    over = clamp0(ctx.taxable_wages - phase_start)
    reduction = ctx.rounding.apply(phase_rate * over)
    credit = clamp0(base - reduction)

    # Step 5.
    return clamp0(tentative - credit) + ctx.additional_withholding
