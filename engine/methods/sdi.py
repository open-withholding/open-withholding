"""Reference implementation of /methods/sdi.md (v1).

State disability insurance / paid family and medical leave — EMPLOYEE
contributions withheld per pay period. One parameter file per state lists
the programme's components (NJ: TDI + FLI; NY: DBL + PFL; MA: family +
medical); each is a flat rate, times the employee's share of it, on wages
up to an optional annual base, with an optional printed per-period cap.

Step numbers in comments reference the normative spec."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.methods.common import clamp0
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    ytd = ctx.ytd or {}
    ytd_wages = D(ytd.get("sdi_wages", "0"), context="ytd.sdi_wages")
    frequency = next(
        (f for f, p in PAY_PERIODS_PER_YEAR.items() if p == ctx.pay_periods), None
    )

    total = ZERO
    for component in params["components"]:
        name = component["name"]
        where = f"sdi.components[{name}]"

        # Step 1: the employee's effective rate — the published rate times
        # the employee's share of it (1 where the state publishes the
        # employee rate itself). Exact; rounded once at step 3.
        rate = D(component["rate"], context=f"{where}.rate")
        share = D(component.get("employee_share", "1"), context=f"{where}.employee_share")

        # Step 2: wages subject, capped at the annual base if one applies.
        wage_base = component.get("wage_base")
        if wage_base is None:
            subject = ctx.taxable_wages
        else:
            subject = min(ctx.taxable_wages,
                          clamp0(D(wage_base, context=f"{where}.wage_base") - ytd_wages))

        # Step 3: this component's contribution, rounded to the cent.
        amount = ctx.rounding.apply(subject * rate * share)

        # Step 4: a maximum contribution caps the rounded amount. Two forms:
        # weekly_max — the publication defines the cap PER WEEK (NY DBL "no
        # more than sixty cents a week", HI TDI's "maximum weekly deduction"),
        # so a period's cap is that amount times the weeks the period covers
        # (52 / pay periods: biweekly 2, semimonthly 2.1667, monthly 4.3333),
        # rounded to the cent — the figures NY payroll practice uses ($1.20,
        # $1.30, $2.60). period_max — the publication prints a per-period
        # table; only the printed frequencies are allowed.
        weekly_max = component.get("weekly_max")
        if weekly_max is not None:
            cap = ctx.rounding.apply(
                D(weekly_max, context=f"{where}.weekly_max") * Decimal(52) / Decimal(ctx.pay_periods)
            )
            amount = min(amount, cap)
        period_max = component.get("period_max")
        if period_max:
            if frequency not in period_max:
                raise InputError(
                    f"{where}: the publication prints a per-period maximum only for "
                    f"{sorted(period_max)}; got pay frequency {frequency!r}"
                )
            amount = min(amount, D(period_max[frequency], context=f"{where}.period_max.{frequency}"))

        total += clamp0(amount)
    return total
