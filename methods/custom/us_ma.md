# Method: `custom/us_ma` (v1)

Massachusetts Circular M percentage method (p.12): flat 5% plus the 9%
surtax tier, computed from period wages less **actual retirement
withholdings** (FICA, Medicare, MA/US/Railroad Retirement) under a
**$2,000 cumulative annual cap**, less a nonlinear exemption factor;
head-of-household and blindness amounts subtract from the per-period TAX.

This spec is **normative**. `/engine/methods/custom/us_ma.py` is the
reference implementation.

## Inputs

- `period_fica_withholding` — this period's FICA/Medicare/retirement
  withholdings (required; the inter-tax sibling of the federal input)
- `ytd.retirement_deduction_used` — the amount already subtracted under
  step 1 this year. The cap is cumulative and produces a **mid-year
  cutoff**: subtract `min(period amount, $2,000 − ytd used)`. Absent means
  0 (start of year). The CALLER maintains this counter (the engine is a
  pure function).
- `filing_status`: `single` (default treatment) or `head_of_household`
- `allowances` — exemptions claimed (spouse counts as 4, per Circular M
  note 1 — the count arrives already totaled)
- `secondary_allowances` — number of blindness claims (employee and/or
  spouse: 0, 1, or 2)

## Params

- `retirement_deduction_cap` — annual ($2,000)
- `exemption_factors[frequency]` — `{claiming_one, per_exemption, plus}`:
  claiming 0 skips the step; claiming 1 subtracts `claiming_one`;
  claiming n>1 subtracts `per_exemption × n + plus`
- `brackets` — annual (5% to $1,107,750; 9% above, surtax-inclusive)
- `hoh_tax_value[frequency]`, `blindness_tax_value[frequency]` — per-period
  TAX subtractions (steps 6-7)
- `low_income_floor[frequency]` — no withholding when the employee claims
  ≥1 exemption and period wages are below this

## Algorithm

```
0. if allowances ≥ 1 and taxable period wages < floor[freq]:
     withhold = additional_withholding; stop
1. remaining = max(0, cap − ytd.retirement_deduction_used)
   w = wages − min(period_fica_withholding, remaining)
2. w −= claiming_one            if allowances == 1
   w −= per_exemption×n + plus  if allowances > 1
   clamp w at 0
3. annual = w × P               (biweekly uses 26; Circular M permits 27)
4. tax    = bracket(annual)
5. period = tax ÷ P
6. period −= hoh_tax_value[freq]              if head_of_household
7. period −= blindness_tax_value[freq] × blind claims
8. withhold = r(max(0, period)) + additional_withholding
```

## Notes (normative)

- Circular M states no rounding rule; cents are encoded.
- The wage-bracket tables in the same document embed only the 5% rate;
  the percentage method is the only path that captures the 9% surtax —
  which is why the tables are not encoded.
- Supplemental wages (section G) are out of scope for v1.
