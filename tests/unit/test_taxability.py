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


def test_matrix_is_cited_release_gate():
    # The matrix header declares draft_uncited a release blocker; this is
    # the mechanical form of that promise.
    import yaml
    from pathlib import Path
    raw = yaml.safe_load(
        (Path(__file__).resolve().parent.parent.parent / "taxability" / "us.yaml").read_text())
    assert raw.get("status") == "cited"
    # Every source carries the full provenance tuple
    for key, src in raw["sources"].items():
        for field in ("document", "url", "sha256", "retrieved"):
            assert src.get(field), f"sources.{key}.{field} missing"
        assert len(src["sha256"]) == 64


def test_nj_verdicts_match_njwt(taxability):
    # NJ-WT p.6: 401(k) up to the federal limit is EXCLUDABLE (the uncited
    # draft had this backwards); p.5: 403(b) and employee-elected cafeteria
    # amounts (FSA, health premiums) are taxable.
    assert taxability.reduces("401k_traditional", "state_income", "US-NJ")
    assert not taxability.reduces("403b_traditional", "state_income", "US-NJ")
    assert not taxability.reduces("fsa_health", "state_income", "US-NJ")
    assert not taxability.reduces("cafeteria_health_premium", "state_income", "US-NJ")
    assert not taxability.reduces("hsa_cafeteria", "state_income", "US-NJ")


def test_ca_hsa_override(taxability):
    # DE 231EB pp.2-3: HSA contributions are Subject in the PIT column
    assert not taxability.reduces("hsa_cafeteria", "state_income", "US-CA")
    assert taxability.reduces("cafeteria_health_premium", "state_income", "US-CA")
