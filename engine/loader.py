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
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import jsonschema
import yaml

from engine.brackets import BASE_TOLERANCE, BracketRow, parse_table
from engine.errors import DataError
from engine.inputs import PAY_PERIODS_PER_YEAR
from engine.money import D, Rounding

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
    source: dict  # single source block, or {"sources": [...]} for multi-document files
    bracket_tables: dict[str, tuple[BracketRow, ...]]  # flattened "status" / "standard.status" keys

    def in_effect(self, as_of: dt.date) -> bool:
        if as_of < self.effective_from:
            return False
        return self.effective_to is None or as_of <= self.effective_to


def _validate_and_parse_brackets(method: str, params: dict) -> dict[str, tuple[BracketRow, ...]]:
    tables: dict[str, tuple[BracketRow, ...]] = {}
    if method in (
        "annualized_percentage",
        "annualized_percentage_phaseout",
        "annualized_percentage_with_credits",
    ):
        for status, rows in params.get("brackets", {}).items():
            tables[status] = parse_table(rows, context=f"params.brackets.{status}")
    elif method == "rate_schedule_percentage":
        # Three-level tables: rate schedule -> frequency -> status group.
        for sched, per_freq in params.get("schedules", {}).items():
            for freq, per_group in per_freq.items():
                for group, rows in per_group.items():
                    tables[f"{sched}.{freq}.{group}"] = parse_table(
                        rows, context=f"params.schedules.{sched}.{freq}.{group}"
                    )
    elif method in ("federal_percentage_2020", "per_period_percentage", "custom/us_ca",
                    "custom/us_ny"):
        # Two-level tables: variant/frequency -> filing status -> rows.
        for outer, per_status in params.get("brackets", {}).items():
            # NY's Annual Tax Rate Schedule bases are statute-derived
            # cumulative amounts that intentionally do not chain with the
            # smoothed withholding rates (drift up to ~$4.30); the real
            # transcription check for this method is the cross-frequency
            # corroboration below.
            tol = (
                Decimal("10.00")
                if method == "custom/us_ny" and outer == "annually"
                else BASE_TOLERANCE
            )
            for status, rows in per_status.items():
                tables[f"{outer}.{status}"] = parse_table(
                    rows, context=f"params.brackets.{outer}.{status}",
                    base_tolerance=tol,
                )
    if method == "custom/us_ny":
        _crosscheck_us_ny_brackets(params)
    return tables


def _crosscheck_us_ny_brackets(params: dict) -> None:
    """NY per-period tables are the Annual Tax Rate Schedule divided by pay
    periods: every base must equal round(annual base / periods) to the cent
    and every rate must match row-for-row. Six independent transcriptions
    corroborating each other is a stronger transcription check than
    cumulative chaining, which NY's annual bases legitimately fail."""
    brackets = params.get("brackets", {})
    annual = brackets.get("annually")
    if not annual:
        raise DataError(
            "custom/us_ny: params.brackets must include the 'annually' schedule "
            "(the Annual Tax Rate Schedule anchors the cross-frequency check)"
        )
    cent = Decimal("0.01")
    for freq, per_status in brackets.items():
        if freq == "annually":
            continue
        periods = PAY_PERIODS_PER_YEAR[freq]
        for status, rows in per_status.items():
            where = f"params.brackets.{freq}.{status}"
            arows = annual.get(status)
            if arows is None:
                raise DataError(f"{where}: no matching status in the annual schedule")
            if len(arows) != len(rows):
                raise DataError(
                    f"{where}: {len(rows)} rows but the annual schedule has "
                    f"{len(arows)} — tables must correspond row-for-row"
                )
            for i, (row, arow) in enumerate(zip(rows, arows)):
                if D(row["rate"], context=f"{where}[{i}].rate") != D(
                    arow["rate"], context=f"annually.{status}[{i}].rate"
                ):
                    raise DataError(
                        f"{where}[{i}]: rate {row['rate']} differs from the annual "
                        f"schedule's {arow['rate']} in the same position"
                    )
                if row.get("base") is None or arow.get("base") is None:
                    continue
                expected = (
                    D(arow["base"], context=f"annually.{status}[{i}].base") / periods
                ).quantize(cent, rounding=ROUND_HALF_UP)
                declared = D(row["base"], context=f"{where}[{i}].base")
                if abs(declared - expected) > cent:
                    raise DataError(
                        f"{where}[{i}]: base {declared} is not the annual schedule's "
                        f"{arow['base']} / {periods} = {expected}; transcription error"
                    )


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
        source=raw["source"] if "source" in raw else {"sources": raw["sources"]},
        bracket_tables=_validate_and_parse_brackets(
            raw.get("custom_implementation") or method, params
        ),
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
