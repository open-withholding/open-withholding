# Golden test corpus

Worked examples transcribed from government publications, one file per
example: `<jurisdiction>-<year>-<n>.yaml`.

```yaml
source: { document: "Pub 15-T (2026)", page: 11, example: 1 }
as_of: 2026-06-15            # date used to select effective parameter files
input:  { ...employee input record, see /schema/employee-input.schema.json... }
expect: { federal_withholding: "171.00" }
```

`expect` keys: `federal_withholding`, `state_withholding`,
`local_withholding`. State/local values may be a scalar (single election in
the input) or a mapping keyed by jurisdiction.

Policy (from DESIGN.md §7):

- A data PR that changes a jurisdiction's parameters MUST update or add that
  jurisdiction's golden tests from the new publication. **No worked example
  transcribed → PR not mergeable** (enforced by the data-golden-guard CI
  job).
- Guides without printed examples (DC, MD) get maintainer-constructed
  cases: inputs chosen by the maintainer, expected values **computed by the
  reference engine** — never hand arithmetic — and noted as such in
  `source.example`.
- A printed example that contradicts its own publication's arithmetic is
  excluded by maintainer adjudication, documented in the data file's
  `source.notes` (NJ's truncated worksheet constants, NY's two Examples 2).
- Target: ≥ 2 examples per jurisdiction per year, covering different filing
  statuses.

The corpus currently holds 141 fixtures across the 43 covered
jurisdictions. Illustrative cases that exercise the runner live in
`/tests/fixtures/golden`.
