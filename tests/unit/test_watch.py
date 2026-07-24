import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pipeline.watch import _window_bounds, check_source

TODAY = dt.date(2026, 7, 9)
SRC = {
    "id": "us-zz-test",
    "document": "Test Guide",
    "landing": "https://x.gov/wh",
    "document_url_pattern": "https://x.gov/guide_{year}.pdf",
    "expected_window": "12-01..01-31",
}


def ok(sha="a" * 64):
    return lambda url: {"status": 200, "sha256": sha, "etag": 'W/"x"',
                        "last_modified": "Mon", "is_pdf": True}


def test_first_sighting_records_baseline_silently():
    events, state = check_source(SRC, {}, ok(), TODAY)
    assert [e["type"] for e in events] == ["baseline"]
    assert state["sha256"] == "a" * 64
    assert state["url"] == "https://x.gov/guide_2026.pdf"


def test_unchanged_is_quiet():
    prior = {"sha256": "a" * 64, "changed_at": "2026-01-05"}
    events, state = check_source(SRC, prior, ok(), TODAY)
    assert events == []
    assert state["sha256"] == "a" * 64


def test_change_detected():
    prior = {"sha256": "b" * 64, "changed_at": "2025-12-20"}
    events, state = check_source(SRC, prior, ok(), TODAY)
    assert [e["type"] for e in events] == ["changed"]
    assert state["sha256"] == "a" * 64
    assert state["changed_at"] == TODAY.isoformat()


def test_404_probes_next_year():
    def fetcher(url):
        if "2027" in url:
            return {"status": 200, "sha256": "c" * 64, "etag": None,
                    "last_modified": None, "is_pdf": True}
        return {"status": 404, "sha256": None, "etag": None,
                "last_modified": None, "is_pdf": False}

    events, _ = check_source(SRC, {"sha256": "b" * 64}, fetcher, TODAY)
    assert events[0]["type"] == "url_404"
    assert "next-year URL exists" in events[0]["detail"]


def test_html_where_pdf_expected():
    fetcher = lambda url: {"status": 200, "sha256": "d" * 64, "etag": None,
                           "last_modified": None, "is_pdf": False}
    events, _ = check_source(SRC, {"sha256": "b" * 64}, fetcher, TODAY)
    assert [e["type"] for e in events] == ["content_type_anomaly"]


def test_stale_when_window_passed_without_change():
    prior = {"sha256": "a" * 64, "changed_at": "2024-12-15"}  # changed two seasons ago
    events, state = check_source(SRC, prior, ok(), TODAY)
    assert [e["type"] for e in events] == ["stale"]
    # flagged once per season, not every run
    events2, _ = check_source(SRC, state, ok(), TODAY)
    assert events2 == []


def test_change_within_window_is_not_stale():
    prior = {"sha256": "a" * 64, "changed_at": "2025-12-20"}
    events, _ = check_source(SRC, prior, ok(), TODAY)
    assert events == []


def test_window_bounds_wrap():
    start, end = _window_bounds("12-01..01-31", dt.date(2026, 7, 9))
    assert (start, end) == (dt.date(2025, 12, 1), dt.date(2026, 1, 31))
    start, end = _window_bounds("09-15..10-31", dt.date(2026, 7, 9))
    assert (start, end) == (dt.date(2025, 9, 15), dt.date(2025, 10, 31))


MULTI_SRC = {
    "id": "us-zz-multi",
    "document": "Test Multi Guide",
    "landing": "https://x.gov/wh",
    "documents": [
        {"name": "guide", "kind": "html", "url": "https://x.gov/guide"},
        {"name": "tables", "kind": "pdf", "url": "https://x.gov/tables_{year}.pdf"},
    ],
    "expected_window": "12-01..01-31",
}


def _multi_fetcher(shas):
    def fetch(url):
        sha = shas[url]
        return {"status": 200, "sha256": sha, "etag": None,
                "last_modified": None, "is_pdf": url.endswith(".pdf")}
    return fetch


def test_multi_document_baseline_per_document():
    fetch = _multi_fetcher({"https://x.gov/guide": "a" * 64,
                            "https://x.gov/tables_2026.pdf": "b" * 64})
    events, state = check_source(MULTI_SRC, {}, fetch, TODAY)
    assert [e["type"] for e in events] == ["baseline", "baseline"]
    assert state["documents"]["guide"]["sha256"] == "a" * 64
    assert state["documents"]["tables"]["sha256"] == "b" * 64


def test_multi_document_single_changed_event_when_both_move():
    prior = {"documents": {
        "guide": {"sha256": "0" * 64, "changed_at": "2025-12-20"},
        "tables": {"sha256": "1" * 64, "changed_at": "2025-12-20"},
    }}
    fetch = _multi_fetcher({"https://x.gov/guide": "a" * 64,
                            "https://x.gov/tables_2026.pdf": "b" * 64})
    events, state = check_source(MULTI_SRC, prior, fetch, TODAY)
    # One combined event -> main() dispatches exactly one extraction.
    assert [e["type"] for e in events] == ["changed"]
    assert "guide" in events[0]["detail"] and "tables" in events[0]["detail"]
    assert state["documents"]["guide"]["changed_at"] == TODAY.isoformat()


def test_multi_document_one_changed_one_quiet():
    prior = {"documents": {
        "guide": {"sha256": "a" * 64, "changed_at": "2025-12-20"},
        "tables": {"sha256": "1" * 64, "changed_at": "2025-12-20"},
    }}
    fetch = _multi_fetcher({"https://x.gov/guide": "a" * 64,
                            "https://x.gov/tables_2026.pdf": "b" * 64})
    events, state = check_source(MULTI_SRC, prior, fetch, TODAY)
    assert [e["type"] for e in events] == ["changed"]
    assert "[tables]" in events[0]["detail"] and "[guide]" not in events[0]["detail"]
    assert state["documents"]["guide"]["changed_at"] == "2025-12-20"


def test_multi_document_html_bytes_are_not_an_anomaly():
    # kind: html must not trip the PDF content check; kind: pdf still does.
    def fetch(url):
        return {"status": 200, "sha256": "c" * 64, "etag": None,
                "last_modified": None, "is_pdf": False}
    events, _ = check_source(MULTI_SRC, {}, fetch, TODAY)
    types = sorted(e["type"] for e in events)
    assert types == ["baseline", "content_type_anomaly"]
    anomaly = next(e for e in events if e["type"] == "content_type_anomaly")
    assert anomaly["detail"].startswith("[tables]")


def test_multi_document_stale_uses_latest_document_change():
    prior = {"documents": {
        "guide": {"sha256": "a" * 64, "changed_at": "2025-11-01"},
        "tables": {"sha256": "b" * 64, "changed_at": "2025-11-15"},
    }}
    fetch = _multi_fetcher({"https://x.gov/guide": "a" * 64,
                            "https://x.gov/tables_2026.pdf": "b" * 64})
    events, state = check_source(MULTI_SRC, prior, fetch, TODAY)
    # Window 12-01..01-31 ended 2026-01-31 with no change since 2025-11-15.
    assert [e["type"] for e in events] == ["stale"]
    assert state["stale_flagged_for"] == "2026-01-31"
    # A change inside the window suppresses staleness.
    prior["documents"]["tables"]["changed_at"] = "2026-01-05"
    events, _ = check_source(MULTI_SRC, prior, fetch, TODAY)
    assert events == []


def test_watch_does_not_import_the_engine():
    # The watch workflow installs only PyYAML; importing pipeline.watch must
    # not drag in pipeline.extract -> engine -> jsonschema (this exact chain
    # broke the daily cron: ModuleNotFoundError on the runner).
    import subprocess
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent.parent
    code = (
        "import sys; sys.path.insert(0, r'%s'); import pipeline.watch; "
        "bad = [m for m in sys.modules if m.startswith('engine') or m == 'pipeline.extract' "
        "or m == 'jsonschema']; assert not bad, bad" % repo
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_default_fetcher_falls_back_to_honest_ua_on_403(monkeypatch):
    # mass.gov 403s the browser UA but accepts the honest UA
    import io
    import urllib.error
    import urllib.request
    from pipeline import discover, watch

    calls = []

    def fake_urlopen(request, timeout=None, context=None):
        ua = request.get_header("User-agent")
        calls.append(ua)
        if ua == discover.BROWSER_UA:
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b""))

        class R:
            status = 200
            headers = {}

            def read(self):
                return b"%PDF fake"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            class headers:  # noqa: N801 — minimal stand-in
                @staticmethod
                def get(_k):
                    return None

        return R()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = watch.default_fetcher("https://example.gov/x.pdf")
    assert result["status"] == 200 and result["is_pdf"]
    assert calls == [discover.BROWSER_UA, discover.HONEST_UA]


def test_default_fetcher_threads_insecure_context(monkeypatch):
    import urllib.request
    from pipeline import watch

    seen = {}

    def fake_urlopen(request, timeout=None, context=None):
        seen["context"] = context

        class R:
            status = 200

            def read(self):
                return b"%PDF"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            class headers:  # noqa: N801
                @staticmethod
                def get(_k):
                    return None

        return R()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    watch.default_fetcher("https://dor.ms.gov/x.pdf", insecure=True)
    assert seen["context"] is not None and seen["context"].check_hostname is False
