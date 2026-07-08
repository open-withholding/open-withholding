"""End-to-end: fixture parameter files -> engine -> hand-computed amounts.

Every expected value here was computed by hand from the fixture numbers; the
comments show the arithmetic so a reviewer can re-derive them.
"""

import datetime as dt
from decimal import Decimal

import pytest

from engine.errors import EngineError, InputError
from engine.inputs import EmployeeInput
from engine.loader import load_parameter_dict, select_effective
from engine.pipeline import compute_withholding

AS_OF = dt.date(2026, 6, 15)


def _params(fixture_params, jurisdiction, tax):
    return select_effective(fixture_params, AS_OF, jurisdiction=jurisdiction, tax=tax)


def _employee(**overrides):
    record = {"pay_frequency": "biweekly", "gross_wages": "2400.00", **overrides}
    return EmployeeInput.from_dict(record)


def test_annualized_percentage_end_to_end(fixture_params, taxability):
    # taxable 2400-120-50=2230; annual 57980; -2440 SD -1000 allowance = 54540
    # tax 145.596 + 46260*0.045 = 2227.296; /26 = 85.6652... -> 85.67
    employee = _employee(
        pretax_deductions=[
            {"type": "401k_traditional", "amount": "120.00"},
            {"type": "hsa_cafeteria", "amount": "50.00"},
        ],
        state=[{"jurisdiction": "US-ZZ", "filing_status": "single", "allowances": 1}],
    )
    pf = _params(fixture_params, "US-ZZ", "state_income_withholding")
    assert compute_withholding(pf, employee, taxability) == Decimal("85.67")


def test_flat_rate_with_annual_allowance_end_to_end(fixture_params, taxability):
    # annual 62400 - 4500 = 57900 * 0.044 = 2547.60; /26 = 97.9846... -> 97.98; +5 extra
    employee = _employee(
        state=[
            {
                "jurisdiction": "US-CO",
                "filing_status": "single",
                "additional_withholding": "5.00",
            }
        ]
    )
    pf = _params(fixture_params, "US-CO", "state_income_withholding")
    assert compute_withholding(pf, employee, taxability) == Decimal("102.98")


def test_flat_rate_local_respects_taxability(fixture_params, taxability):
    # PA: 401(k) does NOT reduce, HSA does -> taxable 2350 * 0.01 = 23.50
    employee = _employee(
        pretax_deductions=[
            {"type": "401k_traditional", "amount": "120.00"},
            {"type": "hsa_cafeteria", "amount": "50.00"},
        ],
        locals=[{"jurisdiction": "US-PA-PSD-700102"}],
    )
    pf = _params(fixture_params, "US-PA-PSD-700102", "local_income_withholding")
    assert compute_withholding(pf, employee, taxability) == Decimal("23.50")


def test_federal_2020_standard_table(fixture_params, taxability):
    # taxable 2230; annual 57980; -12900 adjustment = 45080 AAWA
    # (45080-10000)*0.10 = 3508; /26 = 134.9230...; credits 2000/26 = 76.9230...
    # after credits exactly 58.00
    employee = _employee(
        pretax_deductions=[
            {"type": "401k_traditional", "amount": "120.00"},
            {"type": "hsa_cafeteria", "amount": "50.00"},
        ],
        federal={
            "w4_version": 2020,
            "filing_status": "married_joint",
            "step3_credits": "2000",
        },
    )
    pf = _params(fixture_params, "US", "federal_income_withholding")
    assert compute_withholding(pf, employee, taxability) == Decimal("58.00")


def test_federal_2020_step2_checkbox_and_extra(fixture_params, taxability):
    # annual 62400, no adjustment, checkbox single table:
    # base at 50000 = 2000+5500 = 7500; +12400*0.30 = 11220; /26 = 431.538 -> 431.54; +10
    employee = _employee(
        federal={
            "w4_version": 2020,
            "filing_status": "single",
            "step2_checkbox": True,
            "step4c_extra": "10.00",
        }
    )
    pf = _params(fixture_params, "US", "federal_income_withholding")
    assert compute_withholding(pf, employee, taxability) == Decimal("441.54")


def test_federal_requires_federal_block(fixture_params, taxability):
    pf = _params(fixture_params, "US", "federal_income_withholding")
    with pytest.raises(InputError, match="federal block"):
        compute_withholding(pf, _employee(), taxability)


def test_low_wages_clamp_to_zero(fixture_params, taxability):
    employee = _employee(
        gross_wages="50.00",
        state=[{"jurisdiction": "US-CO", "filing_status": "single"}],
    )
    pf = _params(fixture_params, "US-CO", "state_income_withholding")
    # annual 1300 < 4500 allowance -> 0
    assert compute_withholding(pf, employee, taxability) == Decimal("0.00")


def test_wrong_filing_status_lists_valid_ones(fixture_params, taxability):
    employee = _employee(
        state=[{"jurisdiction": "US-ZZ", "filing_status": "married_joint"}]
    )
    pf = _params(fixture_params, "US-ZZ", "state_income_withholding")
    with pytest.raises(InputError, match="married"):
        compute_withholding(pf, employee, taxability)


def test_unimplemented_method_fails_loud(taxability):
    raw = {
        "schema_version": "0.1",
        "jurisdiction": "US-ZZ",
        "tax": "state_income_withholding",
        "effective_from": "2026-01-01",
        "source": {
            "document": "FIXTURE doc",
            "url": "https://example.gov/x.pdf",
            "retrieved": "2025-12-15",
            "sha256": "0" * 64,
        },
        "method": "wage_bracket_lookup",
        "params": {},
    }
    pf = load_parameter_dict(raw)
    employee = _employee(state=[{"jurisdiction": "US-ZZ", "filing_status": "single"}])
    with pytest.raises(EngineError, match="not implemented"):
        compute_withholding(pf, employee, taxability)
