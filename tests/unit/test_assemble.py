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
        "exemption_counts": [{"kind": "personal", "count": 5},
                             {"kind": "dependent", "count": 3}],
        "additional_withholding": None,
        "expected_withholding": "13.96",
    }
    g = assemble.assemble_golden_case(
        jurisdiction="US-IN", tax="state_income_withholding",
        example=example, as_of="2026-06-15", document="DN #1")
    assert g["input"]["state"][0]["exemptions"] == {"personal": 5, "dependent": 3}


def test_rate_schedule_transform_roundtrip():
    # Extraction shape -> assemble -> loader -> engine matches the printed
    # 2.25% weekly schedule (hand-derived: $3,000 single -> $209.38).
    from engine.pipeline import compute_withholding
    from engine.inputs import EmployeeInput
    from engine.taxability import TaxabilityMatrix
    from decimal import Decimal
    from pathlib import Path

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "exemption_per_period": [{"frequency": "weekly", "amount": "61.54"}],
            "standard_deduction_per_period": [{"frequency": "weekly", "amount": "65.38"}],
            "no_withholding_floor": [{"frequency": "weekly", "amount": "96.00"}],
            "status_groups": [
                {"group": "a", "statuses": ["married_joint", "head_of_household"]},
                {"group": "b", "statuses": ["single", "married_filing_separately", "dependent"]},
            ],
            "schedules": [{
                "schedule": "0.0225",
                "frequencies": [{
                    "frequency": "weekly",
                    "groups": [
                        {"group": "a", "brackets": [
                            {"over": "0", "rate": "0.0700", "base": "0"},
                            {"over": "2885", "rate": "0.0725", "base": "201.92"},
                        ]},
                        {"group": "b", "brackets": [
                            {"over": "0", "rate": "0.0700", "base": "0"},
                            {"over": "1923", "rate": "0.0725", "base": "134.62"},
                            {"over": "2404", "rate": "0.0750", "base": "169.47"},
                            {"over": "2885", "rate": "0.0775", "base": "205.53"},
                        ]},
                    ],
                }],
            }],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-MD", tax="state_income_withholding",
        method="rate_schedule_percentage", extraction=extraction, source=SOURCE)
    pf = load_parameter_dict(raw)
    assert "0.0225.weekly.b" in pf.bracket_tables
    emp = EmployeeInput.from_dict({
        "pay_frequency": "weekly", "gross_wages": "3000.00",
        "state": [{"jurisdiction": "US-MD", "filing_status": "single",
                   "rate_schedule": "0.0225"}],
    })
    taxability = TaxabilityMatrix.from_file(
        Path(__file__).resolve().parent.parent.parent / "taxability" / "us.yaml")
    assert compute_withholding(pf, emp, taxability) == Decimal("209.38")


def test_golden_case_carries_rate_schedule():
    example = {
        "page": 13, "description": "constructed",
        "pay_frequency": "weekly", "gross_wages": "3000.00",
        "filing_status": "single", "allowances": 0,
        "rate_schedule": "0.0225",
        "additional_withholding": None,
        "expected_withholding": "209.38",
    }
    g = assemble.assemble_golden_case(
        jurisdiction="US-MD", tax="state_income_withholding",
        example=example, as_of="2026-06-15", document="MD guide")
    assert g["input"]["state"][0]["rate_schedule"] == "0.0225"


def test_ca_transform_roundtrip():
    # Extraction shape -> assemble -> loader -> engine reproduces Example B
    # (biweekly $1,600 married, 2 regular + 1 estimated -> $2.38).
    from engine.pipeline import compute_withholding
    from engine.inputs import EmployeeInput
    from engine.taxability import TaxabilityMatrix
    from decimal import Decimal
    from pathlib import Path

    cols = {"single": "727", "married_allowances_0_1": "727",
            "married_allowances_2_plus": "1454", "head_of_household": "1454"}
    sd = {"single": "219", "married_allowances_0_1": "219",
          "married_allowances_2_plus": "439", "head_of_household": "439"}
    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "low_income_exemption": [{"frequency": "biweekly", **cols}],
            "estimated_deduction": [{"frequency": "biweekly",
                                     "amounts": ["38", "77", "115"]}],
            "standard_deduction": [{"frequency": "biweekly", **sd}],
            "exemption_allowance": [{"frequency": "biweekly",
                                     "amounts": ["6.47", "12.95", "19.42"]}],
            "brackets": [{
                "frequency": "biweekly",
                "statuses": [{"filing_status": "Married", "rows": [
                    {"over": "0", "rate": "0.011", "base": "0"},
                    {"over": "852", "rate": "0.022", "base": "9.37"},
                ]}],
            }],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-CA", tax="state_income_withholding",
        method="custom/us_ca", extraction=extraction, source=SOURCE)
    assert raw["method"] == "custom"
    assert raw["custom_implementation"] == "custom/us_ca"
    pf = load_parameter_dict(raw)
    assert "biweekly.married" in pf.bracket_tables
    emp = EmployeeInput.from_dict({
        "pay_frequency": "biweekly", "gross_wages": "1600.00",
        "state": [{"jurisdiction": "US-CA", "filing_status": "married",
                   "allowances": 2, "secondary_allowances": 1}],
    })
    taxability = TaxabilityMatrix.from_file(
        Path(__file__).resolve().parent.parent.parent / "taxability" / "us.yaml")
    assert compute_withholding(pf, emp, taxability) == Decimal("2.38")


# --- maintainer adjudications (registry print-defect corrections) ---

MD_MONTHLY_A = [  # the 2.75% monthly (a) table as printed (defective rate in row 4)
    {"over": "0", "rate": "0.0750", "base": "0"},
    {"over": "12500", "rate": "0.0775", "base": "937.50"},
    {"over": "14583", "rate": "0.0800", "base": "1098.96"},
    {"over": "18750", "rate": "0.0825", "base": "1432.29"},
    {"over": "25000", "rate": "0.0825", "base": "1947.92"},
    {"over": "50000", "rate": "0.0900", "base": "4072.92"},
    {"over": "100000", "rate": "0.0925", "base": "8572.92"},
]

ADJ_RATE = {
    "path": ["schedules", "0.0275", "monthly", "a", 4, "rate"],
    "printed": "0.0825",
    "corrected": "0.0850",
    "justification": "next printed base chains only with 8.50%",
}


def _md_params():
    import copy
    return {"schedules": {"0.0275": {"monthly": {"a": copy.deepcopy(MD_MONTHLY_A)}}}}


def test_adjudication_applies_when_transcription_matches_printed():
    params = _md_params()
    results = assemble.apply_adjudications(params, [ADJ_RATE])
    assert results[0]["status"] == "applied"
    assert params["schedules"]["0.0275"]["monthly"]["a"][4]["rate"] == "0.0850"


def test_adjudication_noops_when_transcription_already_correct():
    params = _md_params()
    params["schedules"]["0.0275"]["monthly"]["a"][4]["rate"] = "0.0850"
    results = assemble.apply_adjudications(params, [ADJ_RATE])
    assert results[0]["status"] == "already_correct"
    assert params["schedules"]["0.0275"]["monthly"]["a"][4]["rate"] == "0.0850"


def test_adjudication_fails_loud_on_unexpected_transcription():
    params = _md_params()
    params["schedules"]["0.0275"]["monthly"]["a"][4]["rate"] = "0.0875"
    with pytest.raises(ValueError, match="matches neither"):
        assemble.apply_adjudications(params, [ADJ_RATE])


def test_adjudication_fails_loud_on_missing_path():
    with pytest.raises(ValueError, match="not found"):
        assemble.apply_adjudications(
            _md_params(),
            [{**ADJ_RATE, "path": ["schedules", "0.0330", "monthly", "a", 4, "rate"]}],
        )


def test_adjudicated_table_passes_bracket_validation_and_printed_fails():
    # The whole point: the printed table trips the cumulative-base check,
    # the adjudicated table passes it.
    from engine.brackets import parse_table
    from engine.errors import DataError

    with pytest.raises(DataError, match="recomputed cumulative"):
        parse_table(MD_MONTHLY_A, context="printed")
    params = _md_params()
    assemble.apply_adjudications(params, [ADJ_RATE])
    parse_table(params["schedules"]["0.0275"]["monthly"]["a"], context="adjudicated")


def test_pr_body_renders_adjudications():
    body = assemble.build_pr_body(
        source_id="us-md-withholding-guide",
        jurisdiction="US-MD",
        tax="state_income_withholding",
        method="rate_schedule_percentage",
        source=SOURCE,
        extraction={"classification": "new_year_edition",
                    "effective_from": "2026-01-01", "citations": [], "notes": ""},
        verification={"checks": [], "worked_examples": []},
        golden_paths=[],
        golden_ok=True,
        prev_path=None,
        adjudications=[
            {**ADJ_RATE, "status": "applied"},
            {"path": ["schedules", "0.0240", "monthly", "b", 6, "over"],
             "printed": "83833", "corrected": "83333",
             "justification": "of-excess-over column prints 83,333",
             "status": "already_correct"},
        ],
    )
    assert "Maintainer adjudications (print defects)" in body
    assert "`schedules.0.0275.monthly.a.4.rate`: `0.0825` → `0.0850`" in body
    assert "already `83333` in transcription (printed `83833`)" in body
    assert "Verified each maintainer adjudication's justification" in body


def test_pr_body_omits_adjudication_section_when_none():
    body = assemble.build_pr_body(
        source_id="s", jurisdiction="US-MD", tax="state_income_withholding",
        method="rate_schedule_percentage", source=SOURCE,
        extraction={"classification": "new_year_edition",
                    "effective_from": "2026-01-01", "citations": [], "notes": ""},
        verification={"checks": [], "worked_examples": []},
        golden_paths=[], golden_ok=True, prev_path=None,
    )
    assert "adjudication" not in body.lower()


def test_ny_transform_roundtrip():
    # Extraction shape -> assemble -> loader -> engine reproduces the p.16
    # Example 1 (weekly $400 single, 3 exemptions -> $8.01).
    from engine.pipeline import compute_withholding
    from engine.inputs import EmployeeInput
    from engine.taxability import TaxabilityMatrix

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "deduction": [{"frequency": "weekly", "single": "142.30", "married": "152.90"}],
            "exemption_value": [{"frequency": "weekly", "amount": "19.25"}],
            "brackets": [
                {
                    "frequency": "weekly",
                    "statuses": [{"filing_status": "Single", "rows": [
                        {"over": "0", "rate": "0.0390", "base": "0"},
                        {"over": "163", "rate": "0.0440", "base": "6.38"},
                        {"over": "225", "rate": "0.0515", "base": "9.08"},
                    ]}],
                },
                {
                    "frequency": "annually",
                    "statuses": [{"filing_status": "Single", "rows": [
                        {"over": "0", "rate": "0.0390", "base": "0"},
                        {"over": "8500", "rate": "0.0440", "base": "332.00"},
                        {"over": "11700", "rate": "0.0515", "base": "472.00"},
                    ]}],
                },
            ],
            "method_iii_cutover": [{"frequency": "weekly", "single": "20722", "married": "41449"}],
            "method_iii": [
                {"filing_status": "Single", "bands": [{"over": "1077550", "rate": "0.1045"}]},
                {"filing_status": "Married", "bands": [{"over": "2155350", "rate": "0.1045"}]},
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-NY", tax="state_income_withholding",
        method="custom/us_ny", extraction=extraction, source=SOURCE)
    assert raw["custom_implementation"] == "custom/us_ny"
    pf = load_parameter_dict(raw)
    assert "weekly.single" in pf.bracket_tables
    assert pf.params["method_iii"]["single"][0]["rate"] == "0.1045"
    emp = EmployeeInput.from_dict({
        "pay_frequency": "weekly", "gross_wages": "400.00",
        "state": [{"jurisdiction": "US-NY", "filing_status": "single", "allowances": 3}],
    })
    taxability = TaxabilityMatrix.from_file(
        Path(__file__).resolve().parent.parent.parent / "taxability" / "us.yaml")
    from decimal import Decimal as _D
    assert compute_withholding(pf, emp, taxability) == _D("8.01")


def test_fica_paths_and_slug():
    assert assemble.data_path("US", 2026, "fica") == PurePosixPath(
        "data/us/federal/2026/fica.yaml")
    assert assemble.golden_slug("US", "fica") == "us-federal-fica"
    # Default tax keeps the historical behavior
    assert assemble.data_path("US", 2026) == PurePosixPath(
        "data/us/federal/2026/withholding.yaml")
    assert assemble.golden_slug("US") == "us-federal"


def test_fica_transform_roundtrip():
    # Extraction shape -> assemble -> loader -> engine computes a period.
    from engine.pipeline import compute_withholding
    from engine.inputs import EmployeeInput
    from engine.taxability import TaxabilityMatrix
    from decimal import Decimal as _D

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "social_security": {"employee_rate": "0.062", "employer_rate": "0.062",
                                "wage_base": "150000"},
            "medicare": {"employee_rate": "0.0145", "employer_rate": "0.0145",
                         "additional_employee_rate": "0.009",
                         "additional_threshold": "200000"},
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US", tax="fica", method="fica",
        extraction=extraction, source=SOURCE)
    pf = load_parameter_dict(raw)
    emp = EmployeeInput.from_dict({"pay_frequency": "biweekly", "gross_wages": "2000.00"})
    taxability = TaxabilityMatrix.from_file(
        Path(__file__).resolve().parent.parent.parent / "taxability" / "us.yaml")
    assert compute_withholding(pf, emp, taxability) == _D("153.00")


def test_fica_golden_case_expect_key():
    example = {
        "description": "maintainer-constructed", "page": 1,
        "pay_frequency": "biweekly", "gross_wages": "2000.00",
        "filing_status": None, "allowances": None,
        "additional_withholding": None,
        "expected_withholding": "153.00",
    }
    g = assemble.assemble_golden_case(
        jurisdiction="US", tax="fica", example=example,
        as_of="2026-06-15", document="Pub 15 (2026)")
    assert g["expect"] == {"fica_withholding": "153.00"}
    assert "state" not in g["input"] and "federal" not in g["input"]
