"""External parity rows (tests/parity/expected.csv) must agree with the
engine within a cent. Skips when nothing has been entered yet."""

import csv
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools import parity  # noqa: E402

EXPECTED = parity.load_expected() if parity.EXPECTED_CSV.exists() else {}
SCENARIOS = parity.load_scenarios() if EXPECTED else {}


@pytest.mark.parametrize("sid", sorted(EXPECTED) or [pytest.param("none", marks=pytest.mark.skip(reason="no parity rows entered"))])
def test_external_parity_row(sid, taxability, real_params):
    scenario = SCENARIOS[sid]
    ours = parity.compute(real_params, taxability, scenario["jurisdiction"], scenario["tax"], scenario["input"], scenario["as_of"])
    assert abs(ours - Decimal(EXPECTED[sid]["expected"])) <= parity.TOLERANCE, (
        f"{sid}: engine {ours} vs {EXPECTED[sid].get('source') or 'external'} {EXPECTED[sid]['expected']} — {scenario['describe']}")
