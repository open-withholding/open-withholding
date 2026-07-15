# Method: `rate_schedule_percentage` (v1)

Per-period bracket schedules printed once per **pre-combined rate** (state +
local), with the schedule selected by an employer-side input. Used by
Maryland (Employer Withholding Guide): ten schedules (2.25% … 3.30% local)
plus the special "Maryland resident employees who work in Delaware" schedule;
the employer withholds at the schedule ≥ the employee's county rate (2.25%
also serves nonresidents).

    if gross < floor[frequency]: withhold 0
    taxable  = max(0, gross − standard_deduction[frequency]
                          − allowances × exemption[frequency])
    row      = schedule bracket row for (rate_schedule, frequency, group)
    withhold = r(base + rate × (taxable − over))

This spec is **normative**. `/engine/methods/rate_schedule_percentage.py`
is the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_frequency`, `filing_status`, `allowances` (MW507 exemptions),
`additional_withholding`, and `rate_schedule` — the key of the printed
schedule the employer selected (MD: the county's combined rate, e.g.
"0.0320"). A missing or unknown `rate_schedule` is an error, never a
default: picking a schedule is a legal determination the data set must not
make.

From params:

- `exemption_per_period[frequency]` — printed per-period value of one
  MW507 exemption ($3,200/yr; weekly $61.54)
- `standard_deduction_per_period[frequency]` — printed per-period standard
  deduction ($3,400/yr flat — the 15% min/max was repealed for 2026;
  weekly $65.38)
- `no_withholding_floor[frequency]` — "DO NOT WITHHOLD ON GROSS WAGES LESS
  THAN $X", compared against period GROSS wages (before the deductions),
  identical across schedules and status groups in the 2026 guide
- `status_groups` — map of group key → list of filing statuses
  (MD: `a` = married_joint, head_of_household; `b` = single,
  married_filing_separately, dependent)
- `schedules[rate_schedule][frequency][group]` — printed bracket rows
  {over, base, rate}; rates are the COMBINED state+local marginal rates as
  printed. A missing frequency or schedule is an error, never an
  interpolation.
- envelope `rounding`

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule.

```
1. gross    = gross_wages − Σ pretax_deductions that reduce state_income
              (per /taxability); clamp at 0
2. if gross < no_withholding_floor[frequency]: return additional_withholding
3. taxable  = max(0, gross − standard_deduction_per_period[frequency]
                         − allowances × exemption_per_period[frequency])
4. locate the row in schedules[rate_schedule][frequency][group] with the
   greatest `over` ≤ taxable, where group is the status_groups entry
   containing filing_status
5. withhold = r(base + rate × (taxable − over)) + additional_withholding
```

## Notes (normative)

- Printed bases are authoritative (transcribed, not derived); the guide
  prints them to the cent.
- The floor tests GROSS wages, not taxable income — an employee over the
  floor but with taxable ≤ 0 withholds 0 through step 3's clamp instead.
- The guide prints no worked examples; goldens are maintainer-constructed.
- Withholding is never negative.
