"""The generic pipeline: taxability -> method dispatch -> withholding.

`compute_withholding` is the engine's entry point. It is a pure function of
(parameter file, employee input, taxability matrix); selection of the right
parameter file for an as-of date happens upstream via `loader.select_effective`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.brackets import BracketRow
from engine.errors import EngineError, InputError
from engine.inputs import EmployeeInput, FederalElection
from engine.loader import ParameterFile
from engine.methods import resolve
from engine.money import ZERO, Rounding
from engine.taxability import TaxabilityMatrix

_WAGE_BASE_BY_TAX = {
    "federal_income_withholding": "federal_income",
    "state_income_withholding": "state_income",
    "local_income_withholding": "state_income",  # locals follow their state's treatment
    "fica": "fica",
}


@dataclass(frozen=True)
class MethodContext:
    """Everything a method implementation may read. Methods are pure
    functions MethodContext -> Decimal (the period withholding)."""

    taxable_wages: Decimal  # this period, after pre-tax deductions
    pay_periods: int
    params: dict
    rounding: Rounding
    bracket_tables: dict[str, tuple[BracketRow, ...]]
    filing_status: str | None
    allowances: int
    secondary_allowances: int
    additional_withholding: Decimal
    federal: FederalElection | None
    elected_rate: Decimal | None = None
    elected_annual_amount: Decimal | None = None
    period_federal_income_withholding: Decimal | None = None
    period_fica_withholding: Decimal | None = None
    ytd: dict = None
    exemptions: dict = None  # named counts (IN WH-4 lines 5-8)
    rate_schedule: str | None = None  # employer-selected printed schedule (MD)
    # Employer-side taxes (futa, sui) — from the input's employer block.
    sui_jurisdiction: str | None = None
    sui_experience_rate: Decimal | None = None


def compute_withholding(
    param_file: ParameterFile,
    employee: EmployeeInput,
    taxability: TaxabilityMatrix,
) -> Decimal:
    wage_base = _WAGE_BASE_BY_TAX.get(param_file.tax)
    if wage_base is None:
        raise EngineError(f"tax type {param_file.tax!r} is not computable by this engine version")

    taxable = taxability.taxable_wages(
        employee.gross_wages,
        employee.pretax_deductions,
        wage_base,
        param_file.jurisdiction,
    )

    secondary = 0
    elected_rate = None
    elected_amount = None
    exemptions = {}
    rate_schedule = None
    if param_file.tax == "federal_income_withholding":
        if employee.federal is None:
            raise InputError("federal withholding requested but input has no federal block")
        filing_status = employee.federal.filing_status
        allowances = employee.federal.allowances
        additional = ZERO  # federal extra withholding is step4c, applied by the method
        federal = employee.federal
    elif param_file.tax == "state_income_withholding":
        election = employee.state_election(param_file.jurisdiction)
        filing_status = election.filing_status
        allowances = election.allowances
        secondary = election.secondary_allowances
        additional = election.additional_withholding
        elected_rate = election.elected_rate
        elected_amount = election.elected_annual_amount
        exemptions = election.exemptions
        rate_schedule = election.rate_schedule
        federal = None
    else:  # local, fica: no elections apply
        filing_status = None
        allowances = 0
        additional = ZERO
        federal = None

    ctx = MethodContext(
        taxable_wages=taxable,
        pay_periods=employee.pay_periods_per_year,
        params=param_file.params,
        rounding=param_file.rounding,
        bracket_tables=param_file.bracket_tables,
        filing_status=filing_status,
        allowances=allowances,
        secondary_allowances=secondary,
        additional_withholding=additional,
        federal=federal,
        elected_rate=elected_rate,
        elected_annual_amount=elected_amount,
        exemptions=exemptions,
        rate_schedule=rate_schedule,
        period_federal_income_withholding=employee.period_federal_income_withholding,
        period_fica_withholding=employee.period_fica_withholding,
        ytd=employee.ytd,
    )
    method = resolve(param_file.method, param_file.custom_implementation)
    amount = method(ctx)
    if amount < ZERO:
        raise EngineError(
            f"method {param_file.method!r} produced negative withholding {amount}; "
            f"method implementations must clamp"
        )
    return amount


_EMPLOYER_TAXES = ("futa", "state_unemployment_insurance")


def compute_employer_tax(
    param_file: ParameterFile,
    employee: EmployeeInput,
    taxability: TaxabilityMatrix,
) -> Decimal:
    """Employer-side liability (FUTA, SUI) for one pay period. Same pure
    shape as compute_withholding, but the amount is owed BY the employer —
    it never reduces the employee's pay. v1 computes taxable wages through
    the matrix's `futa` column for both (see methods/sui.md notes)."""
    if param_file.tax not in _EMPLOYER_TAXES:
        raise EngineError(
            f"tax type {param_file.tax!r} is not an employer tax; "
            f"use compute_withholding for withholding taxes"
        )
    taxable = taxability.taxable_wages(
        employee.gross_wages, employee.pretax_deductions, "futa", param_file.jurisdiction
    )
    employer = employee.employer
    if param_file.tax == "state_unemployment_insurance":
        if employer is None or employer.sui_jurisdiction is None:
            raise InputError(
                "sui: input requires an employer block with sui_jurisdiction "
                "and sui_experience_rate (from the state rate notice)"
            )
        if employer.sui_jurisdiction != param_file.jurisdiction:
            raise InputError(
                f"sui: employer.sui_jurisdiction {employer.sui_jurisdiction!r} does "
                f"not match the parameter file's {param_file.jurisdiction!r} — "
                "the entered rate belongs to a different state's notice"
            )
    ctx = MethodContext(
        taxable_wages=taxable,
        pay_periods=employee.pay_periods_per_year,
        params=param_file.params,
        rounding=param_file.rounding,
        bracket_tables=param_file.bracket_tables,
        filing_status=None,
        allowances=0,
        secondary_allowances=0,
        additional_withholding=ZERO,
        federal=None,
        ytd=employee.ytd,
        sui_jurisdiction=employer.sui_jurisdiction if employer else None,
        sui_experience_rate=employer.sui_experience_rate if employer else None,
    )
    method = resolve(param_file.method, param_file.custom_implementation)
    amount = method(ctx)
    if amount < ZERO:
        raise EngineError(
            f"method {param_file.method!r} produced negative employer tax {amount}"
        )
    return amount
