# Method: `resident_nonresident_flat_rate` (v1)

A local income tax with two flat rates on the period's taxable wages — one
for **residents** of the locality and one for **nonresidents** who work
there — with no deductions or allowances. Used by Pennsylvania's Act 32
earned income tax (EIT): every political subdivision (PSD) in the DCED
register carries a total resident rate (municipal resident EIT + school
district EIT) and a municipal nonresident rate. Files are expanded from the
register (`data/us/pa/<year>/locals/act32.yaml` + `act32.csv`, DESIGN §3.6)
as `jurisdiction: US-PA-PSD-<code>`.

This spec is **normative**. `/engine/methods/resident_nonresident_flat_rate.py`
is the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions` (reduced
per the taxability matrix's `state_income` column — locals follow their
state; PA's overrides apply to PSD files), and the locality's
`LocalElection`: `resident` (default true — selects the rate) and
`additional_withholding`.

From params (transcribed from the register row):

- `resident_rate` — decimal fraction; Act 32's **total** resident rate
- `nonresident_rate` — decimal fraction; the municipal nonresident rate
- envelope `rounding` (cents, nearest)

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule.

```
1. taxable_period = gross_wages − Σ pretax_deductions that reduce this
                    file's wage base; floor 0
2. rate           = resident_rate if resident else nonresident_rate
3. withhold       = r(taxable_period × rate) + additional_withholding
```

## Notes (normative)

- Act 32's employer rule — withhold the **greater of** the employee's
  resident rate (residence PSD) and the nonresident rate of the work
  location PSD — compares two jurisdictions' files and is the caller's
  step: compute both and take the larger. One file never knows the other.
- No `resident` flag on the election means resident (the common case: an
  employee working where they live, or the residence-PSD leg of the
  comparison).
- `filing_status` and `allowances` are ignored.
- Withholding is never negative.
