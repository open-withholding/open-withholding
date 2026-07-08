"""Shared helpers for method implementations."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import InputError
from engine.money import ZERO


def clamp0(amount: Decimal) -> Decimal:
    return amount if amount > ZERO else ZERO


def per_status(mapping: dict, status: str | None, *, context: str):
    """Look up a per-filing-status parameter, failing with the jurisdiction's
    valid statuses so UIs can render the right form."""
    if status is None:
        raise InputError(f"{context}: filing_status is required for this method")
    if status not in mapping:
        raise InputError(f"{context}: filing_status {status!r} not one of {sorted(mapping)}")
    return mapping[status]
