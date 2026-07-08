class EngineError(Exception):
    """Base class for all engine failures. The engine fails loud: a wrong
    withholding amount is worse than no answer."""


class DataError(EngineError):
    """A parameter or taxability file is malformed, inconsistent, or fails
    validation beyond what JSON Schema expresses (bracket order, base sums)."""


class InputError(EngineError):
    """The employee input record is invalid or incomplete for the requested
    calculation."""
