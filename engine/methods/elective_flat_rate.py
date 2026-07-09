"""Reference implementation of /methods/elective_flat_rate.md (v1).

Arizona-style: the employee elects a withholding rate from the state's
published list (A-4); the employer applies it flat. No brackets, no
allowances."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.money import ZERO, D


def compute(ctx) -> Decimal:
    params = ctx.params
    rate = ctx.elected_rate
    if rate is None:
        if params.get("default_rate") is None:
            raise InputError(
                "elective_flat_rate: input has no elected_rate and the jurisdiction "
                "publishes no default"
            )
        rate = D(params["default_rate"], context="params.default_rate")
    else:
        allowed = {D(r, context="params.allowed_rates") for r in params.get("allowed_rates", [])}
        if params.get("zero_rate_allowed", False):
            allowed.add(ZERO)
        if allowed and rate not in allowed:
            raise InputError(
                f"elective_flat_rate: elected_rate {rate} is not one of the "
                f"jurisdiction's published elections {sorted(allowed)}"
            )
    return ctx.rounding.apply(ctx.taxable_wages * rate) + ctx.additional_withholding
