"""Registry-backed locals: expand a centrally-published register (CSV) into
one ParameterFile per row (DESIGN §3.6).

Pennsylvania's Act 32 register lists ~2,600 political subdivisions. Keeping
one YAML per PSD would bury the dataset; instead the DCED register is kept
as `act32.csv` beside a `kind: registry` sidecar YAML that carries the
shared envelope (provenance, method, rounding) and the CSV's hash. Loading
the sidecar yields ParameterFiles indistinguishable from hand-written local
files, so the pipeline, goldens and consumers see `US-PA-PSD-<code>` like
any other jurisdiction.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import jsonschema

from engine.errors import DataError
from engine.loader import REPO_ROOT, ParameterFile, load_parameter_dict

REGISTRY_SCHEMA_PATH = REPO_ROOT / "schema" / "registry.schema.json"


@functools.lru_cache(maxsize=None)
def _registry_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(REGISTRY_SCHEMA_PATH.read_text())
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def is_registry(raw: object) -> bool:
    return isinstance(raw, dict) and raw.get("kind") == "registry"


def validate_sidecar(raw: dict, *, where: str) -> None:
    normalized = json.loads(json.dumps(raw, default=str))
    errors = sorted(_registry_validator().iter_errors(normalized), key=lambda e: e.json_path)
    if errors:
        details = "; ".join(f"{e.json_path}: {e.message}" for e in errors[:5])
        raise DataError(f"{where}: registry sidecar failed schema validation: {details}")


def read_rows(csv_path: Path, *, expected_sha256: str, where: str) -> list[dict]:
    data = csv_path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise DataError(
            f"{where}: {csv_path.name} sha256 {actual[:12]}... does not match the sidecar's "
            f"{expected_sha256[:12]}... — the CSV was edited by hand; registers are only "
            f"ever rewritten by the importer"
        )
    rows = list(csv.DictReader(data.decode("utf-8").splitlines()))
    if not rows:
        raise DataError(f"{where}: {csv_path.name} has no data rows")
    return rows


def expand_rows(raw: dict, rows: list[dict], *, path: Path | None) -> list[ParameterFile]:
    """One ParameterFile per row with a nonzero rate. Validation goes through
    load_parameter_dict row by row so an expansion is held to exactly the
    schema a hand-written file would be."""
    where = str(path) if path else "<registry>"
    exp = raw["expansion"]
    key, template = exp["key"], exp["jurisdiction"]
    resident_col, nonresident_col = exp["params"]["resident_rate"], exp["params"]["nonresident_rate"]
    for col in (key, resident_col, nonresident_col):
        if col not in rows[0]:
            raise DataError(f"{where}: CSV lacks column {col!r} named by the sidecar; has {sorted(rows[0])}")
    source = dict(raw["source"])
    base_notes = source.get("notes", "").rstrip()
    out: list[ParameterFile] = []
    seen: set[str] = set()
    for row in rows:
        code = row[key]
        if code in seen:
            raise DataError(f"{where}: duplicate {key} {code!r} in {exp['file']}")
        seen.add(code)
        resident, nonresident = row[resident_col], row[nonresident_col]
        if Decimal(resident) == 0 and Decimal(nonresident) == 0:
            continue
        jurisdiction = template.replace("{" + key + "}", code)
        detail = "; ".join(
            f"{k}={v}" for k, v in row.items()
            if v and k not in (key, resident_col, nonresident_col) and not k.endswith("_effective")
        )
        file_raw = {
            "schema_version": raw["schema_version"],
            "jurisdiction": jurisdiction,
            "tax": raw["tax"],
            "effective_from": str(raw["effective_from"]),
            "effective_to": None if raw.get("effective_to") is None else str(raw["effective_to"]),
            "source": {**source, "notes": (base_notes + f"; register row {key}={code}: {detail}").lstrip("; ")},
            "method": raw["method"],
            "rounding": dict(raw.get("rounding") or {"to": "0.01", "mode": "nearest"}),
            "params": {"resident_rate": resident, "nonresident_rate": nonresident},
        }
        out.append(load_parameter_dict(file_raw, path=path))
    if len(out) != exp["expanded_rows"]:
        raise DataError(
            f"{where}: sidecar says expanded_rows={exp['expanded_rows']} but {len(out)} rows "
            f"carry a nonzero rate"
        )
    if len(rows) != exp["rows"]:
        raise DataError(f"{where}: sidecar says rows={exp['rows']} but the CSV has {len(rows)}")
    return out


def load_registry(raw: dict, *, path: Path) -> list[ParameterFile]:
    """Validate a `kind: registry` sidecar and expand its CSV."""
    where = str(path)
    validate_sidecar(raw, where=where)
    csv_path = path.parent / raw["expansion"]["file"]
    if not csv_path.exists():
        raise DataError(f"{where}: register file {csv_path.name} is missing")
    rows = read_rows(csv_path, expected_sha256=raw["expansion"]["sha256"], where=where)
    return expand_rows(raw, rows, path=path)
