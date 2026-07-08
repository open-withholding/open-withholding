"""Employee input record: parsing and validation.

The engine is a pure function; everything time- or employer-dependent (YTD
wages, SUI experience rates) arrives here as input, never as state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from engine.errors import InputError
from engine.money import ZERO, D

PAY_PERIODS_PER_YEAR = {
    "daily": 260,
    "weekly": 52,
    "biweekly": 26,
    "semimonthly": 24,
    "monthly": 12,
    "quarterly": 4,
    "semiannually": 2,
    "annually": 1,
}

FEDERAL_FILING_STATUSES = ("single", "married_joint", "head_of_household")


def _money(raw: dict, key: str, default: str | None = "0", *, context: str) -> Decimal:
    value = raw.get(key, default)
    if value is None:
        raise InputError(f"{context}.{key} is required")
    amount = D(value, context=f"{context}.{key}")
    if amount < ZERO:
        raise InputError(f"{context}.{key} must be non-negative, got {amount}")
    return amount


@dataclass(frozen=True)
class PretaxDeduction:
    type: str
    amount: Decimal


@dataclass(frozen=True)
class FederalElection:
    w4_version: object  # 2020 or "pre_2020"
    filing_status: str
    step2_checkbox: bool = False
    step3_credits: Decimal = ZERO
    step4a_other_income: Decimal = ZERO
    step4b_deductions: Decimal = ZERO
    step4c_extra: Decimal = ZERO
    allowances: int = 0  # pre_2020 only

    @classmethod
    def from_dict(cls, raw: dict) -> "FederalElection":
        ctx = "federal"
        version = raw.get("w4_version")
        if version not in (2020, "pre_2020"):
            raise InputError(f"{ctx}.w4_version must be 2020 or 'pre_2020', got {version!r}")
        status = raw.get("filing_status")
        if status not in FEDERAL_FILING_STATUSES:
            raise InputError(
                f"{ctx}.filing_status {status!r} not one of {list(FEDERAL_FILING_STATUSES)}"
            )
        allowances = raw.get("allowances", 0)
        if not isinstance(allowances, int) or allowances < 0:
            raise InputError(f"{ctx}.allowances must be an integer >= 0, got {allowances!r}")
        return cls(
            w4_version=version,
            filing_status=status,
            step2_checkbox=bool(raw.get("step2_checkbox", False)),
            step3_credits=_money(raw, "step3_credits", context=ctx),
            step4a_other_income=_money(raw, "step4a_other_income", context=ctx),
            step4b_deductions=_money(raw, "step4b_deductions", context=ctx),
            step4c_extra=_money(raw, "step4c_extra", context=ctx),
            allowances=allowances,
        )


@dataclass(frozen=True)
class StateElection:
    jurisdiction: str
    filing_status: str | None = None
    allowances: int = 0
    secondary_allowances: int = 0  # second allowance kind (e.g. IL-W-4 Line 2)
    additional_withholding: Decimal = ZERO

    @classmethod
    def from_dict(cls, raw: dict) -> "StateElection":
        ctx = f"state[{raw.get('jurisdiction', '?')}]"
        jurisdiction = raw.get("jurisdiction")
        if not jurisdiction:
            raise InputError("state entries require a jurisdiction")
        counts = {}
        for key in ("allowances", "secondary_allowances"):
            value = raw.get(key, 0)
            if not isinstance(value, int) or value < 0:
                raise InputError(f"{ctx}.{key} must be an integer >= 0, got {value!r}")
            counts[key] = value
        return cls(
            jurisdiction=jurisdiction,
            filing_status=raw.get("filing_status"),
            allowances=counts["allowances"],
            secondary_allowances=counts["secondary_allowances"],
            additional_withholding=_money(raw, "additional_withholding", context=ctx),
        )


@dataclass(frozen=True)
class LocalElection:
    jurisdiction: str
    resident: bool = True


@dataclass(frozen=True)
class EmployeeInput:
    pay_frequency: str
    gross_wages: Decimal
    pretax_deductions: tuple[PretaxDeduction, ...] = ()
    federal: FederalElection | None = None
    state: tuple[StateElection, ...] = ()
    locals: tuple[LocalElection, ...] = ()
    ytd: dict[str, Decimal] = field(default_factory=dict)

    @property
    def pay_periods_per_year(self) -> int:
        return PAY_PERIODS_PER_YEAR[self.pay_frequency]

    @classmethod
    def from_dict(cls, raw: dict) -> "EmployeeInput":
        frequency = raw.get("pay_frequency")
        if frequency not in PAY_PERIODS_PER_YEAR:
            raise InputError(
                f"pay_frequency {frequency!r} not one of {sorted(PAY_PERIODS_PER_YEAR)}"
            )
        deductions = []
        for i, entry in enumerate(raw.get("pretax_deductions") or []):
            ctx = f"pretax_deductions[{i}]"
            dtype = entry.get("type")
            if not dtype:
                raise InputError(f"{ctx} requires a type")
            deductions.append(
                PretaxDeduction(type=dtype, amount=_money(entry, "amount", None, context=ctx))
            )
        federal = raw.get("federal")
        ytd = {
            key: D(value, context=f"ytd.{key}")
            for key, value in (raw.get("ytd") or {}).items()
        }
        return cls(
            pay_frequency=frequency,
            gross_wages=_money(raw, "gross_wages", None, context="input"),
            pretax_deductions=tuple(deductions),
            federal=FederalElection.from_dict(federal) if federal else None,
            state=tuple(StateElection.from_dict(s) for s in raw.get("state") or []),
            locals=tuple(
                LocalElection(jurisdiction=l["jurisdiction"], resident=l.get("resident", True))
                for l in raw.get("locals") or []
            ),
            ytd=ytd,
        )

    def state_election(self, jurisdiction: str) -> StateElection:
        for election in self.state:
            if election.jurisdiction == jurisdiction:
                return election
        raise InputError(f"input has no state election for {jurisdiction}")
