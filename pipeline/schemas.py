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

FREQUENCY_ENUM = {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                            "monthly", "quarterly", "semiannually", "annually"]}

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
            "elected_amount_treatment",
            "percent_deduction",
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
            "elected_amount_treatment": {
                "anyOf": [{"enum": ["wage_reduction"]}, {"type": "null"}],
                "description": "\"wage_reduction\" when the document subtracts an "
                "employee-entered dollar amount from wages (MS 89-350); null otherwise",
            },
            "percent_deduction": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["rate", "cap", "requires_allowances"],
                        "properties": {
                            "rate": DECIMAL,
                            "cap": DECIMAL,
                            "requires_allowances": {
                                "type": "boolean",
                                "description": "true when the document zeroes this deduction "
                                "for employees claiming no allowances (SC WH-1603F)",
                            },
                        },
                    },
                    {"type": "null"},
                ],
                "description": "Percentage-of-annual-wages deduction with a cap, or null",
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
    "elective_flat_rate": {
        "type": "object",
        "additionalProperties": False,
        "required": ["allowed_rates", "zero_rate_allowed", "default_rate"],
        "properties": {
            "allowed_rates": {"type": "array", "items": DECIMAL,
                              "description": "The published rate elections, as decimals"},
            "zero_rate_allowed": {"type": "boolean"},
            "default_rate": {**DECIMAL_OR_NULL,
                             "description": "Rate applied when no election is filed, or null"},
        },
    },
    "custom/us_ma": {
        "type": "object",
        "additionalProperties": False,
        "required": ["retirement_deduction_cap", "exemption_factors", "brackets",
                     "hoh_tax_value", "blindness_tax_value", "low_income_floor"],
        "properties": {
            "retirement_deduction_cap": {**DECIMAL, "description": "The cumulative annual FICA-deduction cap ($2,000)"},
            "exemption_factors": {
                "type": "array",
                "description": "Per payroll period: the claiming-'1' amount, and the "
                "per-exemption + plus amounts for claiming more than 1",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "claiming_one", "per_exemption", "plus"],
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                                               "monthly", "quarterly", "semiannually", "annually"]},
                        "claiming_one": DECIMAL,
                        "per_exemption": DECIMAL,
                        "plus": DECIMAL,
                    },
                },
            },
            "brackets": {**BRACKET_ROWS, "description": "ANNUAL: 5% tier then the "
                         "surtax-inclusive 9% tier above the printed threshold"},
            "hoh_tax_value": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                                               "monthly", "quarterly", "semiannually", "annually"]},
                        "amount": DECIMAL,
                    },
                },
            },
            "blindness_tax_value": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                                               "monthly", "quarterly", "semiannually", "annually"]},
                        "amount": DECIMAL,
                    },
                },
            },
            "low_income_floor": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                                               "monthly", "quarterly", "semiannually", "annually"]},
                        "amount": DECIMAL,
                    },
                },
            },
        },
    },
    "custom/us_al": {
        "type": "object",
        "additionalProperties": False,
        "required": ["statuses", "dependent_tiers"],
        "properties": {
            "statuses": {
                "type": "array",
                "description": "One entry per A-4 claim code (zero, s, ms, m, h). "
                "Standard-deduction rows come from the PRINTED Schedule of Standard "
                "Deduction Amounts (every range row, as printed; codes zero and s share "
                "the Single schedule). Bracket variants: 0/S/H/MS share one, M has its "
                "own — transcribe into each code.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "personal_exemption", "standard_deduction", "brackets"],
                    "properties": {
                        "code": {"enum": ["zero", "s", "ms", "m", "h"]},
                        "personal_exemption": DECIMAL,
                        "standard_deduction": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["at_least", "amount"],
                                "properties": {"at_least": DECIMAL, "amount": DECIMAL},
                            },
                            "description": "Printed schedule rows; at_least = the range's "
                            "lower bound (INCLUSIVE)",
                        },
                        "brackets": BRACKET_ROWS,
                    },
                },
            },
            "dependent_tiers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["more_than", "value"],
                    "properties": {"more_than": DECIMAL, "value": DECIMAL},
                },
                "description": "Per-dependent amounts by GI tier; more_than is EXCLUSIVE "
                "('greater than $50,000' -> more_than 50000)",
            },
        },
    },
    "custom/us_or": {
        "type": "object",
        "additionalProperties": False,
        "required": ["credit_per_allowance", "statuses", "status_groups"],
        "properties": {
            "credit_per_allowance": DECIMAL,
            "statuses": {
                "type": "array",
                "description": "Phase-out ladder + allowance-zeroing threshold per "
                "UNDERLYING status (single, married) — both [S] and [M] ladders, from "
                "wherever they are printed",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["status", "allowance_zero_above", "fed_subtraction_phaseout"],
                    "properties": {
                        "status": {"enum": ["single", "married"]},
                        "allowance_zero_above": DECIMAL,
                        "fed_subtraction_phaseout": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["at_least", "cap"],
            "properties": {"at_least": DECIMAL, "cap": DECIMAL},
        },
        "description": "'wages >= X' rows (INCLUSIVE lower); first row at_least 0 carries "
        "the un-phased cap",
    },
                    },
                },
            },
            "status_groups": {
                "type": "array",
                "description": "Brackets + standard deduction per bracket group "
                "('Single with fewer than 3 allowances' -> single_under_3; 'Single with "
                "3 or more allowances, or married' -> married_or_single_3plus)",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["group", "standard_deduction", "wage_tiers"],
                    "properties": {
                        "group": {"enum": ["single_under_3", "married_or_single_3plus"]},
                        "standard_deduction": DECIMAL,
                        "wage_tiers": {
                            "type": "array",
                            "description": "One entry per printed wage band (annual wages "
                            "up to $50,000; $50,000 or higher) — the formula constants "
                            "DIFFER between bands, transcribe each as printed",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["wages_at_least", "formulas"],
                                "properties": {
                                    "wages_at_least": DECIMAL,
                                    "formulas": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["at_least", "base", "rate", "excess_over"],
            "properties": {
                "at_least": DECIMAL, "base": DECIMAL, "rate": DECIMAL, "excess_over": DECIMAL,
            },
        },
        "description": "Printed formula rows 'WH = base + [(BASE - excess_over) x rate]'; "
        "at_least is the row's BASE lower bound; excess_over is copied EXACTLY as printed "
        "(it differs from at_least in the high-wage tier)",
    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "custom/us_ct": {
        "type": "object",
        "additionalProperties": False,
        "required": ["codes"],
        "properties": {
            "codes": {
                "type": "array",
                "description": "One entry per CT-W4 withholding code (a, b, c, d, f). "
                "Shared printed tables (e.g. Table B 'Code A, D, or F') are transcribed "
                "into EACH code they apply to. Code D: exemptions and credits are the "
                "single zero row per the footnotes.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "exemptions", "brackets", "add_back", "recapture", "credits"],
                    "properties": {
                        "code": {"enum": ["a", "b", "c", "d", "f"]},
                        "exemptions": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["more_than", "value"],
            "properties": {"more_than": DECIMAL, "value": DECIMAL},
        },
        "description": "Exclusive-lower 'More Than / Less Than or Equal To' rows, "
        "transcribed row for row as printed (value from the rightmost column)",
    },
                        "brackets": BRACKET_ROWS,
                        "add_back": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["more_than", "value"],
            "properties": {"more_than": DECIMAL, "value": DECIMAL},
        },
        "description": "Exclusive-lower 'More Than / Less Than or Equal To' rows, "
        "transcribed row for row as printed (value from the rightmost column)",
    },
                        "recapture": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["more_than", "value"],
            "properties": {"more_than": DECIMAL, "value": DECIMAL},
        },
        "description": "Exclusive-lower 'More Than / Less Than or Equal To' rows, "
        "transcribed row for row as printed (value from the rightmost column)",
    },
                        "credits": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["more_than", "value"],
            "properties": {"more_than": DECIMAL, "value": DECIMAL},
        },
        "description": "Exclusive-lower 'More Than / Less Than or Equal To' rows, "
        "transcribed row for row as printed (value from the rightmost column)",
    },
                    },
                },
            },
        },
    },
    "annualized_subtraction_percentage": {
        "type": "object",
        "additionalProperties": False,
        "required": ["standard_deduction", "credit_per_allowance", "midrange_snap", "table"],
        "properties": {
            "standard_deduction": DECIMAL,
            "credit_per_allowance": DECIMAL_OR_NULL,
            "midrange_snap": {
                "type": "object",
                "additionalProperties": False,
                "required": ["bracket_size", "midpoint", "snap_below"],
                "properties": {
                    "bracket_size": DECIMAL,
                    "midpoint": DECIMAL,
                    "snap_below": {
                        **DECIMAL,
                        "description": "Per the WORKED EXAMPLE and the table's transition "
                        "ladder, not the prose (known stale-text hazard)",
                    },
                },
            },
            "table": {
                "type": "array",
                "description": "EVERY printed row incl. the full transition ladder, exactly "
                "as printed (from / rate / subtract; subtract null when blank)",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["from", "rate", "subtract"],
                    "properties": {"from": DECIMAL, "rate": DECIMAL, "subtract": DECIMAL_OR_NULL},
                },
            },
        },
    },
    "per_period_credit_phaseout": {
        "type": "object",
        "additionalProperties": False,
        "required": ["rate", "phase_rate", "frequencies"],
        "properties": {
            "rate": DECIMAL,
            "phase_rate": {**DECIMAL, "description": "Credit reduction per dollar of wages over the threshold (UT: 0.013)"},
            "frequencies": {
                "type": "array",
                "description": "One entry per printed schedule (UT Schedules 1-8). Transcribe EVERY frequency.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "statuses"],
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                                               "monthly", "quarterly", "semiannually", "annually"]},
                        "statuses": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["filing_status", "base_allowance", "phase_start"],
                                "properties": {
                                    "filing_status": {"type": "string"},
                                    "base_allowance": DECIMAL,
                                    "phase_start": DECIMAL,
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "custom/us_ca": {
        "type": "object",
        "additionalProperties": False,
        "required": ["low_income_exemption", "estimated_deduction",
                     "standard_deduction", "exemption_allowance", "brackets"],
        "properties": {
            "low_income_exemption": {
                "type": "array",
                "description": "Table 1, one entry per payroll period; the two married "
                "columns split on the number of REGULAR allowances ('0 or 1' vs '2 or "
                "more'); daily/miscellaneous maps to frequency 'daily'",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "single", "married_allowances_0_1",
                                 "married_allowances_2_plus", "head_of_household"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "single": DECIMAL,
                        "married_allowances_0_1": DECIMAL,
                        "married_allowances_2_plus": DECIMAL,
                        "head_of_household": DECIMAL,
                    },
                },
            },
            "estimated_deduction": {
                "type": "array",
                "description": "Table 2: per period, the printed amounts for counts 1..10 "
                "IN ORDER (amounts[0] = one allowance). Do not extrapolate past the table.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amounts"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "amounts": {"type": "array", "minItems": 1, "items": DECIMAL},
                    },
                },
            },
            "standard_deduction": {
                "type": "array",
                "description": "Table 3, same column structure as Table 1",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "single", "married_allowances_0_1",
                                 "married_allowances_2_plus", "head_of_household"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "single": DECIMAL,
                        "married_allowances_0_1": DECIMAL,
                        "married_allowances_2_plus": DECIMAL,
                        "head_of_household": DECIMAL,
                    },
                },
            },
            "exemption_allowance": {
                "type": "array",
                "description": "Table 4: per period, the printed CREDIT amounts for counts "
                "1..10 IN ORDER (amounts[0] = one allowance; omit the zero row).",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amounts"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "amounts": {"type": "array", "minItems": 1, "items": DECIMAL},
                    },
                },
            },
            "brackets": {
                "type": "array",
                "description": "Tables 5-28: one entry per (period, filing status); "
                "statuses are single, married, head_of_household; printed bases are "
                "authoritative",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "statuses"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "statuses": {
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
                        },
                    },
                },
            },
        },
    },
    "custom/us_ny": {
        "type": "object",
        "additionalProperties": False,
        "required": ["deduction", "exemption_value", "brackets",
                     "method_iii_cutover", "method_iii"],
        "properties": {
            "deduction": {
                "type": "array",
                "description": "Table B deduction allowance, one entry per printed "
                "payroll period ('Daily or miscellaneous' maps to 'daily', 'Annual' to "
                "'annually')",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "single", "married"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "single": DECIMAL,
                        "married": DECIMAL,
                    },
                },
            },
            "exemption_value": {
                "type": "array",
                "description": "Table C value of one exemption per payroll period",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {"frequency": FREQUENCY_ENUM, "amount": DECIMAL},
                },
            },
            "brackets": {
                "type": "array",
                "description": "Method II Tables II-A..E AND the Annual Tax Rate "
                "Schedule (frequency 'annually'), one entry per (period, marital "
                "status): over = column 1 'at least' (column 3 repeats it), rate = "
                "column 4, base = column 5. Printed bases authoritative. Do NOT "
                "transcribe the final 'use Method III' line as a row.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "statuses"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "statuses": {
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
                        },
                    },
                },
            },
            "method_iii_cutover": {
                "type": "array",
                "description": "Each bracket table's FINAL printed line ('$X & over -> "
                "use Method III'): the per-period net-wage amount at which Method III "
                "takes over, per period and marital status",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "single", "married"],
                    "properties": {
                        "frequency": FREQUENCY_ENUM,
                        "single": DECIMAL,
                        "married": DECIMAL,
                    },
                },
            },
            "method_iii": {
                "type": "array",
                "description": "Method III top-rate bands on ANNUALIZED net wages, one "
                "entry per marital status; each band: over = column 1 'at least', rate "
                "= column 3",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["filing_status", "bands"],
                    "properties": {
                        "filing_status": {"type": "string"},
                        "bands": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["over", "rate"],
                                "properties": {"over": DECIMAL, "rate": DECIMAL},
                            },
                        },
                    },
                },
            },
        },
    },
    "rate_schedule_percentage": {
        "type": "object",
        "additionalProperties": False,
        "required": ["exemption_per_period", "standard_deduction_per_period",
                     "no_withholding_floor", "status_groups", "schedules"],
        "properties": {
            "exemption_per_period": {
                "type": "array",
                "description": "Printed per-period value of ONE exemption, every payroll period the document prints",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {"frequency": FREQUENCY_ENUM, "amount": DECIMAL},
                },
            },
            "standard_deduction_per_period": {
                "type": "array",
                "description": "Printed per-period standard-deduction allowance",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {"frequency": FREQUENCY_ENUM, "amount": DECIMAL},
                },
            },
            "no_withholding_floor": {
                "type": "array",
                "description": "The printed 'DO NOT WITHHOLD ON GROSS WAGES LESS THAN $X' per period (confirm it is identical across schedules; note in `notes` if any schedule differs)",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "amount"],
                    "properties": {"frequency": FREQUENCY_ENUM, "amount": DECIMAL},
                },
            },
            "status_groups": {
                "type": "array",
                "description": "The printed status groupings, e.g. (a) married filing joint or head of household; (b) single including MFS or dependent. group is a short machine key ('a', 'b'); statuses are lower_snake_case filing-status keys.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["group", "statuses"],
                    "properties": {
                        "group": {"type": "string"},
                        "statuses": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "schedules": {
                "type": "array",
                "description": "One entry per printed rate schedule (MD: 2.25% ... 3.30% plus the Maryland-resident-in-Delaware schedule). schedule is the combined rate as a decimal string ('0.0225') or a snake_case key for special schedules. Transcribe EVERY period and EVERY row; rates are the printed COMBINED marginal rates.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["schedule", "frequencies"],
                    "properties": {
                        "schedule": {"type": "string"},
                        "frequencies": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["frequency", "groups"],
                                "properties": {
                                    "frequency": FREQUENCY_ENUM,
                                    "groups": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "required": ["group", "brackets"],
                                            "properties": {
                                                "group": {"type": "string"},
                                                "brackets": BRACKET_ROWS,
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "deduction_constant_percentage": {
        "type": "object",
        "additionalProperties": False,
        "required": ["rate", "exemption_kinds", "periods_per_year"],
        "properties": {
            "rate": DECIMAL,
            "exemption_kinds": {
                "type": "array",
                "description": "One entry per exemption kind the certificate defines "
                "(IN WH-4: personal=line 5, dependent=line 6, first_time_dependent="
                "line 7, adopted=line 8). kind is a lower_snake_case machine key; "
                "annual_amount is the per-exemption ANNUAL dollar value the document "
                "states for that kind.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "annual_amount"],
                    "properties": {
                        "kind": {"type": "string"},
                        "annual_amount": DECIMAL,
                    },
                },
            },
            "periods_per_year": {
                "type": "array",
                "description": "The divisor each printed deduction-constant column "
                "implies (verify: printed cell = round(n x annual / divisor)). "
                "Transcribe ONLY frequencies the document prints tables for.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "divisor"],
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "biweekly", "semimonthly",
                                               "monthly", "quarterly", "semiannually", "annually"]},
                        "divisor": {"type": "integer"},
                    },
                },
            },
        },
    },
    "per_period_percentage": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "standard_deduction",
            "allowance_amount",
            "allowance_amounts_per_period",
            "allowance_cliff_annual_wages",
            "credit_per_allowance",
            "elected_amount_treatment",
            "frequencies",
        ],
        "properties": {
            "standard_deduction": {
                "anyOf": [PER_STATUS_AMOUNT, {"type": "null"}],
                "description": "ANNUAL per-status exemption divided by period count at "
                "computation time (e.g. Kansas), or null",
            },
            "allowance_amount": {
                **DECIMAL_OR_NULL,
                "description": "ANNUAL per-allowance amount divided with the standard "
                "deduction (e.g. Kansas per-dependent), or null",
            },
            "allowance_cliff_annual_wages": {
                **DECIMAL_OR_NULL,
                "description": "Annualized-wage threshold above which one allowance is worth "
                "exactly $0 (RI cliff), or null",
            },
            "credit_per_allowance": {
                **DECIMAL_OR_NULL,
                "description": "ANNUAL per-allowance tax credit prorated per period "
                "(IA legacy W-4 path: $40/allowance), or null",
            },
            "elected_amount_treatment": {
                "anyOf": [{"enum": ["tax_credit"]}, {"type": "null"}],
                "description": "\"tax_credit\" when the document subtracts an "
                "employee-entered dollar amount from TAX, prorated (IA W-4 line W); "
                "null otherwise",
            },
            "allowance_amounts_per_period": {
                "anyOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["frequency", "amount"],
                            "properties": {
                                "frequency": {
                                    "enum": ["daily", "weekly", "biweekly", "semimonthly",
                                             "monthly", "quarterly", "semiannually", "annually"]
                                },
                                "amount": DECIMAL,
                            },
                        },
                    },
                    {"type": "null"},
                ],
                "description": "The PRINTED per-period value of one allowance per frequency "
                "(e.g. Vermont's table headers), or null",
            },
            "frequencies": {
                "type": "array",
                "description": "One entry per printed payroll-period table. Transcribe EVERY "
                "frequency the document prints.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["frequency", "tables"],
                    "properties": {
                        "frequency": {
                            "enum": ["daily", "weekly", "biweekly", "semimonthly",
                                     "monthly", "quarterly", "semiannually", "annually"]
                        },
                        "tables": PER_STATUS_BRACKETS,
                    },
                },
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
        "exemption_counts",
        "rate_schedule",
        "step2_checkbox",
        "step3_credits",
        "step4a_other_income",
        "step4b_deductions",
        "step4c_extra",
        "additional_withholding",
        "elected_annual_amount",
        "period_federal_income_withholding",
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
        "rate_schedule": {
            "type": ["string", "null"],
            "description": "The printed rate schedule the example uses, matching the "
            "candidate's params.schedules key (MD: '0.0225'); null when the method "
            "has no schedule dimension.",
        },
        "exemption_counts": {
            "type": ["array", "null"],
            "description": "Named exemption counts where the state's certificate "
            "defines more than two kinds (IN WH-4: personal/dependent/"
            "first_time_dependent/adopted). kind MUST match a candidate "
            "params.exemptions key. Null when not applicable.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "count"],
                "properties": {
                    "kind": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
        },
        "step2_checkbox": {"type": ["boolean", "null"], "description": "Federal only; null otherwise"},
        "step3_credits": DECIMAL_OR_NULL,
        "step4a_other_income": DECIMAL_OR_NULL,
        "step4b_deductions": DECIMAL_OR_NULL,
        "step4c_extra": DECIMAL_OR_NULL,
        "additional_withholding": DECIMAL_OR_NULL,
        "elected_annual_amount": {
            **DECIMAL_OR_NULL,
            "description": "Employee-entered dollar amount where the example uses one "
            "(IA W-4 allowance dollars, MS 89-350 exemption); null otherwise",
        },
        "period_federal_income_withholding": {
            **DECIMAL_OR_NULL,
            "description": "Federal income tax withheld THIS PERIOD where the example "
            "states one (OR/AL formulas consume it); divide a stated annual federal "
            "amount by the pay periods; null otherwise",
        },
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
