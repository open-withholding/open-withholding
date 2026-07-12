# Method: `custom/us_ct` (v1)

Connecticut's TPG-211 withholding calculation — the DESIGN §4 escape
hatch's founding member. Sixteen steps driven by five printed tables, all
keyed on the CT-W4 **withholding code** (A, B, C, D, F — encoded as the
election's filing_status) and annualized salary. No allowance counts.

This spec is **normative**. `/engine/methods/custom/us_ct.py` is the
reference implementation. Only control flow lives in code; every constant
comes from the parameter file (all five tables, row for row as printed).

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`pay_periods_per_year` **P**, `filing_status` = withholding code
(`a|b|c|d|f`), `additional_withholding` (CT-W4 line 2).

From params — `codes[<code>]`, each self-contained (shared printed tables
are duplicated per code by extraction, so a reviewer compares cell for
cell):

- `exemptions` — Table A rows
- `brackets` — Table B rows (`over`/`rate`/optional `base`; ordinary
  bracket convention, printed bases authoritative)
- `add_back` — Table C rows
- `recapture` — Table D rows
- `credits` — Table E rows (decimal amounts)

**Range-row semantics (Tables A/C/D/E):** rows are printed as "More Than
X / Less Than or Equal To Y" — the lower bound is EXCLUSIVE. Rows are
encoded `{more_than, value}` ascending, and the applicable row is the
LAST one with `more_than < salary` (strictly). A salary exactly on a
boundary belongs to the row below it: code A salary $24,000 → exemption
$12,000, not $11,000. A salary below the first row's range (Table E
starts above zero) yields value 0.

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule (TPG-211
states no rounding rule; cents are encoded).

```
 1-3. salary   = (gross_wages − reducing pretax deductions, clamp 0) × P
 4-5. exempt   = range_lookup(exemptions, salary)
 6.   taxable  = salary − exempt
      if taxable ≤ 0: withhold = additional_withholding; stop.
 7.   initial  = bracket(taxable) over brackets
 8.   addback  = range_lookup(add_back, salary)      [on SALARY, not taxable]
 9.   recap    = range_lookup(recapture, salary)     [on SALARY]
10.   total    = initial + addback + recap
11.   decimal  = range_lookup(credits, salary)       [on SALARY]
12.   tax      = total × (1 − decimal)
13.   period   = tax ÷ P
14-16. withhold = max(0, r(period) + additional_withholding)
```

## Notes (normative)

- Code D has no exemption and no credit (Table A/E footnotes) — its
  `exemptions`/`credits` tables are the single row `{more_than: "0",
  value: "0"}` / `{more_than: "0", value: "0.00"}`.
- CT-W4 line 3 (employee-requested REDUCED withholding) has no input
  field yet; only line-2 additional amounts are modeled.
- TPG-211 prints no worked examples; goldens are maintainer-constructed
  (or transcribed from IP 2026(1) where it prints calculation examples).
