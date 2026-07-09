"""Reference implementation of /methods/per_period_percentage.md (v1).

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0, per_status
from engine.money import CENT, ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    status = ctx.filing_status
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )

    per_freq = params["brackets"].get(frequency)
    if per_freq is None:
        raise InputError(
            f"per_period_percentage: no printed table for pay frequency {frequency!r}; "
            f"available: {sorted(params['brackets'])}"
        )
    per_status(per_freq, status, context="per_period_percentage")  # validates status
    # loader stores parsed tables under "frequency.status"; resolve the same key
    status_key = "all" if len(per_freq) == 1 and "all" in per_freq else status
    table = ctx.bracket_tables[f"{frequency}.{status_key}"]

    # Step 2: allowance reduction — annual amounts divided per period
    # (cent-rounded, as the worksheets print it), plus any printed
    # per-period allowance value.
    reduction = ZERO
    annual = ZERO
    if params.get("standard_deduction"):
        annual += D(
            per_status(params["standard_deduction"], status, context="per_period_percentage"),
            context="params.standard_deduction",
        )
    if params.get("allowance_amount") is not None:
        annual += ctx.allowances * D(params["allowance_amount"], context="params.allowance_amount")
    if annual > ZERO:
        reduction += (annual / ctx.pay_periods).quantize(CENT, rounding=ROUND_HALF_UP)
    per_period = params.get("allowance_amounts_per_period") or {}
    if frequency in per_period:
        reduction += ctx.allowances * D(
            per_period[frequency], context="params.allowance_amounts_per_period"
        )

    # Step 3: net wage for table purposes.
    net = clamp0(ctx.taxable_wages - reduction)

    # Steps 4-5: per-period bracket tax, round, add extra withholding.
    period_tax = tax_for(table, net)
    return ctx.rounding.apply(period_tax) + ctx.additional_withholding
