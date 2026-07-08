# /pipeline

Automation that keeps /data current: a cheap cron **watcher** that detects
changed publications, an LLM-assisted **extractor** that turns a changed PDF
into a candidate YAML + golden tests, and mechanical validation that gates a
PR for **human review**. See DESIGN.md §8 for the full design.

Status: not yet implemented. `sources.yaml` is the registry the watcher will
consume; entries added here are commitments to watch that source.

Principles (normative, from the design):

- Detection is free and constant; extraction is expensive and event-driven;
  the human reviews diffs, never raw PDFs.
- Every failure mode opens a GitHub issue (`changed`, `url_404`, `stale`,
  `content_type_anomaly`) — never a silent skip.
- Extraction and verification run in separate LLM contexts with different
  framings; candidates that fail mechanical validation become triage issues,
  not PRs.
- Every retrieved PDF is archived immutably, keyed by sha256.
- **Never auto-merge.** The human merge is the trust product.
