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


@pytest.fixture(scope="session")
def real_params():
    """The repo's /data loaded ONCE per session. Loading per golden case
    cost ~0.8 s x 485 cases (15-minute CI runs after Ohio's 214 files)."""
    return load_data_root(REPO_ROOT / "data")
