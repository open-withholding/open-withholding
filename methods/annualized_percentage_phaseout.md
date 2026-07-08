# Method: `annualized_percentage_phaseout` (v1)

Annualized percentage method whose standard deduction **phases out**
linearly with income. Used by Wisconsin (Pub W-166 "alternate method");
Maine's formula has the same shape.

This spec is **normative**. `/engine/methods/annualized_percentage_phaseout.py`
is the reference implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_periods_per_year` **P**, `filing_status`, `allowances` **A**
(exemptions), `additional_withholding`.

From params:

- `deduction_phaseout[filing_status]`: `maximum` **D**, `phase_start` **S**,
  `phase_rate` **r** — the deduction is D until annual wages reach S, then
  shrinks by r per dollar of wages above S, to a floor of 0. (Guides print
  this as three cases; the zero point S + D/r is implied.)
- `exemption_amount` **EA** (optional; default 0) — per exemption claimed
- `brackets[filing_status]` — a jurisdiction with one schedule for all
  statuses publishes a single table under the key `all`
- envelope `rounding`

## Algorithm

All arithmetic in Decimal. Let `r(x)` = apply the envelope rounding rule.

```
1. taxable_period  = gross_wages − Σ pretax_deductions that reduce
                     state_income (per /taxability); clamp at 0

2. annual_wages    = taxable_period × P

3. deduction       = D                          if annual_wages < S
                   = max(0, D − r × (annual_wages − S))   otherwise

4. annual_net      = annual_wages − deduction − (A × EA)
   If annual_net < 0, set 0.

5. annual_tax      = bracket(annual_net)
   (bracket() as defined in /methods/annualized_percentage.md step 4;
   printed base columns are authoritative.)
   If rounding.intermediate == annual, annual_tax = r(annual_tax).

6. period_tax      = annual_tax ÷ P

7. withhold        = r(period_tax) + additional_withholding
```

## Sequencing and rounding notes (normative)

- Same discipline as `annualized_percentage`: round once at step 7 unless
  the worked examples demonstrate intermediate rounding. Wisconsin's
  W-166 examples display intermediate values at cents but the final
  amounts match exact arithmetic (e.g. $350 weekly single, 1 exemption →
  394.653… ÷ 52 → $7.59).
- Negative results clamp to 0 at steps 1, 3 (floor), and 4. Withholding is
  never negative.
