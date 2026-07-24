# Method: `sui` (v1)

State unemployment insurance — an EMPLOYER tax computed per pay period
against the state's annual taxable wage base. The employer's experience
(contribution) rate is assigned annually by the state agency on a rate
notice: it is employer-specific and therefore ALWAYS an input
(`employer.sui_experience_rate`), never data. The data file carries what
the state publishes for everyone: the wage base, the new-employer
rate(s), the schedule's rate range, and any flat surtaxes.

This spec is **normative**. `/engine/methods/sui.py` is the reference
implementation, reached through `engine.pipeline.compute_employer_tax`.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`,
`ytd.sui_wages` (state-UI-taxable wages paid in PRIOR periods this
calendar year; defaults to 0), `employer.sui_jurisdiction` (must equal
the parameter file's jurisdiction — a mismatch fails loud), and
`employer.sui_experience_rate` (from the state rate notice; required).

From params (transcribed from the publication):

- `wage_base` — the annual taxable wage base
- `new_employer_rate` — the published default for new employers
  (informational; the engine still requires the entered rate — a new
  employer enters this value from their own notice)
- `new_employer_rate_construction` — where the state publishes a
  separate construction-industry new-employer rate (optional)
- `rate_range` — `{min, max}` of the published schedule INCLUDING any
  bundled surcharges the state folds into noticed rates (IL's Fund
  Builder; WI's solvency tax). The entered experience rate must fall
  within this range — outside it fails loud, catching typos and
  stale-year notices.
- `surtaxes` — optional list of `{name, rate, wage_base}` add-ons the
  state publishes as SEPARATE flat-rate taxes not included in the
  noticed rate. Each is computed like the main tax against its own wage
  base (capped by the same `ytd.sui_wages` tracker).

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule.

```
1. rate must satisfy rate_range.min ≤ rate ≤ rate_range.max
2. taxable = min(period wages, max(0, wage_base − ytd.sui_wages))
   tax     = r(taxable × rate)
3. for each surtax:
     s_taxable = min(period wages, max(0, surtax.wage_base − ytd.sui_wages))
     tax      += r(s_taxable × surtax.rate)
```

## Notes (normative)

- v1 computes taxable wages through the taxability matrix's `futa`
  column: both covered states' UI wage definitions follow the
  FUTA-style treatment of the modeled deduction types. A state whose UI
  wage definition diverges gets a dedicated matrix column before its
  sui file lands.
- The employer's noticed rate typically already includes bundled
  surcharges (IL Fund Builder, WI solvency); `surtaxes` is only for
  separately-published add-ons. The extraction hint for each source
  says which the state uses.
- An employee's wages count toward one state's base at a time in this
  model; multi-state transfers-of-wage-credit are out of scope for v1.
- Never negative; employer liability only.
