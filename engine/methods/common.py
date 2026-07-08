"""Shared helpers for method implementations."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.money import ZERO


def clamp0(amount: Decimal) -> Decimal:
    return amount if amount > ZERO else ZERO


def per_status(mapping: dict, status: str | None, *, context: str):
    """Look up a per-filing-status parameter, failing with the jurisdiction's
    valid statuses so UIs can render the right form. A jurisdiction with one
    schedule for all employees publishes it under the single key `all`, used
    regardless of (or without) a filing status."""
    if len(mapping) == 1 and "all" in mapping:
        return mapping["all"]
    if status is None:
        raise InputError(f"{context}: filing_status is required for this method")
    if status not in mapping:
        raise InputError(f"{context}: filing_status {status!r} not one of {sorted(mapping)}")
    return mapping[status]
