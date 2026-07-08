# /data

**Empty by design — for now.** Real tax parameters enter this tree only
through the update pipeline (DESIGN.md §8): retrieved from a government
publication, extracted with citations, verified against that publication's
worked examples, and human-reviewed in a PR.

No number may be added here by hand without a complete `source` block
(document, URL, retrieval date, sha256 of the archived PDF) and golden tests
transcribed from the same publication. `tools/validate_data.py` and CI
enforce the parts of that a machine can check.

Layout, once populated: `us/<jurisdiction>/<year>/<tax>.yaml` — see
DESIGN.md §2.
