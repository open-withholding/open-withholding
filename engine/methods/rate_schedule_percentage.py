"""Reference implementation of /methods/rate_schedule_percentage.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )

    floors = params["no_withholding_floor"]
    if frequency not in floors:
        raise InputError(
            f"rate_schedule_percentage: no printed schedule for pay frequency "
            f"{frequency!r}; available: {sorted(floors)}"
        )

    # Step 4 prerequisites first so bad inputs fail loud even under the floor.
    schedule_key = ctx.rate_schedule
    if not schedule_key:
        raise InputError(
            "rate_schedule_percentage: input requires rate_schedule (the "
            "employer-selected printed schedule, e.g. the employee's county "
            f"combined rate); available: {sorted(params['schedules'])}"
        )
    if schedule_key not in params["schedules"]:
        raise InputError(
            f"rate_schedule_percentage: rate_schedule {schedule_key!r} has no "
            f"printed schedule; available: {sorted(params['schedules'])}"
        )
    group = next(
        (g for g, statuses in params["status_groups"].items()
         if ctx.filing_status in statuses),
        None,
    )
    if group is None:
        raise InputError(
            f"rate_schedule_percentage: filing_status {ctx.filing_status!r} not in "
            f"any status group; groups: {params['status_groups']}"
        )

    # Step 2: the floor tests period GROSS wages.
    if ctx.taxable_wages < D(floors[frequency], context=f"no_withholding_floor.{frequency}"):
        return ctx.additional_withholding

    # Step 3.
    sd = D(params["standard_deduction_per_period"][frequency],
           context=f"standard_deduction_per_period.{frequency}")
    exemption = D(params["exemption_per_period"][frequency],
                  context=f"exemption_per_period.{frequency}")
    taxable = clamp0(ctx.taxable_wages - sd - ctx.allowances * exemption)

    # Steps 4-5.
    table = ctx.bracket_tables[f"{schedule_key}.{frequency}.{group}"]
    tax = tax_for(table, taxable)
    return clamp0(ctx.rounding.apply(tax)) + ctx.additional_withholding
