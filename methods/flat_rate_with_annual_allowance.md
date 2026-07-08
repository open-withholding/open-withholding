# Method: `flat_rate_with_annual_allowance` (v1)

A single rate applied to annualized wages after subtracting a per-filing-
status annual allowance. Used by CO, IL, MI, UT-style states.

This spec is **normative**. `/engine/methods/flat_rate_with_annual_allowance.py`
is the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_periods_per_year` **P**, `filing_status`, `additional_withholding`.

Some states in this family scale the allowance by exemptions claimed rather
than filing status; those are represented by publishing one `filing_status`
key per exemption tier, or (if that proves awkward in practice) by a v2 of
this method — the worked examples decide.

From params: `rate`, `filing_status[status].annual_allowance` **AL**.
Envelope: `rounding`.

## Algorithm

All arithmetic in Decimal. Let `r(x)` = apply the envelope rounding rule.

```
1. taxable_period  = gross_wages
                     − Σ pretax_deductions that reduce state_income
                       (per /taxability, with this state's overrides)
   If taxable_period < 0, set 0.

2. annual_wages    = taxable_period × P

3. annual_taxable  = annual_wages − AL
   If annual_taxable < 0, set 0.

4. annual_tax      = annual_taxable × rate
   If rounding.intermediate == annual, annual_tax = r(annual_tax).

5. period_tax      = annual_tax ÷ P

6. withhold        = r(period_tax) + additional_withholding
```

## Notes (normative)

- Same rounding discipline as `annualized_percentage`: round once at the
  final step unless the guide's worked examples demonstrate intermediate
  rounding.
- Withholding is never negative.
