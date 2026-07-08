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
  transcribed → PR not mergeable.**
- Guides without printed examples get maintainer-constructed cases
  cross-checked against the state's own online calculator where one exists,
  noted as such in `source`.
- Target: ≥ 2 examples per jurisdiction per year, covering different filing
  statuses.

This directory is empty until real data lands. Illustrative cases that
exercise the runner live in `/tests/fixtures/golden`.
