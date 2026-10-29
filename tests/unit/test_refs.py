"""Cross-file parameter references (engine/refs.py)."""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.errors import DataError, InputError  # noqa: E402
from engine.inputs import EmployeeInput  # noqa: E402
from engine.loader import load_parameter_dict  # noqa: E402
from engine.pipeline import compute_withholding  # noqa: E402
from engine.refs import find_refs, resolve_refs  # noqa: E402

SOURCE = {"document": "FIXTURE", "url": "https://example.gov/x", "retrieved": "2025-12-15", "sha256": "0" * 64}


def _fica(base, year=2026):
    return load_parameter_dict({
        "schema_version": "0.1", "jurisdiction": "US", "tax": "fica", "effective_from": f"{year}-01-01",
        "source": SOURCE, "method": "fica", "rounding": {"to": "0.01", "mode": "nearest"},
        "params": {"social_security": {"employee_rate": "0.062", "employer_rate": "0.062", "wage_base": base},
                   "medicare": {"employee_rate": "0.0145", "employer_rate": "0.0145",
                                "additional_employee_rate": "0.009", "additional_threshold": "200000"}}})


def _sdi_with_ref(year=2026):
    return load_parameter_dict({
        "schema_version": "0.1", "jurisdiction": "US-ZZ", "tax": "state_disability_insurance",
        "effective_from": f"{year}-01-01", "source": SOURCE, "method": "sdi",
        "rounding": {"to": "0.01", "mode": "nearest"},
        "params": {"wage_definition": "fica", "components": [
            {"name": "pfml", "rate": "0.0100", "employee_share": "0.50",
             "wage_base": {"ref": "federal.social_security_wage_base"}}]}})


def test_find_refs_reports_paths():
    assert find_refs(_sdi_with_ref().params) == [("params.components[0].wage_base", "federal.social_security_wage_base")]
    assert find_refs(_fica("100000").params) == []


def test_resolve_substitutes_the_referenced_value_and_leaves_others_alone():
    sdi, fica = _sdi_with_ref(), _fica("100000")
    resolved = resolve_refs([sdi, fica])
    assert resolved[0].params["components"][0]["wage_base"] == "100000"
    assert resolved[1] is fica
    assert sdi.params["components"][0]["wage_base"] == {"ref": "federal.social_security_wage_base"}  # original untouched


def test_resolve_picks_the_file_in_effect_on_the_referencing_date():
    resolved = resolve_refs([_sdi_with_ref(2027), _fica("100000", 2026), _fica("110000", 2027)])
    assert resolved[0].params["components"][0]["wage_base"] == "110000"


def test_missing_target_fails_loud():
    with pytest.raises(DataError, match="cannot resolve 'federal.social_security_wage_base'"):
        resolve_refs([_sdi_with_ref()])


def test_unknown_reference_name_is_rejected_by_the_schema():
    with pytest.raises(DataError, match="schema validation failed"):
        load_parameter_dict({**_sdi_with_ref().__dict__} if False else {
            "schema_version": "0.1", "jurisdiction": "US-ZZ", "tax": "state_disability_insurance",
            "effective_from": "2026-01-01", "source": SOURCE, "method": "sdi",
            "rounding": {"to": "0.01", "mode": "nearest"},
            "params": {"wage_definition": "fica", "components": [
                {"name": "x", "rate": "0.01", "employee_share": "1", "wage_base": {"ref": "made.up"}}]}})


def test_unresolved_reference_never_acts_as_no_cap(taxability):
    emp = EmployeeInput.from_dict({"pay_frequency": "biweekly", "gross_wages": "2000.00"})
    with pytest.raises(InputError, match="unresolved cross-file reference"):
        compute_withholding(_sdi_with_ref(), emp, taxability)


def test_resolved_reference_caps_like_a_printed_base(taxability):
    sdi = resolve_refs([_sdi_with_ref(), _fica("100000")])[0]
    emp = EmployeeInput.from_dict({"pay_frequency": "biweekly", "gross_wages": "2000.00", "ytd": {"sdi_wages": "99000"}})
    assert compute_withholding(sdi, emp, taxability) == Decimal("5.00")
