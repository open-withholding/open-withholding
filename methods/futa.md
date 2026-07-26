# Method: `futa` (v1)

Federal Unemployment Tax Act — an EMPLOYER tax, not withholding from
wages (IRS Publication 15, section 14). Computed per pay period against
the annual wage base so payroll can accrue it per check; the statutory
deposit/return mechanics (Form 940, quarterly deposits) are out of scope.

This spec is **normative**. `/engine/methods/futa.py` is the reference
implementation, reached through `engine.pipeline.compute_employer_tax`.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`
(reduced per the taxability matrix's `futa` wage base), `ytd.futa_wages`
(FUTA-taxable wages paid in PRIOR periods this calendar year; defaults
to 0), and `employer.sui_jurisdiction` (the state whose UI program the
employer pays into — used only for the credit-reduction lookup).

From params (transcribed from the publication):

- `rate` — the gross FUTA rate (6.0%)
- `wage_base` — the annual FUTA wage base ($7,000, statutory)
- `max_credit` — the maximum credit for timely state UI contributions
  (5.4%), yielding the customary net rate
- `credit_reductions` — per-state additional rate map for
  credit-reduction states (Form 940 Schedule A); an absent state means
  no reduction. May be empty.

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule.

```
1. effective = rate − max_credit
             + credit_reductions.get(employer.sui_jurisdiction, 0)
2. taxable   = min(period futa wages, max(0, wage_base − ytd.futa_wages))
3. tax       = r(taxable × effective)
```

## Notes (normative)

- This computes the accrual for an employer entitled to the FULL state
  credit (timely UI payments). Employers with late or partial state
  contributions owe more; that determination is a filing-time matter
  (Form 940 worksheet), not a per-period parameter.
- A missing `employer` block or `sui_jurisdiction` applies no credit
  reduction (correct for every non-reduction state).
- The tax is an employer liability; it never reduces the employee's pay.
- Never negative; the wage-base cap works exactly like FICA's social
  security cap.
