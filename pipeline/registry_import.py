"""Deterministic register imports — no LLM in the loop (DESIGN §8.2).

Some locals are published as a machine-readable register rather than a
document: Pennsylvania's DCED keeps the official Act 32 EIT register (every
political subdivision's resident / nonresident rates) as a downloadable
spreadsheet. Transcribing 2,600 rows by model would be slower and less
reliable than reading the cells, so a registry source carries
`importer: <name>` and the Extract workflow runs this module instead of the
extraction passes. Everything else is unchanged: the bytes are archived by
sha256, the candidate is validated through the reference engine, pins are
written as goldens, and a human reviews the PR (whose body carries the
row-level diff against the prior register).

Output for `pa_act32`:
    data/us/pa/<year>/locals/act32.csv    the register (every row, rates as fractions)
    data/us/pa/<year>/locals/act32.yaml   `kind: registry` sidecar (engine/registry.py)
    tests/golden/us-pa-psd-<code>-<year>-{1,2}.yaml   regression pins (sampled)
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.errors import EngineError  # noqa: E402
from engine.golden import GoldenCase, run_golden_case  # noqa: E402
from engine.inputs import EmployeeInput  # noqa: E402
from engine.pipeline import compute_withholding  # noqa: E402
from engine.registry import load_registry  # noqa: E402
from engine.taxability import TaxabilityMatrix  # noqa: E402
from pipeline import assemble, discover  # noqa: E402


class ImportFailure(Exception):
    pass


# --- PA Act 32 (DCED "EIT with collector" Excel export) -----------------------

# (csv column, register header). Headers are matched by text, not position —
# DCED has reordered and renamed columns before.
ACT32_COLUMNS: tuple[tuple[str, str], ...] = (
    ("psd_code", "PSD Code"),
    ("tax_collection_district", "Tax Collection District Name"),
    ("county", "County"),
    ("municipality_id", "Municipality ID"),
    ("municipality", "Municipality"),
    ("school_district_id", "School District ID"),
    ("school_district", "School District Name"),
    ("municipal_resident_eit", "Municipal Resident EIT (percent)"),
    ("municipal_nonresident_eit", "Municipal Nonresident EIT (percent)"),
    ("school_district_eit", "School District EIT (percent)"),
    ("school_district_pit", "School District PIT (percent)"),
    ("total_resident_rate", "Total Resident Income Tax (percent)"),
    ("municipal_resident_eit_effective", "Municipal Resident EIT Effective Date"),
    ("municipal_nonresident_eit_effective", "Municipal Nonresident EIT Effective Date"),
    ("school_district_eit_effective", "School District EIT Effective Date"),
)
ACT32_RATE_COLUMNS = (
    "municipal_resident_eit", "municipal_nonresident_eit", "school_district_eit",
    "school_district_pit", "total_resident_rate",
)
ACT32_DATE_COLUMNS = tuple(c for c, _ in ACT32_COLUMNS if c.endswith("_effective"))
ACT32_CSV_COLUMNS = tuple(c for c, _ in ACT32_COLUMNS)
ACT32_KEY = "psd_code"
# Columns that must agree between a PSD's duplicate rows for them to merge.
ACT32_MERGE_MUST_AGREE = (
    "psd_code", "tax_collection_district", "municipality", "school_district_id", "school_district",
    *ACT32_RATE_COLUMNS,
)
ACT32_JURISDICTION = "US-PA-PSD-{psd_code}"
ACT32_RESIDENT, ACT32_NONRESIDENT = "total_resident_rate", "municipal_nonresident_eit"
RATE_PLACES = Decimal("0.000001")
PIN_INPUT = {"pay_frequency": "weekly", "gross_wages": "1000.00"}


def read_act32_workbook(data: bytes) -> tuple[list[dict], set[str]]:
    """Raw rows keyed by csv column (cell values as the sheet holds them),
    plus the set of Reporting Year values seen. Needs xlrd (legacy .xls)."""
    import xlrd  # extract.yml installs it; the engine never needs it

    book = xlrd.open_workbook(file_contents=data, logfile=io.StringIO())
    sheet = book.sheet_by_index(0)
    header_row = next(
        (r for r in range(min(sheet.nrows, 10))
         if any(str(c).strip() == "PSD Code" for c in sheet.row_values(r))),
        None,
    )
    if header_row is None:
        raise ImportFailure("register workbook has no 'PSD Code' header in its first 10 rows")
    headers = {str(c).strip(): i for i, c in enumerate(sheet.row_values(header_row)) if str(c).strip()}
    missing = [h for _, h in ACT32_COLUMNS if h not in headers]
    if missing:
        raise ImportFailure(f"register workbook lacks expected columns: {missing}; has {sorted(headers)}")
    year_idx = headers.get("Reporting Year")
    rows, years = [], set()
    for r in range(header_row + 1, sheet.nrows):
        values = sheet.row_values(r)
        if not str(values[headers["PSD Code"]]).strip():
            continue  # trailing blank / footer rows
        rows.append({col: values[headers[h]] for col, h in ACT32_COLUMNS})
        if year_idx is not None:
            years.add(str(values[year_idx]).strip())
    return rows, years


def percent_to_rate(value) -> str:
    """Register percents (1.0, 0.5, 1.3325) -> decimal-fraction strings with six
    places ("0.010000"). Exactness is checked: a cell the conversion cannot
    represent fails loud rather than rounding a tax rate."""
    text = str(value).strip()
    if text in ("", "None"):
        return "0.000000"
    try:
        pct = Decimal(text)
    except InvalidOperation as exc:
        raise ImportFailure(f"rate cell {value!r} is not a number") from exc
    if pct < 0:
        raise ImportFailure(f"negative rate {value!r}")
    rate = (pct / 100).quantize(RATE_PLACES)
    if rate * 100 != pct:
        raise ImportFailure(f"rate {value!r}% has more precision than six decimal places of a fraction")
    return f"{rate:.6f}"


def date_to_iso(value) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        return dt.datetime.strptime(text, "%m/%d/%Y").date().isoformat()
    except ValueError as exc:
        raise ImportFailure(f"effective date {value!r} is not MM/DD/YYYY") from exc


def _clean_text(value) -> str:
    text = str(value).strip()
    # xlrd gives integer-valued numeric cells as floats ("530035.0")
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def build_register(raw_rows: list[dict], years: set[str], *, year: int) -> list[dict]:
    """Normalize, de-duplicate and sanity-check the register. Pure: raises
    ImportFailure with every problem it can name."""
    if years and years != {str(year)}:
        raise ImportFailure(f"register reports year(s) {sorted(years)}, not {year}")
    normalized: list[dict] = []
    for raw in raw_rows:
        row = {}
        for col in ACT32_CSV_COLUMNS:
            if col in ACT32_RATE_COLUMNS:
                row[col] = percent_to_rate(raw[col])
            elif col in ACT32_DATE_COLUMNS:
                row[col] = date_to_iso(raw[col])
            else:
                row[col] = _clean_text(raw[col])
        if not row[ACT32_KEY].isdigit() or len(row[ACT32_KEY]) != 6:
            raise ImportFailure(f"PSD code {row[ACT32_KEY]!r} is not six digits ({row['municipality']})")
        normalized.append(row)
    if not normalized:
        raise ImportFailure("register has no rows")

    # A municipality straddling two counties is printed once per county
    # (Bethlehem: Lehigh and Northampton) with the same PSD code and figures
    # but a different County / Municipality ID. Those rows collapse into one
    # with the descriptive columns joined ("LEHIGH / NORTHAMPTON"); rows that
    # disagree on a rate or a name are a register defect we refuse.
    by_code: dict[str, list[dict]] = defaultdict(list)
    for row in normalized:
        by_code[row[ACT32_KEY]].append(row)
    rows: list[dict] = []
    conflicts: list[str] = []
    for code, rs in sorted(by_code.items()):
        if len(rs) == 1:
            rows.append(rs[0])
            continue
        if any(len({r[c] for r in rs}) > 1 for c in ACT32_MERGE_MUST_AGREE):
            conflicts.append(
                f"{code}: " + " vs ".join(
                    f"{r['municipality']}/{r['school_district']} {r[ACT32_RESIDENT]}/{r[ACT32_NONRESIDENT]}" for r in rs)
            )
            continue
        merged = dict(rs[0])
        for c in ACT32_CSV_COLUMNS:
            if c not in ACT32_MERGE_MUST_AGREE:
                merged[c] = " / ".join(sorted({r[c] for r in rs if r[c]}))
        rows.append(merged)
    if conflicts:
        raise ImportFailure("PSD code(s) listed with different figures: " + "; ".join(conflicts))

    bad_totals = [
        r[ACT32_KEY] for r in rows
        if Decimal(r["municipal_resident_eit"]) + Decimal(r["school_district_eit"]) + Decimal(r["school_district_pit"])
        != Decimal(r[ACT32_RESIDENT])
    ]
    if bad_totals:
        raise ImportFailure(
            f"{len(bad_totals)} row(s) where municipal resident EIT + school district EIT + PIT "
            f"!= total resident rate: {bad_totals[:10]}"
        )
    zero = sum(1 for r in rows if Decimal(r[ACT32_RESIDENT]) == 0 and Decimal(r[ACT32_NONRESIDENT]) == 0)
    if zero * 2 > len(rows):
        raise ImportFailure(
            f"{zero} of {len(rows)} rows carry no rate — DCED publishes next year's register as "
            f"all zeros until municipalities certify; this edition is not populated yet"
        )
    return rows


def csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(ACT32_CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def read_csv(data: bytes) -> list[dict]:
    return list(csv.DictReader(data.decode("utf-8").splitlines()))


def expanded_count(rows: list[dict]) -> int:
    return sum(1 for r in rows if Decimal(r[ACT32_RESIDENT]) != 0 or Decimal(r[ACT32_NONRESIDENT]) != 0)


def sample_pins(rows: list[dict]) -> list[tuple[str, bool]]:
    """Regression pins cover every distinct figure without 2,600 fixtures: the
    first PSD (by code) of each distinct (resident, nonresident) pair gets a
    resident pin; the first PSD of each distinct nonzero nonresident rate gets
    a nonresident pin."""
    pins: list[tuple[str, bool]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_nonres: set[str] = set()
    for r in rows:  # rows are sorted by code
        res, non = r[ACT32_RESIDENT], r[ACT32_NONRESIDENT]
        if Decimal(res) == 0 and Decimal(non) == 0:
            continue
        if (res, non) not in seen_pairs:
            seen_pairs.add((res, non))
            if Decimal(res) != 0:
                pins.append((r[ACT32_KEY], True))
        if Decimal(non) != 0 and non not in seen_nonres:
            seen_nonres.add(non)
            pins.append((r[ACT32_KEY], False))
    return pins


def diff_registers(prev: list[dict] | None, rows: list[dict]) -> dict:
    """Row-level change summary for the PR body: added / removed PSDs and
    rate changes (old -> new), plus a count of unchanged rows."""
    if prev is None:
        return {"added": [], "removed": [], "changed": [], "unchanged": len(rows), "baseline": True}
    old = {r[ACT32_KEY]: r for r in prev}
    new = {r[ACT32_KEY]: r for r in rows}
    key = lambda r: (r[ACT32_RESIDENT], r[ACT32_NONRESIDENT])  # noqa: E731
    changed = [
        (c, old[c], new[c]) for c in sorted(set(old) & set(new)) if key(old[c]) != key(new[c])
    ]
    return {
        "added": [new[c] for c in sorted(set(new) - set(old))],
        "removed": [old[c] for c in sorted(set(old) - set(new))],
        "changed": changed,
        "unchanged": len(set(old) & set(new)) - len(changed),
        "baseline": False,
    }


def find_prev_register(year: int) -> Path | None:
    """The register this import supersedes: the same year's (an in-year
    re-import) else the latest earlier year's."""
    for y in (year, *range(year - 1, year - 6, -1)):
        candidate = REPO_ROOT / "data" / "us" / "pa" / str(y) / "locals" / "act32.csv"
        if candidate.exists():
            return candidate
    return None


def _dump(mapping: dict) -> str:
    return yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True, width=100)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run(args, source: dict) -> int:
    """Extract-workflow entry point for `importer: pa_act32` sources."""
    from pipeline.extract import ARCHIVE_DIR, OUT_DIR, stamp_edition_year

    source_id, year = args.source_id, int(args.year)
    if source.get("importer") != "pa_act32":
        raise SystemExit(f"unknown importer {source.get('importer')!r}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    triage = OUT_DIR / f"{source_id}-{year}-triage.md"

    print(f"[1/4] fetching + archiving {source_id} register ...")
    doc = source["documents"][0]
    if getattr(args, "pdf", None):
        data, url = Path(args.pdf).read_bytes(), discover.substitute_year(doc["url"], year)
    else:
        url = discover.resolve_document_url(doc, year, insecure=source.get("insecure_tls", False))
        data = discover.fetch(url, insecure=source.get("insecure_tls", False))
    sha = hashlib.sha256(data).hexdigest()
    ARCHIVE_DIR.mkdir(exist_ok=True)
    (ARCHIVE_DIR / f"{sha}.{doc.get('kind', 'xls')}").write_bytes(data)
    print(f"      archived {len(data)//1024} KiB sha256={sha[:12]}...")
    source_block = {
        "document": source["document"], "url": url,
        "retrieved": dt.date.today().isoformat(), "sha256": sha,
    }
    stamp_edition_year(source_block, year)

    print(f"[2/4] reading the register (deterministic, no model) ...")
    try:
        raw_rows, years = read_act32_workbook(data)
        rows = build_register(raw_rows, years, year=year)
    except ImportFailure as exc:
        triage.write_text(f"# Triage: {source_id} {year}\n\n**Failure:** {exc}\n\n"
                          f"Register: {url}\n\nArchived sha256: `{sha}`\n")
        print(f"      FAILED — {exc}")
        return 1
    n_expanded = expanded_count(rows)
    print(f"      {len(raw_rows)} rows read, {len(rows)} distinct PSDs, {n_expanded} with a rate")

    prev_path = find_prev_register(year)
    prev_rows = read_csv(prev_path.read_bytes()) if prev_path else None
    diff = diff_registers(prev_rows, rows)

    effective_from = f"{year}-01-01"
    as_of = assemble.default_as_of(effective_from)
    csv_data = csv_bytes(rows)
    csv_sha = hashlib.sha256(csv_data).hexdigest()
    sidecar = {
        "schema_version": "0.1",
        "kind": "registry",
        "registry": "pa_act32",
        "jurisdiction": source["jurisdiction"],
        "tax": source["tax"],
        "effective_from": effective_from,
        "effective_to": None,
        "source": {
            **source_block,
            "notes": "Imported by pipeline/registry_import.py (deterministic read of the DCED "
                     "register; percents converted to fractions); rows carry DCED's own "
                     "effective dates — the register prints current rates only, so a row "
                     "effective mid-year reflects its post-change rate for the whole year",
        },
        "method": source["method"],
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "expansion": {
            "file": "act32.csv", "sha256": csv_sha, "key": ACT32_KEY,
            "jurisdiction": ACT32_JURISDICTION,
            "params": {"resident_rate": ACT32_RESIDENT, "nonresident_rate": ACT32_NONRESIDENT},
            "rows": len(rows), "expanded_rows": n_expanded,
        },
    }

    print(f"[3/4] mechanical validation (expand + pins through the engine) ...")
    target_root = OUT_DIR / f"{source_id}-{year}" if args.dry_run else REPO_ROOT
    data_dir = target_root / "data" / "us" / "pa" / str(year) / "locals"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "act32.csv").write_bytes(csv_data)
    (data_dir / "act32.yaml").write_text(_dump(sidecar))
    taxability = TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")
    golden_paths: list[str] = []
    try:
        files = load_registry(yaml.safe_load((data_dir / "act32.yaml").read_text()), path=data_dir / "act32.yaml")
        by_jur = {f.jurisdiction: f for f in files}
        by_code = {r[ACT32_KEY]: r for r in rows}
        counts: Counter = Counter()
        for code, resident in sample_pins(rows):
            jurisdiction = ACT32_JURISDICTION.replace("{psd_code}", code)
            record = {**PIN_INPUT, "locals": [{"jurisdiction": jurisdiction, "resident": resident}]}
            amount = compute_withholding(by_jur[jurisdiction], EmployeeInput.from_dict(record), taxability)
            row = by_code[code]
            golden = {
                "source": {
                    "document": source_block["document"], "page": 0,
                    "example": "pipeline-constructed regression pin (deterministic register import, "
                               "no printed examples exist): engine-computed on weekly $1,000 gross, "
                               f"{'resident' if resident else 'nonresident'} of PSD {code} "
                               f"{row['municipality']} / {row['school_district']} ({row['county']}); "
                               f"rates from the register row",
                },
                "as_of": as_of, "input": record,
                "expect": {"local_withholding": str(amount)},
            }
            case = GoldenCase(path=Path("<candidate>"), source=golden["source"],
                              as_of=dt.date.fromisoformat(as_of), input_record=record,
                              expect=golden["expect"])
            results = run_golden_case(case, files, taxability)
            if not all(r.ok for r in results):
                raise ImportFailure(f"pin for {jurisdiction} does not reproduce through the engine")
            counts[code] += 1
            rel = f"tests/golden/{assemble.golden_slug(jurisdiction, source['tax'])}-{year}-{counts[code]}.yaml"
            (target_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (target_root / rel).write_text(_dump(golden))
            golden_paths.append(rel)
    except (ImportFailure, EngineError) as exc:
        triage.write_text(f"# Triage: {source_id} {year}\n\n**Failure:** {exc}\n\n"
                          f"Register: {url}\n\nArchived sha256: `{sha}`\n")
        print(f"      FAILED — {exc}")
        return 1
    print(f"      {len(files)} PSD files expand and load; {len(golden_paths)} regression pins reproduce")

    print(f"[4/4] writing PR body ...")
    pairs = Counter((r[ACT32_RESIDENT], r[ACT32_NONRESIDENT]) for r in rows)
    mid_year = sorted({
        r[c] for r in rows for c in ACT32_DATE_COLUMNS
        if r[c].startswith(str(year)) and not r[c].endswith("-01-01")
    })
    n_mid_year = sum(
        1 for r in rows if any(r[c].startswith(str(year)) and not r[c].endswith("-01-01") for c in ACT32_DATE_COLUMNS)
    )
    lines = [
        f"## `{source_id}`: {source['jurisdiction']} Act 32 EIT register — {n_expanded} PSD files from {len(rows)} rows",
        "",
        f"- **Method:** `{source['method']}` (one expansion per register row; `kind: registry` sidecar + CSV, DESIGN §3.6)",
        f"- **Import:** deterministic read of the DCED spreadsheet (no model); percents converted to fractions exactly",
        f"- **Source authority:** {assemble.AUTHORITY_LABELS.get(source.get('authority'), source.get('authority') or 'unclassified')}",
        f"- **Effective from:** {effective_from}",
        f"- **Source:** [{source_block['document']}]({url}) — retrieved {source_block['retrieved']}",
        f"- **Archived sha256:** `{sha}` (register .xls); CSV sha256 `{csv_sha}`",
        f"- **Supersedes:** `{_rel(prev_path)}`" if prev_path else "- **Supersedes:** none (first register in repo)",
        f"- **Rows:** {len(raw_rows)} read, {len(raw_rows) - len(rows)} identical duplicate row(s) collapsed, "
        f"{len(rows) - n_expanded} zero-rate rows produce no file",
        f"- **Mid-year effective dates in {year}:** {n_mid_year} row(s) ({', '.join(mid_year) or 'none'}) — the register prints "
        "current rates only, so those rows are carried at their post-change rate for the whole year",
        "",
        "### Changes against the superseded register",
        "",
    ]
    if diff["baseline"]:
        lines.append("First import — no prior register to diff against.")
    else:
        lines += [
            f"- {len(diff['changed'])} rate change(s), {len(diff['added'])} PSD(s) added, "
            f"{len(diff['removed'])} removed, {diff['unchanged']} unchanged",
        ]
        if diff["changed"]:
            lines += ["", "| PSD | Municipality | School district | Resident (old → new) | Nonresident (old → new) |",
                      "|---|---|---|---|---|"]
            for code, old, new in diff["changed"]:
                lines.append(
                    f"| {code} | {new['municipality']} | {new['school_district']} | "
                    f"{old[ACT32_RESIDENT]} → {new[ACT32_RESIDENT]} | {old[ACT32_NONRESIDENT]} → {new[ACT32_NONRESIDENT]} |"
                )
        for label, items in (("Added", diff["added"]), ("Removed", diff["removed"])):
            if items:
                lines += ["", f"**{label}:** " + ", ".join(f"{r[ACT32_KEY]} {r['municipality']}" for r in items)]
    lines += [
        "",
        "### Distinct rate pairs (resident total / municipal nonresident)",
        "",
        "| Resident | Nonresident | PSDs |", "|---|---|---|",
        *(f"| {res} | {non} | {n} |" for (res, non), n in sorted(pairs.items())),
        "",
        "### Golden tests",
        "",
        f"- {len(golden_paths)} engine-computed regression pins (weekly $1,000 gross): one resident pin per distinct "
        "rate pair, one nonresident pin per distinct nonresident rate. The register prints no worked examples.",
        "",
        "### Reviewer checklist",
        "",
        "- [ ] Open the register link and spot-check 5+ rows (including Philadelphia 510101 and any changed row) "
        "against the CSV: percent ÷ 100 = fraction",
        "- [ ] Every changed row above is plausible (a municipality or school district levy change, not a parse shift)",
        "- [ ] Row count matches the spreadsheet (header excluded, two-county duplicates merged as stated)",
        "",
        "🤖 Imported by the pipeline (deterministic); every figure above requires human review before merge.",
    ]
    pr_file = OUT_DIR / f"{source_id}-{year}-pr.md"
    pr_file.write_text("\n".join(lines) + "\n")
    print(f"      data: {_rel(data_dir / 'act32.csv')}, {_rel(data_dir / 'act32.yaml')}; {len(golden_paths)} goldens")
    print(f"      PR body: {_rel(pr_file)}")
    return 0
