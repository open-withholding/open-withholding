# Method: `flat_rate` (v1)

A single rate applied to the period's taxable wages, no deductions or
allowances. Used by PA state withholding and by centrally-published locals
(IN/MD counties, OH municipalities and school districts, PA Act 32 EIT).

This spec is **normative**. `/engine/methods/flat_rate.py` is the reference
implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`additional_withholding` (optional per-period amount).

From params: `rate`. Envelope: `rounding`.

## Algorithm

All arithmetic in Decimal. Let `r(x)` = apply the envelope rounding rule.

```
1. taxable_period = gross_wages
                    − Σ pretax_deductions that reduce this file's wage base
                      (per /taxability, with jurisdiction overrides — e.g.
                      401(k) traditional does NOT reduce PA wages)
   If taxable_period < 0, set 0.

2. withhold       = r(taxable_period × rate) + additional_withholding
```

## Notes (normative)

- `filing_status` and `allowances` are ignored; the input schema permits
  them so callers can use one record shape for all jurisdictions.
- `rounding.intermediate` has no effect for this method (there is no
  annualized intermediate).
- Withholding is never negative.
