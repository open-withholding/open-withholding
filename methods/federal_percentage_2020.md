# Method: `federal_percentage_2020` (v1)

Federal income tax withholding for 2020-and-later Forms W-4, following
Pub 15-T **Worksheet 1A** (Percentage Method Tables for Automated Payroll
Systems). Step 2 checkbox selects an alternate bracket table; Steps 3/4
enter at fixed stages below.

This spec is **normative**. `/engine/methods/federal_percentage_2020.py` is
the reference implementation. Line numbers below reference Worksheet 1A so a
reviewer can follow along in the publication.

## Inputs

From the employee input record (`federal` block, `w4_version: 2020`):

- `gross_wages`, `pretax_deductions`, `pay_periods_per_year` **P**
- `filing_status` — `single` (incl. MFS), `married_joint` (incl. QSS),
  `head_of_household`
- `step2_checkbox` — boolean
- `step3_credits` — annual dependents-and-other-credits amount
- `step4a_other_income` — annual
- `step4b_deductions` — annual
- `step4c_extra` — per-period additional withholding

From params:

- `wage_adjustment[filing_status]` — the Worksheet 1A line 1g amount,
  applied only when the Step 2 checkbox is **not** checked
- `brackets.standard[filing_status]` and
  `brackets.step2_checkbox[filing_status]` — annual percentage-method
  tables (rows `over` / `rate` / optional validated `base`)
- envelope `rounding`

## Algorithm

All arithmetic in Decimal. Let `r(x)` = apply the envelope rounding rule.

```
Step 1 — Adjusted Annual Wage Amount (AAWA)
1c. annual_wages   = taxable_period × P
    where taxable_period = gross_wages − Σ pretax_deductions that reduce
    federal_income (per /taxability); clamp at 0
1e. total          = annual_wages + step4a_other_income
1g. adjustment     = 0 if step2_checkbox else wage_adjustment[filing_status]
1i. AAWA           = total − step4b_deductions − adjustment
    If AAWA < 0, set 0.

Step 2 — Tentative withholding amount
2a. table          = brackets.step2_checkbox[status] if step2_checkbox
                     else brackets.standard[status]
2b. annual_tentative = bracket(AAWA) over that table
    (bracket() as defined in /methods/annualized_percentage.md step 4)
2h. tentative_period = annual_tentative ÷ P

Step 3 — Credits
3b. credit_period  = step3_credits ÷ P
3c. after_credits  = tentative_period − credit_period
    If after_credits < 0, set 0.

Step 4 — Extra withholding
4.  withhold       = r(after_credits) + step4c_extra
```

## Sequencing and rounding notes (normative)

- Pub 15-T permits rounding the final amount to the nearest whole dollar;
  the envelope `rounding` block records what the published worked examples
  actually do for the year. **The worked examples decide.**
- `rounding.intermediate: annual` rounds line 2b before 2h, only if the
  year's worked examples demonstrate it.
- Divisions (2h, 3b) are exact Decimal division; only `r()` rounds.
- Clamps at 1i and 3c; withholding is never negative.

## Out of scope for this method

Pre-2020 W-4s (`federal_percentage_pre2020`, separate spec), supplemental
wage flat rates (live in `limits.yaml`), nonresident alien additional
amounts (Tier 2), and the wage-bracket lookup tables.
