from decimal import Decimal

import pytest

from engine.brackets import parse_table, tax_for
from engine.errors import DataError

ROWS = [
    {"over": "0", "rate": "0.0110"},
    {"over": "3324", "rate": "0.0220"},
    {"over": "8280", "rate": "0.0450"},
]


def test_cumulative_bases_recomputed():
    table = parse_table(ROWS)
    assert table[0].base == Decimal("0")
    assert table[1].base == Decimal("36.564")      # 3324 * 0.011
    assert table[2].base == Decimal("145.596")     # + 4956 * 0.022


def test_tax_for_matches_hand_computation():
    table = parse_table(ROWS)
    assert tax_for(table, Decimal("0")) == Decimal("0")
    assert tax_for(table, Decimal("3324")) == Decimal("36.564")
    # 54540 falls in the top bracket: 145.596 + 46260 * 0.045
    assert tax_for(table, Decimal("54540")) == Decimal("2227.296")


def test_declared_base_must_match():
    rows = [dict(ROWS[0]), dict(ROWS[1]), dict(ROWS[2])]
    rows[2]["base"] = "145.596"
    parse_table(rows)  # correct base accepted
    rows[2]["base"] = "145.60"
    with pytest.raises(DataError, match="recomputed cumulative"):
        parse_table(rows)


def test_first_row_must_start_at_zero():
    with pytest.raises(DataError, match="over == 0"):
        parse_table([{"over": "100", "rate": "0.01"}])


def test_rows_must_ascend():
    with pytest.raises(DataError, match="ascending"):
        parse_table([{"over": "0", "rate": "0.01"}, {"over": "0", "rate": "0.02"}])


def test_empty_table_rejected():
    with pytest.raises(DataError, match="empty"):
        parse_table([])


def test_negative_amount_rejected():
    with pytest.raises(DataError):
        tax_for(parse_table(ROWS), Decimal("-1"))
