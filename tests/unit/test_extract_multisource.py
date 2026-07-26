"""Multi-source extraction helpers (schema v0.2 `sources` feature)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pipeline.extract import ExtractionFailure, fetch_documents, html_to_text


PAGE = b"""<html><head><style>p{color:red}</style>
<script>var x = 1;</script></head>
<body><nav>Home | Forms</nav>
<h1>Withholding Formula</h1>
<p>Subtract the standard deduction of $3,250 (single) or $6,500 (married).</p>
<table><tr><th>Bracket</th><th>Rate</th></tr>
<tr><td>$2,000 &ndash; $5,000</td><td>0.8%</td></tr></table>
</body></html>"""


def test_html_to_text_strips_chrome_keeps_content():
    text = html_to_text(PAGE, "https://x.gov/guide")
    assert text.startswith("[HTML source: https://x.gov/guide]")
    assert "$3,250" in text and "0.8%" in text
    assert "var x" not in text and "color:red" not in text
    assert "Home | Forms" not in text  # nav stripped
    assert "–" in text  # entities unescaped


def test_html_to_text_table_cells_tab_separated():
    text = html_to_text(PAGE, "https://x.gov/guide")
    row = next(line for line in text.splitlines() if "$2,000" in line)
    assert "\t" in row


def _fake_fetch(pages):
    def fetch(url, insecure=False):
        return pages[url]
    return fetch


def test_fetch_documents_mixed_kinds(monkeypatch):
    from pipeline import extract

    src = {"id": "us-zz", "documents": [
        {"name": "guide", "kind": "html", "url": "https://x.gov/guide"},
        {"name": "tables", "url": "https://x.gov/tables_{year}.pdf"},  # kind defaults to pdf
    ]}
    monkeypatch.setattr(extract.discover, "fetch", _fake_fetch({
        "https://x.gov/guide": PAGE,
        "https://x.gov/tables_2026.pdf": b"%PDF-1.7 fake",
    }))
    docs = fetch_documents(src, 2026)
    assert [d["name"] for d in docs] == ["guide", "tables"]
    assert docs[0]["kind"] == "html" and "$3,250" in docs[0]["text"]
    assert docs[1]["kind"] == "pdf" and "text" not in docs[1]
    assert docs[1]["url"] == "https://x.gov/tables_2026.pdf"  # {year} substituted


def test_fetch_documents_rejects_non_pdf_bytes(monkeypatch):
    from pipeline import extract

    src = {"id": "us-zz", "documents": [
        {"name": "tables", "kind": "pdf", "url": "https://x.gov/tables.pdf"},
    ]}
    monkeypatch.setattr(extract.discover, "fetch",
                        _fake_fetch({"https://x.gov/tables.pdf": b"<html>error page</html>"}))
    with pytest.raises(ExtractionFailure, match="expected PDF"):
        fetch_documents(src, 2026)


def test_stamp_edition_year_single_source():
    from pipeline.extract import stamp_edition_year

    block = {"document": "Pub X", "url": "u", "retrieved": "d", "sha256": "s"}
    stamp_edition_year(block, 2025)
    assert block["document"] == "Pub X (2025)"


def test_stamp_edition_year_leaves_sources_list_verbatim():
    from pipeline.extract import stamp_edition_year

    block = {"sources": [{"document": "FR-230 (2018)"}, {"document": "Notice 2022-08"}]}
    stamp_edition_year(block, 2018)  # regression: this KeyError'd all four dispatches
    assert block["sources"][0]["document"] == "FR-230 (2018)"
    assert block["sources"][1]["document"] == "Notice 2022-08"


def test_schema_version_bumps_for_sources():
    from pipeline import assemble

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {"rate": "0.0100"},
    }
    multi = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ", tax="state_income_withholding", method="flat_rate",
        extraction=extraction,
        source={"sources": [{"document": "a", "url": "u", "retrieved": "d", "sha256": "0" * 64},
                            {"document": "b", "url": "u", "retrieved": "d", "sha256": "1" * 64}]})
    single = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ", tax="state_income_withholding", method="flat_rate",
        extraction=extraction,
        source={"document": "a", "url": "u", "retrieved": "d", "sha256": "0" * 64})
    assert multi["schema_version"] == "0.2"
    assert single["schema_version"] == "0.1"


def test_single_document_list_collapses_to_source_block():
    # A one-entry `documents:` registry list (WI DWD HTML) must produce a
    # plain `source` block — the schema's `sources` array is minItems 2
    # (this exact shape failed the first us-wi-sui dispatch).
    from pipeline import assemble
    block = {"document": "DWD UI Tax Rates page (HTML)",
             "url": "https://dwd.wisconsin.gov/ui/employers/taxrates.htm",
             "retrieved": "2026-07-26", "sha256": "ab" * 32}
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-WI", tax="state_unemployment_insurance", method="sui",
        extraction={"classification": "new_year_edition",
                    "effective_from": "2026-01-01",
                    "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
                    "params": {"wage_base": "14000", "new_employer_rate": "0.0305",
                               "new_employer_rate_construction": None,
                               "rate_range": {"min": "0.0000", "max": "0.1200"},
                               "surtaxes": None}},
        source=block)
    assert "source" in raw and "sources" not in raw
    assert raw["schema_version"] == "0.1"
    from engine.loader import load_parameter_dict
    load_parameter_dict(raw)
