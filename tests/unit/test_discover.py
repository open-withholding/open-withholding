import pytest

from pipeline.discover import DiscoveryError, extract_links, select_document_url

# Modeled on tax.colorado.gov/DR1098: a year-versioned employer PDF, an
# undated employee-worksheet decoy, and unrelated links.
HTML = """
<html><body>
  <a href="/forms-by-tax-type">Forms</a>
  <a href="/sites/tax/files/documents/DR_1098_2024.pdf">DR 1098 Employer Worksheet</a>
  <a href="/sites/tax/files/documents/DR_1098_Colorado_Withholding_Worksheet_for_Employees.pdf">
    DR 1098 for Employees</a>
  <a href="/sites/tax/files/documents/DR_1098_2024.pdf">duplicate anchor</a>
</body></html>
"""
BASE = "https://tax.colorado.gov/DR1098"
PATTERN = r"DR[_ ]?1098[_ ]?20\d{2}.*\.pdf"


def test_relative_urls_absolutized():
    links = extract_links(HTML, BASE)
    assert ("https://tax.colorado.gov/forms-by-tax-type", "Forms") in links


def test_year_pattern_excludes_undated_decoy_and_dedupes():
    links = extract_links(HTML, BASE)
    url = select_document_url(links, PATTERN, 2026, landing=BASE)
    assert url == "https://tax.colorado.gov/sites/tax/files/documents/DR_1098_2024.pdf"


def test_exact_year_preferred_over_newer():
    links = [
        ("https://x.gov/guide_2025.pdf", "Guide 2025"),
        ("https://x.gov/guide_2026.pdf", "Guide 2026 draft"),
    ]
    assert select_document_url(links, r"guide.*\.pdf", 2025) == "https://x.gov/guide_2025.pdf"


def test_newest_year_wins_when_target_absent():
    links = [
        ("https://x.gov/guide_2023.pdf", ""),
        ("https://x.gov/guide_2024.pdf", ""),
    ]
    assert select_document_url(links, r"guide.*\.pdf", 2026) == "https://x.gov/guide_2024.pdf"


def test_no_match_fails_loud():
    with pytest.raises(DiscoveryError, match="no link matches"):
        select_document_url([("https://x.gov/other.pdf", "Other")], r"guide", 2026)


def test_undated_ambiguity_fails_loud():
    links = [
        ("https://x.gov/guide_a.pdf", "Guide"),
        ("https://x.gov/guide_b.pdf", "Guide"),
    ]
    with pytest.raises(DiscoveryError, match="ambiguous"):
        select_document_url(links, r"guide", 2026)


def test_match_on_anchor_text():
    links = [("https://x.gov/f/8813", "DR 1098 2024 Withholding Worksheet (PDF)")]
    assert select_document_url(links, PATTERN.replace(r"\.pdf", ""), 2026) == "https://x.gov/f/8813"


def test_cms_mirrors_of_same_basename_resolve():
    # revenue.nebraska.gov links one booklet under two path prefixes.
    links = [
        ("https://x.gov/sites/default/files/doc/2026cir_en_whole.pdf", "Circular EN"),
        ("https://x.gov/sites/x.gov/files/doc/2026cir_en_whole.pdf", "Circular EN"),
    ]
    url = select_document_url(links, r"20\d{2}cir_en_whole\.pdf", 2026)
    assert url == "https://x.gov/sites/default/files/doc/2026cir_en_whole.pdf"


def test_distinct_basenames_still_ambiguous():
    links = [
        ("https://x.gov/a/guide_2026.pdf", ""),
        ("https://x.gov/b/tables_2026.pdf", ""),
    ]
    import pytest as _pytest
    with _pytest.raises(DiscoveryError, match="ambiguous"):
        select_document_url(links, r"20\d{2}", 2026)
