"""`supplemental_aggregate` (v1, /methods/supplemental.md): the jurisdiction
publishes no flat option, so supplemental wages are withheld by running the
REGULAR method on combined wages and subtracting the regular withholding.
That needs the regular parameter file, which a single-file method cannot
see — engine.pipeline.compute_supplemental_withholding implements it; the
registered callable only explains how to call it."""

from __future__ import annotations

from decimal import Decimal

from engine.errors import EngineError


def compute(ctx) -> Decimal:
    raise EngineError(
        "supplemental_aggregate needs the jurisdiction's regular withholding file: "
        "call engine.pipeline.compute_supplemental_withholding(files, employee, taxability, as_of, jurisdiction)"
    )
