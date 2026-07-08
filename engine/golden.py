"""Golden-test runner: worked examples transcribed from publications.

A golden case names an as-of date, an employee input record, and expected
withholding amounts. The runner selects the effective parameter files from a
data root, computes, and compares to the cent. CI running these publicly is
the repo's primary trust signal.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from engine.errors import DataError
from engine.inputs import EmployeeInput
from engine.loader import ParameterFile, load_parameter_dict, select_effective
from engine.money import CENT, D
from engine.pipeline import compute_withholding
from engine.taxability import TaxabilityMatrix

_WITHHOLDING_TAXES = (
    "federal_income_withholding",
    "state_income_withholding",
    "local_income_withholding",
)


@dataclass(frozen=True)
class GoldenCase:
    path: Path
    source: dict
    as_of: dt.date
    input_record: dict
    expect: dict


@dataclass(frozen=True)
class GoldenResult:
    expect_key: str
    jurisdiction: str
    expected: Decimal
    actual: Decimal

    @property
    def ok(self) -> bool:
        return self.expected.quantize(CENT) == self.actual.quantize(CENT)


def load_golden_case(path: str | Path) -> GoldenCase:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    for key in ("source", "as_of", "input", "expect"):
        if key not in raw:
            raise DataError(f"{path}: golden case missing {key!r}")
    as_of = raw["as_of"]
    if not isinstance(as_of, dt.date):
        as_of = dt.date.fromisoformat(str(as_of))
    return GoldenCase(
        path=path,
        source=raw["source"],
        as_of=as_of,
        input_record=raw["input"],
        expect=raw["expect"],
    )


def load_data_root(data_root: str | Path) -> list[ParameterFile]:
    """Load every withholding parameter file under a data root. Files for
    tax types the engine doesn't compute yet (SUI, SDI, limits) are skipped
    here; tools/validate_data.py still checks what it can."""
    files = []
    for path in sorted(Path(data_root).rglob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        if isinstance(raw, dict) and raw.get("tax") in _WITHHOLDING_TAXES:
            files.append(load_parameter_dict(raw, path=path))
    return files


def _expected_pairs(case: GoldenCase, employee: EmployeeInput, key: str, expected):
    """Map an expect key to (jurisdiction, tax, expected amount) triples."""
    if key == "federal_withholding":
        return [("US", "federal_income_withholding", expected)]
    if key in ("state_withholding", "local_withholding"):
        tax = f"{key.split('_')[0]}_income_withholding"
        if isinstance(expected, dict):
            return [(jur, tax, amount) for jur, amount in expected.items()]
        elections = employee.state if key == "state_withholding" else employee.locals
        if len(elections) != 1:
            raise DataError(
                f"{case.path}: scalar {key} needs exactly one election in the input; "
                f"use a jurisdiction-keyed mapping instead"
            )
        return [(elections[0].jurisdiction, tax, expected)]
    raise DataError(f"{case.path}: unknown expect key {key!r}")


def run_golden_case(
    case: GoldenCase,
    files: list[ParameterFile],
    taxability: TaxabilityMatrix,
) -> list[GoldenResult]:
    employee = EmployeeInput.from_dict(case.input_record)
    results = []
    for key, expected in case.expect.items():
        for jurisdiction, tax, amount in _expected_pairs(case, employee, key, expected):
            param_file = select_effective(files, case.as_of, jurisdiction=jurisdiction, tax=tax)
            actual = compute_withholding(param_file, employee, taxability)
            results.append(
                GoldenResult(
                    expect_key=key,
                    jurisdiction=jurisdiction,
                    expected=D(amount, context=f"{case.path}: expect.{key}"),
                    actual=actual,
                )
            )
    return results
