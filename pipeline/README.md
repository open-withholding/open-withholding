# /pipeline

Automation that keeps /data current: a cron **watcher** that detects
changed publications, an LLM-assisted **extractor** that turns a PDF (or a
multi-document set) into a candidate YAML + golden tests, and mechanical
validation that gates a PR for **human review**. See DESIGN.md §8. All of
it is implemented and operational; the dataset's 43 jurisdictions were
seeded through this exact machinery.

## Extractor

Normally dispatched via the Extract workflow (by the watcher on a changed
document, or by hand); it can also run locally:

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
   `tests/golden/`, PR body into `pipeline/out/<source>-<year>-pr.md`. In
   CI the pipeline's GitHub App bot opens the PR (one PR per source
   document); a human reviews and merges it.

Between verification and validation, any registry `adjudications` for the
source are applied — guarded print-defect corrections that only take
effect when the transcription matches the declared printed value, rendered
loudly in the PR body (DESIGN.md §8.2). Sources whose publications print
no worked examples dispatch with `no_examples_ok`; maintainer-constructed,
engine-computed golden cases are then required on the PR before the
data-golden-guard check passes.

**Never auto-merge.** The human merge is the trust product.

## Running in GitHub Actions (bot-authored PRs)

`.github/workflows/extract.yml` runs the same extractor via manual dispatch
and opens the PR as the pipeline's **GitHub App bot**, so history visibly
separates "pipeline proposed" (bot author) from "human reviewed and merged"
(maintainer). One-time setup:

1. **Create a GitHub App** (Settings → Developer settings → GitHub Apps →
   New): name it something like `open-withholding-pipeline`; disable the
   webhook; repository permissions **Contents: read & write**, **Pull
   requests: read & write**, **Issues: read & write** (triage reports);
   installable only on your account.
2. After creating: note the **App ID**, then **generate a private key**
   (downloads a `.pem`).
3. **Install the app** on this repository (app page → Install App).
4. **Repo secrets** (Settings → Secrets and variables → Actions):
   `PIPELINE_APP_ID`, `PIPELINE_APP_PRIVATE_KEY` (the full `.pem` contents),
   and `ANTHROPIC_API_KEY`.
5. Dispatch the workflow (Actions → Extract → Run workflow) with a
   `source_id` and `year`.

Failures upload the triage report as an artifact and open a GitHub issue as
the bot. The archived source PDF is kept as a 90-day build artifact — a
stopgap until the durable sha256-keyed archive (DESIGN §8.4) exists.

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

## Watcher

`watch.py`, run by `.github/workflows/watch.yml` on a daily cron (hourly
during the Nov–Jan publication season). Detection is free and constant;
every outcome is loud: a `changed` document dispatches the Extract
workflow for that source, while `url_404`, `stale` (a source's
`expected_window` passed with no change), and `content_type_anomaly` each
open a GitHub issue — never a silent skip. State lives on the
`watcher-state` branch: an auditable history without PR noise on main.
The watcher deliberately imports only PyYAML-weight modules, never the
engine — the workflow installs nothing else (regression-guarded in
`tests/unit/test_watch.py`).
