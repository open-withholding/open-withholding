#!/usr/bin/env python3
"""PR guard: a change to a jurisdiction's withholding parameters MUST come
with golden tests for that jurisdiction transcribed from the new publication
(DESIGN.md §7: no worked example -> not mergeable).

CI runs this on pull requests:  python tools/check_data_golden.py origin/main
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from pipeline.assemble import WITHHOLDING_TAXES, golden_slug  # noqa: E402


def changed_paths(base_ref: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"], cwd=REPO_ROOT, text=True
    )
    return [line for line in out.splitlines() if line.strip()]


def missing_golden(changed: list[str], read_yaml) -> list[str]:
    """For each changed withholding data file, require a changed golden file
    named <jurisdiction-slug>-<year>-*. `read_yaml(path)` returns the parsed
    mapping, or None for deleted/unreadable files (deletions are exempt —
    retiring a file needs no new examples)."""
    errors = []
    for path in changed:
        if not (path.startswith("data/") and path.endswith((".yaml", ".yml"))):
            continue
        raw = read_yaml(path)
        if not isinstance(raw, dict) or raw.get("tax") not in WITHHOLDING_TAXES:
            continue
        slug = golden_slug(raw["jurisdiction"], raw["tax"])
        year = str(raw["effective_from"])[:4]
        prefix = f"tests/golden/{slug}-{year}-"
        if not any(p.startswith(prefix) for p in changed):
            errors.append(
                f"{path}: changes {raw['jurisdiction']} parameters but no golden test "
                f"matching {prefix}* was added or updated in this PR"
            )
    return errors


def main() -> int:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"

    def read_yaml(rel: str):
        path = REPO_ROOT / rel
        if not path.exists():
            return None
        try:
            return yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            return None  # schema validation reports the parse error

    errors = missing_golden(changed_paths(base_ref), read_yaml)
    for error in errors:
        print(f"ERROR {error}")
    if not errors:
        print("data/golden guard: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
