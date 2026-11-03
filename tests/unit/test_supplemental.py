"""Supplemental wages (methods/supplemental.md): the flat method with the
federal excess tier, the aggregate method through the regular file, the
golden expect key, and the assembler's method choice."""

import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.errors import EngineError, InputError  # noqa: E402
from engine.golden import GoldenCase, run_golden_case  # noqa: E402
from engine.inputs import EmployeeInput  # noqa: E402
from engine.loader import select_effective  # noqa: E402
from engine.pipeline import compute_supplemental_withholding, compute_withholding  # noqa: E402
from pipeline import assemble  # noqa: E402

AS_OF = dt.date(2026, 6, 15)


def _emp(**over):
    base = {"pay_frequency": "biweekly", "gross_wages": "5000.00", "wage_type": "supplemental",
            "federal": {"w4_version": 2020, "filing_status": "single"}}
    base.update(over)
    return EmployeeInput.from_dict(base)


def test_flat_rate_bonus(fixture_params, taxability):
    assert compute_supplemental_withholding(fixture_params, _emp(), taxability, AS_OF, "US") == Decimal("1100.00")


def test_flat_rate_pretax_deduction_reduces_the_payment(fixture_params, taxability):
    emp = _emp(pretax_deductions=[{"type": "401k_traditional", "amount": "500.00"}])
    assert compute_supplemental_withholding(fixture_params, emp, taxability, AS_OF, "US") == Decimal("990.00")


def test_federal_excess_tier_splits_at_the_threshold(fixture_params, taxability):
    # 998,000 already paid: 2,000 of this 5,000 at 22%, 3,000 at 37%
    emp = _emp(ytd={"supplemental_wages": "998000.00"})
    assert compute_supplemental_withholding(fixture_params, emp, taxability, AS_OF, "US") == Decimal("1550.00")
    emp = _emp(ytd={"supplemental_wages": "2000000.00"})
    assert compute_supplemental_withholding(fixture_params, emp, taxability, AS_OF, "US") == Decimal("1850.00")


def test_aggregate_is_combined_minus_regular(fixture_params, taxability):
    regular = select_effective(fixture_params, AS_OF, jurisdiction="US-ZZ", tax="state_income_withholding")
    cert = {"jurisdiction": "US-ZZ", "filing_status": "single", "allowances": 1}
    emp = _emp(gross_wages="3000.00", concurrent_regular_wages="2000.00", state=[cert])
    combined = compute_withholding(regular, EmployeeInput.from_dict({"pay_frequency": "biweekly", "gross_wages": "5000.00", "state": [cert]}), taxability)
    alone = compute_withholding(regular, EmployeeInput.from_dict({"pay_frequency": "biweekly", "gross_wages": "2000.00", "state": [cert]}), taxability)
    assert combined > alone > 0
    assert compute_supplemental_withholding(fixture_params, emp, taxability, AS_OF, "US-ZZ") == combined - alone


def test_aggregate_method_cannot_run_as_a_single_file(fixture_params, taxability):
    pf = select_effective(fixture_params, AS_OF, jurisdiction="US-ZZ", tax="supplemental_wage_withholding")
    with pytest.raises(EngineError, match="compute_supplemental_withholding"):
        compute_withholding(pf, _emp(), taxability)


def test_golden_expect_key(fixture_params, taxability):
    case = GoldenCase(path=Path("x"), source={"document": "fixture", "page": 1, "example": "bonus"},
                      as_of=AS_OF, input_record={"pay_frequency": "biweekly", "gross_wages": "5000.00",
                                                 "wage_type": "supplemental", "federal": {"w4_version": 2020, "filing_status": "single"}},
                      expect={"supplemental_withholding": {"US": "1100.00"}})
    results = run_golden_case(case, fixture_params, taxability)
    assert len(results) == 1 and results[0].ok


def test_wage_type_is_validated():
    with pytest.raises(InputError, match="wage_type"):
        EmployeeInput.from_dict({"pay_frequency": "weekly", "gross_wages": "1", "wage_type": "bonus"})


def test_assembler_picks_the_method_the_document_states():
    flat = {"flat_rate": "0.05", "aggregate_only": False, "excess_rate": None, "excess_threshold": None}
    agg = {"flat_rate": None, "aggregate_only": True, "excess_rate": None, "excess_threshold": None}
    neither = {"flat_rate": None, "aggregate_only": False, "excess_rate": None, "excess_threshold": None}
    assert assemble.supplemental_method(flat) == "supplemental_flat_rate"
    assert assemble._transform_params("supplemental", flat) == {"rate": "0.05"}
    assert assemble.supplemental_method(agg) == "supplemental_aggregate"
    assert assemble._transform_params("supplemental", agg) == {}
    with pytest.raises(ValueError, match="one rule or the other"):
        assemble.supplemental_method(neither)
    fed = {"flat_rate": "0.22", "aggregate_only": False, "excess_rate": "0.37", "excess_threshold": "1000000"}
    assert assemble._transform_params("supplemental", fed) == {"rate": "0.22", "excess_rate": "0.37", "excess_threshold": "1000000"}
    assert str(assemble.data_path("US", 2026, "supplemental_wage_withholding")) == "data/us/federal/2026/supplemental.yaml"
    assert assemble.golden_slug("US-CO", "supplemental_wage_withholding") == "us-co-supplemental"


def test_assembled_file_validates_and_golden_assembles():
    from engine.loader import load_parameter_dict
    ext = {"classification": "new_year_edition", "effective_from": "2026-01-01",
           "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none", "intermediate_to": None},
           "params": {"flat_rate": "0.22", "aggregate_only": False, "excess_rate": "0.37", "excess_threshold": "1000000"}}
    src = {"document": "Pub 15 (2026)", "url": "https://x.gov/p15.pdf", "retrieved": "2026-11-03", "sha256": "ab" * 32}
    raw = assemble.assemble_parameter_file(jurisdiction="US", tax="supplemental_wage_withholding", method="supplemental", extraction=ext, source=src)
    assert raw["method"] == "supplemental_flat_rate"
    load_parameter_dict(raw)
    g = assemble.assemble_golden_case(jurisdiction="US", tax="supplemental_wage_withholding", as_of="2026-06-15", document="Pub 15 (2026)",
                                      example={"page": 20, "description": "bonus", "pay_frequency": "biweekly", "gross_wages": "2000",
                                               "filing_status": "n/a", "concurrent_regular_wages": "0", "ytd_supplemental_wages": "0",
                                               "expected_withholding": "440.00"})
    assert g["input"]["wage_type"] == "supplemental" and g["expect"] == {"supplemental_withholding": {"US": "440.00"}}


def _union_params(schema, acc=None):
    """Count parameters whose type is a union (type array or anyOf) — the
    Anthropic structured-output limit is 16 per request schema."""
    acc = [] if acc is None else acc
    if isinstance(schema, dict):
        if isinstance(schema.get("type"), list) or "anyOf" in schema:
            acc.append(schema)
        for v in schema.values():
            _union_params(v, acc)
    elif isinstance(schema, list):
        for v in schema:
            _union_params(v, acc)
    return acc


def test_request_schemas_stay_under_the_union_limit():
    from pipeline.schemas import VERIFICATION_SCHEMA, _PARAMS_BY_METHOD, extraction_schema
    assert len(_union_params(VERIFICATION_SCHEMA)) <= 16, "verification schema: the API rejects >16 union-typed params"
    for method in _PARAMS_BY_METHOD:
        assert len(_union_params(extraction_schema(method))) <= 16, f"extraction schema for {method}"
