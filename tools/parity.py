#!/usr/bin/env python3
"""One-time external parity check (DESIGN §10): does an independent payroll
calculator agree with this dataset + engine?

    python tools/parity.py generate    # scenarios from each jurisdiction's goldens -> tests/parity/scenarios/
    python tools/parity.py worksheet   # tests/parity/WORKSHEET.md: what to type into the calculator
    python tools/parity.py report      # compare tests/parity/expected.csv with the engine

Scenarios are derived from the election shapes the agency goldens already
use (so every input is one the method accepts) and varied over pay
frequency, wages, a pre-tax 401(k) deduction and a wage-base crossing. The
engine's answer is computed live; the external answer is typed by a human
into expected.csv (id, expected, source, entered_on, note). Nothing here is
agency data: parity rows never become goldens.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from engine.errors import EngineError  # noqa: E402
from engine.golden import GoldenCase, _expected_pairs, load_data_root, load_golden_case  # noqa: E402
from engine.inputs import EmployeeInput  # noqa: E402
from engine.loader import select_effective  # noqa: E402
from engine.pipeline import compute_employer_tax, compute_withholding  # noqa: E402
from engine.taxability import TaxabilityMatrix  # noqa: E402
from pipeline.assemble import golden_slug  # noqa: E402

PARITY_DIR = REPO_ROOT / "tests" / "parity"
SCENARIO_DIR = PARITY_DIR / "scenarios"
EXPECTED_CSV = PARITY_DIR / "expected.csv"
YEAR = 2026
AS_OF = f"{YEAR}-06-15"
TOLERANCE = Decimal("0.01")
EMPLOYER_TAXES = ("futa", "state_unemployment_insurance")
INCOME_TAXES = ("federal_income_withholding", "state_income_withholding", "local_income_withholding")
STRIP = ("pay_frequency", "gross_wages", "pretax_deductions", "ytd")
MAX_TEMPLATES = 2

# (tier, pay_frequency, gross, 401k fraction or None)
INCOME_VARIANTS = [
    ("core", "biweekly", "2000.00", None),
    ("extended", "weekly", "900.00", None),
    ("extended", "monthly", "12000.00", "0.06"),
    ("extended", "semimonthly", "4500.00", None),
    ("extended", "biweekly", "2000.00", "0.06"),
    ("extended", "weekly", "15000.00", None),
]
# Local families (IN counties, OH school districts, PA PSDs, MI cities) share
# one method and one rate list: two members each prove the method, the rest
# would be typing the same arithmetic 300 times.
LOCAL_FAMILY_LIMIT = 2
YTD_KEY = {"state_unemployment_insurance": "sui_wages", "futa": "futa_wages"}


def _targets(case: GoldenCase) -> list[tuple[str, str]]:
    employee = EmployeeInput.from_dict(case.input_record)
    out = []
    for key, expected in case.expect.items():
        out += [(j, t) for j, t, _ in _expected_pairs(case, employee, key, expected)]
    return out


def collect_templates() -> dict[tuple[str, str], list[dict]]:
    """(jurisdiction, tax) -> distinct election templates from that
    jurisdiction's current-year goldens."""
    templates: dict[tuple[str, str], list[dict]] = {}
    for path in sorted((REPO_ROOT / "tests" / "golden").glob(f"*-{YEAR}-*.yaml")):
        try:
            case = load_golden_case(path)
            targets = _targets(case)
        except EngineError:
            continue
        template = {k: v for k, v in case.input_record.items() if k not in STRIP}
        for target in targets:
            bucket = templates.setdefault(target, [])
            if template not in bucket and len(bucket) < MAX_TEMPLATES:
                bucket.append(template)
    return templates


def _wage_base(pf) -> str | None:
    p = pf.params
    if pf.tax in ("state_unemployment_insurance", "futa"):
        return str(p["wage_base"])
    if pf.tax in ("state_disability_insurance", "state_unemployment_insurance_employee"):
        comp = (p.get("components") or [{}])[0]
        base = comp.get("wage_base")
        return str(base) if isinstance(base, (str, int)) and str(base).replace(".", "").isdigit() else None
    return None


def _ytd_key(pf) -> str:
    if pf.tax in YTD_KEY:
        return YTD_KEY[pf.tax]
    return pf.params.get("ytd_tracker", "sdi_wages")


def compute(files, taxability, jurisdiction: str, tax: str, record: dict, as_of: str) -> Decimal:
    pf = select_effective(files, dt.date.fromisoformat(as_of), jurisdiction=jurisdiction, tax=tax)
    employee = EmployeeInput.from_dict(record)
    if tax in EMPLOYER_TAXES:
        return compute_employer_tax(pf, employee, taxability)
    return compute_withholding(pf, employee, taxability)


def _describe(record: dict, jurisdiction: str, tax: str) -> str:
    bits = [f"{record['pay_frequency']} gross ${record['gross_wages']}"]
    for ded in record.get("pretax_deductions") or []:
        bits.append(f"pre-tax {ded['type']} ${ded['amount']}")
    for key, val in (record.get("ytd") or {}).items():
        bits.append(f"YTD {key} ${val}")
    if tax == "federal_income_withholding":
        fed = record.get("federal") or {}
        bits.append("W-4: " + ", ".join(f"{k}={v}" for k, v in fed.items() if v not in (None, "0", 0, False)) or "W-4 defaults")
    elif tax == "state_income_withholding":
        for e in record.get("state") or []:
            if e["jurisdiction"] == jurisdiction:
                bits.append("; ".join(f"{k}={v}" for k, v in e.items() if k != "jurisdiction" and v not in (None, "0", 0)))
    elif tax == "local_income_withholding":
        for e in record.get("locals") or []:
            if e["jurisdiction"] == jurisdiction:
                bits.append("local: " + ("; ".join(f"{k}={v}" for k, v in e.items() if k != "jurisdiction") or "defaults"))
        for e in record.get("state") or []:
            bits.append("state cert: " + "; ".join(f"{k}={v}" for k, v in e.items() if k != "jurisdiction" and v not in (None, "0", 0)))
    elif tax == "state_unemployment_insurance":
        emp = record.get("employer") or {}
        bits.append(f"employer rate {emp.get('sui_experience_rate')}")
    return " | ".join(b for b in bits if b)


def generate() -> None:
    files = load_data_root(REPO_ROOT / "data")
    taxability = TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")
    templates = collect_templates()
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    for old in SCENARIO_DIR.glob("*.yaml"):
        old.unlink()
    total = 0
    family_counts: dict[str, int] = {}
    for (jurisdiction, tax), tmpls in sorted(templates.items()):
        if tax == "local_income_withholding":
            parts = jurisdiction.split("-")
            family = "-".join(parts[:3]) if len(parts) > 3 else "-".join(parts[:2])  # US-PA-PSD / US-IN
            family_counts[family] = family_counts.get(family, 0) + 1
            if family_counts[family] > LOCAL_FAMILY_LIMIT:
                continue
        slug = golden_slug(jurisdiction, tax)
        try:
            pf = select_effective(files, dt.date.fromisoformat(AS_OF), jurisdiction=jurisdiction, tax=tax)
        except EngineError:
            continue
        scenarios = []
        for ti, template in enumerate(tmpls):
            if tax in INCOME_TAXES or tax == "fica":
                variants = INCOME_VARIANTS if ti == 0 else INCOME_VARIANTS[:1]
                for tier, freq, gross, k401 in variants:
                    record = {**json.loads(json.dumps(template)), "pay_frequency": freq, "gross_wages": gross}
                    if k401:
                        amount = (Decimal(gross) * Decimal(k401)).quantize(Decimal("0.01"))
                        record["pretax_deductions"] = [{"type": "401k_traditional", "amount": str(amount)}]
                    scenarios.append((tier, record))
            else:
                record = {**json.loads(json.dumps(template)), "pay_frequency": "biweekly", "gross_wages": "2000.00"}
                scenarios.append(("core", record))
                base = _wage_base(pf)
                if base and ti == 0:
                    crossing = {**json.loads(json.dumps(record)),
                                "ytd": {_ytd_key(pf): str(Decimal(base) - Decimal("1000"))}}
                    scenarios.append(("core", crossing))
        out = []
        for n, (tier, record) in enumerate(scenarios, 1):
            try:
                ours = str(compute(files, taxability, jurisdiction, tax, record, AS_OF))
                error = None
            except EngineError as exc:
                ours, error = None, str(exc)[:200]
            out.append({"id": f"{slug}-p{n:02d}", "tier": tier, "jurisdiction": jurisdiction, "tax": tax,
                        "as_of": AS_OF, "describe": _describe(record, jurisdiction, tax), "input": record,
                        "ours": ours, **({"error": error} if error else {})})
        (SCENARIO_DIR / f"{slug}.yaml").write_text(yaml.safe_dump(out, sort_keys=False, width=110))
        total += len(out)
    if not EXPECTED_CSV.exists():
        EXPECTED_CSV.write_text("id,expected,source,entered_on,note\n")
    print(f"{total} scenarios across {len(list(SCENARIO_DIR.glob('*.yaml')))} jurisdiction/tax targets -> {SCENARIO_DIR.relative_to(REPO_ROOT)}")


def load_scenarios() -> dict[str, dict]:
    out = {}
    for path in sorted(SCENARIO_DIR.glob("*.yaml")):
        for s in yaml.safe_load(path.read_text()) or []:
            out[s["id"]] = s
    return out


def load_expected() -> dict[str, dict]:
    if not EXPECTED_CSV.exists():
        return {}
    with EXPECTED_CSV.open() as fh:
        return {row["id"]: row for row in csv.DictReader(fh) if row.get("expected", "").strip()}


def worksheet() -> None:
    scenarios = load_scenarios()
    expected = load_expected()
    lines = ["# Parity worksheet", "",
             "Type each scenario into the external calculator and record its answer in "
             "`tests/parity/expected.csv` (`id,expected,source,entered_on,note`). Core rows first; "
             "extended rows only if a core row disagrees. Record ONLY the tax named in the heading "
             "(e.g. the state income tax line, not the whole paycheck). `ours` is the engine's answer.", ""]
    by_target: dict[tuple[str, str], list[dict]] = {}
    for s in scenarios.values():
        by_target.setdefault((s["jurisdiction"], s["tax"]), []).append(s)
    for tier in ("core", "extended"):
        lines += [f"## {tier.title()} scenarios", ""]
        for (jur, tax), rows in sorted(by_target.items()):
            rows = [r for r in rows if r["tier"] == tier]
            if not rows:
                continue
            lines += [f"### {jur} — {tax.replace('_', ' ')}", "", "| id | scenario | ours | expected |", "|---|---|---|---|"]
            for r in rows:
                exp = expected.get(r["id"], {}).get("expected", "")
                lines.append(f"| {r['id']} | {r['describe']} | {r['ours'] if r['ours'] is not None else 'ERROR: ' + r.get('error', '')} | {exp} |")
            lines.append("")
    (PARITY_DIR / "WORKSHEET.md").write_text("\n".join(lines))
    core = sum(1 for s in scenarios.values() if s["tier"] == "core")
    print(f"worksheet: {core} core + {len(scenarios) - core} extended rows -> {PARITY_DIR.relative_to(REPO_ROOT)}/WORKSHEET.md")


def report() -> int:
    files = load_data_root(REPO_ROOT / "data")
    taxability = TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")
    scenarios = load_scenarios()
    expected = load_expected()
    unknown = sorted(set(expected) - set(scenarios))
    if unknown:
        print(f"ERROR expected.csv ids with no scenario: {unknown}")
    mismatches, matched = [], 0
    for sid, row in sorted(expected.items()):
        if sid not in scenarios:
            continue
        s = scenarios[sid]
        ours = compute(files, taxability, s["jurisdiction"], s["tax"], s["input"], s["as_of"])
        ext = Decimal(row["expected"])
        if abs(ours - ext) <= TOLERANCE:
            matched += 1
        else:
            mismatches.append((sid, ours, ext, row.get("source", ""), s["describe"]))
    covered = {(scenarios[i]["jurisdiction"], scenarios[i]["tax"]) for i in expected if i in scenarios}
    targets = {(s["jurisdiction"], s["tax"]) for s in scenarios.values()}
    print(f"parity: {matched} match, {len(mismatches)} mismatch, {len(expected)} entered of {len(scenarios)} scenarios; "
          f"{len(covered)}/{len(targets)} jurisdiction/tax targets have at least one external value")
    for sid, ours, ext, src, desc in mismatches:
        print(f"MISMATCH {sid}: ours {ours} vs {src or 'external'} {ext} — {desc}")
    return 1 if mismatches or unknown else 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "generate":
        generate(); return 0
    if cmd == "worksheet":
        worksheet(); return 0
    if cmd == "report":
        return report()
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
