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
from engine.registry import is_registry, load_registry  # noqa: E402
from engine.taxability import TaxabilityMatrix  # noqa: E402

WITHHOLDING_TAXES = (
    "federal_income_withholding",
    "state_income_withholding",
    "local_income_withholding",
    "fica",
    "futa",
    "state_unemployment_insurance",
    "state_disability_insurance",
    "state_unemployment_insurance_employee",
)


def main() -> int:
    errors: list[str] = []
    notes: list[str] = []
    checked = 0

    data_root = REPO_ROOT / "data"
    loaded_files = []
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
        if is_registry(raw):
            # Registry sidecar + CSV (PA Act 32): validate the sidecar, the
            # CSV hash, and every expanded row as a parameter file.
            try:
                expanded = load_registry(raw, path=path)
                loaded_files.extend(expanded)
                checked += 1
                notes.append(f"{rel}: registry expanded to {len(expanded)} local parameter file(s)")
            except EngineError as exc:
                errors.append(str(exc))
        elif tax in WITHHOLDING_TAXES:
            try:
                loaded_files.append(load_parameter_dict(raw, path=path))
                checked += 1
            except EngineError as exc:
                errors.append(str(exc))
        elif tax is None:
            errors.append(f"{rel}: missing `tax` field")
        else:
            notes.append(f"{rel}: tax={tax} has no schema yet — NOT validated")

    # Cross-file references must resolve against the set (engine/refs.py):
    # a dangling {ref: ...} is a release blocker, never a silent "no cap".
    try:
        from engine.refs import find_refs, resolve_refs
        resolve_refs(loaded_files)
        n_refs = sum(len(find_refs(f.params)) for f in loaded_files)
        if n_refs:
            notes.append(f"{n_refs} cross-file reference(s) resolved")
    except EngineError as exc:
        errors.append(str(exc))

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
