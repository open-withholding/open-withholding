# Method: `custom/us_or` (v1)

Oregon's computer formula (Pub 150-206-436): BASE = annual wages minus
**federal income tax withheld** (capped, phasing out in steps at high
wages) minus a standard deduction; withholding from wage-tier bracket
formulas in printed `base + rate × (BASE − excess_over)` form, less a
per-allowance credit (zeroed at high wages). Annual result divided by pay
periods.

This spec is **normative**. `/engine/methods/custom/us_or.py` is the
reference implementation.

## The federal-withholding input

Oregon subtracts *actual federal income tax withheld* — an inter-tax
dependency. The engine stays a pure function: the amount arrives as the
employee-input field `period_federal_income_withholding` (this period's
federal withholding, annualized ×P by the method). Absent input with this
method is an error, never an assumed zero (FAQ 1: FICA is NOT included).

## Status groups

The formulas split by OR-W-4 status and allowance count, selected by the
method: `single` with fewer than 3 allowances → `single_under_3`;
`single` with 3+ allowances, or `married` → `married_or_single_3plus`
(married-at-higher-single-rate employees elect `single`, per FAQ 4).

## Params

Two independent keyings, matching the document's structure:

`status_groups[single_under_3 | married_or_single_3plus]` — brackets and
deduction, selected by (status, allowance count):
- `standard_deduction`
- `wage_tiers` — rows `{wages_at_least, formulas}` selecting the bracket
  set by annual WAGES (< $50,000 vs ≥ $50,000 — the printed constants
  differ between tiers); `formulas` rows are
  `{at_least, base, rate, excess_over}` on BASE, exactly as printed
  (the subtrahend differs from the row's lower bound in the high tier)

`statuses[single | married]` — phase-out and zeroing, selected by the
UNDERLYING status alone (the document prints both [S] and [M] ladders in
the married bracket group; a single employee with 3+ allowances uses the
married group's brackets but the single ladder — Example 3):
- `fed_subtraction_phaseout` — rows `{at_least, cap}` on annual WAGES,
  INCLUSIVE lower bound ("wages ≥ X")
- `allowance_zero_above` — annual WAGES above which allowances are 0

`credit_per_allowance` (2026: $263) — subtracted AFTER the rates and the
worksheet's whole-dollar rounding of the annual tax (lines 8-9; FAQ 12)

## Algorithm

```
1. wages    = (gross − reducing pretax deductions, clamp 0) × P
2. fed_cap  = phaseout row for wages (inclusive-lower lookup)
   fed_sub  = min(period_federal_income_withholding × P, fed_cap)
3. BASE     = wages − fed_sub − standard_deduction; clamp 0
4. tier     = last wage_tiers row with wages_at_least ≤ wages
   row      = last formulas row with at_least ≤ BASE
   WH       = r_a(row.base + (BASE − row.excess_over) × row.rate)
              (r_a = intermediate rounding; the worksheet's line 8 rounds
              the annual tax to the whole dollar)
5. allow    = 0 if wages > statuses[status].allowance_zero_above else input
   WH       = WH − credit_per_allowance × allow; clamp 0 (FAQ 10)
6. withhold = r(WH ÷ P) + additional_withholding
```

## Known document defects (2026 edition, Rev. 12-31-25)

The formula tables and Example 1's worksheet are self-consistent and
govern. Stale prose, all report-worthy: Example 1's narrative says BASE
"$21,165" and result "$1,798" where its own worksheet computes $21,090 →
$1,789; the worksheet's credit line says "$256" where the formula uses
$263; the intro and FAQ 3 say the cap is "$8,500 in 2025" where the
tables print $8,750; Example 3's "$5,100" derives from the 2025 ladder
($8,500 − 2×$1,700) — the printed 2026 ladder gives $5,250 for that wage.
