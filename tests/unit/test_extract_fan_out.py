"""End-to-end dry run of the flat-rate list fan-out (Ohio school districts)
through extract.run_flat_rate_fan_out with stubbed model output — the
ordering/gating class of bug that bit the county fan-out is caught here."""

import argparse
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pipeline import extract  # noqa: E402

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
