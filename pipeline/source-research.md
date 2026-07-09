# Source research: remaining state withholding publications

Gathered 2026-07-09 by six parallel source-hunting agents; every PDF URL
verified by download (%PDF magic) and every formula section skimmed from the
actual document. This is the raw material for registry entries and engine
work — with it, "add a state" starts at the document, not the hunt.

Conventions: URL_STABILITY drives the registry entry shape
(document_url_pattern vs link_scan); METHOD_SHAPE/ALLOWANCES/ROUNDING drive
method selection; WORKED_EXAMPLES tells you whether goldens will be
transcribed or maintainer-constructed; ENGINE GAP notes name the feature a
state is waiting on.

## Readiness summary

**Ready now (existing methods; registry entry + dispatch):**
MN (annualized), OH (annualized; Oct-1 reissue cadence), OK (per-period),
MT (per-period; note rounding defect), LA (per-period flat; examples decide
vs annualized), ME (phaseout method; verify 4dp-fraction rounding), DE
(annualized + existing credit_per_allowance — but formula text is HTML-only:
multi-source or maintainer-assembled).

**One small feature each:**
SC (allowance-gated 10%-capped percent-of-wages deduction), RI (exemption
cliff at annualized threshold), IA + MS (employee-entered dollar
amounts — same input feature as CO's DR 0004), AZ (employee-elected flat
rate), IN (third exemption kind + 92-county fanout from one PDF), NJ
(rate-letter selection; multi-source: two stable PDFs; examples image-only).

**Custom tier (dedicated spec each):**
NY (+NYC/Yonkers; 2D allowance table + high-income mandatory flat method),
CA (low-income cliff + wage-reduction and credit allowance kinds), UT
(credit phase-out; per-line dollar rounding), MA (FICA deduction with $2,000
cumulative annual cap; 9% surtax tier; nonlinear exemptions), OR + AL
(federal-withholding-as-input dependency; OR adds step phase-outs, AL adds
stepped deductions and income-tiered dependents), CT (16-step, five
interacting tables keyed on withholding codes), AR (midrange snap + $29
credits), MD (ten pre-combined state+local rate schedules — modeling
decision; 15% deduction repealed 2025, now flat $3,400).

**Cross-cutting infrastructure findings:**
- mass.gov needs full browser headers (Akamai); dor.ms.gov has a broken TLS
  chain (pin intermediate or relax verify); Ohio/MD/MS landing pages are
  JS-rendered (probe URL patterns directly).
- Reissue cadences vary: OH revises Oct 1; IN twice yearly (Oct 1 + Jan 1);
  UT mid-year (June 1 this cycle); MT/NJ revise in place rarely.
- New publication defects found for the QA letter-writing file: OK's example
  prose cites a stale constant; MT's rounding text contradicts its examples.

---

## al-ar-az-ca

```
STATE: AL
DOC_TITLE: Withholding Tax Tables and Instructions for Employers (REVISED January 2026)
PDF_URL: https://www.revenue.alabama.gov/wp-content/uploads/2026/01/whbooklet_0126.pdf
URL_STABILITY: year-versioned-ish (/wp-content/uploads/{yyyy}/01/whbooklet_01{yy}.pdf) but WP paths drift — link_scan safer
LANDING: https://www.revenue.alabama.gov/forms/withholding-tax-tables-and-instructions-for-employers-and-withholding-agents-2/
LINK_PATTERN: whbooklet[^"]*\.pdf
METHOD_SHAPE: annualized: subtract income-STEPPED standard deduction + annualized ACTUAL FEDERAL WITHHOLDING + personal exemption + income-dependent per-dependent amounts; 3 brackets (2/4/5%, M vs others)
ALLOWANCES: std ded steps down in $500 GI increments by status; fed-WH deduction (inter-tax dependency!); personal exemption 0/1500/3000 by A-4 status; dependents $1000/$500/$300 by GI tier
WORKED_EXAMPLES: yes p.7 (M-2 weekly $850 -> $29.59); p.8 = full stepped-deduction schedule
ROUNDING: examples keep cents; dollar rounding optional
NOTES: ENGINE GAPS: stepped (table-driven) deduction; federal-withholding deduction (depends on federal calc output); income-tiered dependent amounts. Custom-tier. Supplemental 5%.

STATE: AR
DOC_TITLE: Arkansas Withholding Tax Formula Method (eff. 2026-01-01)
PDF_URL: https://www.dfa.arkansas.gov/wp-content/uploads/Withholding-Tax-Formula.pdf
URL_STABILITY: stable-in-place
LANDING: https://www.dfa.arkansas.gov/office/taxes/income-tax-administration/withholding-tax-branch/withholding-tax-forms-instructions/
LINK_PATTERN: Withholding-Tax-Formula[^"]*\.pdf
METHOD_SHAPE: annualized with $50-midrange NTI snap below $97,701; single rate table as rate-minus-adjustment rows (0/2/3/3.4/3.7%); per-exemption $29/yr TAX CREDIT; annual tax rounded to dollar; per-period cents
ALLOWANCES: flat $2,470 std ded (no statuses); $29/yr credit per AR4EC exemption
WORKED_EXAMPLES: yes pp.3-4 (Gary: monthly $2,127, 2 exemptions -> $36.50)
ROUNDING: NTI midrange snap; annual tax -> whole dollar; period keeps cents
NOTES: ENGINE GAPS: midrange snap + rate-minus-adjustment form (convertible to base+rate? the adjustment ladder = equivalent; verify) + annual dollar rounding (intermediate_to covers). Probably new method or annualized variant. credit_per_allowance exists in schema already!

STATE: AZ
DOC_TITLE: Form A-4 (2026) + Employer's Instructions A-4i (2026)
PDF_URL: https://azdor.gov/sites/default/files/document/FORMS_WITHHOLDING_2026_A-4_f.pdf (+ ..._A-4i.pdf)
URL_STABILITY: year-versioned: FORMS_WITHHOLDING_{yyyy}_A-4_f.pdf / _A-4i.pdf
LANDING: https://azdor.gov/forms/withholding-forms/arizona-withholding-percentage-election
LINK_PATTERN: FORMS_WITHHOLDING_\d{4}_A-4_?[fi]\.pdf
METHOD_SHAPE: elective flat: elected% (0.5/1.0/1.5/2.0/2.5/3.0/3.5 or 0 w/ certification) x gross + optional extra dollars; default 2.0%
ALLOWANCES: none
WORKED_EXAMPLES: none for computation
ROUNDING: unspecified (trivial)
NOTES: two documents. ENGINE GAP: employee-elected rate input (design open Q5) — new method elective_flat_rate + input field elected_rate.

STATE: CA
DOC_TITLE: California Withholding Schedules 2026 — Method B Exact Calculation (parent DE 44)
PDF_URL: https://edd.ca.gov/siteassets/files/pdf_pub_ctr/26methb.pdf
URL_STABILITY: year-versioned: {yy}methb.pdf
LANDING: https://edd.ca.gov/en/payroll_taxes/rates_and_withholding/
LINK_PATTERN: \d{2}methb\.pdf
METHOD_SHAPE: per-period hybrid: (1) low-income exemption cliff -> $0; (2) subtract Table 2 estimated-deduction amount (DE 4 line 2 allowances); (3) subtract Table 3 std deduction; (4) per-period/status marginal tables (7 periods x statuses = Tables 5-28, base+rate form); (5) subtract Table 4 per-allowance CREDIT
ALLOWANCES: three kinds: low-income threshold (cliff), estimated-deduction allowances (wage reduction), regular allowances (tax credits); married-two-earner uses Single tables
WORKED_EXAMPLES: yes pp.2-4, Examples A-F incl. below-threshold -> $0
ROUNDING: cents throughout
NOTES: 26methb.pdf self-contained. ENGINE GAPS: low-income cliff; wage-reduction allowances + credit allowances simultaneously (secondary_allowances + credit_per_allowance could compose); per-period tables (method exists ✓). CA looks buildable as per_period_percentage + cliff + credits extension.
```

## ct-de-ia-in

```
STATE: CT
DOC_TITLE: TPG-211, 2026 Withholding Calculation Rules (Rev. 12/25)
PDF_URL: https://portal.ct.gov/-/media/drs/forms/2025/wth/tpg-211_1225.pdf
URL_STABILITY: cms-path-needs-link-scan (filename year-versioned tpg-211_12{yy}.pdf; directory year inconsistent)
LANDING: https://portal.ct.gov/drs/drs-forms/current-year-forms/withholding-forms
LINK_PATTERN: tpg-211[^"]*\.pdf
METHOD_SHAPE: custom 16-step: annualize -> Table A exemption (phases out $1,000-per-$1,000 over threshold) -> Table B brackets (3 variants by withholding code) -> ADD Table C 2%-rate phase-out add-back -> ADD Table D recapture (capped steps) -> multiply by (1 - Table E credit decimal .75..0) -> de-annualize -> +- CT-W4 line 2/3
ALLOWANCES: none — everything keys on CT-W4 withholding code (A/B/C/D/F) + salary
WORKED_EXAMPLES: none in TPG-211; companion IP 2026(1) has tables/examples: https://portal.ct.gov/-/media/drs/publications/pubsip/2026/ip-2026-1.pdf
ROUNDING: table values whole dollars; no explicit rule
NOTES: custom/us_ct as DESIGN predicted. 2026 unchanged from 2025. Two-doc likely (TPG-211 + IP for examples).

STATE: DE
DOC_TITLE: DE withholding tables (weekly16.pdf siblings) + formula in HTML Employer's Guide Section 17
PDF_URL: https://revenuefiles.delaware.gov/docs/weekly16.pdf (+daily16/bi-wk16/semi-mth16/month16.pdf)
URL_STABILITY: stable-in-place; DE rates unchanged since 2014
LANDING: https://revenue.delaware.gov/employers-guide-withholding-regulations-employers-duties/
LINK_PATTERN: (daily|weekly|bi-wk|semi-mth|month)16\.pdf
METHOD_SHAPE: annualized: gross annualized - std ded (3,250 single / 6,500 MFJ) -> 7 brackets (0% to 2,000 ... 6.6% over 60,000) -> minus $110 x exemptions (TAX CREDIT) -> / P
ALLOWANCES: std ded by status; $110/exemption credit (credit_per_allowance ✓ already in schema)
WORKED_EXAMPLES: yes, but in the HTML guide (3 annualized examples + bonus examples)
ROUNDING: annual tax whole dollars in examples; per-period cents
NOTES: MULTI-SOURCE: formula+examples HTML-only, tables in PDFs (like Idaho) — add to #26. Trap: /employers-guide-withholding-tables/ page stale-links 2000-era unsuffixed files.

STATE: IA
DOC_TITLE: Iowa Withholding Formula eff. 2026-01-01 (Nov 2025 release)
PDF_URL: https://revenue.iowa.gov/media/53/download?inline=
URL_STABILITY: stable-in-place (Drupal media node re-pointed annually; tables = media/52)
LANDING: https://revenue.iowa.gov/taxes/tax-guidance/withholding-tax/iowa-withholding-tax-information
LINK_PATTERN: /media/5[23]/download
METHOD_SHAPE: per-period flat: T1 = G - D(status); T2 = T1 x 3.8%; T3 = T2 - W/P (employee-entered DOLLAR allowance from IA W-4, prorated, subtracted from TAX); T4 = T3 + additional. Legacy pre-2024 W-4 path: allowances x $40 credits
ALLOWANCES: per-status per-period deduction (annual 13,000/19,500/26,000 by status); W = employee-entered dollars (credit); legacy allowances x $40
WORKED_EXAMPLES: yes pp.4-6, TEN examples
ROUNDING: cents at each step
NOTES: ENGINE GAPS: employee-entered dollar credit (same input feature as MS/CO DR-0004 — call it elected_credit_annual?); per-status deduction fits standard_deduction. Very buildable.

STATE: IN
DOC_TITLE: Departmental Notice #1 eff. 2026-01-01 (R46/01-26) — state + ALL 92 county rates
PDF_URL: https://www.in.gov/dor/files/dn01.pdf
URL_STABILITY: stable-in-place; REISSUED TWICE YEARLY (Oct 1 + Jan 1) — watcher should poll around both
LANDING: https://www.in.gov/dor/business-tax/withholding-income-tax/
LINK_PATTERN: n/a
METHOD_SHAPE: per-period via deduction constants: taxable = gross - (A + B + C per-period constants); state = taxable x 2.95%; county = taxable x county rate (same base)
ALLOWANCES: Table A $1,000/yr personal (incl. 65+/blind extras), Table B $1,500/yr dependents AND first-time-dependent extra, Table C $3,000/yr adopted child — three exemption kinds
WORKED_EXAMPLES: yes p.3 (weekly $800, mixed exemptions, county .01 -> state 13.96 county 4.73)
ROUNDING: cents
NOTES: County list embedded pp.4+ (92 counties, code+rate, asterisks mark changes) — THE Indiana locals source; one extraction can yield state file + 92 county local files. ENGINE GAPS: three exemption kinds (have two: allowances+secondary; need third or model adopted-child into schema), county local files generation.
```

## la-ma-md-me

```
STATE: LA
DOC_TITLE: R-1306 Louisiana Withholding Tables and Formulas (rev 1/26, eff 2026-01-01)
PDF_URL: https://dam.ldr.la.gov/taxforms/1306-1-26.pdf
URL_STABILITY: year-versioned: https://dam.ldr.la.gov/taxforms/1306-1-{yy}.pdf
LANDING: https://revenue.louisiana.gov/tax-policy/tax-manuals (stale-links prior year; prefer direct pattern probe)
LINK_PATTERN: 1306[^"]*\.pdf
METHOD_SHAPE: per-period flat: W = (S - SD/N) x 0.0309; SD by L-4 box code (0 -> none; 1 -> 12,875; 2 -> 25,750); negatives -> 0
ALLOWANCES: only the coded standard deduction (statuses '0'/'1'/'2' essentially)
WORKED_EXAMPLES: yes p.1 (weekly $700 code 1 -> 13.98; biweekly $4,600 code 2 -> 111.54)
ROUNDING: SD/N and final to cents
NOTES: 2026 rate 3.09% (2025 was 3.00% — rate is annual variable). Likely fits per_period_percentage (annual-divided deduction + single-row tables) or plain annualized (differences sub-cent; examples decide at review).

STATE: MA
DOC_TITLE: Circular M 2026 (5% + 4% surtax in percentage method)
PDF_URL: https://www.mass.gov/doc/massachusetts-circular-m-income-tax-withholding-tables-at-50-effective-january-1-2026/download
URL_STABILITY: cms-path-needs-link-scan (slug embeds year+rate); mass.gov needs FULL browser headers (Akamai 403s plain UA+Accept)
LANDING: https://www.mass.gov/lists/massachusetts-dor-withholding-tax-forms
LINK_PATTERN: /doc/[^"]*circular-m[^"]*/download
METHOD_SHAPE: annualized: wages minus ACTUAL FICA/Medicare/retirement withheld (cumulative $2,000/yr cap — mid-year cutoff!) minus exemption factor -> annualize -> 5% to $1,107,750 + 9% above -> de-annualize -> minus HoH ($120/yr) and blindness ($110/yr) TAX credits
ALLOWANCES: exemption factor: $4,400 if claiming 1; $1,000 x n + $3,400 if n>1; spouse counts as 4; skip if 0. Low-income: no WH if >=1 exemption and wages < $8,000/yr
WORKED_EXAMPLES: only supplemental-wage example (p.13); none for the regular method
ROUNDING: no explicit rule
NOTES: ENGINE GAPS: FICA-withheld wage deduction with cumulative annual cap (needs YTD FICA input + our own FICA calc), surtax tier fits brackets, nonlinear exemption factor (n=1 special case), tax credits fit. Custom-tier-adjacent. Wage-bracket tables lack the surtax — percentage method mandatory for correctness.

STATE: MD
DOC_TITLE: 2026 Maryland Employer Withholding Guide
PDF_URL: https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/instructions/withholding/2026/withholding-guide.pdf
URL_STABILITY: year-versioned .../withholding/{year}/withholding-guide.pdf (filename CASE varies by year)
LANDING: ServiceNow KB, JS-rendered — probe the DAM pattern directly
LINK_PATTERN: /withholding/\d{4}/[Ww]ithholding-[Gg]uide\.pdf
METHOD_SHAPE: per-period bracket schedules, one full set per pre-combined state+local rate (10 sets: 2.25..3.30%), split (a) MFJ/HoH/QSS vs (b) Single/MFS/Dependent; employer picks schedule >= employee's county rate
ALLOWANCES: FLAT $3,400/yr standard deduction (15% min/max REPEALED by 2025 legislation!) + $3,200/yr per MW507 exemption; per-period no-withholding floors printed
WORKED_EXAMPLES: none
ROUNDING: bases printed to cents; no explicit rule
NOTES: modeling decision needed: 10 schedule-sets as a rate dimension (county -> schedule mapping is employer-side); nonresident 2.25% special rate; MD-resident-in-DE schedule (3.30%). Standalone per-rate PDFs exist (pm{rate}.pdf). Counties may have progressive local rates by statute but withholding collapses to flat schedules.

STATE: ME
DOC_TITLE: Maine Withholding Tables for Individual Income Tax 2026
PDF_URL: https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/26_wh_tab_instr.pdf
URL_STABILITY: year-versioned: {yy}_wh_tab_instr.pdf (landing also year-versioned)
LANDING: https://www.maine.gov/revenue/tax-return-forms/employment-tax-returns-2026
LINK_PATTERN: \d{2}_wh_tab_instr\.pdf
METHOD_SHAPE: annualized + LINEAR SD phase-out (multiplicative form: SD x (ceiling - wages)/range, fraction rounded 4dp) -> allowances $5,300 each -> 3 brackets w/ printed bases (single 5.8/6.75/7.15; married variants)
ALLOWANCES: W-4ME allowances x $5,300; phasing SD (single 12,450 phase 102,250..177,250; married 27,750 phase 204,550..354,550)
WORKED_EXAMPLES: yes pp.6-7, THREE examples incl. $0 clamp and phase-out case
ROUNDING: phase fraction 4 decimals; FINAL per-period to nearest whole dollar
NOTES: multiplicative phase-out == our annualized_percentage_phaseout with phase_rate = SD/range (single 0.166, married 0.185) EXCEPT the 4dp-fraction rounding path — may differ ~$1 in deduction; final dollar rounding probably absorbs (verify via examples at extraction). Daily factor 260. Fallback default single/0.
```

## mn-ms-mt-nj

```
STATE: MN
DOC_TITLE: 2026 Minnesota Income Tax Withholding Instruction Booklet and Tax Tables
PDF_URL: https://www.revenue.state.mn.us/sites/default/files/2025-12/wh-inst-26.pdf
URL_STABILITY: cms-path-needs-link-scan (upload-month dir varies; _0 dedup suffixes some years)
LANDING: https://www.revenue.state.mn.us/withholding-tax (CONFIRMED links the booklet — earlier JS-search concern resolved)
LINK_PATTERN: /sites/default/files/\d{4}-\d{2}/wh[-_]inst[-_]?\d{2}(_\d+)?\.pdf
METHOD_SHAPE: annualized Computer Formula (p.34): annualize (360/52/26/24/12/1) - allowances -> 4 brackets per status (5.35/6.8/7.85/9.85, cumulative form)
ALLOWANCES: $5,300 x W-4MN allowances from annualized wages
WORKED_EXAMPLES: none
ROUNDING: permissive dollar rounding
NOTES: fits annualized_percentage TODAY; constructed goldens needed. Daily factor 360.

STATE: MS
DOC_TITLE: Pub 89-700-25-1 (Rev 07/25; file revised 1.13.2026; tables eff 2026-01-01)
PDF_URL: https://www.dor.ms.gov/sites/default/files/tax-forms/business/89700251revised1.13.2026.pdf
URL_STABILITY: cms-path-needs-link-scan with ad-hoc revised-date suffixes; STALE guessable sibling /files/business/89700251.pdf has 2024 rates — never path-guess
LANDING: https://www.dor.ms.gov/business/withholding-tax
LINK_PATTERN: 89700\d{3}[a-z0-9.]*\.pdf (take the landing-linked one)
METHOD_SHAPE: TY2026: 0% first $10,000 + flat 4% above. Tables A-D by status x frequency indexed by EMPLOYEE-WRITTEN DOLLAR exemption ($500 steps); general annualized fallback: annualize - exemption dollars - std ded -> tax -> /P
ALLOWANCES: employee writes total dollar exemption on 89-350 (status amounts + $1,500/dependent); std ded by status baked into tables, explicit in fallback
WORKED_EXAMPLES: none for computation
ROUNDING: annualized fallback rounds to whole dollar
NOTES: TLS: dor.ms.gov serves incomplete cert chain — fetcher needs the intermediate CA pinned or verify relaxed. Rate glide path (4.4->4.0->...). ENGINE GAP: elected-dollar exemption input (shared with IA/CO-DR0004). Encode the annualized fallback formula, not the tables.

STATE: MT
DOC_TITLE: Montana Employer and Information Agent Guide with Tax Tables (V4 Nov 2025; 2026 rates per HB 337)
PDF_URL: https://revenuefiles.mt.gov/files/Forms/Montana_Employer_and_Information_Agent_Guide_with_Tax_Tables.pdf
URL_STABILITY: stable-in-place
LANDING: https://revenue.mt.gov/publications/montana-employer-and-information-agent-guide
LINK_PATTERN: n/a
METHOD_SHAPE: per-period W = A + B x (G - C), 3 brackets (0/4.7/5.65) published per period x 3 statuses; formula duplicates tables
ALLOWANCES: none (MW-4 = status + optional extra dollars); std ded embedded in 0% bracket
WORKED_EXAMPLES: yes, 3 per status page (pp.17-19)
ROUNDING: DOC DEFECT: text says round UP to nearest dollar; every example rounds to NEAREST. Follow examples; flag to MT DOR.
NOTES: fits per_period_percentage TODAY (A/B/C == base/rate/over!). Separate Publication 1 exists but this guide is the source.

STATE: NJ
DOC_TITLE: NJ-WT (rev 09/2025) + Percentage Method Rate Tables A-E (eff 10/2020, still current)
PDF_URL: https://www.nj.gov/treasury/taxation/pdf/withholdingtables.pdf (tables); https://www.nj.gov/treasury/taxation/pdf/current/njwt.pdf (instructions + allowance values)
URL_STABILITY: stable-in-place (both; rates static since 10/2020)
LANDING: https://www.nj.gov/treasury/taxation/businesses/payroll/index.shtml (links NJ-WT; tables PDF linked only from INSIDE NJ-WT)
LINK_PATTERN: n/a (fixed URLs)
METHOD_SHAPE: per-period tables, five rate letters A-E selected via NJ-W4 (status boxes + line 3 election), 8 periods each, cumulative form
ALLOWANCES: $1,000/yr per exemption via printed per-period values ($19.20 weekly etc.)
WORKED_EXAMPLES: exist (NJ-WT p.25) but IMAGE-ONLY — needs OCR/manual read for golden transcription
ROUNDING: permissive dollar rounding; some table constants exact cents
NOTES: MULTI-SOURCE: params split across two stable PDFs (tables + allowance values). Rate letters model as filing statuses (A-E) with employer selection logic in notes; elective aspect (line 3) is employee input. Low churn.
```

## ny-oh-ok-or

```
STATE: NY
DOC_TITLE: NYS-50-T-NYS (Rev 1/26, eff 2026)
PDF_URL: https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys.pdf
URL_STABILITY: stable-in-place
LANDING: https://www.tax.ny.gov/forms/withholding_cur_forms.htm
LINK_PATTERN: n/a
METHOD_SHAPE: Method II exact calc = PER-PERIOD bracket tables in (net - col3) x rate + col5 form, recapture baked into rates; Method III MANDATORY flat top-rate when annualized net >= 1,077,550 single / 2,155,350 married (x .1045/.1110/.1170)
ALLOWANCES: combined deduction+exemption Table A by period/status/0-10 exemptions subtracted from wages; >10: Table B deduction + $1,000/yr x count (Table C)
WORKED_EXAMPLES: yes pp.16+18 (8 Method II examples), Method III steps p.22
ROUNDING: cents, no dollar rounding
NOTES: NYC companion: https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf ; Yonkers: https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (both stable, Rev 1/26). ENGINE GAPS: Table-A combined amounts (per period x status x exemption count — a 2D lookup, not linear!), Method III high-income override. per_period_percentage handles the tables; needs allowance-table + flat-override features.

STATE: OH
DOC_TITLE: Employer Withholding Optional Computer Formula (Rev 09/25, eff 2025-10-01) + Percentage Method companion
PDF_URL: https://dam.assets.ohio.gov/image/upload/tax.ohio.gov/employer_withholding/2025%20Withholding%20Tables/WHT_OptionalComputerFormula_2025.pdf
URL_STABILITY: cms-ish pattern with {year} but revised IN PLACE mid-year; landing JS-rendered (curl gets no hrefs)
LANDING: https://tax.ohio.gov/business/ohio-business-taxes/employer-withholding/employer-withholding-tables
LINK_PATTERN: WHT_OptionalComputerFormula_\d{4}\.pdf (needs JS-rendered scan or direct probe)
METHOD_SHAPE: annualized 3 brackets: TW = wages x P - 650 x exemptions; <=26,050: 1.775%; to 100k: 462.39 base + 2.99%; above: 2,673.50 + 3.64%. THE 1.032 MULTIPLIER IS GONE (baked into these withholding-specific rates)
ALLOWANCES: $650/yr per exemption
WORKED_EXAMPLES: none
ROUNDING: unspecified; constants to cents
NOTES: DOT bulletin (Feb 2026): keep using Oct-1-2025 tables despite 2026 rate changes — reissue cadence is Oct 1, not Jan 1. Fits annualized_percentage TODAY (constructed goldens needed). Municipal + school district rates: The Finder (thefinder.tax.ohio.gov, downloadable DB, 403s curl) — separate locals workstream.

STATE: OK
DOC_TITLE: Packet OW-2 2026 (Rev 11-2025)
PDF_URL: https://oklahoma.gov/content/dam/ok/en/tax/documents/resources/publications/businesses/withholding-tables/WHTables-2026.pdf
URL_STABILITY: year-versioned: WHTables-{year}.pdf (2022-2026 confirmed)
LANDING: https://oklahoma.gov/tax/reporting-resources/publications.html (NOT the withholding page)
LINK_PATTERN: WHTables-\d{4}\.pdf
METHOD_SHAPE: per-period tables 1-8, single/married, cumulative base+rate form; zero bracket embeds std deduction; 2026 rates 2.5/3.5/4.5
ALLOWANCES: $1,000/yr per OK-W-4 allowance, per-period division printed
WORKED_EXAMPLES: yes p.7 (semimonthly married $1,825, 2 allowances -> 36.67 -> $37.00). QA FLAG: prose says "$12.19 plus 4.5%" where table+math use $9.10 — stale-text artifact.
ROUNDING: MANDATORY nearest whole dollar
NOTES: fits per_period_percentage TODAY. Percentage formula mandatory above the last bracket row.

STATE: OR
DOC_TITLE: Oregon Withholding Tax Formulas 150-206-436 (Rev 12-31-25, eff 2026)
PDF_URL: https://www.oregon.gov/dor/forms/FormsPubs/withholding-tax-formulas_206-436_2026.pdf
URL_STABILITY: year-versioned: withholding-tax-formulas_206-436_{year}.pdf
LANDING: https://www.oregon.gov/dor/forms/Pages/default.aspx
LINK_PATTERN: withholding-tax-formulas_206-436_\d{4}\.pdf
METHOD_SHAPE: annualized, tiered by wage band and status: BASE = wages - fed tax withheld (capped $8,750, phased out in $1,750 STEPS over 125-145k/250-290k) - std ded; WH = printed base + marginal rate on BASE; minus $263 x allowances (TAX credit); allowances FORCED to 0 above 100k/200k
ALLOWANCES: three mechanisms: capped+step-phased federal-tax subtraction (needs federal WH as input!); std ded 2,910/5,820 (by status AND allowance count >=3); $263/allowance credit with high-income zeroing
WORKED_EXAMPLES: yes p.5 (4 examples incl. cap + zeroed allowances) + FAQ examples
ROUNDING: optional dollar rounding ("may")
NOTES: ENGINE GAPS: federal-withholding input dependency (shared with AL/MA), step-function phase-out, conditional std ded, credit zeroing. Custom-tier. p.7 layout prints [S] phase-out schedule twice — parsing hazard.
```

## ri-sc-ut

```
STATE: RI
DOC_TITLE: 2026 Rhode Island Employer's Income Tax Withholding Tables (effective wages paid on/after 2026-01-01)
PDF_URL: https://tax.ri.gov/sites/g/files/xkgbur541/files/2025-12/2026%20Withholding%20Tax%20Booklet.pdf
URL_STABILITY: cms-path-needs-link-scan (Drupal /sites/g/files/xkgbur541/files/{YYYY-MM}/...; suffix variants across years)
LANDING: https://tax.ri.gov/forms/business-tax-forms/withholding-tax-forms
LINK_PATTERN: (?i)/sites/g/files/[^"]*20\d{2}[^"]*withholding[^"]*\.pdf
METHOD_SHAPE: per-period percentage (Tables 1-8 prorate one 3-bracket schedule: 3.75%/4.75%/5.99%); single schedule for ALL statuses ('all')
ALLOWANCES: $1,000/yr per RI W-4 exemption (per-period values printed, e.g. $19.23 weekly), max 10; CLIFF phase-out — exemption value becomes exactly $0 when annualized wages exceed $290,800 (threshold inflation-indexed)
WORKED_EXAMPLES: yes, p.8 (weekly $2,195, 1 exemption -> $87.57)
ROUNDING: cents throughout
NOTES: one booklet has everything incl. wage-bracket tables + RI W-4. New booklet each December. ENGINE GAP: exemption cliff (per_period_percentage has no wage-conditional allowance zeroing).

STATE: SC
DOC_TITLE: WH-1603F, Formula for Computing South Carolina 2026 Withholding Tax (Rev. 11/4/25)
PDF_URL: https://dor.sc.gov/sites/dor/files/forms/WH1603F_2026.pdf
URL_STABILITY: year-versioned: https://dor.sc.gov/sites/dor/files/forms/WH1603F_{year}.pdf (site migrated; old /forms-site/Forms/ pattern dead for 2026+)
LANDING: https://dor.sc.gov/tax/withholding/forms
LINK_PATTERN: WH1603F_{year}\.pdf
METHOD_SHAPE: annualized_percentage, 3 brackets (0% to 3,640; 3% to 18,230; 6% above), printed in subtraction AND addition forms (addition form = our base+rate model)
ALLOWANCES: $5,000/yr per allowance; standard deduction = 10% of gross capped $7,500/yr — BOTH zero when zero allowances claimed (allowance-gated)
WORKED_EXAMPLES: yes, p.1 (three: $750/wk 3 allowances -> $10.58/wk)
ROUNDING: cents throughout
NOTES: 1-page doc + separate WH-1603 bracket tables. ENGINE GAP: percentage-of-wages standard deduction with cap, gated on allowances>0.

STATE: UT
DOC_TITLE: Publication 14, Utah Withholding Tax Guide (Rev. 4/26, effective pay periods on/after 2026-06-01)
PDF_URL: https://files.tax.utah.gov/tax/forms/pubs/pub-14.pdf
URL_STABILITY: stable-in-place (files.tax.utah.gov host; old tax.utah.gov path 404s); mid-year revisions — Rev. date on p.1 is the version signal
LANDING: https://tax.utah.gov/forms-pubs/pubs/pub-14/
LINK_PATTERN: n/a
METHOD_SHAPE: flat 4.45% + credit-based phase-out per period/status: tentative = wages x 4.45%; credit = max(0, base - 1.3% x max(0, wages - threshold)); withhold = max(0, tentative - credit)
ALLOWANCES: none — only federal W-4 status (Single/Married; HoH uses Single). Annual: base 485/threshold 9,348 (single), 970/18,696 (married); per-period values printed per schedule
WORKED_EXAMPLES: yes, p.11 (six examples across frequencies/statuses)
ROUNDING: EVERY worksheet line rounded to whole dollars in the examples
NOTES: single doc. ENGINE GAP: credit-phase-out method (was expected — custom tier); note per-line dollar rounding.
```

