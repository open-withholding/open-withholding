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
