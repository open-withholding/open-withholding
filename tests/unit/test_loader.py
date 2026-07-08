import datetime as dt

import pytest

from engine.errors import DataError
from engine.loader import load_parameter_dict, select_effective

VALID = {
    "schema_version": "0.1",
    "jurisdiction": "US-ZZ",
    "tax": "state_income_withholding",
    "effective_from": "2026-01-01",
    "effective_to": None,
    "source": {
        "document": "FIXTURE doc",
        "url": "https://example.gov/x.pdf",
        "retrieved": "2025-12-15",
        "sha256": "0" * 64,
    },
    "method": "flat_rate",
    "params": {"rate": "0.0100"},
    "rounding": {"to": "0.01", "mode": "nearest"},
}


def _variant(**overrides):
    raw = {**VALID, **overrides}
    if "source" in overrides and overrides["source"] is None:
        del raw["source"]
    return raw


def test_valid_file_loads():
    pf = load_parameter_dict(VALID)
    assert pf.method == "flat_rate"
    assert pf.effective_from == dt.date(2026, 1, 1)


def test_provenance_is_mandatory():
    with pytest.raises(DataError, match="schema validation failed"):
        load_parameter_dict(_variant(source=None))
    incomplete = dict(VALID["source"])
    del incomplete["sha256"]
    with pytest.raises(DataError, match="schema validation failed"):
        load_parameter_dict(_variant(source=incomplete))


def test_float_rate_rejected_by_schema():
    with pytest.raises(DataError, match="schema validation failed"):
        load_parameter_dict(_variant(params={"rate": 0.01}))


def test_bad_bracket_base_rejected():
    raw = _variant(
        method="annualized_percentage",
        params={
            "brackets": {
                "single": [
                    {"over": "0", "rate": "0.01"},
                    {"over": "1000", "rate": "0.02", "base": "99"},
                ]
            }
        },
    )
    with pytest.raises(DataError, match="recomputed cumulative"):
        load_parameter_dict(raw)


def test_effective_to_before_from_rejected():
    with pytest.raises(DataError, match="precedes"):
        load_parameter_dict(_variant(effective_to="2025-06-30"))


def test_custom_requires_implementation():
    with pytest.raises(DataError, match="schema validation failed"):
        load_parameter_dict(_variant(method="custom"))


def test_select_effective_picks_the_superseding_file():
    original = load_parameter_dict(_variant(effective_to="2026-06-30"))
    revision = load_parameter_dict(
        _variant(effective_from="2026-07-01", params={"rate": "0.0200"})
    )
    files = [original, revision]
    kwargs = {"jurisdiction": "US-ZZ", "tax": "state_income_withholding"}
    assert select_effective(files, dt.date(2026, 3, 1), **kwargs) is original
    assert select_effective(files, dt.date(2026, 8, 1), **kwargs) is revision
    with pytest.raises(DataError, match="no parameter file"):
        select_effective(files, dt.date(2025, 12, 31), **kwargs)


def test_retroactive_correction_wins_tie():
    original = load_parameter_dict(VALID)
    correction = load_parameter_dict(_variant(effective_from="2026-02-01"))
    chosen = select_effective(
        [original, correction],
        dt.date(2026, 3, 1),
        jurisdiction="US-ZZ",
        tax="state_income_withholding",
    )
    assert chosen is correction
