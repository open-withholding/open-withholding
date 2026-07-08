from decimal import Decimal

import pytest

from engine.errors import DataError
from engine.inputs import PretaxDeduction


def test_federal_row(taxability):
    assert taxability.reduces("401k_traditional", "federal_income", "US")
    assert not taxability.reduces("401k_traditional", "fica", "US")


def test_state_default_and_override(taxability):
    assert taxability.reduces("401k_traditional", "state_income", "US-ZZ")
    assert not taxability.reduces("401k_traditional", "state_income", "US-PA")


def test_locals_follow_their_state(taxability):
    assert not taxability.reduces("401k_traditional", "state_income", "US-PA-PSD-700102")


def test_unknown_deduction_type_is_hard_error(taxability):
    with pytest.raises(DataError, match="unknown pretax deduction type"):
        taxability.reduces("mystery_plan", "federal_income", "US")


def test_taxable_wages_clamps_at_zero(taxability):
    deductions = (PretaxDeduction(type="401k_traditional", amount=Decimal("5000")),)
    assert taxability.taxable_wages(
        Decimal("2400"), deductions, "state_income", "US-ZZ"
    ) == Decimal("0")
    # PA override: the 401(k) does not reduce, so wages stay whole.
    assert taxability.taxable_wages(
        Decimal("2400"), deductions, "state_income", "US-PA"
    ) == Decimal("2400")
