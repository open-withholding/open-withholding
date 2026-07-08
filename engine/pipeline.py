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
        federal = None
    else:  # local
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
    )
    method = resolve(param_file.method, param_file.custom_implementation)
    amount = method(ctx)
    if amount < ZERO:
        raise EngineError(
            f"method {param_file.method!r} produced negative withholding {amount}; "
            f"method implementations must clamp"
        )
    return amount
