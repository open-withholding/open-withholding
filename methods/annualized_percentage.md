# Method: `annualized_percentage` (v1)

Annualize the period's taxable wages, subtract a standard deduction and
per-allowance amount, run the result through a bracket table, optionally
subtract per-allowance credits, and de-annualize. This is the standard
percentage method printed in ~25 state withholding guides.

This spec is **normative**. `/engine/methods/annualized_percentage.py` is the
reference implementation. This document doubles as the template for all other
method specs.

## Inputs

From the employee input record (see `/schema/employee-input.schema.json`):

- `gross_wages` — this period
- `pretax_deductions` — typed list, this period
- `pay_periods_per_year` **P** (derived from `pay_frequency`)
- `filing_status` — per this jurisdiction's enum
- `allowances` **A** — integer ≥ 0
- `additional_withholding` — optional per-period amount

From params:

- `standard_deduction[filing_status]` **SD** (optional; default 0)
- `allowance_amount` **AA** (optional; default 0)
- `brackets[filing_status]`
- `credit_per_allowance` **CPA** (optional)
- envelope `rounding`

## Algorithm

All arithmetic in Decimal. Let `r(x)` = apply the envelope rounding rule.

```
1. taxable_period  = gross_wages
                     − Σ pretax_deductions that reduce state_income
                       (per /taxability, with this state's overrides)
   If taxable_period < 0, set 0.

2. annual_wages    = taxable_period × P

3. annual_taxable  = annual_wages − SD − (A × AA)
   If annual_taxable < 0, set 0.

4. annual_tax      = bracket(annual_taxable)
   where bracket(x): find last row with over ≤ x; tax = row.base
   + (x − row.over) × row.rate. When the guide prints a base column, the
   printed value is row.base — the guide's worked examples use it, so the
   engine must too. When no base is printed, row.base is the cumulative sum
   over completed brackets of (bracket_width × rate).
   (The loader validates any printed base against the recomputed cumulative
   sum within a small tolerance, not exact equality: agencies round printed
   thresholds but derive base columns from unrounded amounts — e.g.
   Pub 15-T 2026 prints the checkbox-single boundary as $108,938 for a true
   half-of-MFJ boundary of $108,937.50, making the printed base $20,512.00
   where the printed-threshold sum gives $20,512.12.)

5. if CPA: annual_tax = max(0, annual_tax − A × CPA)

6. period_tax      = annual_tax ÷ P

7. withhold        = r(period_tax) + additional_withholding
```

## Sequencing and rounding notes (normative)

- Rounding is applied **once, at step 7**, unless the jurisdiction's guide
  demonstrates intermediate rounding in its worked examples, in which case
  the YAML sets `rounding.intermediate: annual` and step 4's result is
  rounded before step 6. **The worked examples decide.** When a guide's
  example cannot be reproduced, the transcription or the sequencing is
  wrong — never ship a file whose golden tests fail.
- Division in step 6 is exact Decimal division; only `r()` rounds.
- Negative results clamp to 0 at steps 1, 3, 5. Withholding is never
  negative.

## Out of scope for this method

Supplemental wages, cumulative/percentage-of-YTD methods (a few states offer
them as alternatives; we implement the standard method only in v1).
