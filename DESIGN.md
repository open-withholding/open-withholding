# Open Withholding — Design Document

**Status:** draft v0.1 · seed document for local iteration
**Scope:** Tier 1 US payroll parameters + reference engine + update pipeline

---

## 1. Intent

An open, citation-backed, machine-readable dataset of US payroll tax
parameters (federal, state, and centrally-published locals), plus a small
reference engine that turns those parameters into per-paycheck withholding
amounts, plus automation that keeps the dataset current with minimal human
effort.

**The product is trust.** Every number in this repo must be traceable to a
government publication (URL + retrieval date + document hash), and every
calculation method must reproduce the worked examples printed in those
publications. A stranger should be able to audit any value in under a minute.

### Goals (Tier 1)

- Federal income tax withholding (Pub 15-T, both W-4 regimes, percentage method)
- FICA (SS + Medicare + Additional Medicare), FUTA, supplemental wage rates
- Annual limits constellation: SS wage base, 401(k)/403(b), catch-up, HSA, FSA
- All 42 state/DC income tax withholding formulas
- SUI wage bases + new-employer default rates (employer's actual experience
  rate is always a user input, never data)
- State disability / paid-leave employee withholding where flat-rate
  (CA SDI, NY PFL, WA PFML, NJ, etc.)
- Centrally-published local tax tables only: IN counties, MD counties,
  PA Act 32 register, OH municipal + school district lists, NYC/Yonkers
- Pre-tax deduction taxability matrix (which deduction types reduce which
  wage bases, per jurisdiction, including state nonconformity)
- Reference engine (Python) + golden test corpus from published worked examples

### Non-goals (Tier 1)

- Address → jurisdiction assignment (user selects jurisdictions from lists)
- Experience-rated SUI rates (per-employer, not public data)
- Forms generation / e-filing (Tier 2+; printable 941/940/W-2 live in the
  consuming application, not this repo)
- Garnishments, grossed-up pay, third-party sick pay (Tier 3)
- State reciprocity resolution (Tier 2; the data model reserves room for it)
- Tax *filing* tables (1040-style) — this is withholding only

### Positioning

Closest prior art is PolicyEngine US (YAML parameters + coded formulas +
citations), aimed at tax simulation. This project aims at per-paycheck
withholding, which PolicyEngine does not model. Commercial equivalents:
Symmetry, Vertex, the tax-table subscriptions inside Sage 50 / QuickBooks
Desktop. This repo replaces the *data layer* of those subscriptions, not
their filing services or liability guarantees.

---

## 2. Repository layout

```
/schema/                    JSON Schema for every file type in /data
    withholding.schema.json
    employee-input.schema.json
    sui.schema.json
    limits.schema.json
/methods/                   One .md spec per calculation method (normative)
    annualized_percentage.md
    flat_rate.md
    ...
/data/us/
    federal/2026/
        withholding.yaml    Pub 15-T percentage method, both W-4 regimes
        fica.yaml
        futa.yaml
        limits.yaml         401k, HSA, FSA, supplemental rates, SS wage base
    ca/2026/
        withholding.yaml
        sui.yaml
        sdi.yaml
    pa/2026/
        withholding.yaml
        locals/act32.csv    Converted DCED register (large; CSV not YAML)
    ...one directory per state...
/taxability/
    us.yaml                 deduction-type × wage-base matrix + state overrides
/engine/                    Reference implementation (Python, pure functions)
    pipeline.py             The generic 7-stage pipeline
    methods/                One module per method; custom/ for oddball states
    inputs.py               Employee input validation
/tests/
    golden/                 Worked examples transcribed from publications
        us-federal-2026-*.yaml
        us-ca-2026-*.yaml
    unit/
/pipeline/                  Automation (see §8) — may split to its own repo later
```

Rule of thumb: **/data and /schema are the product; /engine proves the data
is usable; /pipeline is plumbing.** Consumers may depend on /data alone.

---

## 3. Data model

### 3.1 Universal envelope

Every parameter file, regardless of tax type, carries the same envelope:

```yaml
jurisdiction: US-CO           # ISO-3166-2 style; US, US-CA, US-PA-<PSD> for locals
tax: state_income_withholding # enum, see schema
effective_from: 2026-01-01
effective_to: null            # open-ended until superseded
supersedes: us/co/2025/withholding.yaml   # optional back-pointer
source:
  document: "DR 1098 Colorado Withholding Worksheet"
  url: "https://tax.colorado.gov/sites/tax/files/documents/DR1098_2026.pdf"
  retrieved: 2025-12-18
  sha256: "ab3f19..."         # hash of the retrieved PDF
  notes: "Rates from p.4, worked examples p.7-8"
method: flat_rate_with_annual_allowance
params: { ... }               # method-specific, validated per-method by schema
rounding: { to: 1.00, mode: nearest }   # applied where the method spec says
```

Design rules:

- **Effective dating everywhere.** The engine entry point takes an as-of
  date. A mid-year revision is a new file with a later `effective_from`;
  the old file gets `effective_to` set in the same PR. Retroactive
  corrections are representable (a new file can have `effective_from` in
  the past; consumers decide their own re-run policy).
- **Numbers are exact.** Currency as decimal strings or integer cents in
  JSON contexts; rates as decimal strings ("0.0440"). No binary floats in
  data files. The engine uses Decimal.
- **Provenance is mandatory.** CI rejects any data file without a complete
  `source` block.
- **One tax per file.** Withholding, SUI, and SDI are separate files even
  for the same state, because they update on different schedules and cite
  different documents.

### 3.2 Withholding params by example

Flat-rate state:

```yaml
method: flat_rate_with_annual_allowance
params:
  rate: "0.0440"
  filing_status:
    single:  { annual_allowance: "4500" }
    married: { annual_allowance: "9000" }
```

Bracket state (the common case):

```yaml
method: annualized_percentage
params:
  standard_deduction:
    single: "2440"
    married: "4880"
  allowance_amount: "1000"          # per allowance claimed
  brackets:                          # applied to annualized taxable income
    single:
      - { over: "0",      rate: "0.0110" }
      - { over: "3324",   rate: "0.0220" }
      - { over: "8280",   rate: "0.0450" }
      # ...
    married:
      - { over: "0",      rate: "0.0110" }
      # ...
  credit_per_allowance: null        # some states use credits instead
```

Bracket rows use `over` (lower bound) only; upper bounds are implied by the
next row. This eliminates a class of transcription errors (overlapping or
gapped ranges) and matches how most guides print the percentage method.

**All numeric values above are illustrative placeholders, not real 2026
rates.** Real values enter only through the pipeline with source citations.

### 3.3 Federal specifics

`federal/<year>/withholding.yaml` must encode Pub 15-T's structure:

- Two W-4 regimes: `w4_2020_plus` and `w4_pre_2020`, each with its own
  parameter block.
- For 2020+: standard vs. higher (Step 2 checkbox) bracket tables per
  filing status; Steps 3 (dependents credit), 4a (other income), 4b
  (deductions), 4c (extra withholding) enter the pipeline at defined stages
  (see method spec §5).
- For pre-2020: allowance amount × allowances claimed.
- Supplemental flat rates (optional flat method, and the mandatory
  high-earner rate) live in `limits.yaml`.

### 3.4 SUI / SDI files

```yaml
tax: state_unemployment_insurance
params:
  wage_base: "34400"
  new_employer_rate: "0.0340"
  new_employer_rate_construction: "0.0620"   # where applicable
  rate_range: { min: "0.0010", max: "0.0970" }  # informational
  surtaxes:                                   # ETT-style add-ons
    - { name: "Employment Training Tax", rate: "0.0010", wage_base: "7000" }
employer_rate_is_user_input: true             # always true; engine requires it
```

### 3.5 Taxability matrix

`/taxability/us.yaml` maps deduction types to the wage bases they reduce:

```yaml
deduction_types:
  401k_traditional:
    federal_income: reduces
    fica: does_not_reduce
    futa: does_not_reduce
    state_income_default: reduces
    state_overrides: { US-PA: does_not_reduce, US-NJ: does_not_reduce }
  hsa_cafeteria:
    federal_income: reduces
    fica: reduces
    state_income_default: reduces
    state_overrides: { US-CA: does_not_reduce, US-NJ: does_not_reduce }
  # ...
```

State overrides each require a `source` citation (usually a line in that
state's withholding guide). This matrix is small but high-stakes; it gets
its own golden tests.

---

## 4. Method registry

A **method** is a named, versioned, precisely-specified algorithm. The spec
in `/methods/<name>.md` is normative; `/engine/methods/<name>.py` is the
reference implementation; the JSON Schema constrains which `params` shapes
each method accepts.

Expected Tier 1 registry (~10 methods covers ~45 jurisdictions):

| method | used by (approx.) |
|---|---|
| `federal_percentage_2020` | US federal, 2020+ W-4 |
| `federal_percentage_pre2020` | US federal, legacy W-4 |
| `flat_rate` | PA, and locals (IN/MD/OH/PA counties & municipalities) |
| `flat_rate_with_annual_allowance` | CO, IL, MI, UT-style |
| `annualized_percentage` | ~25 bracket states |
| `annualized_percentage_with_credits` | states using credits not deductions |
| `wage_bracket_lookup` | optional alternative where a state only prints tables |
| `custom/us_ct`, `custom/us_ar`, `custom/us_ms`, `custom/us_pr` | escape hatch |

**Escape-hatch discipline:** if the `custom/` list grows past ~10, the
method decomposition is wrong — stop and refactor rather than adding an
11th. Custom methods still read every constant from their YAML file; only
control flow lives in code.

---

## 5. Method spec: `annualized_percentage` (v1)

This is the normative text that would live at
`/methods/annualized_percentage.md`. It doubles as the template for all
other method specs.

### Inputs

From the employee input record (§6): `gross_wages` (this period),
`pretax_deductions` (typed list, this period), `pay_periods_per_year` P,
`filing_status`, `allowances` A (integer ≥ 0), `additional_withholding`
(optional per-period amount).

From params: `standard_deduction[filing_status]` SD,
`allowance_amount` AA, `brackets[filing_status]`,
optional `credit_per_allowance` CPA, envelope `rounding`.

### Algorithm

All arithmetic in Decimal. Let `r(x)` = apply the envelope rounding rule.

```
1. taxable_period  = gross_wages
                     − Σ pretax_deductions that reduce state_income
                       (per /taxability, with this state's overrides)
   If taxable_period < 0, set 0.

2. annual_wages    = taxable_period × P

3. annual_taxable  = annual_wages − SD − (A × AA)
   If annual_taxable < 0, set 0.

4. annual_tax      = bracket(annual_taxable)
   where bracket(x): find last row with over ≤ x; tax = Σ over completed
   brackets of (bracket_width × rate) + (x − row.over) × row.rate.
   (Equivalently, most guides print base_tax + rate × excess; the schema
   permits an optional printed `base` per row. A printed base is
   authoritative — worked examples use it — and is validated at load time
   against the recomputed cumulative sum within a small tolerance, because
   agencies round printed thresholds while deriving base columns from
   unrounded amounts. Learned from Pub 15-T 2026, checkbox-single table.)

5. if CPA: annual_tax = max(0, annual_tax − A × CPA)

6. period_tax      = annual_tax ÷ P

7. withhold        = r(period_tax) + additional_withholding
```

### Sequencing and rounding notes (normative)

- Rounding is applied **once, at step 7**, unless the jurisdiction's guide
  demonstrates intermediate rounding in its worked examples, in which case
  the YAML sets `rounding.intermediate: annual` and step 4's result is
  rounded before step 6. **The worked examples decide.** When a guide's
  example cannot be reproduced, the transcription or the sequencing is
  wrong — never ship a file whose golden tests fail.
- Division in step 6 is exact Decimal division; only `r()` rounds.
- Negative results clamp to 0 at steps 1, 3, 5. Withholding is never
  negative.

### Out of scope for this method

Supplemental wages, cumulative/percentage-of-YTD methods (a few states
offer them as alternatives; we implement the standard method only in v1).

---

## 6. Employee input schema (versioned)

The engine consumes a normalized record; the accounting application maps
its employee master onto this. Sketch:

```yaml
pay_frequency: biweekly        # enum → P (weekly=52, biweekly=26, semimonthly=24, monthly=12, ...)
gross_wages: "2400.00"
pretax_deductions:
  - { type: 401k_traditional, amount: "120.00" }
  - { type: hsa_cafeteria,    amount: "50.00" }
ytd:                           # required for caps
  social_security_wages: "31200.00"
  medicare_wages: "31200.00"
federal:
  w4_version: 2020             # or pre_2020
  filing_status: married_joint # federal enum
  step2_checkbox: false
  step3_credits: "2000"
  step4a_other_income: "0"
  step4b_deductions: "0"
  step4c_extra: "0"
state:
  - jurisdiction: US-CA
    filing_status: married     # per-state enum; schema defines each state's
    allowances: 2              # legal statuses and which fields apply
    additional_withholding: "0"
locals:
  - { jurisdiction: US-PA-PSD-700102, resident: true }
employer:
  sui_jurisdiction: US-CA
  sui_experience_rate: "0.0340"   # user-entered from the state rate notice
```

Notes:

- Filing-status enums are **per-jurisdiction** (federal has no allowances
  post-2020; many states kept them; some states have statuses the federal
  system lacks). The schema publishes each jurisdiction's valid statuses
  and required fields so UIs can render the right form.
- YTD wage figures are inputs, not state — the engine is a pure function.
  Wage-base caps (SS, SUI, SDI) and the Additional Medicare threshold are
  computed from YTD + current period.

---

## 7. Golden tests

Every publication's worked examples are transcribed to
`/tests/golden/<jurisdiction>-<year>-<n>.yaml`:

```yaml
source: { document: "Pub 15-T (2026)", page: 11, example: 1 }
input:  { ...employee input record... }
expect: { federal_withholding: "171.00" }
```

Policy:

- A data PR that changes a jurisdiction's parameters MUST update or add
  that jurisdiction's golden tests from the new publication, and CI must
  pass. **No worked example transcribed → PR not mergeable** (rare guides
  without examples get maintainer-constructed cases cross-checked against
  the state's own online calculator where one exists, noted as such).
- Golden tests are the primary defense against LLM extraction errors and
  the primary trust signal to outside consumers: CI publicly proves the
  repo reproduces the government's own answers.
- Target: ≥ 2 examples per jurisdiction per year, covering different
  filing statuses.

---

## 8. Update pipeline

Three decoupled stages. The design principle: **detection is free and
constant; extraction is expensive and event-driven; the human reviews
diffs, never raw PDFs** (the PDF is one click away when needed).

```
watcher (cron, cheap, no LLM)
   └─ change detected ─→ extractor (LLM, per-document)
                             └─ opens PR ─→ human review ─→ merge
```

### 8.1 Watcher

- `pipeline/sources.yaml` — the registry of every watched source:

  ```yaml
  - id: us-federal-p15t
    landing: "https://www.irs.gov/forms-pubs/about-publication-15-t"
    document_url_pattern: "https://www.irs.gov/pub/irs-pdf/p15t.pdf"
    check: [etag, content_hash]
    expected_window: "12-01..01-15"   # for staleness alerts, not gating
    maps_to: [data/us/federal/{year}/withholding.yaml]
  - id: us-co-dr1098
    landing: "https://tax.colorado.gov/withholding-tax-guidance"
    discovery: link_scan               # find the PDF link on the landing page
    link_pattern: "DR ?1098"
    ...
  ```

- Each run (daily; hourly during Nov–Jan): fetch, compare
  ETag/Last-Modified where honored, else hash the bytes. On change, archive
  the new PDF (see 8.4) and enqueue an extraction job.
- Distinct alert states, each opening a GitHub issue rather than failing
  silently: `changed`, `url_404` (agencies move files constantly —
  for year-versioned URLs, also probe the next-year pattern),
  `stale` (expected_window passed with no change — catches the case where
  the agency published at a *new* URL and we're watching a dead one),
  `content_type_anomaly` (HTML error page where a PDF should be).
- Watch the **landing page** for sources with unstable document URLs;
  `link_scan` discovery handles "find the current-year PDF link."

### 8.2 Extractor

Per changed document, an LLM-assisted job that must produce a PR or a
triage issue — never a silent failure:

1. **Classify:** is this a parameter change, a cosmetic re-issue (agencies
   silently replace PDFs to fix typos), or a new-year edition?
2. **Extract:** prompt the model with the method spec + last year's YAML +
   the new PDF; ask for the new YAML. Structured output against the JSON
   Schema.
3. **Independently verify (separate context):** a second pass that
   receives only the PDF and the *candidate YAML* and must confirm every
   number with a page citation, plus extract the worked examples into
   golden-test fixtures. Extraction and verification in separate calls with
   different framings is the cheap insurance against a single
   hallucinated-but-plausible table.
4. **Mechanical validation:** schema check; bracket monotonicity; any
   precomputed `base` recomputed; golden tests run against the reference
   engine. A candidate that fails goes to a triage issue with the diff and
   the failure, not to a PR.
5. **Open PR:** one PR per source document. Body contains: parameter diff
   (old → new), source URL + pages, golden-test results, the model's page
   citations, and a checklist for the reviewer.

Cost note: this corpus is ~120 documents/year; even generous multi-pass
extraction is cents-to-a-dollar per document. Optimize for reviewer
minutes, not tokens.

**Print-defect adjudications.** Occasionally the published document itself
is internally inconsistent (a rate or cumulative base that contradicts the
document's own bracket chaining — see MD 2026, NJ 2020). A faithful
transcription then deterministically fails mechanical validation, which is
the validator working as intended. The registry entry may carry an
`adjudications` list — the ONLY sanctioned path by which a data file
deviates from print. Each entry states the exact printed (defective) value,
the correction, and a justification derivable from the document's own
arithmetic. The pipeline applies corrections after independent verification
(the verifier must confirm the transcription as printed) and before
mechanical validation, and only when the transcription matches `printed`
exactly (already-corrected transcriptions no-op; anything else fails the
run — so a revised document invalidates stale adjudications loudly).
Every application is rendered in the PR body and counted in the data
file's source notes; a defect report to the issuing agency accompanies
the adjudication.

### 8.3 Human review

The maintainer's entire recurring job:

- Open the PR, read the diff (a rate change is a one-line diff).
- Spot-check 2–3 numbers against the linked PDF pages.
- Confirm golden tests are new (transcribed from the new edition, not
  carried over) — CI flags fixtures whose `source.document` year doesn't
  match the data year.
- Merge, or correct in-place and merge.

Budget: single-digit minutes per document, concentrated Dec–Jan
(~12 docs/week at peak), near-zero the rest of the year.

### 8.4 Source archival

Every retrieved PDF is archived immutably (S3/Spaces bucket or a separate
`sources-archive` repo/LFS), keyed by sha256, referenced from the data
file's `source.sha256`. Rationale: agencies replace and delete PDFs; the
citation is only auditable if we keep the exact bytes we extracted from.
Government publications are public domain — redistribution is fine.

### 8.5 Hosting

- **Watcher + extractor:** a $6 DigitalOcean droplet is ample, but note
  GitHub Actions scheduled workflows can run the whole thing free
  (cron + PR creation are native; the LLM API key lives in repo secrets).
  Recommendation: start on Actions; move to a droplet only if job length
  or scheduling precision becomes a problem. Fewer moving parts, and the
  pipeline's runs are publicly visible, which is itself a trust signal.
- **Never auto-merge.** Even a perfect pipeline shouldn't; the human merge
  is the trust product. The repo's promise is "every number was reviewed."

---

## 9. Versioning & releases

- Data repo tags releases as `2026.0`, `2026.1`, ... (year + revision);
  consumers pin a tag. A release aggregates merged PRs; the changelog is
  generated from PR titles (`us-co: 2026 withholding, rate 4.40% → 4.25%`).
- `/schema` and `/methods` carry their own semver; a data file declares
  `schema_version`. Method spec changes that alter results for identical
  params are **major** and require a new method name if old-year files
  must keep reproducing old-year golden tests (specs are effectively
  immutable once a year ships against them).
- Publish `/data` compiled to a single JSON bundle per release as a build
  artifact, so consumers who don't want YAML/git can fetch one file.

---

## 10. Trust, licensing, liability

- **License:** data under CC0 or ODC-PDDL (it's facts + government works;
  claim nothing), code under MIT/Apache-2.0. Zero-friction licensing is a
  feature — commercial payroll tools adopting the dataset grows the
  reviewer pool.
- **Disclaimer:** prominent README language — no warranty, not tax advice,
  verify against official publications, employers remain responsible for
  their filings. This is the standard posture and consumers expect it.
- **Trust signals, in priority order:** public CI running golden tests;
  per-value provenance; archived source PDFs; visible human review on
  every merge; the staleness dashboard (which sources are current vs.
  awaiting this year's edition).

---

## 11. Open questions (deliberately unresolved)

1. Monorepo (this layout) vs. splitting `/pipeline` out once stable.
2. Wage-bracket tables (the printed lookup grids) as data: skip entirely
   (percentage method suffices) or include for states whose guides *only*
   publish grids?
3. Local tax identifiers: PA PSD codes are official; OH/KY need a chosen
   canonical ID scheme.
4. Reciprocity representation (Tier 2) — reserve `jurisdiction_rules/`?
5. How to represent states with elective employee rates (AZ's
   percentage-election model) in the employee input schema.

## 12. Glossary & caveats

- **All numeric values in this document are illustrative placeholders**,
  including rates, wage bases, and bracket figures. Real values enter the
  repo only through the pipeline with citations.
- Pub 15-T = federal withholding methods; Pub 15/Circular E = employer
  rules & FICA; SUI = state unemployment insurance; SDI/PFML = state
  disability / paid family leave; Act 32 / PSD = Pennsylvania's local
  earned-income-tax system and its political-subdivision codes; EFW2 =
  SSA's W-2 e-file format (Tier 2).
