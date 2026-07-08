from decimal import Decimal

import pytest

from engine.errors import InputError
from engine.inputs import EmployeeInput

BASE = {"pay_frequency": "biweekly", "gross_wages": "2400.00"}


def test_minimal_record():
    emp = EmployeeInput.from_dict(BASE)
    assert emp.pay_periods_per_year == 26
    assert emp.gross_wages == Decimal("2400.00")


def test_bad_pay_frequency():
    with pytest.raises(InputError, match="pay_frequency"):
        EmployeeInput.from_dict({**BASE, "pay_frequency": "fortnightly"})


def test_negative_amounts_rejected():
    with pytest.raises(InputError):
        EmployeeInput.from_dict({**BASE, "gross_wages": "-1"})
    with pytest.raises(InputError):
        EmployeeInput.from_dict(
            {**BASE, "state": [{"jurisdiction": "US-ZZ", "additional_withholding": "-5"}]}
        )


def test_federal_block_validation():
    with pytest.raises(InputError, match="w4_version"):
        EmployeeInput.from_dict({**BASE, "federal": {"w4_version": 2019, "filing_status": "single"}})
    with pytest.raises(InputError, match="filing_status"):
        EmployeeInput.from_dict({**BASE, "federal": {"w4_version": 2020, "filing_status": "married"}})


def test_allowances_must_be_nonnegative_int():
    with pytest.raises(InputError, match="allowances"):
        EmployeeInput.from_dict({**BASE, "state": [{"jurisdiction": "US-ZZ", "allowances": -1}]})


def test_state_election_lookup():
    emp = EmployeeInput.from_dict({**BASE, "state": [{"jurisdiction": "US-ZZ"}]})
    assert emp.state_election("US-ZZ").jurisdiction == "US-ZZ"
    with pytest.raises(InputError, match="no state election"):
        emp.state_election("US-CO")


def test_deductions_require_type():
    with pytest.raises(InputError, match="type"):
        EmployeeInput.from_dict({**BASE, "pretax_deductions": [{"amount": "10.00"}]})
