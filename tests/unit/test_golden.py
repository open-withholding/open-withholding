"""Run the golden corpus: fixture cases against fixture data, and (once real
data lands) /tests/golden cases against /data."""

from pathlib import Path

import pytest

from engine.golden import load_data_root, load_golden_case, run_golden_case

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_CASES = sorted((REPO_ROOT / "tests" / "fixtures" / "golden").glob("*.yaml"))
REAL_CASES = sorted((REPO_ROOT / "tests" / "golden").glob("*.yaml"))


@pytest.mark.parametrize("path", FIXTURE_CASES, ids=lambda p: p.stem)
def test_fixture_golden_case(path, fixture_params, taxability):
    case = load_golden_case(path)
    results = run_golden_case(case, fixture_params, taxability)
    assert results, f"{path}: no expectations ran"
    for result in results:
        assert result.ok, (
            f"{path}: {result.expect_key} for {result.jurisdiction}: "
            f"expected {result.expected}, engine produced {result.actual}"
        )


@pytest.mark.parametrize("path", REAL_CASES, ids=lambda p: p.stem)
def test_real_golden_case(path, taxability):
    files = load_data_root(REPO_ROOT / "data")
    case = load_golden_case(path)
    results = run_golden_case(case, files, taxability)
    assert results, f"{path}: no expectations ran"
    for result in results:
        assert result.ok, (
            f"{path}: {result.expect_key} for {result.jurisdiction}: "
            f"expected {result.expected}, engine produced {result.actual}"
        )


def test_fixture_corpus_is_nonempty():
    assert FIXTURE_CASES, "the illustrative golden corpus vanished"
