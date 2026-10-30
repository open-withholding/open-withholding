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
- successor_found    -> GitHub issue: a source with `successor_pattern` has a
                        NEWER year's file live beside the one we watch (CMSs
                        never delete the old edition, so a direct-URL watch
                        would otherwise miss the reissue silently)

A document entry with `watch: false` (a frozen Wayback snapshot, say) is
skipped by the watcher but still fetched by the extractor.

Never a silent skip. State is a plain JSON mapping kept on the
`watcher-state` branch by the workflow (auditable history, no PR noise).

    python pipeline/watch.py --state watch-state.json [--github] [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
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


OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def content_sha256(data: bytes) -> str:
    """sha256 of the document as watched. Legacy Excel exports (PA DCED's
    Act 32 register) embed a generation timestamp, so their bytes differ on
    every download while the cells do not; for an OLE2 workbook the hash is
    of the cell values instead (xlrd; falls back to bytes when xlrd is not
    installed)."""
    if data[:8] == OLE2_MAGIC:
        try:
            import io
            import xlrd
            book = xlrd.open_workbook(file_contents=data, logfile=io.StringIO())
            h = hashlib.sha256()
            for sheet in book.sheets():
                h.update(sheet.name.encode())
                for r in range(sheet.nrows):
                    h.update(repr(sheet.row_values(r)).encode())
            return h.hexdigest()
        except ImportError:
            pass
        except Exception:
            pass  # not a workbook xlrd can read: hash the bytes
    return hashlib.sha256(data).hexdigest()


def default_fetcher(url: str, _retry: bool = True, *, insecure: bool = False,
                    _ua: str | None = None) -> dict:
    """GET the document; return bytes' hash + caching headers.

    `insecure` disables TLS verification for registry entries flagged
    insecure_tls (dor.ms.gov's broken chain). A 403 on the browser UA is
    retried once with the honest UA — mass.gov's Akamai rejects a browser
    UA from a non-browser TLS stack (the exact inverse of the sites the
    browser UA exists for).

    Returns {"status": int, "sha256": str|None, "etag": str|None,
             "last_modified": str|None, "is_pdf": bool}."""
    request = urllib.request.Request(
        url, headers={"User-Agent": _ua or discover.BROWSER_UA})
    context = None
    if insecure:
        import ssl

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(request, timeout=120, context=context) as resp:
            data = resp.read()
            return {
                "status": resp.status,
                "sha256": content_sha256(data),
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
                "is_pdf": data[:4] == b"%PDF",
            }
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and _ua is None:
            return default_fetcher(url, _retry, insecure=insecure,
                                   _ua=discover.HONEST_UA)
        return {"status": exc.code, "sha256": None, "etag": None,
                "last_modified": None, "is_pdf": False}
    except Exception as exc:  # timeout, TLS, DNS — report, don't crash the sweep
        if _retry:
            import time

            time.sleep(5)  # several state sites drop the first connection
            return default_fetcher(url, _retry=False, insecure=insecure, _ua=_ua)
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
    """Flag a source whose expected_window passed with no observed change —
    but ONLY for windows the watcher was actually watching. A source first
    seen AFTER a window closed cannot have "missed" that season's
    publication (the baseline IS the current edition); the first persisted
    sweep fired 19 of these at once (#136-#154) before this guard."""
    window = source.get("expected_window")
    if not window:
        return
    bounds = _window_bounds(window, today)
    if not bounds:
        return
    start, end = bounds
    # Effective first-seen: the stamped date, else the last recorded change
    # (proof we were watching then), else backfill today and stay silent —
    # a freshly-baselined source has missed nothing.
    first_seen_s = (state.get("first_seen") or new.get("first_seen")
                    or state.get("changed_at")
                    or (last_change.isoformat() if last_change else None))
    if not first_seen_s:
        new["first_seen"] = today.isoformat()
        return
    new.setdefault("first_seen", first_seen_s)
    if dt.date.fromisoformat(first_seen_s) > start:
        return  # not watching when this window opened — nothing was missed
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
        if doc.get("watch", True) is False:
            continue  # frozen input (archive snapshot): the extractor reads it, nobody polls it
        kind = doc.get("kind", "pdf")
        prefix = f"[{doc['name']}] "
        old = docs_state.get(doc["name"], {})
        try:
            url = discover.resolve_document_url(
                doc, year, insecure=source.get("insecure_tls", False))
        except discover.DiscoveryError as exc:
            events.append({"type": "url_404", "detail": prefix + f"link_scan failed: {exc}"})
            continue
        except Exception as exc:  # landing fetch failed
            events.append({"type": "url_404", "detail": prefix + f"landing fetch failed: {exc}"})
            continue
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
        new.setdefault("first_seen", today.isoformat())
        return events, new  # first sighting — no staleness verdict yet

    changed_ats = [d.get("changed_at") for d in docs_state.values() if d.get("changed_at")]
    last_change = dt.date.fromisoformat(max(changed_ats)) if changed_ats else None
    _apply_staleness(source, state, new, events, today, last_change)
    return events, new


def _probe_successors(source: dict, state: dict, new: dict, events: list[dict],
                      fetcher, today: dt.date) -> None:
    """For a source watched at a fixed URL whose agency publishes each edition
    under a NEW filename (tax.colorado.gov/.../DR_1098_2024.pdf), look for the
    neighbouring years' names. A live PDF at a name we do not already watch is
    a `successor_found` event — reported once per URL (state remembers it),
    and it means the registry needs updating, so it opens an issue rather than
    dispatching an extraction that would re-read the old file."""
    pattern = source.get("successor_pattern")
    if not pattern:
        return
    current = new.get("url") or state.get("url")
    seen = list(state.get("successors_seen", []))
    for year in (today.year - 1, today.year, today.year + 1):
        candidate = _substitute_year(pattern, year)
        if candidate == current or candidate in seen:
            continue
        result = fetcher(candidate)
        if result["status"] == 200 and result.get("is_pdf", True):
            events.append({"type": "successor_found",
                           "detail": f"{candidate} is live (sha256={result['sha256'][:12]}...) "
                                     f"while the registry watches {current}; update "
                                     f"document_url_pattern and dispatch an extraction"})
            seen.append(candidate)
    if seen:
        new["successors_seen"] = seen


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
                   changed_at=state.get("changed_at"),
                   first_seen=state.get("first_seen") or today.isoformat())
        events.append({"type": "baseline", "detail": f"{url} sha256={result['sha256'][:12]}..."})
        return events, new

    if result["sha256"] != state["sha256"]:
        events.append({"type": "changed",
                       "detail": f"{url}: {state['sha256'][:12]}... -> {result['sha256'][:12]}..."})
        new.update(sha256=result["sha256"], etag=result.get("etag"),
                   last_modified=result.get("last_modified"), changed_at=today.isoformat())
        return events, new

    # Unchanged — staleness check against the most recent completed window,
    # then look for a newer edition published beside this one.
    changed_at = state.get("changed_at")
    last_change = dt.date.fromisoformat(changed_at) if changed_at else None
    _apply_staleness(source, state, new, events, today, last_change)
    _probe_successors(source, state, new, events, fetcher, today)
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


def _dispatch_extract(source: dict, year: int, dry_run: bool) -> bool:
    """Dispatch the Extract workflow; on failure, open an issue and return False.

    A failed dispatch must not abort the sweep: the 2026-07-27 Maine change
    hit a token without `actions: write`, the uncaught CalledProcessError
    killed every daily run before state was persisted, and GitHub eventually
    disabled the schedule for inactivity. The change is still recorded in
    state (it was observed), so the issue is the hand-off — it carries the
    exact command for a human to run."""
    args = ["gh", "workflow", "run", "extract.yml", "-R", REPO,
            "-f", f"source_id={source['id']}", "-f", f"year={year}"]
    if source.get("no_printed_examples"):
        args += ["-f", "no_examples_ok=true"]
    if dry_run:
        print(f"  [dry-run] would dispatch: {' '.join(args[3:])}")
        return True
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  dispatched extraction for {source['id']}")
        return True
    detail = (result.stderr or result.stdout or "").strip() or f"exit status {result.returncode}"
    print(f"  DISPATCH FAILED for {source['id']}: {detail}", file=sys.stderr)
    _github_issue(
        f"Watcher: {source['id']} dispatch_failed",
        f"**Source:** `{source['id']}` — {source['document']}\n\n"
        f"**Event:** `dispatch_failed` — the document changed but the watcher could not "
        f"start the Extract workflow.\n\n**Error:**\n```\n{detail}\n```\n\n"
        f"The change IS recorded in watcher state, so it will not be re-dispatched. "
        f"Run the extraction by hand:\n\n```\n{' '.join(args)}\n```\n\n"
        f"If the error is a permissions failure, the pipeline GitHub App needs "
        f"**Actions: read & write** (pipeline/README.md, setup step 1).\n\n"
        f"Opened automatically by the watcher (DESIGN §8.1).",
        dry_run,
    )
    return False


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
    failures = 0
    for source in sources:
        entry = state.get(source["id"], {})
        source_fetcher = functools.partial(
            default_fetcher, insecure=source.get("insecure_tls", False))
        events, new_entry = check_source(source, entry, source_fetcher, today)
        state[source["id"]] = new_entry
        for event in events:
            summary[event["type"]] = summary.get(event["type"], 0) + 1
            print(f"{source['id']}: {event['type']} — {event['detail']}")
            if not args.github:
                continue
            if event["type"] == "changed":
                if not _dispatch_extract(source, today.year, args.dry_run):
                    failures += 1
            elif event["type"] in ("url_404", "stale", "content_type_anomaly", "successor_found"):
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
    if failures:
        print(f"{failures} dispatch(es) failed — see the dispatch_failed issue(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
