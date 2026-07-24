#!/usr/bin/env python3
"""Verify the source archive: every sha256 cited by a data file or by the
taxability matrix must exist in archive/ and hash to its own name.

    python tools/verify_archive.py

The citation is only auditable if the exact bytes are retained (agencies
replace and delete documents); this is the mechanical check that we have
them. Run before cutting a release; the release attaches the archive as
assets."""

from __future__ import annotations

import glob
import hashlib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def cited_hashes() -> dict[str, str]:
    want: dict[str, str] = {}
    for p in glob.glob(str(REPO_ROOT / "data" / "**" / "*.yaml"), recursive=True):
        d = yaml.safe_load(open(p))
        if not isinstance(d, dict):
            continue
        for b in d.get("sources") or ([d["source"]] if "source" in d else []):
            want[b["sha256"]] = p
    tax = yaml.safe_load((REPO_ROOT / "taxability" / "us.yaml").read_text())
    for key, src in (tax.get("sources") or {}).items():
        want[src["sha256"]] = f"taxability/us.yaml#{key}"
    return want


def main() -> int:
    want = cited_hashes()
    errors = []
    for sha, cited_by in sorted(want.items()):
        files = [f for f in (REPO_ROOT / "archive").glob(f"{sha}.*")
                 if f.suffix in (".pdf", ".html")]
        if not files:
            errors.append(f"MISSING {sha} (cited by {cited_by})")
            continue
        if hashlib.sha256(files[0].read_bytes()).hexdigest() != sha:
            errors.append(f"CORRUPT {files[0]} (cited by {cited_by})")
    for e in errors:
        print(f"ERROR {e}")
    if not errors:
        print(f"archive OK: {len(want)} cited documents present and hash-verified")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
