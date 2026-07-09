"""IL-shaped (two allowance kinds, single 'all' table) and WI-shaped
(phase-out deduction) methods. Every expected value is either printed in the
publication (WI Pub W-166 examples 1-3, IL-700-T Alice example) or
hand-computed with the arithmetic shown."""

from decimal import Decimal

import pytest

from engine.errors import InputError
from engine.inputs import EmployeeInput
from engine.loader import load_parameter_dict
from engine.pipeline import compute_withholding

SOURCE = {
    "document": "FIXTURE doc",
    "url": "https://example.gov/x.pdf",
    "retrieved": "2026-07-08",
    "sha256": "0" * 64,
}


def _pf(jurisdiction, method, params):
    return load_parameter_dict(
        {
            "schema_version": "0.1",
            "jurisdiction": jurisdiction,
            "tax": "state_income_withholding",
            "effective_from": "2026-01-01",
            "source": SOURCE,
            "method": method,
            "params": params,
            "rounding": {"to": "0.01", "mode": "nearest"},
        }
    )


# IL-700-T 2026 automated payroll method: flat 4.95%, Line 1 $2,925, Line 2 $1,000.
IL = _pf(
    "US-IL",
    "annualized_percentage",
    {
        "allowance_amount": "2925",
        "secondary_allowance_amount": "1000",
        "credit_per_allowance": None,
        "brackets": {"all": [{"over": "0", "rate": "0.0495"}]},
    },
)

# WI Pub W-166 alternate method (2026 revision).
WI = _pf(
    "US-WI",
    "annualized_percentage_phaseout",
    {
        "deduction_phaseout": {
            "single": {"maximum": "6702", "phase_start": "17780", "phase_rate": "0.12"},
            "married": {"maximum": "9461", "phase_start": "25727", "phase_rate": "0.20"},
        },
        "exemption_amount": "400",
        "brackets": {
            "all": [
                {"over": "0", "rate": "0.0354"},
                {"over": "12760", "rate": "0.0465", "base": "451.70"},
                {"over": "25520", "rate": "0.0530", "base": "1045.04"},
                {"over": "280950", "rate": "0.0765", "base": "14582.83"},
            ]
        },
    },
)


def _employee(frequency, gross, **election):
    return EmployeeInput.from_dict(
        {
            "pay_frequency": frequency,
            "gross_wages": gross,
            "state": [{"jurisdiction": election.pop("jurisdiction"), **election}],
        }
    )


def test_il_alice_printed_example(taxability):
    # IL-700-T p.4: $800 weekly, 2 Line-1 + 2 Line-2 allowances -> $32.13
    emp = _employee("weekly", "800.00", jurisdiction="US-IL", allowances=2, secondary_allowances=2)
    assert compute_withholding(IL, emp, taxability) == Decimal("32.13")


def test_il_no_filing_status_needed(taxability):
    # single 'all' table serves elections without a filing_status
    emp = _employee("weekly", "300.00", jurisdiction="US-IL", allowances=2, secondary_allowances=1)
    # (15,600 - 5,850 - 1,000) x 0.0495 / 52 = 433.125/52 = 8.3293 -> 8.33
    assert compute_withholding(IL, emp, taxability) == Decimal("8.33")


def test_wi_printed_example_1(taxability):
    # W-166 ex.1: $350 weekly single, 1 exemption -> $7.59
    emp = _employee("weekly", "350.00", jurisdiction="US-WI", filing_status="single", allowances=1)
    assert compute_withholding(WI, emp, taxability) == Decimal("7.59")


def test_wi_printed_example_2(taxability):
    # W-166 ex.2: $500 weekly single, 3 exemptions -> $14.34
    emp = _employee("weekly", "500.00", jurisdiction="US-WI", filing_status="single", allowances=3)
    assert compute_withholding(WI, emp, taxability) == Decimal("14.34")


def test_wi_printed_example_3(taxability):
    # W-166 ex.3: $1,000 biweekly married, 3 exemptions -> $22.08
    emp = _employee(
        "biweekly", "1000.00", jurisdiction="US-WI", filing_status="married", allowances=3
    )
    assert compute_withholding(WI, emp, taxability) == Decimal("22.08")


def test_wi_deduction_floors_at_zero(taxability):
    # $2,000 weekly single: annual 104,000 >= 73,630 -> deduction 0;
    # 1,045.044 + (104,000-25,520) x 5.30% = 5,204.484; /52 = 100.086 -> 100.09
    emp = _employee("weekly", "2000.00", jurisdiction="US-WI", filing_status="single")
    assert compute_withholding(WI, emp, taxability) == Decimal("100.09")


def test_wi_below_phase_start_keeps_full_deduction(taxability):
    # $300 weekly single: annual 15,600 < 17,780 -> deduction 6,702;
    # net 8,898 x 3.54% = 314.99 (0 exemptions); /52 = 6.0575 -> 6.06
    emp = _employee("weekly", "300.00", jurisdiction="US-WI", filing_status="single")
    assert compute_withholding(WI, emp, taxability) == Decimal("6.06")


def test_wi_unknown_status_lists_valid(taxability):
    emp = _employee("weekly", "500.00", jurisdiction="US-WI", filing_status="head_of_household")
    with pytest.raises(InputError, match="married"):
        compute_withholding(WI, emp, taxability)


def test_phaseout_extraction_transform_loads():
    from pipeline import assemble

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "deduction_phaseout": [
                {"filing_status": "Single", "maximum": "6702", "phase_start": "17780", "phase_rate": "0.12"},
            ],
            "exemption_amount": "400",
            "brackets": [
                {"filing_status": "all", "rows": [{"over": "0", "rate": "0.0354", "base": None}]}
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-WI",
        tax="state_income_withholding",
        method="annualized_percentage_phaseout",
        extraction=extraction,
        source=SOURCE,
    )
    pf = load_parameter_dict(raw)
    assert pf.params["deduction_phaseout"]["single"]["phase_rate"] == "0.12"


def test_va_shaped_intermediate_dollar_rounding(taxability):
    # VA p.22 example: 5 exemptions, semimonthly $2,649 -> T=50,176;
    # annual tax 720 + 5.75% x 33,176 = 2,627.62 -> rounded to 2,628 ->
    # / 24 = 109.50 exactly (the printed W value).
    va = _pf(
        "US-VA",
        "annualized_percentage",
        {
            "standard_deduction": {"all": "8750"},
            "allowance_amount": "930",
            "secondary_allowance_amount": "800",
            "credit_per_allowance": None,
            "brackets": {
                "all": [
                    {"over": "0", "rate": "0.02"},
                    {"over": "3000", "rate": "0.03", "base": "60"},
                    {"over": "5000", "rate": "0.05", "base": "120"},
                    {"over": "17000", "rate": "0.0575", "base": "720"},
                ]
            },
        },
    )
    # override rounding to the VA shape
    from engine.money import Rounding
    import dataclasses
    va = dataclasses.replace(
        va,
        rounding=Rounding.from_dict(
            {"to": "0.01", "mode": "nearest", "intermediate": "annual", "intermediate_to": "1.00"}
        ),
    )
    emp = _employee("semimonthly", "2649.00", jurisdiction="US-VA", allowances=5)
    assert compute_withholding(va, emp, taxability) == Decimal("109.50")
