from pathlib import Path

import pytest

from engine.golden import load_data_root
from engine.taxability import TaxabilityMatrix

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def taxability():
    return TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")


@pytest.fixture(scope="session")
def fixture_params():
    return load_data_root(FIXTURES / "data")
