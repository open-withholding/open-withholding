"""Registry-backed locals (DESIGN §3.6): the engine's expansion of a
`kind: registry` sidecar + CSV, and the deterministic PA Act 32 importer."""

import argparse
import copy
import hashlib
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.errors import DataError  # noqa: E402
from engine.inputs import EmployeeInput  # noqa: E402
from engine.loader import select_effective  # noqa: E402
from engine.pipeline import compute_withholding  # noqa: E402
from engine.registry import load_registry  # noqa: E402
from pipeline import registry_import as ri  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SIDECAR = FIXTURES / "data" / "us" / "pa" / "2026" / "locals" / "act32.yaml"
AS_OF = __import__("datetime").date(2026, 6, 15)


def _pf(files, jurisdiction):
    return select_effective(files, AS_OF, jurisdiction=jurisdiction, tax="local_income_withholding")


# --- engine/registry.py -------------------------------------------------------

def test_registry_expands_nonzero_rows_into_parameter_files(fixture_params):
    jurs = sorted(f.jurisdiction for f in fixture_params if f.jurisdiction.startswith("US-PA-PSD-9901"))
    assert jurs == ["US-PA-PSD-990101", "US-PA-PSD-990102"]      # the zero-rate row has no file
    alpha = _pf(fixture_params, "US-PA-PSD-990101")
    assert alpha.method == "resident_nonresident_flat_rate"
    assert alpha.params == {"resident_rate": "0.015000", "nonresident_rate": "0.010000"}
    assert "psd_code=990101" in alpha.source["notes"] and "ALPHA BORO" in alpha.source["notes"]
    assert alpha.path == SIDECAR


def test_resident_flag_selects_the_rate_and_pa_401k_override_applies(fixture_params, taxability):
    alpha = _pf(fixture_params, "US-PA-PSD-990101")
    base = {"pay_frequency": "weekly", "gross_wages": "1000.00"}
    resident = EmployeeInput.from_dict({**base, "locals": [{"jurisdiction": "US-PA-PSD-990101", "resident": True}]})
    nonresident = EmployeeInput.from_dict({**base, "locals": [{"jurisdiction": "US-PA-PSD-990101", "resident": False}]})
    unflagged = EmployeeInput.from_dict({**base, "locals": [{"jurisdiction": "US-PA-PSD-990101"}]})
    assert compute_withholding(alpha, resident, taxability) == Decimal("15.00")
    assert compute_withholding(alpha, nonresident, taxability) == Decimal("10.00")
    assert compute_withholding(alpha, unflagged, taxability) == Decimal("15.00")   # default resident
    # PA: elective 401(k) deferrals do not reduce wages — the PSD inherits the state override.
    with_401k = EmployeeInput.from_dict({**base, "pretax_deductions": [{"type": "401k_traditional", "amount": "100.00"}],
                                         "locals": [{"jurisdiction": "US-PA-PSD-990101"}]})
    assert compute_withholding(alpha, with_401k, taxability) == Decimal("15.00")


def _sidecar():
    return yaml.safe_load(SIDECAR.read_text())


def test_edited_csv_fails_the_hash_check(tmp_path):
    raw = _sidecar()
    (tmp_path / "act32.csv").write_text((SIDECAR.parent / "act32.csv").read_text().replace("0.015000", "0.016000"))
    (tmp_path / "act32.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(DataError, match="edited by hand"):
        load_registry(raw, path=tmp_path / "act32.yaml")


def test_sidecar_counts_must_match_the_csv(tmp_path):
    raw = _sidecar()
    raw["expansion"]["expanded_rows"] = 3
    (tmp_path / "act32.csv").write_bytes((SIDECAR.parent / "act32.csv").read_bytes())
    with pytest.raises(DataError, match="expanded_rows=3 but 2"):
        load_registry(raw, path=tmp_path / "act32.yaml")


def test_sidecar_schema_rejects_unknown_method():
    raw = _sidecar()
    raw["method"] = "flat_rate"
    with pytest.raises(DataError, match="schema validation"):
        load_registry(raw, path=SIDECAR)


# --- pipeline/registry_import.py (pure parts) ---------------------------------

def _raw(code="010101", muni="EAST BERLIN BORO", county="ADAMS", mid="010303", res=0.5, non=1.0, sd=1.2, pit=0.0, total=1.7):
    return {
        "psd_code": code, "tax_collection_district": "ADAMS TAX COLLECTION DISTRICT", "county": county,
        "municipality_id": mid, "municipality": muni, "school_district_id": "011103",
        "school_district": "BERMUDIAN SPRINGS S D",
        "municipal_resident_eit": res, "municipal_nonresident_eit": non, "school_district_eit": sd,
        "school_district_pit": pit, "total_resident_rate": total,
        "municipal_resident_eit_effective": "", "municipal_nonresident_eit_effective": "01/01/2006",
        "school_district_eit_effective": "07/01/2016",
    }


def test_percent_to_rate_is_exact_six_place_fraction():
    assert ri.percent_to_rate(1.0) == "0.010000"
    assert ri.percent_to_rate(0.5) == "0.005000"
    assert ri.percent_to_rate(1.3325) == "0.013325"
    assert ri.percent_to_rate("") == "0.000000"
    with pytest.raises(ri.ImportFailure, match="more precision"):
        ri.percent_to_rate(1.33251)
    with pytest.raises(ri.ImportFailure, match="negative"):
        ri.percent_to_rate(-1)


def test_build_register_normalizes_and_sorts():
    rows = ri.build_register([_raw(code="010102", mid=10485.0), _raw()], {"2026"}, year=2026)
    assert [r["psd_code"] for r in rows] == ["010101", "010102"]
    assert rows[1]["municipality_id"] == "10485"                    # float cell -> text
    assert rows[0]["total_resident_rate"] == "0.017000"
    assert rows[0]["municipal_nonresident_eit_effective"] == "2006-01-01"
    assert rows[0]["municipal_resident_eit_effective"] == ""


def test_two_county_duplicates_merge_but_conflicting_figures_fail():
    a = _raw(code="480202", muni="BETHLEHEM CITY", county="LEHIGH", mid="390072")
    b = _raw(code="480202", muni="BETHLEHEM CITY", county="NORTHAMPTON", mid="480122")
    rows = ri.build_register([a, b, _raw()], {"2026"}, year=2026)
    merged = next(r for r in rows if r["psd_code"] == "480202")
    assert merged["county"] == "LEHIGH / NORTHAMPTON" and merged["municipality_id"] == "390072 / 480122"
    c = dict(b, municipal_nonresident_eit=0.5)
    with pytest.raises(ri.ImportFailure, match="different figures"):
        ri.build_register([a, c], {"2026"}, year=2026)


def test_build_register_refuses_wrong_year_unpopulated_and_bad_totals():
    with pytest.raises(ri.ImportFailure, match="reports year"):
        ri.build_register([_raw()], {"2025"}, year=2026)
    zeros = [_raw(code=f"0101{i:02d}", res=0, non=0, sd=0, total=0) for i in range(3)]
    with pytest.raises(ri.ImportFailure, match="not populated"):
        ri.build_register(zeros + [_raw(code="019999")], {"2026"}, year=2026)
    with pytest.raises(ri.ImportFailure, match="!= total resident rate"):
        ri.build_register([_raw(total=1.6)], {"2026"}, year=2026)


def test_sample_pins_cover_each_distinct_pair_and_nonresident_rate():
    rows = ri.build_register([
        _raw(code="010101", res=0.5, non=1.0, sd=0.5, total=1.0),
        _raw(code="010102", res=0.5, non=1.0, sd=0.5, total=1.0),      # same pair: no new pin
        _raw(code="010103", res=1.0, non=0.5, sd=0.5, total=1.5),
        _raw(code="010104", res=0, non=0, sd=0, total=0),              # zero: never pinned
    ], {"2026"}, year=2026)
    assert ri.sample_pins(rows) == [("010101", True), ("010101", False), ("010103", True), ("010103", False)]


def test_diff_registers_reports_rate_changes_added_and_removed():
    prev = ri.build_register([_raw(code="010101"), _raw(code="010102")], {"2025"}, year=2025)
    new = ri.build_register([_raw(code="010101", non=0.5), _raw(code="010103")], {"2026"}, year=2026)
    diff = ri.diff_registers(prev, new)
    assert [c for c, _, _ in diff["changed"]] == ["010101"]
    assert [r["psd_code"] for r in diff["added"]] == ["010103"]
    assert [r["psd_code"] for r in diff["removed"]] == ["010102"]
    assert diff["unchanged"] == 0


def test_run_dry_run_writes_register_sidecar_pins_and_pr_body(tmp_path, monkeypatch):
    """End to end with the workbook reader stubbed (no .xls writer is
    available): the written sidecar must load through engine/registry.py
    and the PR body must carry the diff and the pin count."""
    from pipeline import extract
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(extract, "ARCHIVE_DIR", tmp_path / "archive")
    raw_rows = [_raw(code="010101"), _raw(code="010102", res=1.0, non=1.0, sd=0.5, total=1.5),
                _raw(code="010103", res=0, non=0, sd=0, total=0)]
    monkeypatch.setattr(ri, "read_act32_workbook", lambda data: (copy.deepcopy(raw_rows), {"2026"}))
    monkeypatch.setattr(ri, "find_prev_register", lambda year: None)
    source = yaml.safe_load((Path(__file__).resolve().parents[2] / "pipeline" / "sources.yaml").read_text())
    source = next(s for s in source if s["id"] == "us-pa-act32")
    xls = tmp_path / "register.xls"
    xls.write_bytes(b"not really a workbook")
    args = argparse.Namespace(source_id="us-pa-act32", year=2026, pdf=str(xls), dry_run=True)
    assert ri.run(args, source) == 0
    root = tmp_path / "out" / "us-pa-act32-2026"
    sidecar_path = root / "data/us/pa/2026/locals/act32.yaml"
    sidecar = yaml.safe_load(sidecar_path.read_text())
    assert sidecar["kind"] == "registry" and sidecar["expansion"] == {
        "file": "act32.csv", "sha256": hashlib.sha256((root / "data/us/pa/2026/locals/act32.csv").read_bytes()).hexdigest(),
        "key": "psd_code", "jurisdiction": "US-PA-PSD-{psd_code}",
        "params": {"resident_rate": "total_resident_rate", "nonresident_rate": "municipal_nonresident_eit"},
        "rows": 3, "expanded_rows": 2,
    }
    assert sidecar["source"]["sha256"] == hashlib.sha256(b"not really a workbook").hexdigest()
    files = load_registry(sidecar, path=sidecar_path)
    assert sorted(f.jurisdiction for f in files) == ["US-PA-PSD-010101", "US-PA-PSD-010102"]
    pins = sorted(p.name for p in (root / "tests/golden").glob("*.yaml"))
    assert pins == ["us-pa-psd-010101-2026-1.yaml", "us-pa-psd-010101-2026-2.yaml", "us-pa-psd-010102-2026-1.yaml"]
    pin = yaml.safe_load((root / "tests/golden/us-pa-psd-010101-2026-2.yaml").read_text())
    assert pin["input"]["locals"] == [{"jurisdiction": "US-PA-PSD-010101", "resident": False}]
    assert pin["expect"] == {"local_withholding": "10.00"}                 # 1,000 x 1.0% nonresident
    body = (tmp_path / "out" / "us-pa-act32-2026-pr.md").read_text()
    assert "2 PSD files from 3 rows" in body and "3 engine-computed regression pins" in body
    assert "First import" in body and "| 0.017000 | 0.010000 | 1 |" in body


def test_run_unpopulated_register_writes_triage(tmp_path, monkeypatch):
    from pipeline import extract
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(extract, "ARCHIVE_DIR", tmp_path / "archive")
    zeros = [_raw(code=f"0101{i:02d}", res=0, non=0, sd=0, total=0) for i in range(3)]
    monkeypatch.setattr(ri, "read_act32_workbook", lambda data: (zeros, {"2027"}))
    source = {"id": "us-pa-act32", "jurisdiction": "US-PA", "tax": "local_income_withholding",
              "method": "resident_nonresident_flat_rate", "importer": "pa_act32", "authority": "publication",
              "document": "register", "documents": [{"name": "r", "kind": "xls", "url": "https://x.gov/r?y={year}"}]}
    xls = tmp_path / "r.xls"
    xls.write_bytes(b"zeros")
    args = argparse.Namespace(source_id="us-pa-act32", year=2027, pdf=str(xls), dry_run=True)
    assert ri.run(args, source) == 1
    assert "not populated" in (tmp_path / "out" / "us-pa-act32-2027-triage.md").read_text()
    assert not (tmp_path / "out" / "us-pa-act32-2027-pr.md").exists()


def test_run_identical_register_is_a_cosmetic_reissue_with_no_pr(tmp_path, monkeypatch):
    """DCED's .xls bytes carry a timestamp; when the parsed register equals the
    committed CSV for the year, nothing is proposed."""
    from pipeline import extract
    monkeypatch.setattr(extract, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(extract, "ARCHIVE_DIR", tmp_path / "archive")
    raw_rows = [_raw(code="010101"), _raw(code="010102", res=1.0, non=1.0, sd=0.5, total=1.5)]
    monkeypatch.setattr(ri, "read_act32_workbook", lambda data: (copy.deepcopy(raw_rows), {"2026"}))
    prev = tmp_path / "data/us/pa/2026/locals/act32.csv"
    prev.parent.mkdir(parents=True)
    prev.write_bytes(ri.csv_bytes(ri.build_register(copy.deepcopy(raw_rows), {"2026"}, year=2026)))
    monkeypatch.setattr(ri, "find_prev_register", lambda year: prev)
    source = {"id": "us-pa-act32", "jurisdiction": "US-PA", "tax": "local_income_withholding",
              "method": "resident_nonresident_flat_rate", "importer": "pa_act32", "authority": "publication",
              "document": "register", "documents": [{"name": "r", "kind": "xls", "url": "https://x.gov/r?y={year}"}]}
    xls = tmp_path / "r.xls"
    xls.write_bytes(b"same cells, new timestamp")
    args = argparse.Namespace(source_id="us-pa-act32", year=2026, pdf=str(xls), dry_run=True)
    assert ri.run(args, source) == 0
    assert not (tmp_path / "out" / "us-pa-act32-2026-pr.md").exists()
    assert not (tmp_path / "out" / "us-pa-act32-2026-triage.md").exists()
