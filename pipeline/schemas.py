"""JSON Schemas for the LLM passes' structured outputs.

Structured outputs require `additionalProperties: false` on every object and
support no dynamic keys, so shapes that the data files store as
filing-status-keyed mappings are represented here as arrays of
{filing_status, ...} entries. `pipeline.assemble` converts them to the data
file shape. The envelope (jurisdiction, tax, source block) is deliberately
absent: it comes from the source registry and the retrieval step, never from
the model.
"""

DECIMAL = {
    "type": "string",
    "description": "Exact decimal as a string, e.g. \"0.0440\" or \"12900\". Never a float.",
}
DECIMAL_OR_NULL = {"type": ["string", "null"], "description": "Exact decimal string, or null"}

BRACKET_ROWS = {
    "type": "array",
    "description": "Rows ascending by `over` (lower bound); first row has over \"0\". "
    "`base` is the printed cumulative tax at the lower bound, or null if the guide does not print one.",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["over", "rate", "base"],
        "properties": {"over": DECIMAL, "rate": DECIMAL, "base": DECIMAL_OR_NULL},
    },
}

PER_STATUS_BRACKETS = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["filing_status", "rows"],
        "properties": {
            "filing_status": {"type": "string"},
            "rows": BRACKET_ROWS,
        },
    },
}

PER_STATUS_AMOUNT = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["filing_status", "amount"],
        "properties": {"filing_status": {"type": "string"}, "amount": DECIMAL},
    },
}

ROUNDING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["to", "mode", "intermediate", "intermediate_to"],
    "properties": {
        "to": {**DECIMAL, "description": "Round the FINAL per-period amount to this multiple, e.g. \"1.00\" or \"0.01\""},
        "mode": {"enum": ["nearest", "up", "down", "half_even"]},
        "intermediate": {
            "enum": ["none", "annual"],
            "description": "\"annual\" ONLY if the guide's worked examples demonstrably round the annualized tax before dividing by pay periods",
        },
        "intermediate_to": {
            **DECIMAL_OR_NULL,
            "description": "Granularity of the intermediate (annual) rounding when it differs "
            "from the final `to` (e.g. VA: annual tax to \"1.00\", final to \"0.01\"); "
            "null when intermediate is none or uses the same granularity",
        },
    },
}

_PARAMS_BY_METHOD = {
    "flat_rate": {
        "type": "object",
        "additionalProperties": False,
        "required": ["rate"],
        "properties": {"rate": DECIMAL},
    },
    "flat_rate_with_annual_allowance": {
        "type": "object",
        "additionalProperties": False,
        "required": ["rate", "allowances"],
        "properties": {
            "rate": DECIMAL,
            "allowances": {
                **PER_STATUS_AMOUNT,
                "description": "Annual allowance per filing status",
            },
        },
    },
    "annualized_percentage": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "standard_deduction",
            "allowance_amount",
            "secondary_allowance_amount",
            "credit_per_allowance",
            "brackets",
        ],
        "properties": {
            "standard_deduction": {
                "anyOf": [PER_STATUS_AMOUNT, {"type": "null"}],
                "description": "Per filing status, or null if this state has none",
            },
            "allowance_amount": DECIMAL_OR_NULL,
            "secondary_allowance_amount": {
                **DECIMAL_OR_NULL,
                "description": "Per second-kind allowance where the state defines one "
                "(e.g. IL-W-4 Line 2 at $1,000); null otherwise",
            },
            "credit_per_allowance": DECIMAL_OR_NULL,
            "brackets": {
                **PER_STATUS_BRACKETS,
                "description": "One entry per filing status. A state with one schedule for "
                "all employees (no filing statuses) uses a single entry with "
                "filing_status \"all\".",
            },
        },
    },
    "annualized_percentage_phaseout": {
        "type": "object",
        "additionalProperties": False,
        "required": ["deduction_phaseout", "exemption_amount", "brackets"],
        "properties": {
            "deduction_phaseout": {
                "type": "array",
                "description": "Per filing status: the deduction equals `maximum` until annual wages "
                "reach `phase_start`, then shrinks by `phase_rate` per dollar above it, floored at 0",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["filing_status", "maximum", "phase_start", "phase_rate"],
                    "properties": {
                        "filing_status": {"type": "string"},
                        "maximum": DECIMAL,
                        "phase_start": DECIMAL,
                        "phase_rate": DECIMAL,
                    },
                },
            },
            "exemption_amount": DECIMAL_OR_NULL,
            "brackets": {
                **PER_STATUS_BRACKETS,
                "description": "One entry per filing status; a single schedule for all "
                "statuses uses one entry with filing_status \"all\"",
            },
        },
    },
    "federal_percentage_2020": {
        "type": "object",
        "additionalProperties": False,
        "required": ["wage_adjustment", "brackets_standard", "brackets_step2_checkbox"],
        "properties": {
            "wage_adjustment": {
                **PER_STATUS_AMOUNT,
                "description": "Worksheet 1A line 1g amounts per filing status "
                "(single, married_joint, head_of_household)",
            },
            "brackets_standard": PER_STATUS_BRACKETS,
            "brackets_step2_checkbox": PER_STATUS_BRACKETS,
        },
    },
}


def extraction_schema(method: str) -> dict:
    if method not in _PARAMS_BY_METHOD:
        raise ValueError(
            f"extractor has no schema for method {method!r}; known: {sorted(_PARAMS_BY_METHOD)}"
        )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["classification", "effective_from", "rounding", "params", "citations", "notes"],
        "properties": {
            "classification": {
                "enum": ["new_year_edition", "parameter_change", "cosmetic_reissue"],
                "description": "cosmetic_reissue = the document changed but no parameter did",
            },
            "effective_from": {
                "type": "string",
                "description": "ISO date (YYYY-MM-DD) the parameters take effect",
            },
            "rounding": ROUNDING,
            "params": _PARAMS_BY_METHOD[method],
            "citations": {
                "type": "array",
                "description": "One entry per parameter group, citing where it was read",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["what", "page"],
                    "properties": {"what": {"type": "string"}, "page": {"type": "integer"}},
                },
            },
            "notes": {
                "type": "string",
                "description": "Anything the reviewer must know: ambiguities, layout quirks, values you were unsure about",
            },
        },
    }


WORKED_EXAMPLE = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "page",
        "description",
        "pay_frequency",
        "gross_wages",
        "filing_status",
        "allowances",
        "secondary_allowances",
        "step2_checkbox",
        "step3_credits",
        "step4a_other_income",
        "step4b_deductions",
        "step4c_extra",
        "additional_withholding",
        "expected_withholding",
    ],
    "properties": {
        "page": {"type": "integer"},
        "description": {"type": "string"},
        "pay_frequency": {
            "enum": ["daily", "weekly", "biweekly", "semimonthly", "monthly", "quarterly", "semiannually", "annually"]
        },
        "gross_wages": DECIMAL,
        "filing_status": {"type": "string"},
        "allowances": {"type": ["integer", "null"]},
        "secondary_allowances": {
            "type": ["integer", "null"],
            "description": "Second allowance kind where the state defines one; null otherwise",
        },
        "step2_checkbox": {"type": ["boolean", "null"], "description": "Federal only; null otherwise"},
        "step3_credits": DECIMAL_OR_NULL,
        "step4a_other_income": DECIMAL_OR_NULL,
        "step4b_deductions": DECIMAL_OR_NULL,
        "step4c_extra": DECIMAL_OR_NULL,
        "additional_withholding": DECIMAL_OR_NULL,
        "expected_withholding": {
            **DECIMAL,
            "description": "The FINAL amount the publication's example arrives at, INCLUDING "
            "any additional withholding the example adds — the total actually withheld",
        },
    },
}

VERIFICATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["all_values_confirmed", "checks", "worked_examples"],
    "properties": {
        "all_values_confirmed": {"type": "boolean"},
        "checks": {
            "type": "array",
            "description": "One entry per numeric value in the candidate, confirmed against the document",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "candidate_value", "page", "confirmed", "note"],
                "properties": {
                    "path": {"type": "string", "description": "e.g. params.brackets.single[2].rate"},
                    "candidate_value": {"type": "string"},
                    "page": {"type": ["integer", "null"]},
                    "confirmed": {"type": "boolean"},
                    "note": {"type": ["string", "null"]},
                },
            },
        },
        "worked_examples": {
            "type": "array",
            "description": "EVERY worked example in the document that exercises this withholding method",
            "items": WORKED_EXAMPLE,
        },
    },
}
