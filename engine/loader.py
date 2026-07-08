"""Load and validate parameter files.

Validation is layered: JSON Schema for shape, then checks the schema cannot
express (bracket monotonicity, precomputed `base` sums, effective-date
sanity). A file that fails any layer never reaches a calculation.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import yaml

from engine.brackets import BracketRow, parse_table
from engine.errors import DataError
from engine.money import Rounding

REPO_ROOT = Path(__file__).resolve().parent.parent
WITHHOLDING_SCHEMA_PATH = REPO_ROOT / "schema" / "withholding.schema.json"


@functools.lru_cache(maxsize=None)
def _withholding_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(WITHHOLDING_SCHEMA_PATH.read_text())
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )


def _parse_date(value: object, *, context: str) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise DataError(f"{context}: {value!r} is not an ISO date") from exc


@dataclass(frozen=True)
class ParameterFile:
    path: Path | None
    jurisdiction: str
    tax: str
    effective_from: dt.date
    effective_to: dt.date | None
    method: str
    custom_implementation: str | None
    params: dict
    rounding: Rounding
    source: dict
    bracket_tables: dict[str, tuple[BracketRow, ...]]  # flattened "status" / "standard.status" keys

    def in_effect(self, as_of: dt.date) -> bool:
        if as_of < self.effective_from:
            return False
        return self.effective_to is None or as_of <= self.effective_to


def _validate_and_parse_brackets(method: str, params: dict) -> dict[str, tuple[BracketRow, ...]]:
    tables: dict[str, tuple[BracketRow, ...]] = {}
    if method in ("annualized_percentage", "annualized_percentage_with_credits"):
        for status, rows in params.get("brackets", {}).items():
            tables[status] = parse_table(rows, context=f"params.brackets.{status}")
    elif method == "federal_percentage_2020":
        for variant, per_status in params.get("brackets", {}).items():
            for status, rows in per_status.items():
                tables[f"{variant}.{status}"] = parse_table(
                    rows, context=f"params.brackets.{variant}.{status}"
                )
    return tables


def load_parameter_dict(raw: dict, *, path: Path | None = None) -> ParameterFile:
    """Validate an already-parsed mapping. Split out from load_parameter_file
    so tests and the extraction pipeline can validate candidates in memory."""
    where = str(path) if path else "<memory>"
    # YAML parses bare dates as datetime.date; the JSON Schema validator
    # expects strings. Normalize before validation.
    normalized = json.loads(json.dumps(raw, default=str))
    errors = sorted(_withholding_validator().iter_errors(normalized), key=lambda e: e.json_path)
    if errors:
        details = "; ".join(f"{e.json_path}: {e.message}" for e in errors[:5])
        raise DataError(f"{where}: schema validation failed: {details}")

    effective_from = _parse_date(raw["effective_from"], context=f"{where}: effective_from")
    effective_to = raw.get("effective_to")
    if effective_to is not None:
        effective_to = _parse_date(effective_to, context=f"{where}: effective_to")
        if effective_to < effective_from:
            raise DataError(f"{where}: effective_to precedes effective_from")

    method = raw["method"]
    params = raw["params"]
    return ParameterFile(
        path=path,
        jurisdiction=raw["jurisdiction"],
        tax=raw["tax"],
        effective_from=effective_from,
        effective_to=effective_to,
        method=method,
        custom_implementation=raw.get("custom_implementation"),
        params=params,
        rounding=Rounding.from_dict(raw.get("rounding")),
        source=raw["source"],
        bracket_tables=_validate_and_parse_brackets(method, params),
    )


def load_parameter_file(path: str | Path) -> ParameterFile:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise DataError(f"{path}: not a mapping")
    return load_parameter_dict(raw, path=path)


def select_effective(
    files: list[ParameterFile], as_of: dt.date, *, jurisdiction: str, tax: str
) -> ParameterFile:
    """Pick the parameter file in effect on `as_of` for one jurisdiction+tax.
    Ties (retroactive corrections) resolve to the latest effective_from."""
    candidates = [
        f
        for f in files
        if f.jurisdiction == jurisdiction and f.tax == tax and f.in_effect(as_of)
    ]
    if not candidates:
        raise DataError(
            f"no parameter file for {jurisdiction}/{tax} in effect on {as_of.isoformat()}"
        )
    return max(candidates, key=lambda f: f.effective_from)
