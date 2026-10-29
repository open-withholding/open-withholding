"""Cross-file parameter references (DESIGN §3.1).

Some statutes define a parameter by pointing at ANOTHER jurisdiction's
parameter — Massachusetts, Washington and Colorado cap paid-leave premiums
at "the Social Security wage base" without ever printing the figure. A data
file records exactly that: `wage_base: {ref: federal.social_security_wage_base}`.
The reference stays in the file (a reader sees what the law says) and is
resolved against the referenced file for the same effective date when the
data root is loaded as a set. Resolution fails loud when the target file is
missing, and an unresolved reference reaching a method fails loud too, so a
reference can never silently act as "no cap".

References are the exception to "every file stands alone": they are allowed
only where the law itself cross-references, never to avoid transcribing a
printed shared table (the Indiana county fan-out duplicates those on purpose).
"""

from __future__ import annotations

import copy
import dataclasses
from typing import Any

from engine.errors import DataError
from engine.loader import ParameterFile, select_effective

# name -> (jurisdiction, tax, path into that file's params)
REF_TARGETS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "federal.social_security_wage_base": ("US", "fica", ("social_security", "wage_base")),
}


def is_ref(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"ref"}


def find_refs(obj: Any, _path: str = "params") -> list[tuple[str, str]]:
    """[(json-ish path, ref name)] for every reference inside params."""
    found: list[tuple[str, str]] = []
    if is_ref(obj):
        return [(_path, obj["ref"])]
    if isinstance(obj, dict):
        for k, v in obj.items():
            found += find_refs(v, f"{_path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += find_refs(v, f"{_path}[{i}]")
    return found


def _lookup(target: ParameterFile, path: tuple[str, ...], where: str) -> Any:
    node: Any = target.params
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise DataError(f"{where}: referenced file {target.path} has no params.{'.'.join(path)}")
        node = node[key]
    return node


def _substitute(obj: Any, resolver) -> Any:
    if is_ref(obj):
        return resolver(obj["ref"])
    if isinstance(obj, dict):
        return {k: _substitute(v, resolver) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(v, resolver) for v in obj]
    return obj


def resolve_refs(files: list[ParameterFile]) -> list[ParameterFile]:
    """Return the files with every `{ref: name}` replaced by the referenced
    value, looked up in the file in effect on the referencing file's
    effective_from. Files without references are returned unchanged."""
    out = []
    for f in files:
        refs = find_refs(f.params)
        if not refs:
            out.append(f)
            continue
        where = str(f.path) if f.path else f"<{f.jurisdiction}/{f.tax}>"

        def resolver(name: str, _f=f, _where=where):
            if name not in REF_TARGETS:
                raise DataError(f"{_where}: unknown parameter reference {name!r}; "
                                f"known: {sorted(REF_TARGETS)}")
            jurisdiction, tax, path = REF_TARGETS[name]
            try:
                target = select_effective(files, _f.effective_from, jurisdiction=jurisdiction, tax=tax)
            except DataError as exc:
                raise DataError(f"{_where}: cannot resolve {name!r}: {exc}") from exc
            return _lookup(target, path, _where)

        out.append(dataclasses.replace(f, params=_substitute(copy.deepcopy(f.params), resolver)))
    return out
