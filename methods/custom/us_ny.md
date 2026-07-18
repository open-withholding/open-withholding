# Method: `custom/us_ny` (v1)

New York State Method II — Exact Calculation Method, with the Method III
Top Income Tax Rates override (Publication NYS-50-T-NYS, pages 14–22).
The same structure is printed for New York City (NYS-50-T-NYC) and can be
reused by that jurisdiction's file.

    1. net  = wages − (Table B deduction + exemptions × Table C value)
    2. if net ≥ the payroll table's printed Method III cutover
         → Method III: annualized flat band on net × periods
       else
         → Method II: bracket computation (col5 + col4 × (net − col1))

This spec is **normative**. `/engine/methods/custom/us_ny.py` is the
reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_frequency`, `filing_status` (`single`, `married`), `allowances`
(IT-2104 exemptions claimed), `additional_withholding`.

From params (all printed values transcribed verbatim):

- `deduction[frequency][status]` — Table B deduction allowance
- `exemption_value[frequency]` — Table C value of one exemption
  ($1,000/yr basis)
- `brackets[frequency][status]` — Tables II-A..E and the Annual Tax Rate
  Schedule, rows {over, rate, base}: over = column 1 "at least"
  (identical to column 3 "subtract" in every printed row), rate =
  column 4, base = column 5. Printed bases authoritative.
- `method_iii_cutover[frequency][status]` — each bracket table's final
  printed line: "$X & over → use Method III"
- `method_iii[status]` — the page-22 bands: rows {over, rate} on
  ANNUALIZED net wages (single: 1,077,550 / 5,000,000 / 25,000,000 at
  10.45% / 11.10% / 11.70%; married differs only in the first bound)
- envelope `rounding` (cents, nearest, no intermediate)

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule;
`periods` = pay periods per year for the CALCULATION frequency.

```
0. Conversion (page 23 rule A/B): quarterly computes at monthly on
   wages ÷ 3 with factor 3; semiannually at monthly on wages ÷ 6 with
   factor 6. All other supported frequencies compute natively with
   factor 1. The division is exact Decimal, not rounded.
1. net = max(0, wages − deduction[freq][status]
                     − allowances × exemption_value[freq])
   (Table A is the precomputed deduction + n × exemption grid for
   n ≤ 10; the Step 1 instruction for n > 10 IS this formula, so the
   formula is used for every count.)
2. if net ≥ method_iii_cutover[freq][status]:
       annualized = net × periods
       rate = the LAST method_iii band whose over ≤ annualized
              (the sliver where the per-period cutover annualizes to
              just below the first band's bound uses the first band)
       tax = r(annualized × rate ÷ periods)
   else:
       tax = r(base + rate × (net − over)) from brackets[freq][status]
3. withhold = max(0, tax × factor) + additional_withholding
   (rule A step 4: the common-period amount is computed and rounded
   first, then multiplied by the conversion factor)
```

## Notes (normative)

- Supported frequencies: the printed daily, weekly, biweekly,
  semimonthly, monthly, annually — plus quarterly and semiannually by
  the printed conversion rule. Anything else fails loud.
- The Method II ↔ III boundary follows the PRINTED per-period cutover
  (e.g. single weekly $20,722), not the instructions' annualized note:
  the two disagree on a sliver (20,722 × 52 = 1,077,544 < 1,077,550)
  and the tables are the operative rule.
- Rounding is a single final nearest-cent rounding. This reproduces the
  printed Examples 1, 3, and 4 for both statuses exactly. Both printed
  Examples 2 are internally inconsistent by exactly 1¢ in opposite
  directions (single Step 4 prints 165.00 × 0.0753 = "12.43" where the
  product is 12.4245; married prints 58.80 × 0.0707 = "4.15" where the
  product is 4.15716) — publication defects; those two examples are
  excluded from goldens, per the NJ precedent.
- The married rate ladder is non-monotonic (the 13.49% tax-benefit
  recapture band sits between 6.40% and 7.35%); only the bounds must
  ascend.
- The Annual Tax Rate Schedule's printed bases are statute-derived
  cumulative amounts that intentionally do NOT chain with the smoothed
  withholding rates (drift up to ~$4.30 at the 2026 single table's upper
  rows), so the loader relaxes the cumulative-chaining tolerance to
  $10.00 for the annual tables only. The operative transcription check
  is structural: every per-period table is the annual schedule divided
  by pay periods — row-for-row equal rates, and each base equal to
  round(annual base ÷ periods) to the cent. The loader enforces this
  cross-frequency corroboration (six independent transcriptions of the
  same schedule), and requires the annual schedule to be present.
- Table D (employer-elected federal-allowance adjustment) and the
  Method I wage-bracket / dollar-to-dollar lookup tables are out of
  scope.
- Withholding is never negative.
