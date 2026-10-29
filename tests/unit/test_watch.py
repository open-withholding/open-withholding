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


def _stale_source():
    return {"id": "s", "document": "Doc", "jurisdiction": "US-ZZ",
            "tax": "state_income_withholding", "method": "flat_rate",
            "landing": "https://x.gov", "document_url_pattern": "https://x.gov/d.pdf",
            "check": ["content_hash"], "expected_window": "12-01..01-15"}


def _ok_fetcher(url, **kw):
    import hashlib
    return {"status": 200, "sha256": hashlib.sha256(b"%PDF x").hexdigest(),
            "etag": None, "last_modified": None, "is_pdf": True}


def test_staleness_not_flagged_for_window_before_first_seen():
    # First seen July 2026; the 12-01..01-15 window ended in January —
    # the watcher wasn't watching, so nothing was "missed" (#136-#154).
    import datetime as dt
    from pipeline.watch import check_source
    today = dt.date(2026, 7, 25)
    events, new = check_source(_stale_source(), {}, _ok_fetcher, today)  # baseline
    assert [e["type"] for e in events] == ["baseline"]
    assert new["first_seen"] == "2026-07-25"
    events, new2 = check_source(_stale_source(), new, _ok_fetcher,
                                dt.date(2026, 7, 26))
    assert [e["type"] for e in events] == []  # no stale event


def test_staleness_flags_once_a_watched_window_passes():
    import datetime as dt
    from pipeline.watch import check_source
    state = {"sha256": _ok_fetcher("u")["sha256"], "first_seen": "2026-07-25",
             "changed_at": None}
    # The NEXT season (12-01-2026..01-15-2027) passes with no change:
    events, new = check_source(_stale_source(), state, _ok_fetcher,
                               dt.date(2027, 2, 1))
    assert [e["type"] for e in events] == ["stale"]
    # ...and only once per season
    events, _ = check_source(_stale_source(), new, _ok_fetcher, dt.date(2027, 2, 2))
    assert [e["type"] for e in events] == []


def test_dispatch_failure_opens_issue_and_does_not_raise(monkeypatch):
    """Regression: 2026-07-27..09-25 every daily sweep died on an uncaught
    CalledProcessError from `gh workflow run` (the App token lacked
    actions:write), state was never persisted, and GitHub disabled the
    schedule for inactivity. A failed dispatch is an issue, not a crash."""
    from pipeline import watch

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        import subprocess
        if args[:3] == ["gh", "workflow", "run"]:
            return subprocess.CompletedProcess(
                args, 1, stdout="", stderr="HTTP 403: Resource not accessible by integration")
        if args[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(args, 0, stdout="0\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(watch.subprocess, "run", fake_run)
    ok_ = watch._dispatch_extract(SRC, 2026, dry_run=False)
    assert ok_ is False
    created = [c for c in calls if c[:3] == ["gh", "issue", "create"]]
    assert len(created) == 1
    title = created[0][created[0].index("--title") + 1]
    body = created[0][created[0].index("--body") + 1]
    assert title == "Watcher: us-zz-test dispatch_failed"
    assert "Resource not accessible by integration" in body
    assert "gh workflow run extract.yml -R" in body and "source_id=us-zz-test" in body
    assert "Actions: read & write" in body


def test_main_persists_state_and_exits_nonzero_when_a_dispatch_fails(monkeypatch, tmp_path):
    """The sweep finishes, state is written (the change was observed), and
    the run is red so the failure is visible — but it is not a traceback."""
    import json
    import subprocess

    from pipeline import watch

    changed = dict(SRC, id="us-aa-changed")
    quiet = dict(SRC, id="us-bb-quiet", document_url_pattern="https://y.gov/q_{year}.pdf")
    monkeypatch.setattr(watch.yaml, "safe_load", lambda _text: [changed, quiet])

    def fetcher(url, _retry=True, *, insecure=False, _ua=None):
        sha = ("n" if "x.gov" in url else "q") * 64
        return {"status": 200, "sha256": sha, "etag": None, "last_modified": None, "is_pdf": True}

    monkeypatch.setattr(watch, "default_fetcher", fetcher)
    issues = []

    def fake_run(args, **kwargs):
        if args[:3] == ["gh", "workflow", "run"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")
        if args[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(args, 0, stdout="0\n", stderr="")
        issues.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(watch.subprocess, "run", fake_run)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "us-aa-changed": {"sha256": "o" * 64, "changed_at": "2026-01-05"},
        "us-bb-quiet": {"sha256": "q" * 64, "changed_at": "2026-01-05"},
    }))
    monkeypatch.setattr(sys, "argv", ["watch.py", "--state", str(state_path), "--github"])

    assert watch.main() == 1
    persisted = json.loads(state_path.read_text())
    assert persisted["us-aa-changed"]["sha256"] == "n" * 64, "the observed change is recorded"
    assert "checked_at" in persisted["us-bb-quiet"], "the sweep continued past the failure"
    assert len(issues) == 1 and "dispatch_failed" in issues[0][issues[0].index("--title") + 1]


# --- successor_pattern (#168): the agency publishes each edition under a NEW
# filename and never deletes the old one, so a direct-URL watch sees nothing.

SUCC = {
    "id": "us-co-test",
    "document": "DR 1098",
    "landing": "https://tax.x.gov/DR1098",
    "document_url_pattern": "https://tax.x.gov/files/DR_1098_2024.pdf",
    "successor_pattern": "https://tax.x.gov/files/DR_1098_{year}.pdf",
}


def _succ_fetcher(live: set[str], sha="a" * 64):
    calls = []

    def fetcher(url):
        calls.append(url)
        if url in live:
            return {"status": 200, "sha256": sha if "2024" in url else "e" * 64,
                    "etag": None, "last_modified": None, "is_pdf": True}
        return {"status": 404, "sha256": None, "etag": None, "last_modified": None, "is_pdf": False}

    fetcher.calls = calls
    return fetcher


def test_successor_probe_finds_a_newer_edition_once():
    prior = {"sha256": "a" * 64, "changed_at": "2024-01-10", "url": SUCC["document_url_pattern"]}
    live = {SUCC["document_url_pattern"], "https://tax.x.gov/files/DR_1098_2026.pdf"}
    fetcher = _succ_fetcher(live)
    events, state = check_source(SUCC, prior, fetcher, TODAY)  # TODAY is 2026-07-09
    assert [e["type"] for e in events] == ["successor_found"]
    assert "DR_1098_2026.pdf is live" in events[0]["detail"]
    assert state["successors_seen"] == ["https://tax.x.gov/files/DR_1098_2026.pdf"]
    # Probed the neighbouring years, never re-fetched the file it already watches.
    probed = [u for u in fetcher.calls if u != SUCC["document_url_pattern"]]
    assert probed == [f"https://tax.x.gov/files/DR_1098_{y}.pdf" for y in (2025, 2026, 2027)]

    # Next sweep: the successor is remembered; no second event, no re-probe of it.
    fetcher2 = _succ_fetcher(live)
    events2, state2 = check_source(SUCC, state, fetcher2, TODAY)
    assert events2 == []
    assert "https://tax.x.gov/files/DR_1098_2026.pdf" not in fetcher2.calls
    assert state2["successors_seen"] == state["successors_seen"]


def test_successor_probe_is_quiet_when_nothing_newer_exists():
    prior = {"sha256": "a" * 64, "changed_at": "2024-01-10", "url": SUCC["document_url_pattern"]}
    events, state = check_source(SUCC, prior, _succ_fetcher({SUCC["document_url_pattern"]}), TODAY)
    assert events == []
    assert "successors_seen" not in state


def test_successor_probe_skipped_when_primary_changed():
    """A changed primary already dispatches an extraction — don't stack a probe on it."""
    prior = {"sha256": "b" * 64, "changed_at": "2024-01-10", "url": SUCC["document_url_pattern"]}
    live = {SUCC["document_url_pattern"], "https://tax.x.gov/files/DR_1098_2026.pdf"}
    fetcher = _succ_fetcher(live)
    events, _ = check_source(SUCC, prior, fetcher, TODAY)
    assert [e["type"] for e in events] == ["changed"]
    assert fetcher.calls == [SUCC["document_url_pattern"]]


# --- documents[].watch: false (#169): a Wayback snapshot is frozen by
# definition; polling it only earns 429s.

def test_unwatched_document_is_skipped_but_siblings_are_checked():
    src = {
        "id": "us-dc-test", "document": "FR-230 + friends", "landing": "https://x.gov",
        "documents": [
            {"name": "live", "kind": "pdf", "url": "https://x.gov/live.pdf"},
            {"name": "frozen", "kind": "html", "watch": False,
             "url": "https://web.archive.org/web/2025/https://x.gov/release"},
        ],
    }
    calls = []

    def fetcher(url):
        calls.append(url)
        return {"status": 200, "sha256": "f" * 64, "etag": None, "last_modified": None, "is_pdf": True}

    events, state = check_source(src, {}, fetcher, TODAY)
    assert calls == ["https://x.gov/live.pdf"]
    assert [e["type"] for e in events] == ["baseline"]
    assert set(state["documents"]) == {"live"}


def test_multi_document_entry_discovered_by_link_scan(monkeypatch):
    """A documents[] entry with landing + link_pattern is resolved each sweep;
    a newer release on the listing is a `changed` event (WA's ESD release)."""
    from pipeline import discover
    monkeypatch.setattr(discover, "discover_document_url",
                        lambda landing, pattern, year, *, insecure=False: "https://esd.x.gov/release/2026/rate-12-2027")
    src = {"id": "us-wa-test", "document": "WA PFML", "landing": "https://x.gov",
           "documents": [{"name": "release", "kind": "html", "landing": "https://esd.x.gov/news",
                          "link_pattern": "rate-", "url": "https://esd.x.gov/release/2025/rate-113-2026"}]}
    prior = {"documents": {"release": {"url": "https://esd.x.gov/release/2025/rate-113-2026",
                                       "sha256": "a" * 64, "changed_at": "2025-12-01"}}}
    seen = []

    def fetcher(url):
        seen.append(url)
        return {"status": 200, "sha256": "b" * 64, "etag": None, "last_modified": None, "is_pdf": False}

    events, state = check_source(src, prior, fetcher, TODAY)
    assert seen == ["https://esd.x.gov/release/2026/rate-12-2027"]
    assert [e["type"] for e in events] == ["changed"]
    assert state["documents"]["release"]["url"].endswith("rate-12-2027")


def test_multi_document_link_scan_failure_without_fallback_is_url_404(monkeypatch):
    from pipeline import discover

    def boom(landing, pattern, year, *, insecure=False):
        raise discover.DiscoveryError("no link matches")

    monkeypatch.setattr(discover, "discover_document_url", boom)
    src = {"id": "us-zz-test", "document": "d", "landing": "https://x.gov",
           "documents": [{"name": "rel", "kind": "html", "landing": "https://x.gov/news", "link_pattern": "zzz"}]}
    events, _ = check_source(src, {}, lambda url: None, TODAY)
    assert [e["type"] for e in events] == ["url_404"] and "link_scan failed" in events[0]["detail"]
