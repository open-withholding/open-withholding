# Method: `custom/us_ca` (v1)

California Method B — Exact Calculation (EDD Withholding Schedules,
`{yy}methb.pdf`, part of DE 44). Five printed steps:

    1. gross ≤ Table 1 low-income exemption        → withhold 0
    2. wages   = gross − Table 2 estimated-deduction amount
                 (DE 4 additional allowances for estimated deductions)
    3. taxable = wages − Table 3 standard deduction
    4. tax     = Tables 5–28 bracket computation (base + rate × excess)
    5. withhold = max(0, tax − Table 4 exemption allowance credit)

This spec is **normative**. `/engine/methods/custom/us_ca.py` is the
reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_frequency`, `filing_status` (`single`, `married`,
`head_of_household` — DE 4's "single or married with two or more incomes"
box and married-with-multiple-employers both map to `single`),
`allowances` (REGULAR withholding allowances — Table 4 credits and the
married column split), `secondary_allowances` (DE 4 additional allowances
for estimated deductions — Table 2 only; footnote 1: these must NOT be
counted in the Table 4 credit), `additional_withholding`.

From params (all printed values transcribed verbatim):

- `low_income_exemption[frequency][column]` — Table 1
- `estimated_deduction[frequency]` — Table 2: list of amounts for counts
  1..10; a count over 10 uses the ONE-allowance amount × count (footnote 2)
- `standard_deduction[frequency][column]` — Table 3
- `exemption_allowance[frequency]` — Table 4: list of amounts for counts
  0..10; a count over 10 uses the ONE-allowance amount × count (footnote 1
  under Table 4: 15 weekly allowances → 15 × $3.24 = $48.60)
- `brackets[frequency][status]` — Tables 5–28 rows {over, rate, base};
  printed bases authoritative
- envelope `rounding` (cents, nearest)

Tables 1 and 3 print FOUR columns; the `column` key is resolved as:
`single` for single filers; `head_of_household`; and for married the
REGULAR-allowance count picks `married_allowances_0_1` (0 or 1) or
`married_allowances_2_plus` (2 or more). Bracket tables key on the three
statuses only (`single`, `married`, `head_of_household`).

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule.

```
1. gross ≤ low_income_exemption[frequency][column]
     → return additional_withholding (no income tax withheld)
2. wages   = gross − estimated_deduction lookup (0 when secondary count 0;
             one-allowance × count when count > 10)
3. taxable = max(0, wages − standard_deduction[frequency][column])
4. tax     = r(base + rate × (taxable − over)) from
             brackets[frequency][status]
5. withhold = max(0, tax − exemption_allowance lookup (count > 10 →
             one-allowance × count)) + additional_withholding
```

## Notes (normative)

- The Table 1 comparison is on GROSS wages before any table subtraction,
  and is `≤` ("less than, or equal to" per the printed Step 1).
- Example B confirms step composition: biweekly $1,600 married, 3
  allowances (1 estimated): 1,600 − 38 = 1,562 − 439 = 1,123 →
  9.37 + 2.2% × (1,123 − 852) = 15.33 − 12.95 (TWO regular allowances)
  = $2.38.
- Example E computes an ANNUAL amount and prorates back to the period —
  an employer option this method version does not model per-period;
  transcribe such examples with `pay_frequency: annually` and the printed
  annual amount, or exclude them.
- The daily/miscellaneous column maps to pay frequency `daily`.
- Withholding is never negative.
