#!/usr/bin/env python3
"""The watcher (DESIGN §8.1): detection is free and constant.

Polls every source in pipeline/sources.yaml, compares content hashes (and
ETag/Last-Modified where honored) against the last-seen state, and reacts:

- changed            -> dispatch the Extract workflow for the source (the
                        extraction is event-driven; the human still reviews
                        and merges the resulting PR — never auto-merge)
- url_404            -> GitHub issue; for year-patterned URLs, also probes
                        the next year's URL (agencies move files constantly)
- stale              -> GitHub issue when a source's expected_window has
                        passed with no change (catches publication at a NEW
                        url while we watch a dead one)
- content_type_anomaly -> GitHub issue (HTML error page where a PDF should be)

Never a silent skip. State is a plain JSON mapping kept on the
`watcher-state` branch by the workflow (auditable history, no PR noise).

    python pipeline/watch.py --state watch-state.json [--github] [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from pipeline import discover  # noqa: E402
from pipeline.discover import substitute_year as _substitute_year  # noqa: E402

REPO = "open-withholding/open-withholding"


def default_fetcher(url: str, _retry: bool = True) -> dict:
    """GET the document; return bytes' hash + caching headers.

    Returns {"status": int, "sha256": str|None, "etag": str|None,
             "last_modified": str|None, "is_pdf": bool}."""
    request = urllib.request.Request(url, headers={"User-Agent": discover.BROWSER_UA})
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            data = resp.read()
            return {
                "status": resp.status,
                "sha256": hashlib.sha256(data).hexdigest(),
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
                "is_pdf": data[:4] == b"%PDF",
            }
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "sha256": None, "etag": None,
                "last_modified": None, "is_pdf": False}
    except Exception as exc:  # timeout, TLS, DNS — report, don't crash the sweep
        if _retry:
            import time

            time.sleep(5)  # several state sites drop the first connection
            return default_fetcher(url, _retry=False)
        return {"status": 0, "error": str(exc)[:200], "sha256": None,
                "etag": None, "last_modified": None, "is_pdf": False}


def _window_bounds(window: str, today: dt.date) -> tuple[dt.date, dt.date] | None:
    """expected_window "MM-DD..MM-DD" -> the most recent season's (start, end)
    with end <= today, handling year-end wrap (e.g. 12-01..01-15)."""
    try:
        start_s, end_s = window.split("..")
        sm, sd = (int(x) for x in start_s.split("-"))
        em, ed = (int(x) for x in end_s.split("-"))
    except ValueError:
        return None
    for year in (today.year, today.year - 1):
        end = dt.date(year, em, ed)
        start = dt.date(year if (sm, sd) <= (em, ed) else year - 1, sm, sd)
        if end <= today:
            return start, end
    return None


def _apply_staleness(source: dict, state: dict, new: dict, events: list[dict],
                     today: dt.date, last_change: dt.date | None) -> None:
    """Flag a source whose expected_window passed with no observed change."""
    window = source.get("expected_window")
    if not window:
        return
    bounds = _window_bounds(window, today)
    if not bounds:
        return
    start, end = bounds
    recently_flagged = state.get("stale_flagged_for") == end.isoformat()
    if (last_change is None or last_change < start) and not recently_flagged:
        events.append({"type": "stale",
                       "detail": f"expected_window {window} (ended {end}) passed "
                                 f"with no observed change; the agency may have "
                                 f"published at a new URL"})
        new["stale_flagged_for"] = end.isoformat()


def _check_documents(source: dict, state: dict, fetcher, today: dt.date) -> tuple[list[dict], dict]:
    """Multi-document sources: per-document state keyed by name; at most one
    `changed` event per source (a single extraction re-reads every document)."""
    events: list[dict] = []
    year = today.year
    new = dict(state)
    new["checked_at"] = today.isoformat()
    docs_state = dict(state.get("documents", {}))
    changed_details: list[str] = []

    for doc in source["documents"]:
        url = _substitute_year(doc["url"], year)
        kind = doc.get("kind", "pdf")
        prefix = f"[{doc['name']}] "
        old = docs_state.get(doc["name"], {})
        result = fetcher(url)
        if result["status"] == 404 or result["status"] == 0:
            detail = f"{url} -> {result.get('error', result['status'])}"
            if "{year}" in doc["url"] or "{yy}" in doc["url"]:
                next_url = _substitute_year(doc["url"], year + 1)
                if fetcher(next_url)["status"] == 200:
                    detail += f"; NOTE: next-year URL exists: {next_url}"
            events.append({"type": "url_404", "detail": prefix + detail})
            continue
        if result["status"] != 200:
            events.append({"type": "url_404", "detail": prefix + f"{url} -> HTTP {result['status']}"})
            continue
        if kind == "pdf" and not result["is_pdf"]:
            events.append({"type": "content_type_anomaly",
                           "detail": prefix + f"{url} returned non-PDF bytes (HTML error page?)"})
            continue
        entry = {"url": url, "sha256": result["sha256"], "etag": result.get("etag"),
                 "last_modified": result.get("last_modified"),
                 "changed_at": old.get("changed_at")}
        if old.get("sha256") is None:
            events.append({"type": "baseline",
                           "detail": prefix + f"{url} sha256={result['sha256'][:12]}..."})
        elif result["sha256"] != old["sha256"]:
            changed_details.append(
                prefix + f"{url}: {old['sha256'][:12]}... -> {result['sha256'][:12]}...")
            entry["changed_at"] = today.isoformat()
        docs_state[doc["name"]] = entry
    new["documents"] = docs_state

    if changed_details:
        events.append({"type": "changed", "detail": "; ".join(changed_details)})
        return events, new
    if any(e["type"] == "baseline" for e in events):
        return events, new  # first sighting — no staleness verdict yet

    changed_ats = [d.get("changed_at") for d in docs_state.values() if d.get("changed_at")]
    last_change = dt.date.fromisoformat(max(changed_ats)) if changed_ats else None
    _apply_staleness(source, state, new, events, today, last_change)
    return events, new


def check_source(source: dict, state: dict, fetcher, today: dt.date) -> tuple[list[dict], dict]:
    """Pure logic: one source -> (events, new state entry). No side effects."""
    if source.get("documents"):
        return _check_documents(source, state, fetcher, today)

    events: list[dict] = []
    year = today.year
    new = dict(state)
    new["checked_at"] = today.isoformat()

    # Resolve the current document URL.
    url = None
    if source.get("document_url_pattern"):
        url = _substitute_year(source["document_url_pattern"], year)
    else:
        try:
            url = discover.discover_document_url(
                source["landing"], source["link_pattern"], year,
                insecure=source.get("insecure_tls", False),
            )
        except discover.DiscoveryError as exc:
            events.append({"type": "url_404", "detail": f"link_scan failed: {exc}"})
            return events, new
        except Exception as exc:
            events.append({"type": "url_404", "detail": f"landing fetch failed: {exc}"})
            return events, new
    new["url"] = url

    result = fetcher(url)
    if result["status"] == 404 or result["status"] == 0:
        detail = f"{url} -> {result.get('error', result['status'])}"
        # Agencies move year-patterned files; probe next year's name.
        if source.get("document_url_pattern") and (
            "{year}" in source["document_url_pattern"] or "{yy}" in source["document_url_pattern"]
        ):
            next_url = _substitute_year(source["document_url_pattern"], year + 1)
            if fetcher(next_url)["status"] == 200:
                detail += f"; NOTE: next-year URL exists: {next_url}"
        events.append({"type": "url_404", "detail": detail})
        return events, new
    if result["status"] != 200:
        events.append({"type": "url_404", "detail": f"{url} -> HTTP {result['status']}"})
        return events, new
    if not result["is_pdf"]:
        events.append({"type": "content_type_anomaly",
                       "detail": f"{url} returned non-PDF bytes (HTML error page?)"})
        return events, new

    if state.get("sha256") is None:
        # First sighting: record a baseline silently — the data for already-
        # extracted sources came from these same bytes.
        new.update(sha256=result["sha256"], etag=result.get("etag"),
                   last_modified=result.get("last_modified"),
                   changed_at=state.get("changed_at"))
        events.append({"type": "baseline", "detail": f"{url} sha256={result['sha256'][:12]}..."})
        return events, new

    if result["sha256"] != state["sha256"]:
        events.append({"type": "changed",
                       "detail": f"{url}: {state['sha256'][:12]}... -> {result['sha256'][:12]}..."})
        new.update(sha256=result["sha256"], etag=result.get("etag"),
                   last_modified=result.get("last_modified"), changed_at=today.isoformat())
        return events, new

    # Unchanged — staleness check against the most recent completed window.
    changed_at = state.get("changed_at")
    last_change = dt.date.fromisoformat(changed_at) if changed_at else None
    _apply_staleness(source, state, new, events, today, last_change)
    return events, new


def _github_issue(title: str, body: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would open issue: {title}")
        return
    existing = subprocess.run(
        ["gh", "issue", "list", "-R", REPO, "--state", "open",
         "--search", f'in:title "{title}"', "--json", "number", "--jq", "length"],
        capture_output=True, text=True,
    )
    if existing.returncode == 0 and existing.stdout.strip() not in ("", "0"):
        print(f"  issue already open, skipping: {title}")
        return
    subprocess.run(["gh", "issue", "create", "-R", REPO, "--title", title, "--body", body],
                   check=True, capture_output=True, text=True)
    print(f"  opened issue: {title}")


def _dispatch_extract(source: dict, year: int, dry_run: bool) -> None:
    args = ["gh", "workflow", "run", "extract.yml", "-R", REPO,
            "-f", f"source_id={source['id']}", "-f", f"year={year}"]
    if source.get("no_printed_examples"):
        args += ["-f", "no_examples_ok=true"]
    if dry_run:
        print(f"  [dry-run] would dispatch: {' '.join(args[3:])}")
        return
    subprocess.run(args, check=True, capture_output=True, text=True)
    print(f"  dispatched extraction for {source['id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, help="Path to the state JSON file")
    parser.add_argument("--github", action="store_true",
                        help="Open issues / dispatch extractions (else report only)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sources = yaml.safe_load((REPO_ROOT / "pipeline" / "sources.yaml").read_text())
    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    today = dt.date.today()

    summary: dict[str, int] = {}
    for source in sources:
        entry = state.get(source["id"], {})
        events, new_entry = check_source(source, entry, default_fetcher, today)
        state[source["id"]] = new_entry
        for event in events:
            summary[event["type"]] = summary.get(event["type"], 0) + 1
            print(f"{source['id']}: {event['type']} — {event['detail']}")
            if not args.github:
                continue
            if event["type"] == "changed":
                _dispatch_extract(source, today.year, args.dry_run)
            elif event["type"] in ("url_404", "stale", "content_type_anomaly"):
                _github_issue(
                    f"Watcher: {source['id']} {event['type']}",
                    f"**Source:** `{source['id']}` — {source['document']}\n\n"
                    f"**Event:** `{event['type']}`\n\n**Detail:** {event['detail']}\n\n"
                    f"Landing: {source['landing']}\n\n"
                    f"Opened automatically by the watcher (DESIGN §8.1); "
                    f"close after resolving the source registry or confirming the false alarm.",
                    args.dry_run,
                )

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    checked = len(sources)
    print(f"\nwatched {checked} source(s): " +
          (", ".join(f"{k}={v}" for k, v in sorted(summary.items())) or "all unchanged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
