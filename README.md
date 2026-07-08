<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/logo-horizontal-dark.svg">
    <img src="branding/logo-horizontal.svg" alt="open withholding" width="480">
  </picture>
</p>

An open, citation-backed, machine-readable dataset of US payroll tax
parameters (federal, state, and centrally-published locals), plus a
reference engine that turns those parameters into per-paycheck withholding
amounts, plus automation that keeps the dataset current.

**The product is trust.** Every number in this repo must be traceable to a
government publication (URL + retrieval date + document hash), and every
calculation method must reproduce the worked examples printed in those
publications. A stranger should be able to audit any value in under a
minute. See [DESIGN.md](DESIGN.md) for the full design.

## Status: pre-alpha scaffold

The schemas, method specs, reference engine, golden-test harness, and CI are
in place. **`/data` is intentionally empty** — real tax parameters enter
only through the update pipeline (DESIGN.md §8) with source citations and
publication-transcribed golden tests. Everything numeric currently in the
repo (test fixtures, examples) is illustrative and fake.

## Layout

| Path | What it is |
|---|---|
| `/schema` | JSON Schema for every file type in `/data` |
| `/methods` | One normative spec per calculation method |
| `/data` | The product: parameter files with mandatory provenance (empty until the pipeline lands) |
| `/taxability` | Deduction-type × wage-base matrix + state overrides (draft, uncited) |
| `/engine` | Reference implementation (Python, pure functions, Decimal-only) |
| `/tests/golden` | Worked examples transcribed from publications |
| `/pipeline` | Watcher → extractor → PR automation (design stage) |

Rule of thumb: **/data and /schema are the product; /engine proves the data
is usable; /pipeline is plumbing.** Consumers may depend on `/data` alone.

## Running the engine and tests

Requires Python ≥ 3.11 with `PyYAML`, `jsonschema`, and `pytest`:

```sh
pip install "PyYAML>=6" "jsonschema>=4" "pytest>=8"
python tools/validate_data.py   # validate every data artifact
pytest -q                       # engine unit tests + golden corpus
```

Minimal usage:

```python
import datetime
from engine import (
    EmployeeInput, TaxabilityMatrix,
    load_parameter_file, select_effective, compute_withholding,
)

files = [load_parameter_file(p) for p in ...]   # or engine.golden.load_data_root
pf = select_effective(files, datetime.date(2026, 6, 15),
                      jurisdiction="US-CO", tax="state_income_withholding")
taxability = TaxabilityMatrix.from_file("taxability/us.yaml")
employee = EmployeeInput.from_dict({...})       # see schema/employee-input.schema.json
amount = compute_withholding(pf, employee, taxability)
```

## Contributing data

Hand-edited parameter values are not accepted. A data PR must carry a
complete `source` block (document, URL, retrieval date, sha256 of the
archived PDF) and golden tests transcribed from the same publication's
worked examples. CI enforces schema validity, bracket consistency, and the
golden corpus; a human reviews and merges every data change — always.

## Disclaimer

This project provides data and software **without warranty of any kind**.
It is **not tax advice**. Values must be verified against the official
government publications cited before use; employers remain solely
responsible for their withholding, deposits, and filings.

## License

Code is licensed under [MIT](LICENSE). Data files under `/data` are intended
for release under **CC0-1.0** (public-domain dedication) — the official
dedication text will be added as `data/LICENSE` before the first data
release. Government publications referenced are public domain.
