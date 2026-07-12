# Method: `per_period_credit_phaseout` (v1)

Flat rate with a per-period **credit** that phases out linearly above a
wage threshold. Used by Utah (Pub 14 withholding schedules):

    tentative = wages × rate
    reduction = phase_rate × max(0, wages − phase_start)
    credit    = max(0, base_allowance − reduction)
    withhold  = max(0, tentative − credit)

This spec is **normative**. `/engine/methods/per_period_credit_phaseout.py`
is the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_frequency` (must have a printed schedule), `filing_status`,
`additional_withholding`. No allowance counts — Utah's worksheet keys off
federal W-4 filing status only (head of household uses the single column).

From params:

- `rate` — the flat rate (UT 2026: 4.45%)
- `phase_rate` — credit reduction per dollar over the threshold (UT: 1.3%)
- `schedules[frequency][filing_status]` — printed per-period `base_allowance`
  and `phase_start`; a missing frequency is an error, never an interpolation
- envelope `rounding`

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule, applied at
**every worksheet line** — Utah's printed examples round each line to the
whole dollar ($400 × .0445 = 18; 220 × .013 = 3), so the envelope sets
`to: 1.00` and the method rounds where the worksheet does.

```
1. taxable  = gross_wages − Σ pretax_deductions that reduce state_income
              (per /taxability); clamp at 0
2. tentative = r(taxable × rate)
3. reduction = r(phase_rate × max(0, taxable − phase_start))
4. credit    = max(0, base_allowance − reduction)
5. withhold  = max(0, tentative − credit) + additional_withholding
```

## Notes (normative)

- The credit fully phases out at phase_start + base_allowance/phase_rate.
- Negative results clamp to 0 at steps 1, 4, and 5 (before the addition).
- Withholding is never negative.
