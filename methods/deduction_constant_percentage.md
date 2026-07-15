# Method: `deduction_constant_percentage` (v1)

Flat rate on period wages minus per-period "deduction constants" — one
constant per **named exemption kind**, each computed from an annual value and
independently rounded. Used by Indiana (Departmental Notice #1):

    constant_k = r(count_k × annual_k ÷ periods)   for each kind k
    taxable    = max(0, wages − Σ constant_k)
    withhold   = r(taxable × rate)

This spec is **normative**. `/engine/methods/deduction_constant_percentage.py`
is the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_frequency`, `additional_withholding`, and the named
`exemptions: {kind: count}` map (IN WH-4: `personal` = line 5, `dependent` =
line 6, `first_time_dependent` = line 7, `adopted` = line 8). No
`filing_status` and no positional allowance counts. A count for a kind not in
params is an error, never silently ignored.

From params:

- `rate` — the flat rate (IN 2026: 2.95%)
- `exemptions[kind]` — ANNUAL dollar value per exemption of that kind
  (IN 2026: personal $1,000; dependent $1,500; first_time_dependent $1,500;
  adopted $3,000)
- `periods_per_year[frequency]` — the divisors implied by the document's
  printed deduction-constant tables. Transcribed, not assumed: DN #1's Daily
  column is annual ÷ **365**, not the engine's 260 working days. A pay
  frequency missing from this map is an error, never an interpolation.
- envelope `rounding`

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule (IN: nearest
cent).

```
1. taxable_gross = gross_wages − Σ pretax_deductions that reduce state_income
                   (per /taxability); clamp at 0
2. For each kind k with count_k > 0:
       constant_k = r(count_k × annual_k ÷ periods_per_year[frequency])
   Each kind rounds INDEPENDENTLY — DN #1's example looks up line 6 (three
   dependents → $86.54) and line 7 (one first-time dependent → $28.85)
   separately; folding them into one count of four gives $115.38, one cent
   off the example's $86.54 + $28.85 = $115.39.
3. taxable  = max(0, taxable_gross − Σ constant_k)
4. withhold = r(taxable × rate) + additional_withholding
```

## Notes (normative)

- `constant_k` reproduces every printed deduction-constant table cell:
  the tables print r(n × annual ÷ periods) per row, NOT n × the one-exemption
  constant (Table B weekly: 2 × $28.85 = $57.70, but the printed row 2 is
  $57.69 = r(3000 ÷ 52)).
- Non-periodic payments (bonuses) are computed without exemptions per DN #1;
  supplemental-wage handling is out of scope for this method version.
- Negative results clamp to 0 at steps 1 and 3. Withholding is never
  negative.
- Indiana county income tax uses the SAME taxable base (step 3) with the
  county's rate — a county parameter file is this method with the county
  rate and identical exemption params.
