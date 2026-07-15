"""The assemble layer is what turns model output into repo artifacts — it
must produce files the loader accepts and golden cases the runner accepts."""

import datetime as dt
from decimal import Decimal
from pathlib import Path, PurePosixPath

import pytest

from engine.golden import GoldenCase, run_golden_case
from engine.loader import load_parameter_dict
from pipeline import assemble

SOURCE = {
    "document": "FIXTURE doc (2026)",
    "url": "https://example.gov/x.pdf",
    "retrieved": "2026-07-07",
    "sha256": "0" * 64,
}


def test_data_path_and_slug():
    assert assemble.data_path("US", 2026) == PurePosixPath("data/us/federal/2026/withholding.yaml")
    assert assemble.data_path("US-CO", 2026) == PurePosixPath("data/us/co/2026/withholding.yaml")
    assert assemble.data_path("US-PA-PSD-700102", 2026) == PurePosixPath(
        "data/us/pa/2026/locals/psd-700102.yaml"
    )
    assert assemble.golden_slug("US") == "us-federal"
    assert assemble.golden_slug("US-PA-PSD-700102") == "us-pa-psd-700102"


def test_flat_rate_with_allowance_transform_loads():
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "rate": "0.0440",
            "allowances": [
                {"filing_status": "single", "amount": "4500"},
                {"filing_status": "married", "amount": "9000"},
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-CO",
        tax="state_income_withholding",
        method="flat_rate_with_annual_allowance",
        extraction=extraction,
        source=SOURCE,
    )
    pf = load_parameter_dict(raw)  # full schema + loader validation
    assert pf.params["filing_status"]["married"]["annual_allowance"] == "9000"


def test_federal_transform_none_bases_dropped():
    rows = [
        {"over": "0", "rate": "0.00", "base": None},
        {"over": "5000", "rate": "0.10", "base": "0"},
    ]
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "wage_adjustment": [{"filing_status": "single", "amount": "8600"}],
            "brackets_standard": [{"filing_status": "single", "rows": rows}],
            "brackets_step2_checkbox": [{"filing_status": "single", "rows": rows}],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US",
        tax="federal_income_withholding",
        method="federal_percentage_2020",
        extraction=extraction,
        source=SOURCE,
    )
    first_row = raw["params"]["brackets"]["standard"]["single"][0]
    assert "base" not in first_row  # null base omitted, declared base kept
    assert raw["params"]["brackets"]["standard"]["single"][1]["base"] == "0"
    load_parameter_dict(raw)


def test_bad_extraction_is_rejected_by_loader():
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "standard_deduction": None,
            "allowance_amount": None,
            "credit_per_allowance": None,
            "brackets": [
                {
                    "filing_status": "single",
                    "rows": [
                        {"over": "0", "rate": "0.01", "base": None},
                        {"over": "1000", "rate": "0.02", "base": "99"},  # wrong base
                    ],
                }
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ",
        tax="state_income_withholding",
        method="annualized_percentage",
        extraction=extraction,
        source=SOURCE,
    )
    with pytest.raises(Exception, match="recomputed cumulative"):
        load_parameter_dict(raw)


def _example(**overrides):
    base = {
        "page": 7,
        "description": "Example 1",
        "pay_frequency": "biweekly",
        "gross_wages": "2400.00",
        "filing_status": "single",
        "allowances": 1,
        "step2_checkbox": None,
        "step3_credits": None,
        "step4a_other_income": None,
        "step4b_deductions": None,
        "step4c_extra": None,
        "additional_withholding": None,
        "expected_withholding": "97.98",
    }
    return {**base, **overrides}


def test_state_golden_case_runs_against_candidate(taxability):
    # CO-shaped candidate; the DESIGN §3.2 numbers give 97.98 for this input.
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "rate": "0.0440",
            "allowances": [{"filing_status": "single", "amount": "4500"}],
        },
    }
    pf = load_parameter_dict(
        assemble.assemble_parameter_file(
            jurisdiction="US-CO",
            tax="state_income_withholding",
            method="flat_rate_with_annual_allowance",
            extraction=extraction,
            source=SOURCE,
        )
    )
    golden = assemble.assemble_golden_case(
        jurisdiction="US-CO",
        tax="state_income_withholding",
        example=_example(allowances=0),
        as_of=assemble.default_as_of("2026-01-01"),
        document=SOURCE["document"],
    )
    case = GoldenCase(
        path=Path("<candidate>"),
        source=golden["source"],
        as_of=dt.date.fromisoformat(golden["as_of"]),
        input_record=golden["input"],
        expect=golden["expect"],
    )
    results = run_golden_case(case, [pf], taxability)
    assert results and all(r.ok for r in results)
    assert results[0].actual == Decimal("97.98")


def test_federal_golden_case_shape():
    golden = assemble.assemble_golden_case(
        jurisdiction="US",
        tax="federal_income_withholding",
        example=_example(
            filing_status="married_joint", step2_checkbox=False, step3_credits="2000"
        ),
        as_of="2026-06-15",
        document=SOURCE["document"],
    )
    federal = golden["input"]["federal"]
    assert federal["w4_version"] == 2020
    assert federal["step3_credits"] == "2000"
    assert federal["step4a_other_income"] == "0"  # nulls default to "0"
    assert golden["expect"] == {"federal_withholding": "97.98"}


def test_default_as_of():
    assert assemble.default_as_of("2026-01-01") == "2026-06-15"
    # mid-year revision: as_of must fall inside the new file's window
    assert assemble.default_as_of("2026-07-01") == "2026-07-01"


def test_prose_filing_status_labels_normalized_to_snake_case():
    # MO's extractor returned the guide's prose labels (PR #8); the backstop
    # normalizes params keys and golden inputs identically.
    from pipeline.assemble import snake

    assert snake("Married and Spouse Works") == "married_spouse_works"  # connectors dropped
    assert snake("Head of Household") == "head_of_household"  # "of" kept
    assert snake("Married Filing Jointly or Qualifying Surviving Spouse") == "married_joint"
    assert snake("married_joint") == "married_joint"  # idempotent

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "1.00", "mode": "nearest", "intermediate": "none"},
        "params": {
            "rate": "0.0440",
            "allowances": [{"filing_status": "Married and Spouse Works", "amount": "9000"}],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ",
        tax="state_income_withholding",
        method="flat_rate_with_annual_allowance",
        extraction=extraction,
        source=SOURCE,
    )
    assert list(raw["params"]["filing_status"]) == ["married_spouse_works"]

    golden = assemble.assemble_golden_case(
        jurisdiction="US-ZZ",
        tax="state_income_withholding",
        example=_example(filing_status="Married and Spouse Works"),
        as_of="2026-06-15",
        document="doc",
    )
    assert golden["input"]["state"][0]["filing_status"] == "married_spouse_works"


def test_multi_source_provenance_roundtrip():
    # v0.2: a sources list validates and assembles in place of source
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {"rate": "0.0100"},
    }
    sources = {"sources": [
        {"document": "tables", "url": "https://example.gov/a.pdf",
         "retrieved": "2026-07-12", "sha256": "0" * 64},
        {"document": "formula page", "url": "https://example.gov/guide",
         "retrieved": "2026-07-12", "sha256": "1" * 64},
    ]}
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ", tax="state_income_withholding",
        method="flat_rate", extraction=extraction, source=sources)
    assert "source" not in raw and len(raw["sources"]) == 2
    load_parameter_dict(raw)  # schema accepts the list form


def test_single_source_still_required():
    import pytest as _p
    from engine.errors import DataError
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {"rate": "0.0100"},
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ", tax="state_income_withholding",
        method="flat_rate", extraction=extraction, source=SOURCE)
    both = dict(raw)
    both["sources"] = [dict(SOURCE, document="dup")]
    with _p.raises(DataError, match="schema validation"):
        load_parameter_dict(both)  # source AND sources is rejected
    neither = {k: v for k, v in raw.items() if k != "source"}
    with _p.raises(DataError, match="schema validation"):
        load_parameter_dict(neither)  # provenance still mandatory


def test_build_pr_body_multi_source_lists_every_document():
    body = assemble.build_pr_body(
        source_id="us-zz-multi",
        jurisdiction="US-ZZ",
        tax="state_income_withholding",
        method="flat_rate",
        source={"sources": [
            {"document": "Guide (HTML)", "url": "https://x.gov/guide",
             "retrieved": "2026-07-12", "sha256": "0" * 64},
            {"document": "Tables", "url": "https://x.gov/tables.pdf",
             "retrieved": "2026-07-12", "sha256": "1" * 64},
        ]},
        extraction={"classification": "new_year_edition",
                    "effective_from": "2026-01-01", "citations": []},
        verification={"checks": [], "worked_examples": []},
        golden_paths=[],
        golden_ok=True,
        prev_path=None,
    )
    assert "[Guide (HTML)](https://x.gov/guide)" in body
    assert "[Tables](https://x.gov/tables.pdf)" in body
    assert body.count("Archived sha256") == 2


def test_deduction_constant_transform_roundtrip():
    # Extraction shape -> assemble -> loader -> engine reproduces DN #1's
    # printed example ($800 weekly, 5/3/1/2 exemptions -> $13.96).
    from engine.pipeline import compute_withholding
    from engine.inputs import EmployeeInput
    from engine.taxability import TaxabilityMatrix
    from pathlib import Path

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "rate": "0.0295",
            "exemption_kinds": [
                {"kind": "Personal", "annual_amount": "1000"},
                {"kind": "dependent", "annual_amount": "1500"},
                {"kind": "first_time_dependent", "annual_amount": "1500"},
                {"kind": "adopted", "annual_amount": "3000"},
            ],
            "periods_per_year": [
                {"frequency": "daily", "divisor": 365},
                {"frequency": "weekly", "divisor": 52},
                {"frequency": "biweekly", "divisor": 26},
                {"frequency": "semimonthly", "divisor": 24},
                {"frequency": "monthly", "divisor": 12},
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-IN", tax="state_income_withholding",
        method="deduction_constant_percentage", extraction=extraction, source=SOURCE)
    assert raw["params"]["exemptions"]["personal"] == "1000"  # snake'd
    assert raw["params"]["periods_per_year"]["daily"] == "365"
    pf = load_parameter_dict(raw)
    emp = EmployeeInput.from_dict({
        "pay_frequency": "weekly", "gross_wages": "800.00",
        "state": [{"jurisdiction": "US-IN",
                   "exemptions": {"personal": 5, "dependent": 3,
                                  "first_time_dependent": 1, "adopted": 2}}],
    })
    taxability = TaxabilityMatrix.from_file(
        Path(__file__).resolve().parent.parent.parent / "taxability" / "us.yaml")
    from decimal import Decimal
    assert compute_withholding(pf, emp, taxability) == Decimal("13.96")


def test_golden_case_carries_exemption_counts():
    example = {
        "page": 3, "description": "DN1 example",
        "pay_frequency": "weekly", "gross_wages": "800.00",
        "filing_status": "all", "allowances": None,
        "exemption_counts": {"personal": 5, "dependent": 3},
        "additional_withholding": None,
        "expected_withholding": "13.96",
    }
    g = assemble.assemble_golden_case(
        jurisdiction="US-IN", tax="state_income_withholding",
        example=example, as_of="2026-06-15", document="DN #1")
    assert g["input"]["state"][0]["exemptions"] == {"personal": 5, "dependent": 3}
