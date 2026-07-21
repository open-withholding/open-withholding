# Method: `fica` (v1)

Federal Insurance Contributions Act withholding — Social Security (OASDI)
and Medicare (HI) — per IRS Publication 15 (Circular E). Computes the
EMPLOYEE withholding for one pay period; the employer-share rates are
carried in params for completeness but do not enter the returned amount
(the employer share is a tax on the employer, not withholding from wages).

This spec is **normative**. `/engine/methods/fica.py` is the reference
implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`
(reduced per the taxability matrix's `fica` wage base — e.g. Section 125
cafeteria health premiums reduce it; traditional 401(k) does not),
`ytd.social_security_wages` and `ytd.medicare_wages` (FICA-taxable wages
paid in PRIOR periods this calendar year; each defaults to 0 when absent,
which is exact for a first paycheck and conservative for Social Security
otherwise). No filing status, allowances, or elections apply.

From params (transcribed from the publication):

- `social_security.employee_rate`, `social_security.employer_rate`,
  `social_security.wage_base` — the annual wage base limit
- `medicare.employee_rate`, `medicare.employer_rate`
- `medicare.additional_employee_rate`,
  `medicare.additional_threshold` — the Additional Medicare Tax rate and
  the calendar-year wage threshold at which the withholding obligation
  begins; it has NO employer match and is statutorily not
  inflation-adjusted
- envelope `rounding` (cents, nearest — Pub 15's fractions-of-cents rule)

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule; `wages` =
this period's FICA-taxable wages; `ytd_ss` / `ytd_med` as above.

```
1. ss_taxable = min(wages, max(0, wage_base − ytd_ss))
   ss = r(ss_taxable × social_security.employee_rate)
2. medicare = r(wages × medicare.employee_rate)
3. addl_taxable = max(0, wages + ytd_med − max(additional_threshold, ytd_med))
   (the portion of THIS period's wages that lies above the threshold,
   given wages already paid this year)
   additional = r(addl_taxable × medicare.additional_employee_rate)
4. withhold = ss + medicare + additional
```

## Notes (normative)

- Each component is rounded to the cent independently, then summed —
  Pub 15 computes the taxes separately.
- Social Security stops exactly at the wage base: the period that crosses
  it withholds on the sub-base portion only; later periods withhold 0.
- Additional Medicare withholding starts in the period that crosses the
  threshold and applies to every Medicare-taxable dollar above it,
  regardless of the employee's actual filing-status liability threshold —
  the WITHHOLDING obligation is per-employer and flat (Pub 15).
- `ytd` amounts are the wages BASE (taxable wages), not tax withheld.
- Withholding is never negative; all params are non-negative.
