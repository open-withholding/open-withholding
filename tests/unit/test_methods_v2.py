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
