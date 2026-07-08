"""The deduction-type × wage-base taxability matrix.

Small but high-stakes: it decides which pre-tax deductions reduce which wage
bases in which jurisdictions. Unknown deduction types are a hard error —
silently treating an unknown 125-plan type as fully taxable (or not) is
exactly the kind of quiet wrongness this project exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from engine.errors import DataError
from engine.inputs import PretaxDeduction
from engine.money import ZERO

# Wage-base keys a deduction entry may declare directly.
_DIRECT_BASES = ("federal_income", "fica", "futa")
_VERDICTS = ("reduces", "does_not_reduce")


def _state_of(jurisdiction: str) -> str:
    """US-PA-PSD-700102 -> US-PA. Locals follow their state's income-tax
    treatment until a local override scheme proves necessary."""
    parts = jurisdiction.split("-")
    if len(parts) < 2:
        raise DataError(f"jurisdiction {jurisdiction!r} has no state component")
    return "-".join(parts[:2])


@dataclass(frozen=True)
class TaxabilityMatrix:
    deduction_types: dict

    @classmethod
    def from_file(cls, path: str | Path) -> "TaxabilityMatrix":
        raw = yaml.safe_load(Path(path).read_text())
        types = raw.get("deduction_types")
        if not isinstance(types, dict) or not types:
            raise DataError(f"{path}: taxability file has no deduction_types mapping")
        for name, entry in types.items():
            for base in (*_DIRECT_BASES, "state_income_default"):
                verdict = entry.get(base)
                if verdict not in _VERDICTS:
                    raise DataError(
                        f"{path}: deduction_types.{name}.{base} must be one of "
                        f"{list(_VERDICTS)}, got {verdict!r}"
                    )
            for state, verdict in (entry.get("state_overrides") or {}).items():
                if verdict not in _VERDICTS:
                    raise DataError(
                        f"{path}: deduction_types.{name}.state_overrides.{state} "
                        f"must be one of {list(_VERDICTS)}, got {verdict!r}"
                    )
        return cls(deduction_types=types)

    def reduces(self, deduction_type: str, wage_base: str, jurisdiction: str) -> bool:
        """Does `deduction_type` reduce `wage_base` (federal_income | fica |
        futa | state_income) in `jurisdiction`?"""
        entry = self.deduction_types.get(deduction_type)
        if entry is None:
            raise DataError(
                f"unknown pretax deduction type {deduction_type!r}; "
                f"known types: {sorted(self.deduction_types)}"
            )
        if wage_base in _DIRECT_BASES:
            return entry[wage_base] == "reduces"
        if wage_base == "state_income":
            overrides = entry.get("state_overrides") or {}
            state = _state_of(jurisdiction)
            verdict = overrides.get(state, entry["state_income_default"])
            return verdict == "reduces"
        raise DataError(f"unknown wage base {wage_base!r}")

    def taxable_wages(
        self,
        gross_wages: Decimal,
        deductions: tuple[PretaxDeduction, ...],
        wage_base: str,
        jurisdiction: str,
    ) -> Decimal:
        """Gross minus every deduction that reduces this wage base here,
        clamped at zero."""
        taxable = gross_wages
        for deduction in deductions:
            if self.reduces(deduction.type, wage_base, jurisdiction):
                taxable -= deduction.amount
        return taxable if taxable > ZERO else ZERO
