#!/usr/bin/env python3
"""Validate every data artifact in the repo. CI runs this before the tests.

Checks: withholding parameter files against schema + loader invariants
(provenance, bracket monotonicity, precomputed bases), the taxability
matrix, and that golden case files parse. Tax types without a schema yet
(SUI, SDI, limits) are reported, not silently skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from engine.errors import EngineError  # noqa: E402
from engine.golden import load_golden_case  # noqa: E402
from engine.loader import load_parameter_dict  # noqa: E402
from engine.taxability import TaxabilityMatrix  # noqa: E402

WITHHOLDING_TAXES = (
    "federal_income_withholding",
    "state_income_withholding",
    "local_income_withholding",
    "fica",
)


def main() -> int:
    errors: list[str] = []
    notes: list[str] = []
    checked = 0

    data_root = REPO_ROOT / "data"
    for path in sorted(data_root.rglob("*.yaml")):
        rel = path.relative_to(REPO_ROOT)
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: YAML parse error: {exc}")
            continue
        if not isinstance(raw, dict):
            errors.append(f"{rel}: not a mapping")
            continue
        tax = raw.get("tax")
        if tax in WITHHOLDING_TAXES:
            try:
                load_parameter_dict(raw, path=path)
                checked += 1
            except EngineError as exc:
                errors.append(str(exc))
        elif tax is None:
            errors.append(f"{rel}: missing `tax` field")
        else:
            notes.append(f"{rel}: tax={tax} has no schema yet — NOT validated")

    try:
        TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")
        checked += 1
    except EngineError as exc:
        errors.append(str(exc))

    for path in sorted((REPO_ROOT / "tests" / "golden").glob("*.yaml")):
        try:
            load_golden_case(path)
            checked += 1
        except EngineError as exc:
            errors.append(str(exc))

    for note in notes:
        print(f"NOTE  {note}")
    for error in errors:
        print(f"ERROR {error}")
    print(f"{checked} artifact(s) validated, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
