from decimal import Decimal

import pytest

from engine.errors import DataError
from engine.money import D, Rounding


def test_parses_strings_and_ints():
    assert D("0.0440") == Decimal("0.0440")
    assert D(45000) == Decimal("45000")


def test_rejects_floats_and_bools():
    with pytest.raises(DataError):
        D(0.044)
    with pytest.raises(DataError):
        D(True)


def test_rejects_garbage():
    with pytest.raises(DataError):
        D("4,500")


def test_default_rounding_is_cents_half_up():
    r = Rounding()
    assert r.apply(Decimal("85.665")) == Decimal("85.67")
    assert r.apply(Decimal("85.664")) == Decimal("85.66")


def test_round_to_dollar_modes():
    cases = [
        ("nearest", "171.50", "172.00"),
        ("half_even", "171.50", "172.00"),
        ("half_even", "172.50", "172.00"),
        ("up", "171.01", "172.00"),
        ("down", "171.99", "171.00"),
    ]
    for mode, amount, expected in cases:
        r = Rounding.from_dict({"to": "1.00", "mode": mode})
        assert r.apply(Decimal(amount)) == Decimal(expected), (mode, amount)


def test_invalid_rounding_blocks_rejected():
    with pytest.raises(DataError):
        Rounding.from_dict({"to": "1.00", "mode": "sideways"})
    with pytest.raises(DataError):
        Rounding.from_dict({"to": "0", "mode": "nearest"})
    with pytest.raises(DataError):
        Rounding.from_dict({"to": "1.00", "mode": "nearest", "intermediate": "period"})


def test_intermediate_to_differs_from_final():
    from engine.money import Rounding

    # VA-shaped: annual tax to whole dollars, final to cents.
    r = Rounding.from_dict(
        {"to": "0.01", "mode": "nearest", "intermediate": "annual", "intermediate_to": "1.00"}
    )
    assert r.apply_intermediate(Decimal("2627.62")) == Decimal("2628.00")
    assert r.apply(Decimal("2628") / 24) == Decimal("109.50")
    # without intermediate_to, intermediate rounding uses `to`
    r2 = Rounding.from_dict({"to": "0.01", "mode": "nearest", "intermediate": "annual"})
    assert r2.apply_intermediate(Decimal("2627.62")) == Decimal("2627.62")
    with pytest.raises(DataError):
        Rounding.from_dict({"to": "0.01", "mode": "nearest", "intermediate_to": "0"})
