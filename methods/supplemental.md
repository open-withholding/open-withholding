# Methods: `supplemental_flat_rate` and `supplemental_aggregate` (v1)

Supplemental wages — bonuses, commissions, overtime paid separately,
severance, back pay, vested stock — are withheld under rules that differ
from the regular percentage method. Each jurisdiction's supplemental file
(`tax: supplemental_wage_withholding`, `data/us/<st>/<year>/supplemental.yaml`,
`data/us/federal/<year>/supplemental.yaml`) records which of two methods
applies. The registry extracts both under the method name `supplemental`;
the assembled file carries the concrete name.

This spec is **normative**. `/engine/methods/supplemental_flat_rate.py` and
`/engine/pipeline.py::compute_supplemental_withholding` are the reference
implementations.

## Inputs

From the employee input record: `gross_wages` is the **supplemental
payment**; `wage_type: supplemental`; `pretax_deductions` taken from that
payment (reduced per the taxability matrix for the jurisdiction's income
column, as for regular wages); `ytd.supplemental_wages` (calendar-year
supplemental wages paid before this payment); and, for the aggregate
method, `concurrent_regular_wages` — the regular wages of the current or
most recent payroll period (Pub 15 §7: when supplemental wages are paid
separately, add them to the regular wages for the current or most recent
period). Certificates (`federal`, `state`) are read only by the aggregate
method, which runs the regular formula.

## `supplemental_flat_rate`

From params: `rate`; optionally `excess_rate` and `excess_threshold` (the
federal mandatory 37% on cumulative supplemental wages over $1,000,000).

```
1. taxable   = gross_wages − Σ pretax_deductions that reduce this base; floor 0
2. ytd       = ytd.supplemental_wages (0 if absent)
3. if excess_threshold is set:
       below = max(0, min(taxable, excess_threshold − ytd))
       above = taxable − below
   else: below = taxable, above = 0
4. withhold  = r(below × rate + above × excess_rate)
```

No allowances, filing status or certificate extras apply; `additional_withholding`
is not added (it belongs to the regular paycheck). Withholding is never negative.

## `supplemental_aggregate`

Params: none. The jurisdiction publishes no flat option: supplemental wages
are combined with regular wages and withheld under the regular method.

```
1. combined  = withhold_regular(concurrent_regular_wages + gross_wages)
2. regular   = withhold_regular(concurrent_regular_wages)
3. withhold  = max(0, combined − regular)
```

`withhold_regular` is the jurisdiction's regular income-withholding file
(`state_income_withholding` / `federal_income_withholding`) in effect on
the same date, applied to the employee's certificate as given, with the
pretax deductions attached to the input applied once to the combined
amount. A consumer that computes the regular paycheck itself may instead
run the regular method on the combined wages and subtract what it already
withheld.

## Notes (normative)

- A jurisdiction with a flat option may still require aggregation in
  particular cases (federal: no income tax withheld from regular wages in
  the current or preceding year). The file records the published flat
  rule; applying the exception is the caller's determination.
- Where a state's only published rule is "withhold as for regular wages"
  or "use the aggregate method", the file is `supplemental_aggregate`.
- A state whose supplemental rate is expressed as a percentage of the
  federal supplemental withholding (Vermont) is out of scope for v1.
