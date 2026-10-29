"""End-to-end dry run of the flat-rate list fan-out (Ohio school districts)
through extract.run_flat_rate_fan_out with stubbed model output — the
ordering/gating class of bug that bit the county fan-out is caught here."""

import argparse
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.loader import load_parameter_dict  # noqa: E402
from pipeline import assemble, extract  # noqa: E402

SOURCE = {
    "id": "us-oh-school-districts", "jurisdiction": "US-OH",
    "tax": "local_income_withholding", "method": "flat_rate",
    "fan_out": "flat_rate_list", "fan_out_id_prefix": "SD",
    "document": "School Districts With an Income Tax",
}
SOURCE_BLOCK = {
    "document": "School Districts With an Income Tax (2026)",
    "url": "https://example.gov/School_Districts_2026.pdf",
    "retrieved": "2026-10-28", "sha256": "ab" * 32,
}
EXTRACTION = {
    "classification": "new_year_edition", "effective_from": "2026-01-01",
    "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none", "intermediate_to": None},
    "params": {"districts": [
        {"code": "0505", "name": "Trimble LSD", "counties": "Athens, Morgan", "tax_base": "earned_income", "rate": "0.0100"},
        {"code": "1505", "name": "East Palestine CSD", "counties": "Columbiana", "tax_base": "earned_income", "rate": "0.0000"},
        {"code": "3301", "name": "Ada EVSD", "counties": "Hardin, Hancock", "tax_base": "traditional", "rate": "0.0150"},
    ]},
    "citations": [{"what": "district list", "page": 2}], "notes": "",
}


def _args(tmp_path, **over):
    base = dict(source_id="us-oh-school-districts", year=2026, dry_run=True, no_examples_ok=True)
    base.update(over)
    return argparse.Namespace(**base)


def _verification(confirmed=True, examples=()):
    return {"all_values_confirmed": confirmed,
            "checks": [{"path": "params.districts[0].rate", "candidate_value": "0.0100",
                        "page": 2, "confirmed": confirmed, "note": None}],
            "worked_examples": list(examples)}


def test_fan_out_dry_run_writes_files_and_pins(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path)
    rc = extract.run_flat_rate_fan_out(_args(tmp_path), SOURCE, EXTRACTION, _verification(), dict(SOURCE_BLOCK))
    assert rc == 0
    root = tmp_path / "us-oh-school-districts-2026"
    data = sorted(p.name for p in (root / "data/us/oh/2026/locals").glob("*.yaml"))
    assert data == ["sd-0505.yaml", "sd-3301.yaml"]           # the expired district has no file
    goldens = sorted(p.name for p in (root / "tests/golden").glob("*.yaml"))
    assert goldens == ["us-oh-sd-0505-2026-1.yaml", "us-oh-sd-3301-2026-1.yaml"]
    pin = yaml.safe_load((root / "tests/golden/us-oh-sd-3301-2026-1.yaml").read_text())
    assert pin["expect"] == {"local_withholding": "15.00"}       # 1,000 x 1.5%
    assert pin["input"]["locals"] == [{"jurisdiction": "US-OH-SD-3301", "resident": True}]
    assert "maintainer-approved (no_examples_ok at dispatch)" in pin["source"]["example"]
    body = (tmp_path / "us-oh-school-districts-2026-pr.md").read_text()
    assert "2 files" in body and "1 zero-rate (expired) rows produce no file" in body
    assert "| 0505 | Trimble LSD | Athens, Morgan | earned_income | 0.0100 |" in body


def test_fan_out_without_examples_needs_the_dispatch_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path)
    rc = extract.run_flat_rate_fan_out(_args(tmp_path, no_examples_ok=False), SOURCE, EXTRACTION,
                                       _verification(), dict(SOURCE_BLOCK))
    assert rc == 1
    assert "--no-examples-ok was not given" in (tmp_path / "us-oh-school-districts-2026-triage.md").read_text()


def test_fan_out_printed_example_is_assigned_by_arithmetic(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path)
    example = {"description": "weekly $800, 1.5% district", "page": 1, "pay_frequency": "weekly",
               "gross_wages": "800.00", "filing_status": None, "allowances": None,
               "exemption_counts": None, "additional_withholding": None, "resident": None,
               "expected_withholding": "12.00"}
    rc = extract.run_flat_rate_fan_out(_args(tmp_path, no_examples_ok=False), SOURCE, EXTRACTION,
                                       _verification(examples=[example]), dict(SOURCE_BLOCK))
    assert rc == 0
    root = tmp_path / "us-oh-school-districts-2026"
    g = yaml.safe_load((root / "tests/golden/us-oh-sd-3301-2026-1.yaml").read_text())
    assert "assigned by arithmetic" in g["source"]["example"] and g["expect"] == {"local_withholding": "12.00"}


def test_fan_out_unconfirmed_value_fails_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path)
    rc = extract.run_flat_rate_fan_out(_args(tmp_path), SOURCE, EXTRACTION, _verification(confirmed=False), dict(SOURCE_BLOCK))
    assert rc == 1
    assert not (tmp_path / "us-oh-school-districts-2026").exists()


def test_fan_out_duplicate_codes_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path)
    dup = {**EXTRACTION, "params": {"districts": EXTRACTION["params"]["districts"] + [
        {"code": "0505", "name": "Trimble LSD", "counties": None, "tax_base": "earned_income", "rate": "0.0100"}]}}
    rc = extract.run_flat_rate_fan_out(_args(tmp_path), SOURCE, dup, _verification(), dict(SOURCE_BLOCK))
    assert rc == 1
    assert "duplicate district codes" in (tmp_path / "us-oh-school-districts-2026-triage.md").read_text()



# --- flat-rate list fan-out (Ohio school districts)

def test_flat_rate_fan_out_files_are_self_contained_and_skip_zero_rates():
    extraction = {
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none",
                     "intermediate_to": None},
        "params": {"districts": [
            {"code": "0505", "name": "Trimble LSD", "counties": "Athens, Morgan",
             "tax_base": "earned_income", "rate": "0.0100"},
            {"code": "1505", "name": "East Palestine CSD", "counties": "Columbiana",
             "tax_base": "earned_income", "rate": "0.0000"},   # expired -> no file
            {"code": "3301", "name": "Ada EVSD", "counties": "Hardin, Hancock",
             "tax_base": "traditional", "rate": "0.0150"},
        ]},
    }
    pairs = assemble.assemble_flat_rate_fan_out(
        state="US-OH", tax="local_income_withholding", method="flat_rate",
        extraction=extraction, source=SOURCE_BLOCK, id_prefix="SD")
    assert [j for j, _ in pairs] == ["US-OH-SD-0505", "US-OH-SD-3301"]
    for j, raw in pairs:
        load_parameter_dict(raw)  # every file stands alone
        assert str(assemble.data_path(j, 2026, "local_income_withholding")).startswith("data/us/oh/2026/locals/sd-")
    trimble = dict(pairs)["US-OH-SD-0505"]
    assert trimble["params"] == {"rate": "0.0100"}
    assert "SD 0505 Trimble LSD (Athens, Morgan), earned income tax base" in trimble["source"]["notes"]
    assert "intermediate_to" not in trimble["rounding"]


def test_mechanical_validation_resolves_cross_file_references():
    """A candidate with wage_base: {ref: federal.social_security_wage_base}
    must validate its goldens against the resolved federal base (DE's first
    reference run died with 'unresolved cross-file reference' here)."""
    from engine.taxability import TaxabilityMatrix
    from pipeline.extract import REPO_ROOT, run_mechanical_validation
    param_dict = {
        "schema_version": "0.1", "jurisdiction": "US-ZZ", "tax": "state_disability_insurance",
        "effective_from": "2026-01-01",
        "source": {"document": "FIXTURE", "url": "https://example.gov/x", "retrieved": "2026-01-01", "sha256": "0" * 64},
        "method": "sdi", "rounding": {"to": "0.01", "mode": "nearest"},
        "params": {"wage_definition": "fica", "components": [
            {"name": "x", "rate": "0.0100", "employee_share": "0.50",
             "wage_base": {"ref": "federal.social_security_wage_base"}}]},
    }
    # Past the real 2026 federal base (184,500) nothing is subject -> 0.00
    golden = {"source": {"document": "FIXTURE", "page": 1, "example": "past the cap"}, "as_of": "2026-06-15",
              "input": {"pay_frequency": "biweekly", "gross_wages": "2000.00", "ytd": {"sdi_wages": "184500"}},
              "expect": {"sdi_withholding": {"US-ZZ": "0.00"}}}
    taxability = TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")
    run_mechanical_validation(param_dict, [golden], taxability)  # raises on failure
