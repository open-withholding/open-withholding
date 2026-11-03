# External parity check

A one-time proof that an independent payroll calculator agrees with this
dataset and engine, done by hand (DESIGN §10). Nothing here is agency data:
parity rows never become goldens, and a disagreement is adjudicated against
the publication — the external calculator can be wrong too.

```sh
python tools/parity.py generate    # rebuild scenarios/ from the goldens' election shapes
python tools/parity.py worksheet   # WORKSHEET.md: what to type, and the engine's answer
python tools/parity.py report      # compare expected.csv against the engine (CI runs this too)
```

How to fill it in:

1. Open `WORKSHEET.md`. Core rows (one biweekly $2,000 case per
   jurisdiction and tax) come first; extended rows only matter where a core
   row disagrees.
2. Enter the scenario into the external calculator (PaycheckCity or a state
   revenue department's own calculator). Record **only the tax named in the
   heading** — the state income tax line, not the whole paycheck — as
   dollars and cents.
3. Append a line to `expected.csv`: `id,expected,source,entered_on,note`,
   e.g. `us-ca-p01,61.12,PaycheckCity,2026-11-02,`.
4. `python tools/parity.py report`. Matches are within one cent; anything
   else is a finding to adjudicate against the publication.

Mapping notes: our `allowances` is the certificate's regular allowance
count; `secondary_allowances` is the second line where one exists (CA DE 4
estimated-deduction allowances, HI, IL). `resident` on a local picks the
resident or nonresident rate. SUI scenarios use the published new-employer
rate as the employer's rate. Calculators that round withholding to whole
dollars (an option Pub 15-T permits) will differ by up to fifty cents on the
federal line; note it and move on.
