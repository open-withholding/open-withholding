"""Landing-page link discovery: find the current edition's PDF URL.

Only the IRS keeps documents at stable URLs; most agencies publish through a
CMS whose file paths move with every revision. A `link_scan` source watches a
stable landing page and scans its anchors for the link matching
`link_pattern`. Selection rules, learned from real state sites:

- Prefer a match mentioning the target year; otherwise take the newest year
  found among matches (agencies don't reissue when nothing changed — in 2026
  Colorado's current DR 1098 is still the 2024 edition).
- Ambiguity is an error, never a guess: multiple candidates with no year to
  distinguish them goes to triage (DESIGN §8.1: fail loud, not silently).
"""

from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

# Several state tax sites (Drupal/CDN-fronted) return 403 to non-browser
# user agents — our honest "open-withholding/0.1" UA is rejected outright.
# We identify via the repo instead; the watcher touches each source at most
# daily (hourly Nov-Jan), far below any abusive rate.
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

_YEAR = re.compile(r"20\d{2}")


class DiscoveryError(Exception):
    pass


def substitute_year(pattern: str, year: int) -> str:
    """{year} -> 2026, {yy} -> 26 (LA's 1306-1-{yy}.pdf, ME's {yy}_wh_tab_instr.pdf).

    Lives here (not extract.py) so the watcher can import it without pulling
    in the engine and its dependencies — the watch workflow installs only
    PyYAML."""
    return pattern.replace("{year}", str(year)).replace("{yy}", f"{year % 100:02d}")


def fetch(url: str, *, timeout: int = 120, insecure: bool = False) -> bytes:
    """`insecure` disables TLS verification for the handful of agencies that
    serve incomplete certificate chains (dor.ms.gov). The sha256 archive and
    human review still gate what the bytes are used for."""
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    context = None
    if insecure:
        import ssl

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(request, timeout=timeout, context=context) as resp:
        return resp.read()


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # (href, text)
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = _AnchorParser()
    parser.feed(html)
    return [(urljoin(base_url, href), text) for href, text in parser.links if href]


def select_document_url(
    links: list[tuple[str, str]], link_pattern: str, year: int, *, landing: str = "?"
) -> str:
    pattern = re.compile(link_pattern, re.IGNORECASE)
    matches: dict[str, str] = {}  # href -> text; dedupe repeated anchors
    for href, text in links:
        if pattern.search(href) or pattern.search(text):
            matches.setdefault(href, text)
    if not matches:
        raise DiscoveryError(
            f"{landing}: no link matches {link_pattern!r} — the agency may have moved "
            f"the document (watcher state: stale/url_404)"
        )
    if len(matches) == 1:
        return next(iter(matches))

    def years_of(href: str) -> list[int]:
        return [int(y) for y in _YEAR.findall(href + " " + matches[href])]

    exact = [h for h in matches if year in years_of(h)]
    if len(exact) == 1:
        return exact[0]
    candidates = exact or list(matches)
    dated = [(max(years_of(h)), h) for h in candidates if years_of(h)]
    if dated:
        best_year = max(y for y, _ in dated)
        best = [h for y, h in dated if y == best_year]
        if len(best) == 1:
            return best[0]
        candidates = best
    # CMS mirrors: the same document linked under multiple path prefixes
    # (observed on revenue.nebraska.gov: /sites/default/files/... and
    # /sites/revenue.nebraska.gov/files/... for one filename). One shared
    # basename means one document — pick deterministically.
    if len({h.rsplit("/", 1)[-1].lower() for h in candidates}) == 1:
        return sorted(candidates)[0]
    raise DiscoveryError(
        f"{landing}: {link_pattern!r} is ambiguous — candidates: "
        + ", ".join(sorted(matches))
    )


def discover_document_url(
    landing: str, link_pattern: str, year: int, *, insecure: bool = False
) -> str:
    html = fetch(landing, insecure=insecure).decode("utf-8", errors="replace")
    return select_document_url(
        extract_links(html, landing), link_pattern, year, landing=landing
    )
