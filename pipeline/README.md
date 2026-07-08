# /pipeline

Automation that keeps /data current: a cheap cron **watcher** that detects
changed publications (not yet implemented), an LLM-assisted **extractor**
that turns a PDF into a candidate YAML + golden tests, and mechanical
validation that gates a PR for **human review**. See DESIGN.md §8.

## Extractor (implemented)

Drive it manually per document — this is also how the dataset gets seeded,
so seeding exercises the exact machinery that will do steady-state updates:

```sh
export ANTHROPIC_API_KEY=...          # or `ant auth login`
python pipeline/extract.py us-federal-p15t --year 2026
python pipeline/extract.py us-co-dr1098 --year 2026 --pdf ~/Downloads/DR1098_2026.pdf
```

Stages (each visible in the output):

1. **Fetch + archive** — download (or take `--pdf`), verify it's a PDF,
   archive to `archive/<sha256>.pdf`. The sha256 goes into the data file's
   `source` block; provenance never comes from the model.
2. **Extract** — Claude reads the PDF plus the normative method spec and the
   prior edition's YAML (shape reference only), and returns structured
   parameters with page citations.
3. **Independently verify** — a second call in a *fresh context* receives
   only the PDF and the candidate YAML; it must confirm every number with a
   page citation and transcribe every applicable worked example.
4. **Mechanical validation** — JSON Schema, bracket monotonicity/`base`
   recomputation, then the reference engine must reproduce every transcribed
   worked example. Any failure → triage report in `pipeline/out/`, no
   candidate files.
5. **Write candidate** — parameter file into `data/`, golden fixtures into
   `tests/golden/`, PR body into `pipeline/out/<source>-<year>-pr.md`. A
   human reviews the diff and opens the PR (one PR per source document).

**Never auto-merge.** The human merge is the trust product.

## Registry

`sources.yaml` — one entry per watched publication. `jurisdiction`, `tax`,
and `method` tell the extractor what it's transcribing; the model never
chooses them. Entries added here are commitments to watch that source.

## CI guards

- `tools/check_data_golden.py` (PR-only job): a changed withholding data
  file with no changed `tests/golden/<jurisdiction>-<year>-*` fixture fails
  the PR — the no-worked-example-no-merge rule, enforced mechanically.
- `tools/setup_branch_protection.sh <owner>/<repo>`: one-time GitHub setup —
  requires the CI checks on main, blocks direct pushes and force pushes,
  including for admins.

## Watcher (not yet implemented)

Principles from the design: detection is free and constant; every failure
mode opens a GitHub issue (`changed`, `url_404`, `stale`,
`content_type_anomaly`) — never a silent skip.
