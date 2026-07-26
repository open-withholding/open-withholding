import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

from check_data_golden import missing_golden  # noqa: E402

CO_FILE = {
    "jurisdiction": "US-CO",
    "tax": "state_income_withholding",
    "effective_from": "2026-01-01",
}
SUI_FILE = {
    "jurisdiction": "US-CO",
    "tax": "state_unemployment_insurance",
    "effective_from": "2026-01-01",
}


def _reader(mapping):
    return lambda path: mapping.get(path)


def test_data_change_without_golden_fails():
    changed = ["data/us/co/2026/withholding.yaml"]
    errors = missing_golden(changed, _reader({changed[0]: CO_FILE}))
    assert len(errors) == 1 and "us-co-2026" in errors[0]


def test_data_change_with_golden_passes():
    changed = ["data/us/co/2026/withholding.yaml", "tests/golden/us-co-2026-1.yaml"]
    assert missing_golden(changed, _reader({changed[0]: CO_FILE})) == []


def test_wrong_jurisdiction_golden_does_not_count():
    changed = ["data/us/co/2026/withholding.yaml", "tests/golden/us-zz-2026-1.yaml"]
    assert len(missing_golden(changed, _reader({changed[0]: CO_FILE}))) == 1


def test_sui_files_now_guarded_and_deleted_files_exempt():
    # SUI became a computable tax (methods/sui.md): its data files require
    # goldens like everything else. Deleted files remain exempt.
    changed = ["data/us/co/2026/sui.yaml", "data/us/co/2025/withholding.yaml"]
    reader = _reader({"data/us/co/2026/sui.yaml": SUI_FILE})  # 2025 file deleted -> None
    errors = missing_golden(changed, reader)
    assert len(errors) == 1 and "us-co-sui-2026-" in errors[0]
    # With a matching golden in the changeset, the guard is satisfied.
    changed.append("tests/golden/us-co-sui-2026-1.yaml")
    assert missing_golden(changed, reader) == []


def test_federal_slug():
    changed = ["data/us/federal/2026/withholding.yaml", "tests/golden/us-federal-2026-1.yaml"]
    us = {"jurisdiction": "US", "tax": "federal_income_withholding", "effective_from": "2026-01-01"}
    assert missing_golden(changed, _reader({changed[0]: us})) == []
