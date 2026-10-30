# Parity worksheet

Type each scenario into the external calculator and record its answer in `tests/parity/expected.csv` (`id,expected,source,entered_on,note`). Core rows first; extended rows only if a core row disagrees. Record ONLY the tax named in the heading (e.g. the state income tax line, not the whole paycheck). `ours` is the engine's answer.

## Core scenarios

### US — federal income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-federal-p01 | biweekly gross $2000.00 | W-4: w4_version=2020, filing_status=married_joint | 76.15 |  |
| us-federal-p07 | biweekly gross $2000.00 | W-4: w4_version=2020, filing_status=single, step2_checkbox=True, step3_credits=2000, step4c_extra=25.00 | 218.27 |  |

### US — fica

| id | scenario | ours | expected |
|---|---|---|---|
| us-federal-fica-p01 | biweekly gross $2000.00 | 153.00 |  |

### US — futa

| id | scenario | ours | expected |
|---|---|---|---|
| us-federal-futa-p01 | biweekly gross $2000.00 | 12.00 |  |
| us-federal-futa-p02 | biweekly gross $2000.00 | YTD futa_wages $6000 | 6.00 |  |

### US-AK — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ak-sui-p01 | biweekly gross $2000.00 | employer rate 0.0100 | 20.00 |  |
| us-ak-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $53200.00 | employer rate 0.0100 | 10.00 |  |

### US-AK — state unemployment insurance employee

| id | scenario | ours | expected |
|---|---|---|---|
| us-ak-sui-employee-p01 | biweekly gross $2000.00 | 10.00 |  |
| us-ak-sui-employee-p02 | biweekly gross $2000.00 | YTD sui_wages $53200.00 | 5.00 |  |

### US-AL — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-al-p01 | biweekly gross $2000.00 | filing_status=m; allowances=2 | 77.86 |  |
| us-al-p07 | biweekly gross $2000.00 | filing_status=s; allowances=1 | 0.00 |  |

### US-AR — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ar-p01 | biweekly gross $2000.00 | filing_status=default; allowances=2 | 54.15 |  |
| us-ar-p07 | biweekly gross $2000.00 | 56.38 |  |

### US-AZ — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-az-p01 | biweekly gross $2000.00 | elected_rate=0.025 | 50.00 |  |
| us-az-p07 | biweekly gross $2000.00 | 40.00 |  |

### US-CA — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ca-sdi-p01 | biweekly gross $2000.00 | 26.00 |  |

### US-CA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ca-p01 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 49.11 |  |
| us-ca-p07 | biweekly gross $2000.00 | filing_status=married; allowances=2; secondary_allowances=1 | 11.18 |  |

### US-CA — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ca-sui-p01 | biweekly gross $2000.00 | employer rate 0.034 | 70.00 |  |
| us-ca-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $6000 | employer rate 0.034 | 35.00 |  |
| us-ca-sui-p03 | biweekly gross $2000.00 | employer rate 0.062 | 126.00 |  |

### US-CO — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-co-sdi-p01 | biweekly gross $2000.00 | 8.80 |  |
| us-co-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $183500 | 4.40 |  |

### US-CO — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-co-sui-p01 | biweekly gross $2000.00 | employer rate 0.0305 | 61.00 |  |
| us-co-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $29600 | employer rate 0.0305 | 30.50 |  |
| us-co-sui-p03 | biweekly gross $2000.00 | employer rate 0.0058 | 11.60 |  |

### US-CT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ct-p01 | biweekly gross $2000.00 | filing_status=a | 80.47 |  |
| us-ct-p07 | biweekly gross $2000.00 | filing_status=b | 59.37 |  |

### US-DE — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-de-sdi-p01 | biweekly gross $2000.00 | 8.00 |  |
| us-de-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $183500 | 4.00 |  |

### US-FL — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-fl-sui-p01 | biweekly gross $2000.00 | employer rate 0.0270 | 54.00 |  |
| us-fl-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $6000 | employer rate 0.0270 | 27.00 |  |
| us-fl-sui-p03 | biweekly gross $2000.00 | employer rate 0.0540 | 108.00 |  |

### US-GA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ga-p01 | biweekly gross $2000.00 | filing_status=married_joint; allowances=1 | 32.63 |  |
| us-ga-p07 | biweekly gross $2000.00 | filing_status=head_of_household; allowances=2 | 51.82 |  |

### US-HI — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-hi-sdi-p01 | biweekly gross $2000.00 | 10.00 |  |

### US-HI — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-hi-p01 | biweekly gross $2000.00 | filing_status=single; allowances=3; secondary_allowances=1 | 87.18 |  |
| us-hi-p07 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 106.00 |  |

### US-IA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ia-p01 | biweekly gross $2000.00 | filing_status=other_married_spouse_earns; elected_annual_amount=40 | 55.46 |  |
| us-ia-p07 | biweekly gross $2000.00 | filing_status=married_pre2024; allowances=2 | 34.92 |  |

### US-ID — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-id-p01 | biweekly gross $2000.00 | filing_status=single; allowances=4 | 44.00 |  |
| us-id-p07 | biweekly gross $2000.00 | filing_status=married; allowances=4 | 13.00 |  |

### US-IL — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-il-p01 | biweekly gross $2000.00 | filing_status=all; allowances=2; secondary_allowances=2 | 84.05 |  |
| us-il-p07 | biweekly gross $2000.00 | 99.00 |  |

### US-IL — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-il-sui-p01 | biweekly gross $2000.00 | employer rate 0.03350 | 67.00 |  |
| us-il-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $13250 | employer rate 0.03350 | 33.50 |  |
| us-il-sui-p03 | biweekly gross $2000.00 | employer rate 0.00750 | 15.00 |  |

### US-IN — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-in-p01 | biweekly gross $2000.00 | filing_status=all; exemptions={'personal': 5, 'dependent': 3, 'first_time_dependent': 1, 'adopted': 2} | 39.71 |  |

### US-KY — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ky-p01 | biweekly gross $2000.00 | 65.48 |  |

### US-LA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-la-p01 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 46.50 |  |
| us-la-p07 | biweekly gross $2000.00 | filing_status=married_joint; allowances=2 | 31.20 |  |

### US-MA — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ma-sdi-p01 | biweekly gross $2000.00 | 9.20 |  |
| us-ma-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $183500 | 4.60 |  |

### US-MA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ma-p01 | biweekly gross $2000.00 | allowances=1 | 88.49 |  |
| us-ma-p07 | biweekly gross $2000.00 | 0.00 |  |

### US-MA — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ma-sui-p01 | biweekly gross $2000.00 | employer rate 0.0242 | 48.40 |  |
| us-ma-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $14000 | employer rate 0.0242 | 24.20 |  |
| us-ma-sui-p03 | biweekly gross $2000.00 | employer rate 0.0094 | 18.80 |  |

### US-MD — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-md-p01 | biweekly gross $2000.00 | filing_status=married_joint; allowances=1; rate_schedule=0.0320 | 138.82 |  |
| us-md-p07 | biweekly gross $2000.00 | filing_status=married_joint; rate_schedule=0.0275 | 140.19 |  |

### US-ME — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-me-p01 | biweekly gross $2000.00 | filing_status=single; allowances=2 | 65.00 |  |
| us-me-p07 | biweekly gross $2000.00 | filing_status=married; allowances=2 | 30.00 |  |

### US-MI — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mi-p01 | biweekly gross $2000.00 | allowances=2 | 65.71 |  |
| us-mi-p07 | biweekly gross $2000.00 | 85.00 |  |

### US-MI — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-mi-sui-p01 | biweekly gross $2000.00 | employer rate 0.027 | 54.00 |  |
| us-mi-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $8000 | employer rate 0.027 | 27.00 |  |
| us-mi-sui-p03 | biweekly gross $2000.00 | employer rate 0.0006 | 1.20 |  |

### US-MN — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mn-p01 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 91.27 |  |
| us-mn-p07 | biweekly gross $2000.00 | filing_status=married; allowances=2 | 54.94 |  |

### US-MN — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-mn-sui-p01 | biweekly gross $2000.00 | employer rate 0.0930 | 466.00 |  |
| us-mn-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $43000 | employer rate 0.0930 | 233.00 |  |
| us-mn-sui-p03 | biweekly gross $2000.00 | employer rate 0.0040 | 288.00 |  |

### US-MO — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mo-p01 | biweekly gross $2000.00 | filing_status=married_spouse_works | 58.00 |  |
| us-mo-p07 | biweekly gross $2000.00 | filing_status=single | 58.00 |  |

### US-MS — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ms-p01 | biweekly gross $2000.00 | filing_status=single; elected_annual_amount=6000.00 | 52.00 |  |
| us-ms-p07 | biweekly gross $2000.00 | filing_status=single | 61.00 |  |

### US-MT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mt-p01 | biweekly gross $2000.00 | filing_status=single | 65.00 |  |
| us-mt-p07 | biweekly gross $2000.00 | filing_status=married_jointly | 36.00 |  |

### US-NC — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-nc-p01 | biweekly gross $2000.00 | filing_status=single_married_surviving_spouse; allowances=2 | 54.00 |  |

### US-NC — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-nc-sui-p01 | biweekly gross $2000.00 | employer rate 0.0100 | 20.00 |  |
| us-nc-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $33200 | employer rate 0.0100 | 10.00 |  |
| us-nc-sui-p03 | biweekly gross $2000.00 | employer rate 0.0006 | 1.20 |  |

### US-ND — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-nd-p01 | biweekly gross $2000.00 | filing_status=single | 0.00 |  |
| us-nd-p07 | biweekly gross $2000.00 | filing_status=married_joint | 0.00 |  |

### US-NE — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ne-p01 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 67.92 |  |
| us-ne-p07 | biweekly gross $2000.00 | filing_status=married; allowances=2; additional_withholding=10.00 | 62.04 |  |

### US-NJ — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-nj-sdi-p01 | biweekly gross $2000.00 | 8.40 |  |
| us-nj-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $170100 | 4.20 |  |

### US-NJ — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-nj-sui-p01 | biweekly gross $2000.00 | employer rate 0.028 | 56.00 |  |
| us-nj-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $43800 | employer rate 0.028 | 28.00 |  |
| us-nj-sui-p03 | biweekly gross $2000.00 | employer rate 0.005 | 10.00 |  |

### US-NJ — state unemployment insurance employee

| id | scenario | ours | expected |
|---|---|---|---|
| us-nj-sui-employee-p01 | biweekly gross $2000.00 | 8.50 |  |
| us-nj-sui-employee-p02 | biweekly gross $2000.00 | YTD sui_wages $43800 | 4.26 |  |

### US-NM — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-nm-p01 | biweekly gross $2000.00 | filing_status=married; additional_withholding=20.00 | 63.56 |  |
| us-nm-p07 | biweekly gross $2000.00 | filing_status=single | 63.72 |  |

### US-NY — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-sdi-p01 | biweekly gross $2000.00 | 9.84 |  |

### US-NY — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-p01 | biweekly gross $2000.00 | filing_status=single; allowances=3 | 80.04 |  |
| us-ny-p07 | biweekly gross $2000.00 | filing_status=single; allowances=2 | 82.12 |  |

### US-NY — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-sui-p01 | biweekly gross $2000.00 | employer rate 0.04025 | 82.00 |  |
| us-ny-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $16600 | employer rate 0.04025 | 41.00 |  |
| us-ny-sui-p03 | biweekly gross $2000.00 | employer rate 0.09425 | 190.00 |  |

### US-NY-NYC — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-nyc-p01 | biweekly gross $2000.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 60.42 |  |
| us-ny-nyc-p07 | biweekly gross $2000.00 | local: resident=True; allowances=1 | state cert: filing_status=single | 63.62 |  |

### US-NY-YONKERS — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-yonkers-p01 | biweekly gross $2000.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 13.41 |  |
| us-ny-yonkers-p07 | biweekly gross $2000.00 | local: resident=False | state cert: filing_status=single | 10.00 |  |

### US-OH — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-oh-sui-p01 | biweekly gross $2000.00 | employer rate 0.0270 | 57.00 |  |
| us-oh-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $8000 | employer rate 0.0270 | 28.50 |  |
| us-oh-sui-p03 | biweekly gross $2000.00 | employer rate 0.0040 | 11.00 |  |

### US-OH-SD-0203 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-oh-sd-0203-p01 | biweekly gross $2000.00 | local: resident=True | 10.00 |  |

### US-OH-SD-0204 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-oh-sd-0204-p01 | biweekly gross $2000.00 | local: resident=True | 10.00 |  |

### US-OK — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ok-p01 | biweekly gross $2000.00 | filing_status=married; allowances=2 | 48.00 |  |
| us-ok-p07 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 69.00 |  |

### US-OR — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-or-sdi-p01 | biweekly gross $2000.00 | 12.00 |  |
| us-or-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $183500 | 6.00 |  |

### US-OR — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-or-p01 | biweekly gross $2000.00 | filing_status=single | 123.00 |  |
| us-or-p07 | biweekly gross $2000.00 | filing_status=single | 146.00 |  |

### US-PA — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-pa-sui-p01 | biweekly gross $2000.00 | employer rate 0.038220 | 76.44 |  |
| us-pa-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $9000 | employer rate 0.038220 | 38.22 |  |
| us-pa-sui-p03 | biweekly gross $2000.00 | employer rate 0.014190 | 28.38 |  |

### US-PA — state unemployment insurance employee

| id | scenario | ours | expected |
|---|---|---|---|
| us-pa-sui-employee-p01 | biweekly gross $2000.00 | 1.40 |  |

### US-PA-PSD-010101 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-pa-psd-010101-p01 | biweekly gross $2000.00 | local: resident=True | 34.00 |  |
| us-pa-psd-010101-p07 | biweekly gross $2000.00 | local: resident=False | 20.00 |  |

### US-PA-PSD-010104 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-pa-psd-010104-p01 | biweekly gross $2000.00 | local: resident=True | 34.00 |  |

### US-RI — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-ri-sdi-p01 | biweekly gross $2000.00 | 22.00 |  |
| us-ri-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $99000 | 11.00 |  |

### US-RI — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ri-p01 | biweekly gross $2000.00 | filing_status=all; allowances=1 | 73.56 |  |
| us-ri-p07 | biweekly gross $2000.00 | allowances=10 | 60.58 |  |

### US-SC — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-sc-p01 | biweekly gross $2000.00 | filing_status=all; allowances=3 | 48.15 |  |
| us-sc-p07 | biweekly gross $2000.00 | 94.77 |  |

### US-TX — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-tx-sui-p01 | biweekly gross $2000.00 | employer rate 0.0270 | 54.00 |  |
| us-tx-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $8000 | employer rate 0.0270 | 27.00 |  |
| us-tx-sui-p03 | biweekly gross $2000.00 | employer rate 0.0625 | 125.00 |  |

### US-UT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ut-p01 | biweekly gross $2000.00 | filing_status=single | 89.00 |  |
| us-ut-p07 | biweekly gross $2000.00 | filing_status=married | 69.00 |  |

### US-VA — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-va-sui-p01 | biweekly gross $2000.00 | employer rate 0.025 | 50.00 |  |
| us-va-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $7000 | employer rate 0.025 | 25.00 |  |
| us-va-sui-p03 | biweekly gross $2000.00 | employer rate 0.001 | 2.00 |  |

### US-VT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-vt-p01 | biweekly gross $2000.00 | filing_status=married; allowances=2 | 37.91 |  |
| us-vt-p07 | biweekly gross $2000.00 | filing_status=single; allowances=1 | 54.98 |  |

### US-WA — state disability insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-wa-sdi-p01 | biweekly gross $2000.00 | 16.14 |  |
| us-wa-sdi-p02 | biweekly gross $2000.00 | YTD sdi_wages $183500 | 8.07 |  |

### US-WA — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-wa-sui-p01 | biweekly gross $2000.00 | employer rate 0.0600 | 120.00 |  |
| us-wa-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $77200 | employer rate 0.0600 | 60.00 |  |
| us-wa-sui-p03 | biweekly gross $2000.00 | employer rate 0.0024 | 4.80 |  |

### US-WI — state unemployment insurance

| id | scenario | ours | expected |
|---|---|---|---|
| us-wi-sui-p01 | biweekly gross $2000.00 | employer rate 0.0305 | 61.00 |  |
| us-wi-sui-p02 | biweekly gross $2000.00 | YTD sui_wages $13000 | employer rate 0.0305 | 30.50 |  |
| us-wi-sui-p03 | biweekly gross $2000.00 | employer rate 0.0250 | 50.00 |  |

### US-WV — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-wv-p01 | biweekly gross $2000.00 | filing_status=married_both_working_two_jobs; allowances=1 | 65.07 |  |
| us-wv-p07 | biweekly gross $2000.00 | filing_status=single_hoh_married_one_income; allowances=2 | 55.54 |  |

## Extended scenarios

### US — federal income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-federal-p02 | weekly gross $900.00 | W-4: w4_version=2020, filing_status=married_joint | 28.08 |  |
| us-federal-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | W-4: w4_version=2020, filing_status=married_joint | 1009.93 |  |
| us-federal-p04 | semimonthly gross $4500.00 | W-4: w4_version=2020, filing_status=married_joint | 358.33 |  |
| us-federal-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | W-4: w4_version=2020, filing_status=married_joint | 64.15 |  |
| us-federal-p06 | weekly gross $15000.00 | W-4: w4_version=2020, filing_status=married_joint | 3832.09 |  |

### US — fica

| id | scenario | ours | expected |
|---|---|---|---|
| us-federal-fica-p02 | weekly gross $900.00 | 68.85 |  |
| us-federal-fica-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | 918.00 |  |
| us-federal-fica-p04 | semimonthly gross $4500.00 | 344.25 |  |
| us-federal-fica-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | 153.00 |  |
| us-federal-fica-p06 | weekly gross $15000.00 | 1147.50 |  |

### US-AL — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-al-p02 | weekly gross $900.00 | filing_status=m; allowances=2 | 32.09 |  |
| us-al-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=m; allowances=2 | 519.74 |  |
| us-al-p04 | semimonthly gross $4500.00 | filing_status=m; allowances=2 | 201.99 |  |
| us-al-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=m; allowances=2 | 69.93 |  |
| us-al-p06 | weekly gross $15000.00 | filing_status=m; allowances=2 | 738.43 |  |

### US-AR — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ar-p02 | weekly gross $900.00 | filing_status=default; allowances=2 | 23.38 |  |
| us-ar-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=default; allowances=2 | 398.25 |  |
| us-ar-p04 | semimonthly gross $4500.00 | filing_status=default; allowances=2 | 156.96 |  |
| us-ar-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=default; allowances=2 | 49.73 |  |
| us-ar-p06 | weekly gross $15000.00 | filing_status=default; allowances=2 | 550.60 |  |

### US-AZ — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-az-p02 | weekly gross $900.00 | elected_rate=0.025 | 22.50 |  |
| us-az-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | elected_rate=0.025 | 282.00 |  |
| us-az-p04 | semimonthly gross $4500.00 | elected_rate=0.025 | 112.50 |  |
| us-az-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | elected_rate=0.025 | 47.00 |  |
| us-az-p06 | weekly gross $15000.00 | elected_rate=0.025 | 375.00 |  |

### US-CA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ca-p02 | weekly gross $900.00 | filing_status=single; allowances=1 | 18.06 |  |
| us-ca-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=1 | 764.75 |  |
| us-ca-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=1 | 265.76 |  |
| us-ca-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=1 | 41.19 |  |
| us-ca-p06 | weekly gross $15000.00 | filing_status=single; allowances=1 | 1605.97 |  |

### US-CT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ct-p02 | weekly gross $900.00 | filing_status=a | 32.12 |  |
| us-ct-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=a | 608.05 |  |
| us-ct-p04 | semimonthly gross $4500.00 | filing_status=a | 229.38 |  |
| us-ct-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=a | 68.99 |  |
| us-ct-p06 | weekly gross $15000.00 | filing_status=a | 1047.54 |  |

### US-GA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ga-p02 | weekly gross $900.00 | filing_status=married_joint; allowances=1 | 11.32 |  |
| us-ga-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married_joint; allowances=1 | 417.33 |  |
| us-ga-p04 | semimonthly gross $4500.00 | filing_status=married_joint; allowances=1 | 151.78 |  |
| us-ga-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married_joint; allowances=1 | 26.64 |  |
| us-ga-p06 | weekly gross $15000.00 | filing_status=married_joint; allowances=1 | 714.91 |  |

### US-HI — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-hi-p02 | weekly gross $900.00 | filing_status=single; allowances=3; secondary_allowances=1 | 36.39 |  |
| us-hi-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=3; secondary_allowances=1 | 716.22 |  |
| us-hi-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=3; secondary_allowances=1 | 271.15 |  |
| us-hi-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=3; secondary_allowances=1 | 78.54 |  |
| us-hi-p06 | weekly gross $15000.00 | filing_status=single; allowances=3; secondary_allowances=1 | 1144.64 |  |

### US-IA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ia-p02 | weekly gross $900.00 | filing_status=other_married_spouse_earns; elected_annual_amount=40 | 23.93 |  |
| us-ia-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=other_married_spouse_earns; elected_annual_amount=40 | 384.14 |  |
| us-ia-p04 | semimonthly gross $4500.00 | filing_status=other_married_spouse_earns; elected_annual_amount=40 | 148.75 |  |
| us-ia-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=other_married_spouse_earns; elected_annual_amount=40 | 50.90 |  |
| us-ia-p06 | weekly gross $15000.00 | filing_status=other_married_spouse_earns; elected_annual_amount=40 | 559.73 |  |

### US-ID — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-id-p02 | weekly gross $900.00 | filing_status=single; allowances=4 | 17.00 |  |
| us-id-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=4 | 463.00 |  |
| us-id-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=4 | 171.00 |  |
| us-id-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=4 | 38.00 |  |
| us-id-p06 | weekly gross $15000.00 | filing_status=single; allowances=4 | 764.00 |  |

### US-IL — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-il-p02 | weekly gross $900.00 | filing_status=all; allowances=2; secondary_allowances=2 | 37.08 |  |
| us-il-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=all; allowances=2; secondary_allowances=2 | 525.98 |  |
| us-il-p04 | semimonthly gross $4500.00 | filing_status=all; allowances=2; secondary_allowances=2 | 206.56 |  |
| us-il-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=all; allowances=2; secondary_allowances=2 | 78.11 |  |
| us-il-p06 | weekly gross $15000.00 | filing_status=all; allowances=2; secondary_allowances=2 | 735.03 |  |

### US-IN — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-in-p02 | weekly gross $900.00 | filing_status=all; exemptions={'personal': 5, 'dependent': 3, 'first_time_dependent': 1, 'adopted': 2} | 16.91 |  |
| us-in-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=all; exemptions={'personal': 5, 'dependent': 3, 'first_time_dependent': 1, 'adopted': 2} | 290.97 |  |
| us-in-p04 | semimonthly gross $4500.00 | filing_status=all; exemptions={'personal': 5, 'dependent': 3, 'first_time_dependent': 1, 'adopted': 2} | 111.85 |  |
| us-in-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=all; exemptions={'personal': 5, 'dependent': 3, 'first_time_dependent': 1, 'adopted': 2} | 36.17 |  |
| us-in-p06 | weekly gross $15000.00 | filing_status=all; exemptions={'personal': 5, 'dependent': 3, 'first_time_dependent': 1, 'adopted': 2} | 432.86 |  |

### US-KY — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ky-p02 | weekly gross $900.00 | 29.24 |  |
| us-ky-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | 385.00 |  |
| us-ky-p04 | semimonthly gross $4500.00 | 152.60 |  |
| us-ky-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | 61.28 |  |
| us-ky-p06 | weekly gross $15000.00 | 522.74 |  |

### US-LA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-la-p02 | weekly gross $900.00 | filing_status=single; allowances=1 | 20.16 |  |
| us-la-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=1 | 315.40 |  |
| us-la-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=1 | 122.47 |  |
| us-la-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=1 | 42.79 |  |
| us-la-p06 | weekly gross $15000.00 | filing_status=single; allowances=1 | 455.85 |  |

### US-MA — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ma-p02 | weekly gross $900.00 | allowances=1 | 37.69 |  |
| us-ma-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | allowances=1 | 542.59 |  |
| us-ma-p04 | semimonthly gross $4500.00 | allowances=1 | 212.79 |  |
| us-ma-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | allowances=1 | 82.49 |  |
| us-ma-p06 | weekly gross $15000.00 | allowances=1 | 742.69 |  |

### US-MD — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-md-p02 | weekly gross $900.00 | filing_status=married_joint; allowances=1; rate_schedule=0.0320 | 61.46 |  |
| us-md-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married_joint; allowances=1; rate_schedule=0.0320 | 853.04 |  |
| us-md-p04 | semimonthly gross $4500.00 | filing_status=married_joint; allowances=1; rate_schedule=0.0320 | 335.89 |  |
| us-md-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married_joint; allowances=1; rate_schedule=0.0320 | 129.28 |  |
| us-md-p06 | weekly gross $15000.00 | filing_status=married_joint; allowances=1; rate_schedule=0.0320 | 1306.96 |  |

### US-ME — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-me-p02 | weekly gross $900.00 | filing_status=single; allowances=2 | 26.00 |  |
| us-me-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=2 | 659.00 |  |
| us-me-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=2 | 234.00 |  |
| us-me-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=2 | 58.00 |  |
| us-me-p06 | weekly gross $15000.00 | filing_status=single; allowances=2 | 1048.00 |  |

### US-MI — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mi-p02 | weekly gross $900.00 | allowances=2 | 28.61 |  |
| us-mi-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | allowances=2 | 437.61 |  |
| us-mi-p04 | semimonthly gross $4500.00 | allowances=2 | 170.35 |  |
| us-mi-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | allowances=2 | 60.61 |  |
| us-mi-p06 | weekly gross $15000.00 | allowances=2 | 627.86 |  |

### US-MN — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mn-p02 | weekly gross $900.00 | filing_status=single; allowances=1 | 38.83 |  |
| us-mn-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=1 | 684.06 |  |
| us-mn-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=1 | 257.54 |  |
| us-mn-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=1 | 83.11 |  |
| us-mn-p06 | weekly gross $15000.00 | filing_status=single; allowances=1 | 1349.04 |  |

### US-MO — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mo-p02 | weekly gross $900.00 | filing_status=married_spouse_works | 24.00 |  |
| us-mo-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married_spouse_works | 452.00 |  |
| us-mo-p04 | semimonthly gross $4500.00 | filing_status=married_spouse_works | 172.00 |  |
| us-mo-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married_spouse_works | 52.00 |  |
| us-mo-p06 | weekly gross $15000.00 | filing_status=married_spouse_works | 687.00 |  |

### US-MS — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ms-p02 | weekly gross $900.00 | filing_status=single; elected_annual_amount=6000.00 | 22.00 |  |
| us-ms-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; elected_annual_amount=6000.00 | 390.00 |  |
| us-ms-p04 | semimonthly gross $4500.00 | filing_status=single; elected_annual_amount=6000.00 | 150.00 |  |
| us-ms-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; elected_annual_amount=6000.00 | 47.00 |  |
| us-ms-p06 | weekly gross $15000.00 | filing_status=single; elected_annual_amount=6000.00 | 586.00 |  |

### US-MT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-mt-p02 | weekly gross $900.00 | filing_status=single | 28.00 |  |
| us-mt-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single | 525.00 |  |
| us-mt-p04 | semimonthly gross $4500.00 | filing_status=single | 199.00 |  |
| us-mt-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single | 59.00 |  |
| us-mt-p06 | weekly gross $15000.00 | filing_status=single | 821.00 |  |

### US-NC — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-nc-p02 | weekly gross $900.00 | filing_status=single_married_surviving_spouse; allowances=2 | 23.00 |  |
| us-nc-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single_married_surviving_spouse; allowances=2 | 401.00 |  |
| us-nc-p04 | semimonthly gross $4500.00 | filing_status=single_married_surviving_spouse; allowances=2 | 154.00 |  |
| us-nc-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single_married_surviving_spouse; allowances=2 | 49.00 |  |
| us-nc-p06 | weekly gross $15000.00 | filing_status=single_married_surviving_spouse; allowances=2 | 600.00 |  |

### US-ND — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-nd-p02 | weekly gross $900.00 | filing_status=single | 0.00 |  |
| us-nd-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single | 126.00 |  |
| us-nd-p04 | semimonthly gross $4500.00 | filing_status=single | 41.00 |  |
| us-nd-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single | 0.00 |  |
| us-nd-p06 | weekly gross $15000.00 | filing_status=single | 326.00 |  |

### US-NE — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ne-p02 | weekly gross $900.00 | filing_status=single; allowances=1 | 29.48 |  |
| us-ne-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=1 | 464.13 |  |
| us-ne-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=1 | 179.63 |  |
| us-ne-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=1 | 62.55 |  |
| us-ne-p06 | weekly gross $15000.00 | filing_status=single; allowances=1 | 677.37 |  |

### US-NM — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-nm-p02 | weekly gross $900.00 | filing_status=married; additional_withholding=20.00 | 37.50 |  |
| us-nm-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married; additional_withholding=20.00 | 439.40 |  |
| us-nm-p04 | semimonthly gross $4500.00 | filing_status=married; additional_withholding=20.00 | 174.52 |  |
| us-nm-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married; additional_withholding=20.00 | 58.40 |  |
| us-nm-p06 | weekly gross $15000.00 | filing_status=married; additional_withholding=20.00 | 810.58 |  |

### US-NY — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-p02 | weekly gross $900.00 | filing_status=single; allowances=3 | 34.65 |  |
| us-ny-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single; allowances=3 | 600.78 |  |
| us-ny-p04 | semimonthly gross $4500.00 | filing_status=single; allowances=3 | 216.66 |  |
| us-ny-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single; allowances=3 | 73.56 |  |
| us-ny-p06 | weekly gross $15000.00 | filing_status=single; allowances=3 | 1079.78 |  |

### US-NY-NYC — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-nyc-p02 | weekly gross $900.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 26.06 |  |
| us-ny-nyc-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 424.90 |  |
| us-ny-nyc-p04 | semimonthly gross $4500.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 164.00 |  |
| us-ny-nyc-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 55.44 |  |
| us-ny-nyc-p06 | weekly gross $15000.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 624.91 |  |

### US-NY-YONKERS — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ny-yonkers-p02 | weekly gross $900.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 5.80 |  |
| us-ny-yonkers-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 100.63 |  |
| us-ny-yonkers-p04 | semimonthly gross $4500.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 36.29 |  |
| us-ny-yonkers-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 12.32 |  |
| us-ny-yonkers-p06 | weekly gross $15000.00 | local: resident=True; allowances=3 | state cert: filing_status=single | 180.86 |  |

### US-OH-SD-0203 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-oh-sd-0203-p02 | weekly gross $900.00 | local: resident=True | 4.50 |  |
| us-oh-sd-0203-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | local: resident=True | 56.40 |  |
| us-oh-sd-0203-p04 | semimonthly gross $4500.00 | local: resident=True | 22.50 |  |
| us-oh-sd-0203-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | local: resident=True | 9.40 |  |
| us-oh-sd-0203-p06 | weekly gross $15000.00 | local: resident=True | 75.00 |  |

### US-OH-SD-0204 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-oh-sd-0204-p02 | weekly gross $900.00 | local: resident=True | 4.50 |  |
| us-oh-sd-0204-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | local: resident=True | 56.40 |  |
| us-oh-sd-0204-p04 | semimonthly gross $4500.00 | local: resident=True | 22.50 |  |
| us-oh-sd-0204-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | local: resident=True | 9.40 |  |
| us-oh-sd-0204-p06 | weekly gross $15000.00 | local: resident=True | 75.00 |  |

### US-OK — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ok-p02 | weekly gross $900.00 | filing_status=married; allowances=2 | 20.00 |  |
| us-ok-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married; allowances=2 | 417.00 |  |
| us-ok-p04 | semimonthly gross $4500.00 | filing_status=married; allowances=2 | 157.00 |  |
| us-ok-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married; allowances=2 | 43.00 |  |
| us-ok-p06 | weekly gross $15000.00 | filing_status=married; allowances=2 | 654.00 |  |

### US-OR — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-or-p02 | weekly gross $900.00 | filing_status=single | 58.00 |  |
| us-or-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single | 917.00 |  |
| us-or-p04 | semimonthly gross $4500.00 | filing_status=single | 338.00 |  |
| us-or-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single | 123.00 |  |
| us-or-p06 | weekly gross $15000.00 | filing_status=single | 1446.00 |  |

### US-PA-PSD-010101 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-pa-psd-010101-p02 | weekly gross $900.00 | local: resident=True | 15.30 |  |
| us-pa-psd-010101-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | local: resident=True | 204.00 |  |
| us-pa-psd-010101-p04 | semimonthly gross $4500.00 | local: resident=True | 76.50 |  |
| us-pa-psd-010101-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | local: resident=True | 34.00 |  |
| us-pa-psd-010101-p06 | weekly gross $15000.00 | local: resident=True | 255.00 |  |

### US-PA-PSD-010104 — local income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-pa-psd-010104-p02 | weekly gross $900.00 | local: resident=True | 15.30 |  |
| us-pa-psd-010104-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | local: resident=True | 204.00 |  |
| us-pa-psd-010104-p04 | semimonthly gross $4500.00 | local: resident=True | 76.50 |  |
| us-pa-psd-010104-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | local: resident=True | 34.00 |  |
| us-pa-psd-010104-p06 | weekly gross $15000.00 | local: resident=True | 255.00 |  |

### US-RI — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ri-p02 | weekly gross $900.00 | filing_status=all; allowances=1 | 33.03 |  |
| us-ri-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=all; allowances=1 | 463.47 |  |
| us-ri-p04 | semimonthly gross $4500.00 | filing_status=all; allowances=1 | 177.58 |  |
| us-ri-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=all; allowances=1 | 69.06 |  |
| us-ri-p06 | weekly gross $15000.00 | filing_status=all; allowances=1 | 838.26 |  |

### US-SC — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-sc-p02 | weekly gross $900.00 | filing_status=all; allowances=3 | 18.68 |  |
| us-sc-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=all; allowances=3 | 509.63 |  |
| us-sc-p04 | semimonthly gross $4500.00 | filing_status=all; allowances=3 | 186.41 |  |
| us-sc-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=all; allowances=3 | 41.67 |  |
| us-sc-p06 | weekly gross $15000.00 | filing_status=all; allowances=3 | 861.42 |  |

### US-UT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-ut-p02 | weekly gross $900.00 | filing_status=single | 40.00 |  |
| us-ut-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=single | 502.00 |  |
| us-ut-p04 | semimonthly gross $4500.00 | filing_status=single | 200.00 |  |
| us-ut-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=single | 84.00 |  |
| us-ut-p06 | weekly gross $15000.00 | filing_status=single | 668.00 |  |

### US-VT — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-vt-p02 | weekly gross $900.00 | filing_status=married; allowances=2 | 15.62 |  |
| us-vt-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married; allowances=2 | 390.92 |  |
| us-vt-p04 | semimonthly gross $4500.00 | filing_status=married; allowances=2 | 120.20 |  |
| us-vt-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married; allowances=2 | 33.89 |  |
| us-vt-p06 | weekly gross $15000.00 | filing_status=married; allowances=2 | 1113.21 |  |

### US-WV — state income withholding

| id | scenario | ours | expected |
|---|---|---|---|
| us-wv-p02 | weekly gross $900.00 | filing_status=married_both_working_two_jobs; allowances=1 | 27.97 |  |
| us-wv-p03 | monthly gross $12000.00 | pre-tax 401k_traditional $720.00 | filing_status=married_both_working_two_jobs; allowances=1 | 459.15 |  |
| us-wv-p04 | semimonthly gross $4500.00 | filing_status=married_both_working_two_jobs; allowances=1 | 177.36 |  |
| us-wv-p05 | biweekly gross $2000.00 | pre-tax 401k_traditional $120.00 | filing_status=married_both_working_two_jobs; allowances=1 | 59.58 |  |
| us-wv-p06 | weekly gross $15000.00 | filing_status=married_both_working_two_jobs; allowances=1 | 673.74 |  |
