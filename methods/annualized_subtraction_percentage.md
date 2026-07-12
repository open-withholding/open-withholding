# Method: `annualized_subtraction_percentage` (v1)

Annualized percentage method in Arkansas's printed form: net taxable
income is **snapped to the $50 midrange** of its $100 bracket (below a
ceiling), then taxed as `rate × income − subtraction` from a printed
ladder, rounded to the whole dollar, less per-exemption credits.

This spec is **normative**.
`/engine/methods/annualized_subtraction_percentage.py` is the reference
implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_periods_per_year` **P** (AR's daily factor is 260), `allowances` **A**
(AR4EC exemptions), `additional_withholding`. No filing statuses.

From params:

- `standard_deduction` **SD** — flat (AR 2026: $2,470)
- `midrange_snap`: `bracket_size` (100), `midpoint` (50), `snap_below` —
  incomes under `snap_below` are looked up at
  `floor(income / bracket_size) × bracket_size + midpoint`; at or above it,
  the exact dollar figure is used
- `credit_per_allowance` **CPA** — annual per-exemption tax credit (AR: $29)
- `table` — rows `{from, rate, subtract}`, `from` ascending from "0",
  `subtract` omitted/null meaning 0; the row is the last with
  `from ≤ income`. This is the document's printed form; it is
  algebraically equivalent to base+rate-on-excess but is encoded as
  printed so a reviewer can compare cell-for-cell.
- envelope `rounding` (AR: intermediate annual to 1.00, final to cents)

## Algorithm

All arithmetic in Decimal; `r_a(x)` = the intermediate rounding rule,
`r(x)` = the final rule.

```
1. taxable  = gross_wages − Σ pretax_deductions that reduce state_income;
              clamp at 0
2. annual   = taxable × P
3. nti      = max(0, annual − SD)
4. snapped  = floor(nti / bracket_size) × bracket_size + midpoint
              if nti < snap_below, else nti
5. row      = last table row with from ≤ snapped
   gross_tax = snapped × row.rate − row.subtract; clamp at 0
6. gross_tax = r_a(gross_tax)                     (AR: whole dollar)
7. net_tax  = max(0, gross_tax − A × CPA)
8. withhold = r(net_tax ÷ P) + additional_withholding
```

## Notes (normative)

- **Known AR document defect (2026 edition):** step 2's prose says exact
  lookup begins at "$100,001 and over," but the worked example uses
  "less than $97,701" and the printed adjustment ladder's final row opens
  at $97,601 — `snap_below` is 97,701 per the example, and the prose
  figure appears stale. The worked examples decide.
- The transition ladder ($94,701–$97,600, thirty $100-wide rows with
  descending subtractions) is encoded row-for-row as printed.
