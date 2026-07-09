# Method: `per_period_percentage` (v1)

Percentage method computed **directly at the pay period's granularity**,
from bracket tables the jurisdiction prints per payroll frequency. Used
where the published per-period tables carry independently rounded
thresholds/bases and the guide's worked examples compute from them — so an
annualized computation cannot reproduce the printed answers exactly
(Kansas KW-100, Vermont GB-1210, New Mexico FYI-104).

This spec is **normative**. `/engine/methods/per_period_percentage.py` is
the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_frequency` (must have a printed table), `filing_status`,
`allowances` **A**, `additional_withholding`.

From params (each allowance mechanism optional; a jurisdiction uses the
ones its worksheet prints):

- `standard_deduction[filing_status]` **SD** — an ANNUAL per-status
  exemption divided by the period count at computation time (Kansas's
  status exemption)
- `allowance_amount` **AA** — ANNUAL per-allowance amount, divided with SD
  (Kansas's per-dependent amount)
- `allowance_amounts_per_period[frequency]` **AAP** — the printed
  per-period value of one allowance (Vermont's table headers)
- `brackets[frequency][filing_status]` — per-period rows (`over`/`rate`/
  optional `base`; printed bases are authoritative, as everywhere)
- envelope `rounding`

## Algorithm

All arithmetic in Decimal. Let `r(x)` = the envelope rounding rule and
`r¢(x)` = rounding to the cent, half up. P = pay periods per year.

```
1. taxable_period = gross_wages − Σ pretax_deductions that reduce
                    state_income (per /taxability); clamp at 0

2. reduction      = r¢( (SD + A × AA) ÷ P )     where SD/AA are present
                  + A × AAP[frequency]           where AAP is present

3. net            = taxable_period − reduction; clamp at 0

4. period_tax     = bracket(net) over brackets[frequency][filing_status]
                    (bracket() as defined in
                    /methods/annualized_percentage.md step 4)

5. withhold       = r(period_tax) + additional_withholding
```

## Notes (normative)

- The division in step 2 rounds to the cent, matching how the worksheets
  print it (Kansas: $20,640 ÷ 24 = $860.00).
- A pay frequency with no printed table is an error, never an
  interpolation. A jurisdiction with one schedule for all statuses uses
  the key `all` (as in `annualized_percentage`).
- `rounding.intermediate` does not apply (there is no annualized
  intermediate); `rounding.to`/`mode` govern step 5 (Kansas rounds to the
  whole dollar; the examples decide, as always).
- Negative results clamp to 0 at steps 1 and 3. Withholding is never
  negative.
