# Method: `elective_flat_rate` (v1)

The employee elects a withholding rate from the jurisdiction's published
list; the employer applies it flat to taxable wages. Used by Arizona
(Form A-4: 0.5%–3.5% in half-point steps, 0% with an annual no-liability
certification, employer default 2.0% when no A-4 is filed within the
deadline).

This spec is **normative**. `/engine/methods/elective_flat_rate.py` is the
reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`elected_rate` (the A-4 election; optional), `additional_withholding`.

From params:

- `allowed_rates` — the published elections; an input rate outside the list
  is an error, never a silent acceptance
- `zero_rate_allowed` — whether 0% (with certification) is a valid election
- `default_rate` (optional) — applied when the input carries no election
  (AZ: 2.0% when no A-4 is filed)
- envelope `rounding`

## Algorithm

```
1. taxable_period = gross_wages − Σ pretax_deductions that reduce
                    state_income (per /taxability); clamp at 0
2. rate           = elected_rate, validated against allowed_rates
                    (plus 0 when zero_rate_allowed); else default_rate;
                    no election and no default is an error
3. withhold       = r(taxable_period × rate) + additional_withholding
```
