<!-- For data PRs, the extractor generates a body (pipeline/out/*-pr.md) with
     the parameter diff, page citations, verification results, and golden-test
     status — use that as the PR body and complete the checklist below.
     For code/schema/docs PRs, delete the data checklist. -->

## Summary

<!-- What changed and why. Data PRs: one PR per source document. -->

## Data PR checklist (delete if not a data PR)

- [ ] One source document only; complete `source` block (document, URL, retrieval date, sha256)
- [ ] Golden tests added/updated, transcribed from **this** edition's worked examples
- [ ] Spot-checked 2–3 values against the linked PDF pages (reviewer)
- [ ] Rounding block matches what the worked examples actually do
- [ ] Prior-year file's `effective_to` / `supersedes` updated if this supersedes it
- [ ] CI green: schema validation, bracket consistency, golden corpus
