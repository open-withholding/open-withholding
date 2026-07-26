"""Open Withholding reference engine.

Pure functions from (parameter file, employee input) to per-paycheck
withholding amounts. /data and /schema are the product; this engine proves
the data is usable and anchors the golden tests.
"""

from engine.errors import EngineError, DataError, InputError
from engine.pipeline import compute_employer_tax, compute_withholding
from engine.loader import load_parameter_file, select_effective
from engine.inputs import EmployeeInput
from engine.taxability import TaxabilityMatrix

__all__ = [
    "EngineError",
    "DataError",
    "InputError",
    "compute_withholding",
    "compute_employer_tax",
    "load_parameter_file",
    "select_effective",
    "EmployeeInput",
    "TaxabilityMatrix",
]
