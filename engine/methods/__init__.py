"""Method registry: registered name -> reference implementation.

The normative text lives in /methods/<name>.md; code here must match it.
Methods not yet implemented simply aren't registered — dispatch fails loud.
"""

from engine.errors import EngineError
from engine.methods import (
    annualized_percentage,
    annualized_subtraction_percentage,
    annualized_percentage_phaseout,
    federal_percentage_2020,
    flat_rate,
    elective_flat_rate,
    flat_rate_with_annual_allowance,
    per_period_credit_phaseout,
    per_period_percentage,
)
from engine.methods.custom import us_ct as custom_us_ct
from engine.methods.custom import us_al as custom_us_al
from engine.methods.custom import us_ma as custom_us_ma
from engine.methods.custom import us_or as custom_us_or

REGISTRY = {
    "flat_rate": flat_rate.compute,
    "flat_rate_with_annual_allowance": flat_rate_with_annual_allowance.compute,
    "annualized_percentage": annualized_percentage.compute,
    "annualized_percentage_phaseout": annualized_percentage_phaseout.compute,
    "annualized_subtraction_percentage": annualized_subtraction_percentage.compute,
    "per_period_percentage": per_period_percentage.compute,
    "elective_flat_rate": elective_flat_rate.compute,
    "per_period_credit_phaseout": per_period_credit_phaseout.compute,
    "federal_percentage_2020": federal_percentage_2020.compute,
    "custom/us_ct": custom_us_ct.compute,
    "custom/us_or": custom_us_or.compute,
    "custom/us_al": custom_us_al.compute,
    "custom/us_ma": custom_us_ma.compute,
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
