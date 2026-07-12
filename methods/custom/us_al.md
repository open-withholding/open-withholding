# Method: `custom/us_al` (v1)

Alabama's withholding formula (Form A-4 booklet, p.7): annualized gross
income less four deductions — a **stepped standard deduction** (printed
schedule, income-dependent), the employee's **annualized actual federal
withholding** (uncapped — the second user of the
`period_federal_income_withholding` input), a personal exemption by claim
code, and **income-tiered per-dependent amounts** — then two bracket
variants, de-annualized.

This spec is **normative**. `/engine/methods/custom/us_al.py` is the
reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_periods_per_year` **P**, `filing_status` = A-4 claim code
(`zero|s|ms|m|h`), `allowances` = number of dependents other than spouse,
`period_federal_income_withholding` (required; annualized ×P, no cap),
`additional_withholding`.

## Params

- `statuses[<code>]`: `personal_exemption` (0 / 1,500 / 3,000),
  `standard_deduction` rows `{at_least, amount}` — the printed Schedule of
  Standard Deduction Amounts, INCLUSIVE lower bound (last row with
  at_least ≤ GI; codes `zero` and `s` share the single schedule as
  printed), and `brackets` (ordinary convention; codes 0/S/H/MS share one
  printed variant, M has its own — duplicated per code)
- `dependent_tiers` — rows `{more_than, value}` on GI, EXCLUSIVE lower
  ("greater than $50,000"): GI exactly $50,000 → $1,000/dependent

## Algorithm

```
1. GI      = (gross − reducing pretax deductions, clamp 0) × P
2. A       = standard-deduction row for GI (inclusive-lower lookup)
   B       = period_federal_income_withholding × P
   C       = personal_exemption
   D       = allowances × dependent-tier amount for GI (exclusive-lower)
3. taxable = GI − (A + B + C + D); clamp 0
4. tax     = bracket(taxable)
5. withhold = r(tax ÷ P) + additional_withholding
```

## Notes (normative)

- The p.7 example displays the annualized federal amount rounded to the
  dollar ($35.19 × 52 shown as $1,830.00); exact arithmetic ($1,829.88)
  yields the same final cent ($29.59) — no rounding step is encoded, and
  the example reproduces either way.
- The formula text expresses the standard deduction as step arithmetic
  ("less $25 for each $500 increment or part thereof"); the printed p.8
  schedule is the same function in range form and is what's encoded —
  printed rows are authoritative.
