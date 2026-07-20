# /data

The product: citation-backed payroll withholding parameters, laid out as
`us/<jurisdiction>/<year>/<tax>.yaml`. Currently populated with state and
federal income withholding for 43 jurisdictions (federal + all 41
income-taxing states + DC), 2026 editions; jurisdictions with mid-year
revisions (Georgia, Utah) carry one file per effective window.

Every value here entered through the update pipeline (DESIGN.md §8):
retrieved from a government publication, extracted with page citations,
independently verified against that publication in a fresh context, and
human-reviewed in a PR. No number may be added by hand. Each file carries a
complete `source` block (document, URL, retrieval date, sha256 of the
archived document — or a `sources` list for multi-document citations) and
is exercised by golden tests transcribed from the same publication's worked
examples.

The only sanctioned deviation from print is a maintainer adjudication of a
publication defect (DESIGN.md §8.2): declared in the source registry with
the printed value, the correction, and a justification derived from the
document's own arithmetic; disclosed in the PR body and counted in the
file's `source.notes`.

`tools/validate_data.py` and CI enforce the parts of this a machine can
check.
