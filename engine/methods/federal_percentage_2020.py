"""Reference implementation of /methods/federal_percentage_2020.md (v1).

Line numbers in comments reference Pub 15-T Worksheet 1A."""

from __future__ import annotations

from decimal import Decimal

from engine.brackets import tax_for
from engine.errors import InputError
from engine.methods.common import clamp0, per_status
from engine.money import ZERO, D


# Pub 15-T computational bridge (pp.4-5): a 2019-or-earlier W-4 maps onto
# the 2020+ worksheet. "Single" and "Married, but withhold at higher Single
# rate" become single; "Married" becomes married_joint; HoH cannot be
# reached from an old form.
_BRIDGE_STATUS = {
    "single": "single",
    "married_higher_single": "single",
    "married": "married_joint",
}


def compute(ctx) -> Decimal:
    w4 = ctx.federal
    if w4 is None:
        raise InputError("federal_percentage_2020 requires the input's federal block")
    if w4.w4_version == "pre_2020":
        # Computational bridge steps 1-4: derive 2020+ W-4 values from the
        # old form, then run the standard worksheet unchanged.
        bridge = ctx.params.get("computational_bridge")
        if not bridge:
            raise InputError(
                "federal_percentage_2020: input has a pre-2020 W-4 but this "
                "edition's params carry no computational_bridge block"
            )
        status = _BRIDGE_STATUS.get(w4.filing_status)
        if status is None:
            raise InputError(
                f"pre-2020 W-4 filing_status must be one of "
                f"{sorted(_BRIDGE_STATUS)}, got {w4.filing_status!r}"
            )
        filing_status = status
        step2_checkbox = False
        step3_credits = ZERO
        step4a = D(bridge["step4a"][status], context=f"computational_bridge.step4a.{status}")
        step4b = w4.allowances * D(
            bridge["allowance_amount"], context="computational_bridge.allowance_amount"
        )
        step4c = w4.step4c_extra  # old W-4 line 6
    elif w4.w4_version == 2020:
        filing_status = w4.filing_status
        step2_checkbox = w4.step2_checkbox
        step3_credits = w4.step3_credits
        step4a = w4.step4a_other_income
        step4b = w4.step4b_deductions
        step4c = w4.step4c_extra
    else:
        raise InputError(
            f"federal_percentage_2020 handles 2020+ and pre-2020 W-4s; "
            f"input has {w4.w4_version!r}"
        )

    # Step 1 — Adjusted Annual Wage Amount (lines 1c..1i).
    annual_wages = ctx.taxable_wages * ctx.pay_periods
    total = annual_wages + step4a
    if step2_checkbox:
        adjustment = ZERO
        variant = "step2_checkbox"
    else:
        adjustment = D(
            per_status(
                ctx.params["wage_adjustment"], filing_status, context="federal_percentage_2020"
            ),
            context="params.wage_adjustment",
        )
        variant = "standard"
    aawa = clamp0(total - step4b - adjustment)

    # Step 2 — tentative withholding (lines 2a..2h).
    key = f"{variant}.{filing_status}"
    if key not in ctx.bracket_tables:
        raise InputError(
            f"federal_percentage_2020: no bracket table {key!r}; "
            f"available: {sorted(ctx.bracket_tables)}"
        )
    annual_tentative = tax_for(ctx.bracket_tables[key], aawa)
    if ctx.rounding.intermediate == "annual":
        annual_tentative = ctx.rounding.apply_intermediate(annual_tentative)
    tentative_period = annual_tentative / ctx.pay_periods

    # Step 3 — credits (lines 3a..3c).
    after_credits = clamp0(tentative_period - step3_credits / ctx.pay_periods)

    # Step 4 — extra withholding (line 4a; old W-4 line 6 via the bridge).
    return ctx.rounding.apply(after_credits) + step4c
