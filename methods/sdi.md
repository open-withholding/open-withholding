# Method: `sdi` (v1.1)

State disability insurance and paid family / medical leave — the EMPLOYEE
contribution withheld from wages each pay period (CA SDI, NJ TDI + FLI,
NY DBL + PFL, MA PFML, RI TDI, HI TDI, WA/OR/CO/MN/DE paid leave, …).
One parameter file per state (`tax: state_disability_insurance`,
`data/us/<st>/<year>/sdi.yaml`) lists the programme's **components**;
each is a flat rate on wages, optionally capped by an annual wage base
and by a printed per-period maximum. Employer-side contributions are not
withholding and are out of scope (they belong with FUTA/SUI).

This spec is **normative**. `/engine/methods/sdi.py` is the reference
implementation.

## Inputs

From the employee input record: `gross_wages`, `pretax_deductions`
(reduced per the taxability matrix column named by `wage_definition`),
`pay_frequency`, `ytd.sdi_wages` (programme-taxable wages paid in PRIOR
periods this calendar year; defaults to 0 — exact for a first paycheck,
conservative otherwise). No filing status or elections apply.

From params (all printed values transcribed verbatim):

- `wage_definition` — which taxability-matrix wage base defines the
  programme's wages: `fica` (default — most programmes follow the UI /
  FICA treatment of pre-tax deductions), `futa`, or `state_income`.
- `components[]` — one entry per published contribution:
  - `name` — the programme's own label (`SDI`, `TDI`, `FLI`, `DBL`,
    `PFL`, `family`, `medical`, …)
  - `rate` — the published rate as a decimal fraction
  - `employee_share` — the fraction of `rate` the employee pays: `"1"`
    where the publication states the employee rate itself (CA, NY PFL,
    MA's per-share rates); the printed split where it states a total
    rate and a share (WA, OR, CO, MN, DE)
  - `wage_base` — annual taxable wage limit, or null where the programme
    has none (CA SDI since 2024, NY DBL)
  - `weekly_max` — the maximum contribution where the publication defines
    it PER WEEK (NY DBL: "no more than sixty cents a week"; HI TDI: the
    "maximum weekly deduction"). A period's cap is `weekly_max × 52 ÷
    pay periods`, rounded to the cent — weekly 0.60, biweekly 1.20,
    semimonthly 1.30, monthly 2.60 for NY DBL, the figures payroll
    practice uses. Null where the publication defines no weekly cap.
  - `period_max` — `{frequency: amount}` where the publication prints a
    per-period maximum TABLE, or null. Only printed frequencies are
    encoded; an unprinted frequency fails loud rather than prorating.
    (A cap stated once per week is `weekly_max`, not a one-row table.)
- envelope `rounding` (cents, nearest)

## Algorithm

All arithmetic in Decimal; `r(x)` = the envelope rounding rule; `wages` =
this period's programme-taxable wages; `ytd` = `ytd.sdi_wages`.

```
for each component:
  1. effective_rate = rate × employee_share            (exact)
  2. subject = wages                                   if wage_base is null
             = min(wages, max(0, wage_base − ytd))     otherwise
  3. amount  = r(subject × effective_rate)
  4. amount  = min(amount, r(weekly_max × 52 ÷ periods))  if weekly_max
     amount  = min(amount, period_max[frequency])          if period_max printed
withhold = Σ amount
```

## Notes (normative)

- Each component is rounded to the cent independently, then summed — the
  publications state and cap each contribution separately.
- One `ytd.sdi_wages` tracker serves every component of a state's file:
  the programmes within a state share a wage definition, and a component
  without a base simply ignores it. A state whose components use
  different wage definitions gets two files, not one.
- `employee_share` keeps the publication's own framing: a state that
  prints "1.0% total, employees pay 60%" is transcribed as rate 0.0100
  and share 0.60 — never pre-multiplied — so the verifier can confirm
  both numbers against the page.
- The wage base caps WAGES, not contributions: a published "maximum
  annual contribution" that is rate × a wage ceiling is transcribed as
  that wage ceiling (NY PFL: the statewide average weekly wage × 52).
- v1.1 (2026-10-28): `weekly_max` added. v1's `period_max` alone made a
  weekly-defined cap unusable for any other payroll frequency (the NY
  DBL file would have failed loud for every biweekly employer).
- Withholding is never negative; all params are non-negative.
