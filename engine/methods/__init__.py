"""Method registry: registered name -> reference implementation.

The normative text lives in /methods/<name>.md; code here must match it.
Methods not yet implemented simply aren't registered — dispatch fails loud.
"""

from engine.errors import EngineError
from engine.methods import (
    annualized_percentage,
    annualized_percentage_phaseout,
    federal_percentage_2020,
    flat_rate,
    elective_flat_rate,
    flat_rate_with_annual_allowance,
    per_period_percentage,
)

REGISTRY = {
    "flat_rate": flat_rate.compute,
    "flat_rate_with_annual_allowance": flat_rate_with_annual_allowance.compute,
    "annualized_percentage": annualized_percentage.compute,
    "annualized_percentage_phaseout": annualized_percentage_phaseout.compute,
    "per_period_percentage": per_period_percentage.compute,
    "elective_flat_rate": elective_flat_rate.compute,
    "federal_percentage_2020": federal_percentage_2020.compute,
}


def resolve(method: str, custom_implementation: str | None = None):
    if method == "custom":
        key = custom_implementation or ""
        if key in REGISTRY:
            return REGISTRY[key]
        raise EngineError(f"custom implementation {key!r} is not registered")
    if method in REGISTRY:
        return REGISTRY[method]
    raise EngineError(
        f"method {method!r} is not implemented in this engine version; "
        f"registered: {sorted(REGISTRY)}"
    )
