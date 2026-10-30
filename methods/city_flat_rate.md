# Method: `city_flat_rate` (v1)

A city income tax with a **resident rate** and a **nonresident rate** on
wages after an annual per-exemption deduction — the Michigan Uniform City
Income Tax Ordinance (Act 284 of 1964), followed by all 24 Michigan cities
that levy an income tax (Detroit 2.4% / 1.2%, Grand Rapids and Saginaw
1.5% / 0.75%, Highland Park 2.0% / 1.0%, the rest 1.0% / 0.5%; the
nonresident rate is half the resident rate by statute). Used for
`tax: local_income_withholding` files `data/us/mi/<year>/locals/<city>.yaml`.

This spec is **normative**. `/engine/methods/city_flat_rate.py` is the
reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`
(reduced per the taxability matrix's `state_income` column — locals
follow their state), `pay_frequency` → **P** periods per year, and the
city's `LocalElection`: `resident` (required — selects the rate; a
nonresident is withheld on only the wages earned in the city, which is
what the caller passes as gross), `allowances` (the exemption count from
the city's withholding certificate, e.g. Detroit DW-4; when omitted the
parent state's count is inherited — MI-W4 and the city certificates
usually agree), `additional_withholding`.

From params (transcribed from the city's employer withholding guide):

- `resident_rate`, `nonresident_rate` — decimal fractions
- `exemption_amount` — the ANNUAL deduction per exemption ($600 under the
  Uniform Ordinance; some cities print a different figure — transcribe
  what the city prints)
- envelope `rounding` (cents, nearest; `intermediate: annual` only where a
  guide demonstrates rounding the annual tax)

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule.

```
1. rate            = resident_rate if resident else nonresident_rate
2. annual_wages    = taxable_period × P
3. annual_taxable  = max(0, annual_wages − exemption_amount × allowances)
4. annual_tax      = annual_taxable × rate      (r_intermediate if annual)
5. withhold        = r(annual_tax ÷ P) + additional_withholding
```

## Notes (normative)

- A file without a `resident` flag on the local election fails loud: the
  rate cannot be chosen. (The state-level methods ignore residency.)
- Michigan cities publish withholding TABLES derived from this formula;
  only the formula is transcribed (tables embed bracket rounding).
- Withholding is never negative.
