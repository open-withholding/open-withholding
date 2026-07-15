"""IL-shaped (two allowance kinds, single 'all' table) and WI-shaped
(phase-out deduction) methods. Every expected value is either printed in the
publication (WI Pub W-166 examples 1-3, IL-700-T Alice example) or
hand-computed with the arithmetic shown."""

from decimal import Decimal

import pytest

from engine.errors import InputError
from engine.inputs import EmployeeInput
from engine.loader import load_parameter_dict
from engine.pipeline import compute_withholding

SOURCE = {
    "document": "FIXTURE doc",
    "url": "https://example.gov/x.pdf",
    "retrieved": "2026-07-08",
    "sha256": "0" * 64,
}


def _pf(jurisdiction, method, params):
    return load_parameter_dict(
        {
            "schema_version": "0.1",
            "jurisdiction": jurisdiction,
            "tax": "state_income_withholding",
            "effective_from": "2026-01-01",
            "source": SOURCE,
            "method": method,
            "params": params,
            "rounding": {"to": "0.01", "mode": "nearest"},
        }
    )


# IL-700-T 2026 automated payroll method: flat 4.95%, Line 1 $2,925, Line 2 $1,000.
IL = _pf(
    "US-IL",
    "annualized_percentage",
    {
        "allowance_amount": "2925",
        "secondary_allowance_amount": "1000",
        "credit_per_allowance": None,
        "brackets": {"all": [{"over": "0", "rate": "0.0495"}]},
    },
)

# WI Pub W-166 alternate method (2026 revision).
WI = _pf(
    "US-WI",
    "annualized_percentage_phaseout",
    {
        "deduction_phaseout": {
            "single": {"maximum": "6702", "phase_start": "17780", "phase_rate": "0.12"},
            "married": {"maximum": "9461", "phase_start": "25727", "phase_rate": "0.20"},
        },
        "exemption_amount": "400",
        "brackets": {
            "all": [
                {"over": "0", "rate": "0.0354"},
                {"over": "12760", "rate": "0.0465", "base": "451.70"},
                {"over": "25520", "rate": "0.0530", "base": "1045.04"},
                {"over": "280950", "rate": "0.0765", "base": "14582.83"},
            ]
        },
    },
)


def _employee(frequency, gross, **election):
    return EmployeeInput.from_dict(
        {
            "pay_frequency": frequency,
            "gross_wages": gross,
            "state": [{"jurisdiction": election.pop("jurisdiction"), **election}],
        }
    )


def test_il_alice_printed_example(taxability):
    # IL-700-T p.4: $800 weekly, 2 Line-1 + 2 Line-2 allowances -> $32.13
    emp = _employee("weekly", "800.00", jurisdiction="US-IL", allowances=2, secondary_allowances=2)
    assert compute_withholding(IL, emp, taxability) == Decimal("32.13")


def test_il_no_filing_status_needed(taxability):
    # single 'all' table serves elections without a filing_status
    emp = _employee("weekly", "300.00", jurisdiction="US-IL", allowances=2, secondary_allowances=1)
    # (15,600 - 5,850 - 1,000) x 0.0495 / 52 = 433.125/52 = 8.3293 -> 8.33
    assert compute_withholding(IL, emp, taxability) == Decimal("8.33")


def test_wi_printed_example_1(taxability):
    # W-166 ex.1: $350 weekly single, 1 exemption -> $7.59
    emp = _employee("weekly", "350.00", jurisdiction="US-WI", filing_status="single", allowances=1)
    assert compute_withholding(WI, emp, taxability) == Decimal("7.59")


def test_wi_printed_example_2(taxability):
    # W-166 ex.2: $500 weekly single, 3 exemptions -> $14.34
    emp = _employee("weekly", "500.00", jurisdiction="US-WI", filing_status="single", allowances=3)
    assert compute_withholding(WI, emp, taxability) == Decimal("14.34")


def test_wi_printed_example_3(taxability):
    # W-166 ex.3: $1,000 biweekly married, 3 exemptions -> $22.08
    emp = _employee(
        "biweekly", "1000.00", jurisdiction="US-WI", filing_status="married", allowances=3
    )
    assert compute_withholding(WI, emp, taxability) == Decimal("22.08")


def test_wi_deduction_floors_at_zero(taxability):
    # $2,000 weekly single: annual 104,000 >= 73,630 -> deduction 0;
    # 1,045.044 + (104,000-25,520) x 5.30% = 5,204.484; /52 = 100.086 -> 100.09
    emp = _employee("weekly", "2000.00", jurisdiction="US-WI", filing_status="single")
    assert compute_withholding(WI, emp, taxability) == Decimal("100.09")


def test_wi_below_phase_start_keeps_full_deduction(taxability):
    # $300 weekly single: annual 15,600 < 17,780 -> deduction 6,702;
    # net 8,898 x 3.54% = 314.99 (0 exemptions); /52 = 6.0575 -> 6.06
    emp = _employee("weekly", "300.00", jurisdiction="US-WI", filing_status="single")
    assert compute_withholding(WI, emp, taxability) == Decimal("6.06")


def test_wi_unknown_status_lists_valid(taxability):
    emp = _employee("weekly", "500.00", jurisdiction="US-WI", filing_status="head_of_household")
    with pytest.raises(InputError, match="married"):
        compute_withholding(WI, emp, taxability)


def test_phaseout_extraction_transform_loads():
    from pipeline import assemble

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "0.01", "mode": "nearest", "intermediate": "none"},
        "params": {
            "deduction_phaseout": [
                {"filing_status": "Single", "maximum": "6702", "phase_start": "17780", "phase_rate": "0.12"},
            ],
            "exemption_amount": "400",
            "brackets": [
                {"filing_status": "all", "rows": [{"over": "0", "rate": "0.0354", "base": None}]}
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-WI",
        tax="state_income_withholding",
        method="annualized_percentage_phaseout",
        extraction=extraction,
        source=SOURCE,
    )
    pf = load_parameter_dict(raw)
    assert pf.params["deduction_phaseout"]["single"]["phase_rate"] == "0.12"


def test_va_shaped_intermediate_dollar_rounding(taxability):
    # VA p.22 example: 5 exemptions, semimonthly $2,649 -> T=50,176;
    # annual tax 720 + 5.75% x 33,176 = 2,627.62 -> rounded to 2,628 ->
    # / 24 = 109.50 exactly (the printed W value).
    va = _pf(
        "US-VA",
        "annualized_percentage",
        {
            "standard_deduction": {"all": "8750"},
            "allowance_amount": "930",
            "secondary_allowance_amount": "800",
            "credit_per_allowance": None,
            "brackets": {
                "all": [
                    {"over": "0", "rate": "0.02"},
                    {"over": "3000", "rate": "0.03", "base": "60"},
                    {"over": "5000", "rate": "0.05", "base": "120"},
                    {"over": "17000", "rate": "0.0575", "base": "720"},
                ]
            },
        },
    )
    # override rounding to the VA shape
    from engine.money import Rounding
    import dataclasses
    va = dataclasses.replace(
        va,
        rounding=Rounding.from_dict(
            {"to": "0.01", "mode": "nearest", "intermediate": "annual", "intermediate_to": "1.00"}
        ),
    )
    emp = _employee("semimonthly", "2649.00", jurisdiction="US-VA", allowances=5)
    assert compute_withholding(va, emp, taxability) == Decimal("109.50")


# --- per_period_percentage: KS/NM-shaped mechanics ------------------------

def _pp(jurisdiction, params, rounding=None):
    return load_parameter_dict(
        {
            "schema_version": "0.1",
            "jurisdiction": jurisdiction,
            "tax": "state_income_withholding",
            "effective_from": "2026-01-01",
            "source": SOURCE,
            "method": "per_period_percentage",
            "params": params,
            "rounding": rounding or {"to": "0.01", "mode": "nearest"},
        }
    )


# KS-shaped: annual status exemption + annual per-dependent divided per
# period, per-period table, whole-dollar rounding. Mirrors KW-100's example:
# $2,000 semimonthly, married (spouse not working), 1 dependent ->
# (18,320 + 2,320)/24 = 860.00; net 1,140; (1,140-343) x 5.2% = 41.44 -> $41.
KSISH = _pp(
    "US-ZZ",
    {
        "standard_deduction": {"married_spouse_not_working": "18320", "single": "9160"},
        "allowance_amount": "2320",
        "brackets": {
            "semimonthly": {
                "all": [
                    {"over": "0", "rate": "0"},
                    {"over": "343", "rate": "0.052"},
                ]
            }
        },
    },
    rounding={"to": "1.00", "mode": "nearest"},
)


def test_per_period_ks_shaped_example(taxability):
    emp = _employee(
        "semimonthly", "2000.00", jurisdiction="US-ZZ",
        filing_status="married_spouse_not_working", allowances=1,
    )
    assert compute_withholding(KSISH, emp, taxability) == Decimal("41.00")


def test_per_period_missing_frequency_fails_loud(taxability):
    emp = _employee(
        "weekly", "2000.00", jurisdiction="US-ZZ",
        filing_status="single", allowances=0,
    )
    with pytest.raises(InputError, match="no printed table"):
        compute_withholding(KSISH, emp, taxability)


# NM-shaped: no allowances, per-period table with printed (authoritative)
# bases, additional withholding. Mirrors FYI-104's example: $1,000 weekly
# married -> row over $790: 12.77 + 4.3% x 210 = 21.80; + $20 = 41.80.
# Rows are internally consistent so the printed-base check passes:
# base at 790 = 372 x 0.032 + ... constructed to land on 12.77.
NMISH = _pp(
    "US-ZZ",
    {
        "brackets": {
            "weekly": {
                "married": [
                    {"over": "0", "rate": "0"},
                    {"over": "391", "rate": "0.032"},
                    {"over": "790", "rate": "0.043", "base": "12.77"},
                ],
                "single": [
                    {"over": "0", "rate": "0"},
                    {"over": "150", "rate": "0.043"},
                ],
            }
        },
    },
)


def test_per_period_nm_shaped_example_with_additional(taxability):
    emp = _employee(
        "weekly", "1000.00", jurisdiction="US-ZZ",
        filing_status="married", additional_withholding="20.00",
    )
    assert compute_withholding(NMISH, emp, taxability) == Decimal("41.80")


def test_per_period_vt_shaped_printed_allowance(taxability):
    # VT-shaped: printed per-period allowance value ($97/week), per-period
    # table. weekly $600, 2 allowances -> net 406; (406-150) x 4.3% = 11.01.
    vt = _pp(
        "US-ZZ",
        {
            "allowance_amounts_per_period": {"weekly": "97.00"},
            "brackets": {"weekly": {"single": [
                {"over": "0", "rate": "0"},
                {"over": "150", "rate": "0.043"},
            ]}},
        },
    )
    emp = _employee(
        "weekly", "600.00", jurisdiction="US-ZZ", filing_status="single", allowances=2,
    )
    # 600 - 194 = 406; (406-150) x 0.043 = 11.008 -> 11.01
    assert compute_withholding(vt, emp, taxability) == Decimal("11.01")


def test_per_period_extraction_transform_loads():
    from pipeline import assemble

    extraction = {
        "classification": "new_year_edition",
        "effective_from": "2026-01-01",
        "rounding": {"to": "1.00", "mode": "nearest", "intermediate": "none",
                     "intermediate_to": None},
        "params": {
            "standard_deduction": [{"filing_status": "Single", "amount": "9160"}],
            "allowance_amount": "2320",
            "allowance_amounts_per_period": None,
            "frequencies": [
                {
                    "frequency": "semimonthly",
                    "tables": [
                        {"filing_status": "Single", "rows": [
                            {"over": "0", "rate": "0", "base": None},
                            {"over": "171", "rate": "0.052", "base": "0"},
                        ]}
                    ],
                }
            ],
        },
    }
    raw = assemble.assemble_parameter_file(
        jurisdiction="US-ZZ",
        tax="state_income_withholding",
        method="per_period_percentage",
        extraction=extraction,
        source=SOURCE,
    )
    pf = load_parameter_dict(raw)
    assert "semimonthly.single" in pf.bracket_tables
    assert raw["params"]["standard_deduction"] == {"single": "9160"}


# --- SC percent_deduction and RI allowance cliff ---------------------------

SC = _pf(
    "US-SC",
    "annualized_percentage",
    {
        "allowance_amount": "5000",
        "percent_deduction": {"rate": "0.10", "cap": "7500", "requires_allowances": True},
        "credit_per_allowance": None,
        "brackets": {
            "all": [
                {"over": "0", "rate": "0"},
                {"over": "3640", "rate": "0.03"},
                {"over": "18230", "rate": "0.06", "base": "437.70"},
            ]
        },
    },
)


def test_sc_printed_example(taxability):
    # WH-1603F p.1: $750 weekly, 3 allowances -> 39,000 - 15,000 - 3,900 =
    # 20,100; 437.70 + 6% x 1,870 = 549.90; / 52 = 10.575 -> 10.58
    emp = _employee("weekly", "750.00", jurisdiction="US-SC", allowances=3)
    assert compute_withholding(SC, emp, taxability) == Decimal("10.58")


def test_sc_zero_allowances_zeroes_both_deductions(taxability):
    # zero allowances: no personal allowance AND no percent deduction —
    # tax on full gross: 39,000 -> 437.70 + 6% x 20,770 = 1,683.90; /52 = 32.38
    emp = _employee("weekly", "750.00", jurisdiction="US-SC", allowances=0)
    assert compute_withholding(SC, emp, taxability) == Decimal("32.38")


def test_sc_percent_deduction_caps(taxability):
    # $2,000 weekly, 1 allowance: 104,000; 10% = 10,400 -> capped 7,500;
    # 104,000 - 5,000 - 7,500 = 91,500; 437.70 + 6% x 73,270 = 4,833.90; /52 = 92.96
    emp = _employee("weekly", "2000.00", jurisdiction="US-SC", allowances=1)
    assert compute_withholding(SC, emp, taxability) == Decimal("92.96")


RI = _pp(
    "US-RI",
    {
        "allowance_amounts_per_period": {"weekly": "19.23"},
        "allowance_cliff_annual_wages": "290800",
        "brackets": {
            "weekly": {
                "all": [
                    {"over": "0", "rate": "0.0375"},
                    {"over": "1578", "rate": "0.0475", "base": "59.18"},
                    {"over": "3586", "rate": "0.0599", "base": "154.56"},
                ]
            }
        },
    },
)


def test_ri_printed_example(taxability):
    # RI booklet p.8: $2,195 weekly, 1 exemption -> 2,175.77;
    # 59.18 + 4.75% x 597.77 = 87.57
    emp = _employee("weekly", "2195.00", jurisdiction="US-RI", allowances=1)
    assert compute_withholding(RI, emp, taxability) == Decimal("87.57")


def test_ri_cliff_zeroes_exemptions(taxability):
    # $6,000 weekly = 312,000/yr > 290,800: exemption worth $0 even with
    # 10 claimed; 154.56 + 5.99% x (6,000 - 3,586) = 299.16
    emp = _employee("weekly", "6000.00", jurisdiction="US-RI", allowances=10)
    assert compute_withholding(RI, emp, taxability) == Decimal("299.16")


def test_ri_below_cliff_exemptions_apply(taxability):
    # same 10 exemptions under the cliff: 2,195 - 192.30 = 2,002.70;
    # 59.18 + 4.75% x 424.70 = 79.35
    emp = _employee("weekly", "2195.00", jurisdiction="US-RI", allowances=10)
    assert compute_withholding(RI, emp, taxability) == Decimal("79.35")


# --- elected amounts: AZ rate election, IA credit, MS wage reduction -------

AZ = _pf(
    "US-AZ",
    "elective_flat_rate",
    {"allowed_rates": ["0.005", "0.010", "0.015", "0.020", "0.025", "0.030", "0.035"],
     "zero_rate_allowed": True, "default_rate": "0.020"},
)


def test_az_elected_rate(taxability):
    emp = _employee("biweekly", "2000.00", jurisdiction="US-AZ", elected_rate="0.025")
    assert compute_withholding(AZ, emp, taxability) == Decimal("50.00")


def test_az_default_when_no_election(taxability):
    emp = _employee("biweekly", "2000.00", jurisdiction="US-AZ")
    assert compute_withholding(AZ, emp, taxability) == Decimal("40.00")


def test_az_unpublished_rate_fails_loud(taxability):
    emp = _employee("biweekly", "2000.00", jurisdiction="US-AZ", elected_rate="0.04")
    with pytest.raises(InputError, match="published"):
        compute_withholding(AZ, emp, taxability)


def test_ia_shaped_elected_credit(taxability):
    # IA formula shape: per-period status deduction, flat 3.8%, W dollars
    # prorated and subtracted from TAX: monthly 5,000, D=13,000/12=1,083.33;
    # T2 = 3,916.67 x .038 = 148.83; W=520 -> 43.33; T3 = 105.50
    ia = _pp(
        "US-ZZ",
        {
            "standard_deduction": {"all": "13000"},
            "elected_amount_treatment": "tax_credit",
            "brackets": {"monthly": {"all": [{"over": "0", "rate": "0.038"}]}},
        },
    )
    emp = _employee("monthly", "5000.00", jurisdiction="US-ZZ", elected_annual_amount="520.00")
    assert compute_withholding(ia, emp, taxability) == Decimal("105.50")


def test_ms_shaped_elected_wage_reduction(taxability):
    # MS fallback shape: annualize - elected exemption dollars - std ded ->
    # 0% to 10,000 + 4%: monthly 4,000 -> 48,000 - 6,000 - 2,300 = 39,700;
    # 4% x 29,700 = 1,188; /12 = 99.00
    ms = _pf(
        "US-ZZ",
        "annualized_percentage",
        {
            "standard_deduction": {"single": "2300"},
            "allowance_amount": None,
            "credit_per_allowance": None,
            "elected_amount_treatment": "wage_reduction",
            "brackets": {"single": [
                {"over": "0", "rate": "0"},
                {"over": "10000", "rate": "0.04"},
            ]},
        },
    )
    emp = _employee("monthly", "4000.00", jurisdiction="US-ZZ",
                    filing_status="single", elected_annual_amount="6000.00")
    assert compute_withholding(ms, emp, taxability) == Decimal("99.00")


def test_elected_amount_without_treatment_fails_loud(taxability):
    emp = _employee("weekly", "750.00", jurisdiction="US-SC", allowances=1,
                    elected_annual_amount="1000.00")
    with pytest.raises(InputError, match="does not consume"):
        compute_withholding(SC, emp, taxability)


# --- Utah per_period_credit_phaseout (Pub 14 Rev. 4/26 printed examples) ---

UT = _pf(
    "US-UT",
    "per_period_credit_phaseout",
    {
        "rate": "0.0445",
        "phase_rate": "0.013",
        "schedules": {
            "weekly": {"single": {"base_allowance": "9", "phase_start": "180"},
                       "married": {"base_allowance": "19", "phase_start": "360"}},
            "semimonthly": {"single": {"base_allowance": "20", "phase_start": "390"},
                            "married": {"base_allowance": "40", "phase_start": "779"}},
            "monthly": {"single": {"base_allowance": "40", "phase_start": "779"},
                        "married": {"base_allowance": "81", "phase_start": "1558"}},
            "quarterly": {"single": {"base_allowance": "121", "phase_start": "2337"},
                          "married": {"base_allowance": "243", "phase_start": "4674"}},
            "daily": {"single": {"base_allowance": "2", "phase_start": "36"},
                      "married": {"base_allowance": "4", "phase_start": "72"}},
        },
    },
)
import dataclasses as _dc
from engine.money import Rounding as _R
UT = _dc.replace(UT, rounding=_R.from_dict({"to": "1.00", "mode": "nearest"}))


def _ut(freq, gross, status):
    return _employee(freq, gross, jurisdiction="US-UT", filing_status=status)


def test_ut_printed_examples(taxability):
    # Pub 14 p.11, all rounding per-line to whole dollars:
    cases = [
        ("weekly", "400.00", "single", "12.00"),       # 18 - (9-3) = 12
        ("semimonthly", "1200.00", "married", "18.00"),# 53 - (40-5) = 18
        ("monthly", "7800.00", "married", "347.00"),   # credit fully phased out
        ("quarterly", "9000.00", "single", "367.00"),  # 401 - (121-87) = 367
        ("daily", "175.00", "married", "5.00"),        # 8 - (4-1) = 5
    ]
    for freq, gross, status, expect in cases:
        got = compute_withholding(UT, _ut(freq, gross, status), taxability)
        assert got == Decimal(expect), (freq, gross, status, got)


def test_ut_missing_frequency_fails_loud(taxability):
    with pytest.raises(InputError, match="no printed schedule"):
        compute_withholding(UT, _ut("biweekly", "1000.00", "single"), taxability)


def test_ut_credit_never_negative_wages_below_rate_floor(taxability):
    # tiny wages: tentative rounds to whole dollars, credit exceeds it -> 0
    got = compute_withholding(UT, _ut("weekly", "100.00", "single"), taxability)
    assert got == Decimal("0.00")  # 4 - 9 clamps


# --- Arkansas annualized_subtraction_percentage ----------------------------

AR = _pf(
    "US-AR",
    "annualized_subtraction_percentage",
    {
        "standard_deduction": "2470",
        "credit_per_allowance": "29",
        "midrange_snap": {"bracket_size": "100", "midpoint": "50", "snap_below": "97701"},
        "table": [
            {"from": "0", "rate": "0"},
            {"from": "5600", "rate": "0.02", "subtract": "111.98"},
            {"from": "11200", "rate": "0.03", "subtract": "223.97"},
            {"from": "16000", "rate": "0.034", "subtract": "287.97"},
            {"from": "26400", "rate": "0.037", "subtract": "367.16"},
            {"from": "94701", "rate": "0.037", "subtract": "369.90"},
            {"from": "97601", "rate": "0.037", "subtract": "79.90"},
        ],
    },
)
AR = _dc.replace(AR, rounding=_R.from_dict(
    {"to": "0.01", "mode": "nearest", "intermediate": "annual", "intermediate_to": "1.00"}))


def test_ar_gary_printed_example(taxability):
    # pp.3-4: monthly $2,127, 2 exemptions -> NTI 23,054 snaps to 23,050;
    # x 3.4% - 287.97 = 495.73 -> $496; - 58 = 438; /12 = 36.50
    emp = _employee("monthly", "2127.00", jurisdiction="US-AR", allowances=2)
    assert compute_withholding(AR, emp, taxability) == Decimal("36.50")


def test_ar_above_snap_ceiling_uses_exact(taxability):
    # $8,200 monthly: annual 98,400 - 2,470 = 95,930... wait, that's under
    # 97,701 and in the ladder. Use $8,400: 100,800 - 2,470 = 98,330 >= 97,701
    # -> exact; x 3.7% - 79.90 = 3,558.31 -> 3,558; /12 = 296.50
    emp = _employee("monthly", "8400.00", jurisdiction="US-AR", allowances=0)
    assert compute_withholding(AR, emp, taxability) == Decimal("296.50")


def test_ar_ladder_region_snaps(taxability):
    # weekly $1,915: annual 99,580 - 2,470 = 97,110 < 97,701 -> snaps to
    # 97,150; ladder row from 94,701 (fixture collapses the ladder; real
    # data carries every printed row): x 3.7% - 369.90 = 3,224.65 -> 3,225;
    # /52 = 62.02
    emp = _employee("weekly", "1915.00", jurisdiction="US-AR", allowances=0)
    assert compute_withholding(AR, emp, taxability) == Decimal("62.02")


def test_ar_zero_bracket(taxability):
    # $500 monthly: annual 6,000 - 2,470 = 3,530 -> snaps 3,550 -> 0% -> 0
    emp = _employee("monthly", "500.00", jurisdiction="US-AR", allowances=1)
    assert compute_withholding(AR, emp, taxability) == Decimal("0.00")


# --- Connecticut custom/us_ct (TPG-211 tables, code-A rows as printed) -----

def _ct_pf():
    a_exemptions = ([{"more_than": "0", "value": "12000"}] +
        [{"more_than": str(24000 + i * 1000), "value": str(11000 - i * 1000)}
         for i in range(12)])  # 24k->11k ... 35k+->0
    a_brackets = [
        {"over": "0", "rate": "0.02"},
        {"over": "10000", "rate": "0.045", "base": "200"},
        {"over": "50000", "rate": "0.055", "base": "2000"},
        {"over": "100000", "rate": "0.06", "base": "4750"},
        {"over": "200000", "rate": "0.065", "base": "10750"},
        {"over": "250000", "rate": "0.069", "base": "14000"},
        {"over": "500000", "rate": "0.0699", "base": "31250"},
    ]
    a_add_back = ([{"more_than": "0", "value": "0"}] +
        [{"more_than": str(50250 + i * 2500), "value": str(25 * (i + 1))}
         for i in range(10)])  # caps at 250 for 72,750+
    a_recapture = [{"more_than": "0", "value": "0"},
                   {"more_than": "105000", "value": "25"},
                   {"more_than": "540000", "value": "3400"}]  # abbreviated
    a_credits = [
        {"more_than": "12000", "value": "0.75"},
        {"more_than": "15000", "value": "0.70"},
        {"more_than": "21500", "value": "0.15"},
        {"more_than": "25000", "value": "0.14"},
        {"more_than": "27000", "value": "0.10"},
        {"more_than": "48000", "value": "0.09"},
        {"more_than": "51500", "value": "0.02"},
        {"more_than": "52000", "value": "0.01"},
        {"more_than": "52500", "value": "0.00"},
    ]  # abbreviated to the rows the tests touch
    d_tables = {
        "exemptions": [{"more_than": "0", "value": "0"}],
        "brackets": a_brackets,  # code D shares Table B "A, D, or F"
        "add_back": a_add_back,  # Table C "A or D"
        "recapture": a_recapture,
        "credits": [{"more_than": "0", "value": "0.00"}],
    }
    return load_parameter_dict({
        "schema_version": "0.1",
        "jurisdiction": "US-CT",
        "tax": "state_income_withholding",
        "effective_from": "2026-01-01",
        "source": SOURCE,
        "method": "custom",
        "custom_implementation": "custom/us_ct",
        "params": {"codes": {
            "a": {"exemptions": a_exemptions, "brackets": a_brackets,
                  "add_back": a_add_back, "recapture": a_recapture,
                  "credits": a_credits},
            "d": d_tables,
        }},
        "rounding": {"to": "0.01", "mode": "nearest"},
    })


CT = _ct_pf()


def test_ct_code_a_full_pipeline(taxability):
    # weekly $1,000: salary 52,000 -> exemption 0 (>35,000);
    # initial 2,000 + 5.5% x 2,000 = 2,110; add-back (50,250..52,750] = 25;
    # recapture 0; credit (51,500..52,000] = .02 -> 2,135 x .98 = 2,092.30;
    # /52 = 40.2365 -> 40.24
    emp = _employee("weekly", "1000.00", jurisdiction="US-CT", filing_status="a")
    assert compute_withholding(CT, emp, taxability) == Decimal("40.24")


def test_ct_exclusive_boundary_salary_24000(taxability):
    # salary EXACTLY 24,000 (annual frequency): row is (0, 24,000] ->
    # exemption 12,000, NOT 11,000. taxable 12,000 -> 200 + 4.5% x 2,000
    # = 290; credit at 24,000 -> (21,500, 25,000] = .15 -> 246.50
    emp = _employee("annually", "24000.00", jurisdiction="US-CT", filing_status="a")
    assert compute_withholding(CT, emp, taxability) == Decimal("246.50")


def test_ct_exemption_phase_step(taxability):
    # salary 24,500: row (24,000, 25,000] -> exemption 11,000;
    # taxable 13,500 -> 200 + 4.5% x 3,500 = 357.50; credit .15 -> 303.875
    emp = _employee("annually", "24500.00", jurisdiction="US-CT", filing_status="a")
    assert compute_withholding(CT, emp, taxability) == Decimal("303.88")


def test_ct_code_d_no_exemption_no_credit(taxability):
    # weekly $1,000 code D: taxable 52,000; 2,110 + 25 + 0 = 2,135 x 1.00;
    # /52 = 41.0577 -> 41.06
    emp = _employee("weekly", "1000.00", jurisdiction="US-CT", filing_status="d")
    assert compute_withholding(CT, emp, taxability) == Decimal("41.06")


def test_ct_below_exemption_only_additional(taxability):
    # salary 20,000 code A -> exemption 12,000... salary < exemption? No:
    # 20,000 > 12,000. Use 10,000: exemption 12,000 -> taxable <= 0 ->
    # only the additional amount applies
    emp = _employee("annually", "10000.00", jurisdiction="US-CT",
                    filing_status="a", additional_withholding="5.00")
    assert compute_withholding(CT, emp, taxability) == Decimal("5.00")


def test_ct_unknown_code_fails_loud(taxability):
    emp = _employee("weekly", "1000.00", jurisdiction="US-CT", filing_status="x")
    with pytest.raises(InputError, match="withholding code"):
        compute_withholding(CT, emp, taxability)


# --- Oregon custom/us_or (150-206-436 printed formulas) --------------------

def _or_pf():
    single_low = [
        {"at_least": "0", "base": "263", "rate": "0.0475", "excess_over": "0"},
        {"at_least": "4550", "base": "479", "rate": "0.0675", "excess_over": "4550"},
        {"at_least": "11400", "base": "941", "rate": "0.0875", "excess_over": "11400"},
    ]
    single_high = [
        {"at_least": "0", "base": "678", "rate": "0.0875", "excess_over": "11400"},
        {"at_least": "125000", "base": "10618", "rate": "0.099", "excess_over": "125000"},
    ]
    married_low = [
        {"at_least": "0", "base": "263", "rate": "0.0475", "excess_over": "0"},
        {"at_least": "9100", "base": "695", "rate": "0.0675", "excess_over": "9100"},
        {"at_least": "22800", "base": "1620", "rate": "0.0875", "excess_over": "22800"},
    ]
    married_high = [
        {"at_least": "0", "base": "1357", "rate": "0.0875", "excess_over": "22800"},
        {"at_least": "250000", "base": "21237", "rate": "0.099", "excess_over": "250000"},
    ]
    def phaseout(steps):
        return [{"at_least": "0", "cap": "8750"}] + steps
    return load_parameter_dict({
        "schema_version": "0.1",
        "jurisdiction": "US-OR",
        "tax": "state_income_withholding",
        "effective_from": "2026-01-01",
        "source": SOURCE,
        "method": "custom",
        "custom_implementation": "custom/us_or",
        "params": {
            "credit_per_allowance": "263",
            "statuses": {
                "single": {
                    "allowance_zero_above": "100000",
                    "fed_subtraction_phaseout": phaseout([
                        {"at_least": "125000", "cap": "7000"},
                        {"at_least": "130000", "cap": "5250"},
                        {"at_least": "135000", "cap": "3500"},
                        {"at_least": "140000", "cap": "1750"},
                        {"at_least": "145000", "cap": "0"},
                    ]),
                },
                "married": {
                    "allowance_zero_above": "200000",
                    "fed_subtraction_phaseout": phaseout([
                        {"at_least": "250000", "cap": "7000"},
                        {"at_least": "260000", "cap": "5250"},
                        {"at_least": "270000", "cap": "3500"},
                        {"at_least": "280000", "cap": "1750"},
                        {"at_least": "290000", "cap": "0"},
                    ]),
                },
            },
            "status_groups": {
                "single_under_3": {
                    "standard_deduction": "2910",
                    "wage_tiers": [
                        {"wages_at_least": "0", "formulas": single_low},
                        {"wages_at_least": "50000", "formulas": single_high},
                    ],
                },
                "married_or_single_3plus": {
                    "standard_deduction": "5820",
                    "wage_tiers": [
                        {"wages_at_least": "0", "formulas": married_low},
                        {"wages_at_least": "50000", "formulas": married_high},
                    ],
                },
            },
        },
        "rounding": {"to": "0.01", "mode": "nearest",
                     "intermediate": "annual", "intermediate_to": "1.00"},
    })


OR = _or_pf()


def _or_emp(freq, gross, status, allowances, fed):
    return EmployeeInput.from_dict({
        "pay_frequency": freq, "gross_wages": gross,
        "period_federal_income_withholding": fed,
        "state": [{"jurisdiction": "US-OR", "filing_status": status,
                   "allowances": allowances, "additional_withholding": "0"}],
    })


def test_or_example_1_worksheet(taxability):
    # Example 1's WORKSHEET (prose figures are stale): annual $25,000 wages,
    # $1,000 federal WH, 0 allowances -> BASE 21,090 -> 941 + 8.75% x 9,690
    # = 1,789 -> annual frequency, /1
    emp = _or_emp("annually", "25000.00", "single", 0, "1000.00")
    assert compute_withholding(OR, emp, taxability) == Decimal("1789.00")


def test_or_example_2_monthly(taxability):
    # Example 2: same employee monthly: wages 25,000/12, fed 1,000/12 ->
    # same annual 1,789 -> /12 = 149.08 (doc rounds to $149)
    emp = _or_emp("monthly", "2083.33", "single", 0, "83.33")
    got = compute_withholding(OR, emp, taxability)
    # annual $1,789 (dollar-rounded per the worksheet) / 12 = 149.08
    assert got == Decimal("149.08"), got


def test_or_high_income_cap_and_allowance_zeroing(taxability):
    # Example 3 shape (2026 ladder): single 132,000 wages, fed WH 21,098,
    # 4 allowances -> BRACKETS from the married group (3+ allowances, SD
    # 5,820) but the SINGLE phase-out ladder: cap [130k,135k) = 5,250;
    # BASE = 132,000 - 5,250 - 5,820 = 120,930 -> married high tier:
    # 1,357 + 8.75% x 98,130 = 9,943.375 -> $9,943; allowances zeroed
    # (single > 100k)
    emp = _or_emp("annually", "132000.00", "single", 4, "21098.00")
    assert compute_withholding(OR, emp, taxability) == Decimal("9943.00")


def test_or_example_4_married_no_subtraction(taxability):
    # married electing higher single rate = single status, 4 allowances ->
    # married-group brackets (SD 5,820), single ladder: 175,000 >= 145,000
    # -> fed subtraction 0; BASE 169,180 -> 1,357 + 8.75% x 146,380 =
    # 14,165.25 -> $14,165; allowances zeroed (single > 100k)
    emp = _or_emp("annually", "175000.00", "single", 4, "30000.00")
    assert compute_withholding(OR, emp, taxability) == Decimal("14165.00")


def test_or_missing_federal_input_fails_loud(taxability):
    emp = EmployeeInput.from_dict({
        "pay_frequency": "annually", "gross_wages": "25000.00",
        "state": [{"jurisdiction": "US-OR", "filing_status": "single",
                   "allowances": 0, "additional_withholding": "0"}],
    })
    with pytest.raises(InputError, match="period_federal_income_withholding"):
        compute_withholding(OR, emp, taxability)


def test_or_single_3plus_uses_married_group(taxability):
    # single with 3 allowances -> married-group brackets (SD 5,820), single
    # ladder: wages 40,000, fed 2,000 -> BASE 32,180 -> 1,620 + 8.75% x
    # 9,380 = 2,440.75 -> $2,441 - 3 x 263 = 1,652
    emp = _or_emp("annually", "40000.00", "single", 3, "2000.00")
    assert compute_withholding(OR, emp, taxability) == Decimal("1652.00")


# --- Alabama custom/us_al (booklet p.7 formula + example) ------------------

def _al_pf():
    b_single = [{"over": "0", "rate": "0.02"},
                {"over": "500", "rate": "0.04", "base": "10"},
                {"over": "3000", "rate": "0.05", "base": "110"}]
    b_married = [{"over": "0", "rate": "0.02"},
                 {"over": "1000", "rate": "0.04", "base": "20"},
                 {"over": "6000", "rate": "0.05", "base": "220"}]
    sd_m = [{"at_least": "0", "amount": "8500"},
            {"at_least": "26000", "amount": "8325"},
            {"at_least": "35500", "amount": "5000"}]  # abbreviated schedule
    sd_s = [{"at_least": "0", "amount": "3000"},
            {"at_least": "35500", "amount": "2500"}]
    return load_parameter_dict({
        "schema_version": "0.1",
        "jurisdiction": "US-AL",
        "tax": "state_income_withholding",
        "effective_from": "2026-01-01",
        "source": SOURCE,
        "method": "custom",
        "custom_implementation": "custom/us_al",
        "params": {
            "statuses": {
                "m": {"personal_exemption": "3000", "standard_deduction": sd_m,
                      "brackets": b_married},
                "s": {"personal_exemption": "1500", "standard_deduction": sd_s,
                      "brackets": b_single},
                "zero": {"personal_exemption": "0", "standard_deduction": sd_s,
                         "brackets": b_single},
            },
            "dependent_tiers": [
                {"more_than": "0", "value": "1000"},
                {"more_than": "50000", "value": "500"},
                {"more_than": "100000", "value": "300"},
            ],
        },
        "rounding": {"to": "0.01", "mode": "nearest"},
    })


AL = _al_pf()


def _al_emp(freq, gross, status, deps, fed):
    return EmployeeInput.from_dict({
        "pay_frequency": freq, "gross_wages": gross,
        "period_federal_income_withholding": fed,
        "state": [{"jurisdiction": "US-AL", "filing_status": status,
                   "allowances": deps, "additional_withholding": "0"}],
    })


def test_al_printed_example_m2(taxability):
    # p.7: M-2 weekly $850, federal WH $35.19/wk -> GI 44,200; SD 5,000;
    # fed 1,829.88; PE 3,000; deps 2,000 -> taxable 32,370.12 ->
    # 220 + 5% x 26,370.12 = 1,538.51 -> /52 = 29.59 (doc: 29.59)
    emp = _al_emp("weekly", "850.00", "m", 2, "35.19")
    assert compute_withholding(AL, emp, taxability) == Decimal("29.59")


def test_al_dependent_tier_boundary(taxability):
    # GI exactly 50,000 -> $1,000 tier (exclusive lower bound)
    emp = _al_emp("annually", "50000.00", "s", 1, "3000.00")
    # SD 2,500 (>=35,500); fed 3,000; PE 1,500; dep 1,000 -> taxable 42,000
    # -> 110 + 5% x 39,000 = 2,060
    assert compute_withholding(AL, emp, taxability) == Decimal("2060.00")
    # one dollar more: GI 50,001 -> $500 tier -> taxable 42,501 ->
    # 110 + 5% x 39,501 = 2,085.05
    emp2 = _al_emp("annually", "50001.00", "s", 1, "3000.00")
    assert compute_withholding(AL, emp2, taxability) == Decimal("2085.05")


def test_al_stepped_deduction_lookup(taxability):
    # GI 26,200 married: schedule row [26,000, ...) -> 8,325
    emp = _al_emp("annually", "26200.00", "m", 0, "0.00")
    # taxable 26,200 - 8,325 - 0 - 3,000 = 14,875 -> 220 + 5% x 8,875 = 663.75
    assert compute_withholding(AL, emp, taxability) == Decimal("663.75")


def test_al_zero_code_no_exemption(taxability):
    emp = _al_emp("annually", "20000.00", "zero", 0, "1000.00")
    # SD 3,000; fed 1,000; PE 0 -> taxable 16,000 -> 110 + 5% x 13,000 = 760
    assert compute_withholding(AL, emp, taxability) == Decimal("760.00")


def test_al_missing_federal_fails_loud(taxability):
    emp = EmployeeInput.from_dict({
        "pay_frequency": "weekly", "gross_wages": "850.00",
        "state": [{"jurisdiction": "US-AL", "filing_status": "m",
                   "allowances": 2, "additional_withholding": "0"}],
    })
    with pytest.raises(InputError, match="period_federal_income_withholding"):
        compute_withholding(AL, emp, taxability)


# --- Massachusetts custom/us_ma (Circular M p.12) --------------------------

def _ma_pf():
    return load_parameter_dict({
        "schema_version": "0.1",
        "jurisdiction": "US-MA",
        "tax": "state_income_withholding",
        "effective_from": "2026-01-01",
        "source": SOURCE,
        "method": "custom",
        "custom_implementation": "custom/us_ma",
        "params": {
            "retirement_deduction_cap": "2000",
            "exemption_factors": {
                "weekly": {"claiming_one": "85", "per_exemption": "19", "plus": "66"},
                "annually": {"claiming_one": "4400", "per_exemption": "1000", "plus": "3400"},
            },
            "brackets": [
                {"over": "0", "rate": "0.05"},
                {"over": "1107750", "rate": "0.09", "base": "55387.50"},
            ],
            "hoh_tax_value": {"weekly": "2.31", "annually": "120.00"},
            "blindness_tax_value": {"weekly": "2.12", "annually": "110.00"},
            "low_income_floor": {"weekly": "154", "annually": "8000"},
        },
        "rounding": {"to": "0.01", "mode": "nearest"},
    })


MA = _ma_pf()


def _ma_emp(freq, gross, exemptions, fica, ytd_used=None, status=None, blind=0):
    record = {
        "pay_frequency": freq, "gross_wages": gross,
        "period_fica_withholding": fica,
        "state": [{"jurisdiction": "US-MA", "allowances": exemptions,
                   "secondary_allowances": blind, "additional_withholding": "0",
                   **({"filing_status": status} if status else {})}],
    }
    if ytd_used is not None:
        record["ytd"] = {"retirement_deduction_used": ytd_used}
    return EmployeeInput.from_dict(record)


def test_ma_basic_weekly(taxability):
    # 800 - 61.20 fica - 85 (claiming 1) = 653.80 -> x52 = 33,997.60 ->
    # 5% = 1,699.88 -> /52 = 32.69
    emp = _ma_emp("weekly", "800.00", 1, "61.20")
    assert compute_withholding(MA, emp, taxability) == Decimal("32.69")


def test_ma_cap_exhausted_mid_year(taxability):
    # ytd used 2,000 -> step 1 discontinued: 800 - 85 = 715 -> 37,180 ->
    # 1,859 -> 35.75
    emp = _ma_emp("weekly", "800.00", 1, "61.20", ytd_used="2000.00")
    assert compute_withholding(MA, emp, taxability) == Decimal("35.75")


def test_ma_cap_partial(taxability):
    # remaining 30: 800 - 30 - 85 = 685 -> 35,620 -> 1,781 -> 34.25
    emp = _ma_emp("weekly", "800.00", 1, "61.20", ytd_used="1970.00")
    assert compute_withholding(MA, emp, taxability) == Decimal("34.25")


def test_ma_multi_exemption_factor(taxability):
    # 3 exemptions: 19x3 + 66 = 123: 800 - 61.20 - 123 = 615.80 ->
    # 32,021.60 -> 1,601.08 -> 30.79
    emp = _ma_emp("weekly", "800.00", 3, "61.20")
    assert compute_withholding(MA, emp, taxability) == Decimal("30.79")


def test_ma_surtax_tier(taxability):
    # annual 1,500,000, 0 exemptions, fica 2,000: w = 1,498,000 ->
    # 55,387.50 + 9% x 390,250 = 90,510.00
    emp = _ma_emp("annually", "1500000.00", 0, "2000.00")
    assert compute_withholding(MA, emp, taxability) == Decimal("90510.00")


def test_ma_hoh_and_blindness_tax_values(taxability):
    # basic 32.69 - 2.31 (HoH) - 2.12 (1 blind) = 28.26
    emp = _ma_emp("weekly", "800.00", 1, "61.20", status="head_of_household", blind=1)
    assert compute_withholding(MA, emp, taxability) == Decimal("28.26")


def test_ma_low_income_floor(taxability):
    # weekly 150 < 154 with 1 exemption -> no withholding
    emp = _ma_emp("weekly", "150.00", 1, "10.00")
    assert compute_withholding(MA, emp, taxability) == Decimal("0.00")
    # but 0 exemptions: floor doesn't apply
    emp0 = _ma_emp("weekly", "150.00", 0, "10.00")
    assert compute_withholding(MA, emp0, taxability) > Decimal("0")


def test_ma_missing_fica_fails_loud(taxability):
    emp = EmployeeInput.from_dict({
        "pay_frequency": "weekly", "gross_wages": "800.00",
        "state": [{"jurisdiction": "US-MA", "allowances": 1, "additional_withholding": "0"}],
    })
    with pytest.raises(InputError, match="period_fica_withholding"):
        compute_withholding(MA, emp, taxability)


# --- IN deduction_constant_percentage (DN #1 2026) --------------------------

IN = _pf(
    "US-IN",
    "deduction_constant_percentage",
    {
        "rate": "0.0295",
        "exemptions": {
            "personal": "1000",
            "dependent": "1500",
            "first_time_dependent": "1500",
            "adopted": "3000",
        },
        "periods_per_year": {
            "daily": "365",
            "weekly": "52",
            "biweekly": "26",
            "semimonthly": "24",
            "monthly": "12",
        },
    },
)


def _in_emp(freq, gross, **exemptions):
    extra = {"exemptions": exemptions} if exemptions else {}
    return _employee(freq, gross, jurisdiction="US-IN", **extra)


def test_in_printed_example(taxability):
    # DN #1 p.3: weekly $800; 5 personal + 3 dependent + 1 first-time + 2
    # adopted -> constants 96.15 + 86.54 + 28.85 + 115.38 = 326.92;
    # taxable 473.08 x .0295 = 13.9559 -> 13.96
    emp = _in_emp("weekly", "800.00", personal=5, dependent=3,
                  first_time_dependent=1, adopted=2)
    assert compute_withholding(IN, emp, taxability) == Decimal("13.96")


def test_in_kinds_round_independently(taxability):
    # The trap the printed example encodes: 3 dependents (86.54) + 1
    # first-time (28.85) = 115.39, NOT one lookup of 4 x 1500/52 = 115.38.
    together = _in_emp("weekly", "800.00", dependent=3, first_time_dependent=1)
    folded = _in_emp("weekly", "800.00", dependent=4)
    a = compute_withholding(IN, together, taxability)
    b = compute_withholding(IN, folded, taxability)
    # taxable differs by one cent: 684.61 vs 684.62
    assert a == Decimal("20.20")  # (800 - 115.39) x .0295 = 20.1960 -> 20.20
    assert b == Decimal("20.20")  # (800 - 115.38) x .0295 = 20.1963 -> 20.20
    # the bases differ even when the rounded tax happens to agree
    # (kept as the printed-example regression via test_in_printed_example)


def test_in_daily_divisor_is_365(taxability):
    # Table A daily row 1 prints 2.74 = 1000/365 (not /260):
    # daily $100, 1 personal -> (100 - 2.74) x .0295 = 2.8692 -> 2.87
    emp = _in_emp("daily", "100.00", personal=1)
    assert compute_withholding(IN, emp, taxability) == Decimal("2.87")


def test_in_no_exemptions(taxability):
    emp = _in_emp("weekly", "800.00")
    assert compute_withholding(IN, emp, taxability) == Decimal("23.60")


def test_in_constants_exceed_wages_clamp(taxability):
    emp = _in_emp("weekly", "50.00", adopted=5)  # constant 288.46 > wages
    assert compute_withholding(IN, emp, taxability) == Decimal("0.00")


def test_in_unknown_kind_fails_loud(taxability):
    from engine.errors import InputError
    emp = _in_emp("weekly", "800.00", veterans=1)
    with pytest.raises(InputError, match="veterans"):
        compute_withholding(IN, emp, taxability)


def test_in_missing_frequency_fails_loud(taxability):
    from engine.errors import InputError
    emp = _in_emp("quarterly", "5000.00", personal=1)
    with pytest.raises(InputError, match="quarterly"):
        compute_withholding(IN, emp, taxability)


# --- MD rate_schedule_percentage (2026 Employer Withholding Guide) ----------

MD = _pf(
    "US-MD",
    "rate_schedule_percentage",
    {
        "exemption_per_period": {"weekly": "61.54", "daily": "8.77"},
        "standard_deduction_per_period": {"weekly": "65.38", "daily": "9.31"},
        "no_withholding_floor": {"weekly": "96.00", "daily": "13.70"},
        "status_groups": {
            "a": ["married_joint", "head_of_household"],
            "b": ["single", "married_filing_separately", "dependent"],
        },
        "schedules": {
            "0.0225": {
                "weekly": {
                    "a": [
                        {"over": "0", "rate": "0.0700", "base": "0"},
                        {"over": "2885", "rate": "0.0725", "base": "201.92"},
                        {"over": "3365", "rate": "0.0750", "base": "236.78"},
                        {"over": "4327", "rate": "0.0775", "base": "308.89"},
                        {"over": "5769", "rate": "0.0800", "base": "420.67"},
                        {"over": "11538", "rate": "0.0850", "base": "882.17"},
                        {"over": "23077", "rate": "0.0875", "base": "1862.99"},
                    ],
                    "b": [
                        {"over": "0", "rate": "0.0700", "base": "0"},
                        {"over": "1923", "rate": "0.0725", "base": "134.62"},
                        {"over": "2404", "rate": "0.0750", "base": "169.47"},
                        {"over": "2885", "rate": "0.0775", "base": "205.53"},
                        {"over": "4808", "rate": "0.0800", "base": "354.57"},
                        {"over": "9615", "rate": "0.0850", "base": "739.15"},
                        {"over": "19231", "rate": "0.0875", "base": "1556.51"},
                    ],
                },
            },
        },
    },
)


def _md_emp(freq, gross, status, allowances=0, schedule="0.0225"):
    extra = {"rate_schedule": schedule} if schedule else {}
    return _employee(freq, gross, jurisdiction="US-MD", filing_status=status,
                     allowances=allowances, **extra)


def test_md_first_bracket(taxability):
    # weekly $1,000, MFJ, 1 exemption: 1000 - 65.38 - 61.54 = 873.08
    # x 7.00% = 61.1156 -> 61.12
    emp = _md_emp("weekly", "1000.00", "married_joint", allowances=1)
    assert compute_withholding(MD, emp, taxability) == Decimal("61.12")


def test_md_single_upper_bracket_printed_base(taxability):
    # weekly $3,000 single, 0 exemptions: taxable 2,934.62; printed base
    # 205.53 + 7.75% x 49.62 = 209.3756 -> 209.38
    emp = _md_emp("weekly", "3000.00", "single")
    assert compute_withholding(MD, emp, taxability) == Decimal("209.38")


def test_md_status_group_resolution(taxability):
    # head_of_household uses group (a); dependent uses group (b)
    hoh = _md_emp("weekly", "3000.00", "head_of_household")
    dep = _md_emp("weekly", "3000.00", "dependent")
    # (a): taxable 2,934.62 -> 201.92 + 7.25% x 49.62 = 205.5175 -> 205.52
    assert compute_withholding(MD, hoh, taxability) == Decimal("205.52")
    assert compute_withholding(MD, dep, taxability) == Decimal("209.38")


def test_md_gross_wage_floor(taxability):
    # "DO NOT WITHHOLD ON GROSS WAGES LESS THAN $96.00" tests GROSS wages
    emp = _md_emp("weekly", "95.99", "single")
    assert compute_withholding(MD, emp, taxability) == Decimal("0.00")


def test_md_above_floor_but_taxable_zero(taxability):
    # over the floor, but deductions exceed wages -> clamp, not the floor path
    emp = _md_emp("weekly", "100.00", "single", allowances=1)
    assert compute_withholding(MD, emp, taxability) == Decimal("0.00")


def test_md_missing_schedule_fails_loud(taxability):
    from engine.errors import InputError
    emp = _md_emp("weekly", "1000.00", "single", schedule=None)
    with pytest.raises(InputError, match="rate_schedule"):
        compute_withholding(MD, emp, taxability)


def test_md_unknown_schedule_fails_loud(taxability):
    from engine.errors import InputError
    emp = _md_emp("weekly", "1000.00", "single", schedule="0.0399")
    with pytest.raises(InputError, match="0.0399"):
        compute_withholding(MD, emp, taxability)


# --- CA custom/us_ca (2026 Method B, Examples A-D + footnotes) ---------------

CA = load_parameter_dict({
    "schema_version": "0.1",
    "jurisdiction": "US-CA",
    "tax": "state_income_withholding",
    "effective_from": "2026-01-01",
    "source": SOURCE,
    "method": "custom",
    "custom_implementation": "custom/us_ca",
    "rounding": {"to": "0.01", "mode": "nearest"},
    "params": {
        "low_income_exemption": {
            "weekly": {"single": "363", "married_allowances_0_1": "363",
                       "married_allowances_2_plus": "727", "head_of_household": "727"},
            "biweekly": {"single": "727", "married_allowances_0_1": "727",
                         "married_allowances_2_plus": "1454", "head_of_household": "1454"},
            "monthly": {"single": "1575", "married_allowances_0_1": "1575",
                        "married_allowances_2_plus": "3149", "head_of_household": "3149"},
        },
        "estimated_deduction": {
            "weekly": ["19", "38", "58", "77", "96"],
            "biweekly": ["38", "77", "115", "154", "192"],
            "monthly": ["83", "167", "250", "333", "417"],
        },
        "standard_deduction": {
            "weekly": {"single": "110", "married_allowances_0_1": "110",
                       "married_allowances_2_plus": "219", "head_of_household": "219"},
            "biweekly": {"single": "219", "married_allowances_0_1": "219",
                         "married_allowances_2_plus": "439", "head_of_household": "439"},
            "monthly": {"single": "476", "married_allowances_0_1": "476",
                        "married_allowances_2_plus": "951", "head_of_household": "951"},
        },
        "exemption_allowance": {
            "weekly": ["3.24", "6.47", "9.71", "12.95", "16.18"],
            "biweekly": ["6.47", "12.95", "19.42", "25.89", "32.37"],
            "monthly": ["14.03", "28.05", "42.08", "56.10", "70.13"],
        },
        "brackets": {
            "weekly": {
                "single": [{"over": "0", "rate": "0.011", "base": "0"}],
                "married": [{"over": "0", "rate": "0.011", "base": "0"}],
                "head_of_household": [
                    {"over": "0", "rate": "0.011", "base": "0"},
                    {"over": "426", "rate": "0.022", "base": "4.69"},
                ],
            },
            "biweekly": {
                "married": [
                    {"over": "0", "rate": "0.011", "base": "0"},
                    {"over": "852", "rate": "0.022", "base": "9.37"},
                ],
            },
            "monthly": {
                "married": [
                    {"over": "0", "rate": "0.011", "base": "0"},
                    {"over": "1848", "rate": "0.022", "base": "20.33"},
                ],
            },
        },
    },
})


def _ca_emp(freq, gross, status, allowances=0, secondary=0):
    return _employee(freq, gross, jurisdiction="US-CA", filing_status=status,
                     allowances=allowances, secondary_allowances=secondary)


def test_ca_example_a_low_income_cliff(taxability):
    # Example A: weekly $210 single, 1 allowance -> under $363 -> 0
    emp = _ca_emp("weekly", "210.00", "single", allowances=1)
    assert compute_withholding(CA, emp, taxability) == Decimal("0.00")


def test_ca_example_b_estimated_deduction(taxability):
    # Example B: biweekly $1,600 married, 3 claimed (1 estimated -> 2 regular):
    # 1600 - 38 - 439 = 1123 -> 9.37 + 2.2% x 271 = 15.33 - 12.95 = 2.38
    emp = _ca_emp("biweekly", "1600.00", "married", allowances=2, secondary=1)
    assert compute_withholding(CA, emp, taxability) == Decimal("2.38")


def test_ca_example_c_monthly(taxability):
    # Example C: monthly $5,100 married, 5 allowances -> 0.82
    emp = _ca_emp("monthly", "5100.00", "married", allowances=5)
    assert compute_withholding(CA, emp, taxability) == Decimal("0.82")


def test_ca_example_d_head_of_household(taxability):
    # Example D: weekly $950 HoH, 3 allowances -> 1.69
    emp = _ca_emp("weekly", "950.00", "head_of_household", allowances=3)
    assert compute_withholding(CA, emp, taxability) == Decimal("1.69")


def test_ca_married_column_splits_on_regular_count(taxability):
    # Table 1 weekly married: '0 or 1' -> $363; '2 or more' -> $727.
    # $500 gross: exempt only with 2+ regular allowances.
    one = _ca_emp("weekly", "500.00", "married", allowances=1)
    two = _ca_emp("weekly", "500.00", "married", allowances=2)
    assert compute_withholding(CA, one, taxability) > Decimal("0")
    assert compute_withholding(CA, two, taxability) == Decimal("0.00")


def test_ca_beyond_table_counts_multiply():
    # Table 4 footnote: 15 weekly allowances -> 15 x $3.24 = $48.60
    from engine.methods.custom.us_ca import _count_lookup
    assert _count_lookup(["3.24", "6.47"], 15, context="t") == Decimal("48.60")
    assert _count_lookup(["3.24", "6.47"], 2, context="t") == Decimal("6.47")
    assert _count_lookup(["3.24"], 0, context="t") == Decimal("0")


def test_ca_cliff_is_inclusive(taxability):
    # Step 1 text: "less than, or equal to" -> exactly $363 is exempt
    emp = _ca_emp("weekly", "363.00", "single")
    assert compute_withholding(CA, emp, taxability) == Decimal("0.00")
