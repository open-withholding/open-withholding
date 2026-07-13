"""Turn LLM extraction/verification output into repo artifacts.

Pure functions, no network and no LLM: everything here is unit-testable. The
model's per-filing-status arrays become the data files' keyed mappings, the
envelope is stamped from the registry + retrieval metadata, and worked
examples become golden-test fixtures.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import PurePosixPath

WITHHOLDING_TAXES = (
    "federal_income_withholding",
    "state_income_withholding",
    "local_income_withholding",
)


def data_path(jurisdiction: str, year: int) -> PurePosixPath:
    """Repo-relative path for a jurisdiction-year withholding file."""
    parts = jurisdiction.split("-")
    if jurisdiction == "US":
        return PurePosixPath(f"data/us/federal/{year}/withholding.yaml")
    if len(parts) == 2:
        return PurePosixPath(f"data/us/{parts[1].lower()}/{year}/withholding.yaml")
    local_id = "-".join(parts[2:]).lower()
    return PurePosixPath(f"data/us/{parts[1].lower()}/{year}/locals/{local_id}.yaml")


def golden_slug(jurisdiction: str) -> str:
    """Filename prefix for golden cases: US -> us-federal, US-CO -> us-co."""
    return "us-federal" if jurisdiction == "US" else jurisdiction.lower()


# Connector words carry no meaning in a status key: "married and spouse
# works" and "married spouse works" are the same status. "of" is kept —
# head_of_household is the established spelling everywhere.
_CONNECTORS = {"and", "or"}

# Spelling variants of the same concept converge on one canonical key,
# matching the keys already merged in the dataset (federal, CO). Semantic
# distinctions are per-jurisdiction and are NEVER merged here — this table
# only collapses different spellings, not different meanings.
_ALIASES = {
    "married_filing_jointly": "married_joint",
    "married_filing_joint": "married_joint",
    "married_filing_jointly_qualifying_surviving_spouse": "married_joint",
    "head_of_household_hoh": "head_of_household",
}


def snake(label: str) -> str:
    """Filing-status keys are machine identifiers, not prose. Extraction is
    prompted to emit snake_case (reusing the prior edition's keys when one
    exists); this is the deterministic backstop for prose labels like
    "Married and Spouse Works". Idempotent on already-canonical keys."""
    words = [
        w for w in re.sub(r"[^a-z0-9]+", " ", label.lower()).split() if w not in _CONNECTORS
    ]
    key = "_".join(words)
    return _ALIASES.get(key, key)


def _status_map(entries: list[dict], value_key: str = "amount") -> dict:
    return {snake(e["filing_status"]): e[value_key] for e in entries}


def _bracket_map(entries: list[dict]) -> dict:
    out = {}
    for e in entries:
        rows = []
        for row in e["rows"]:
            cleaned = {"over": row["over"], "rate": row["rate"]}
            if row.get("base") is not None:
                cleaned["base"] = row["base"]
            rows.append(cleaned)
        out[snake(e["filing_status"])] = rows
    return out


def _transform_params(method: str, params: dict) -> dict:
    if method == "flat_rate":
        return {"rate": params["rate"]}
    if method == "flat_rate_with_annual_allowance":
        return {
            "rate": params["rate"],
            "filing_status": {
                fs: {"annual_allowance": amount}
                for fs, amount in _status_map(params["allowances"]).items()
            },
        }
    if method == "annualized_percentage":
        out: dict = {}
        if params.get("standard_deduction"):
            out["standard_deduction"] = _status_map(params["standard_deduction"])
        out["allowance_amount"] = params.get("allowance_amount")
        if params.get("secondary_allowance_amount") is not None:
            out["secondary_allowance_amount"] = params["secondary_allowance_amount"]
        if params.get("percent_deduction") is not None:
            out["percent_deduction"] = params["percent_deduction"]
        if params.get("elected_amount_treatment") is not None:
            out["elected_amount_treatment"] = params["elected_amount_treatment"]
        out["credit_per_allowance"] = params.get("credit_per_allowance")
        out["brackets"] = _bracket_map(params["brackets"])
        return out
    if method == "annualized_percentage_phaseout":
        return {
            "deduction_phaseout": {
                snake(e["filing_status"]): {
                    "maximum": e["maximum"],
                    "phase_start": e["phase_start"],
                    "phase_rate": e["phase_rate"],
                }
                for e in params["deduction_phaseout"]
            },
            "exemption_amount": params.get("exemption_amount"),
            "brackets": _bracket_map(params["brackets"]),
        }
    if method == "elective_flat_rate":
        return {
            "allowed_rates": params["allowed_rates"],
            "zero_rate_allowed": params["zero_rate_allowed"],
            **({"default_rate": params["default_rate"]}
               if params.get("default_rate") is not None else {}),
        }
    if method == "custom/us_ma":
        def freq_map(rows):
            return {e["frequency"]: e["amount"] for e in rows}
        return {
            "retirement_deduction_cap": params["retirement_deduction_cap"],
            "exemption_factors": {
                e["frequency"]: {"claiming_one": e["claiming_one"],
                                 "per_exemption": e["per_exemption"], "plus": e["plus"]}
                for e in params["exemption_factors"]
            },
            "brackets": [
                {"over": r["over"], "rate": r["rate"],
                 **({"base": r["base"]} if r.get("base") is not None else {})}
                for r in params["brackets"]
            ],
            "hoh_tax_value": freq_map(params["hoh_tax_value"]),
            "blindness_tax_value": freq_map(params["blindness_tax_value"]),
            "low_income_floor": freq_map(params["low_income_floor"]),
        }
    if method == "custom/us_al":
        return {
            "statuses": {
                e["code"]: {
                    "personal_exemption": e["personal_exemption"],
                    "standard_deduction": e["standard_deduction"],
                    "brackets": [
                        {"over": r["over"], "rate": r["rate"],
                         **({"base": r["base"]} if r.get("base") is not None else {})}
                        for r in e["brackets"]
                    ],
                }
                for e in params["statuses"]
            },
            "dependent_tiers": params["dependent_tiers"],
        }
    if method == "custom/us_or":
        return {
            "credit_per_allowance": params["credit_per_allowance"],
            "statuses": {
                e["status"]: {
                    "allowance_zero_above": e["allowance_zero_above"],
                    "fed_subtraction_phaseout": e["fed_subtraction_phaseout"],
                }
                for e in params["statuses"]
            },
            "status_groups": {
                e["group"]: {
                    "standard_deduction": e["standard_deduction"],
                    "wage_tiers": e["wage_tiers"],
                }
                for e in params["status_groups"]
            },
        }
    if method == "custom/us_ct":
        return {
            "codes": {
                e["code"]: {
                    "exemptions": e["exemptions"],
                    "brackets": [
                        {"over": r["over"], "rate": r["rate"],
                         **({"base": r["base"]} if r.get("base") is not None else {})}
                        for r in e["brackets"]
                    ],
                    "add_back": e["add_back"],
                    "recapture": e["recapture"],
                    "credits": e["credits"],
                }
                for e in params["codes"]
            }
        }
    if method == "annualized_subtraction_percentage":
        return {
            "standard_deduction": params["standard_deduction"],
            "credit_per_allowance": params.get("credit_per_allowance"),
            "midrange_snap": params["midrange_snap"],
            "table": [
                {"from": r["from"], "rate": r["rate"],
                 **({"subtract": r["subtract"]} if r.get("subtract") is not None else {})}
                for r in params["table"]
            ],
        }
    if method == "per_period_credit_phaseout":
        return {
            "rate": params["rate"],
            "phase_rate": params["phase_rate"],
            "schedules": {
                e["frequency"]: {
                    snake(st["filing_status"]): {
                        "base_allowance": st["base_allowance"],
                        "phase_start": st["phase_start"],
                    }
                    for st in e["statuses"]
                }
                for e in params["frequencies"]
            },
        }
    if method == "per_period_percentage":
        out = {}
        if params.get("standard_deduction"):
            out["standard_deduction"] = _status_map(params["standard_deduction"])
        if params.get("allowance_amount") is not None:
            out["allowance_amount"] = params["allowance_amount"]
        if params.get("allowance_amounts_per_period"):
            out["allowance_amounts_per_period"] = {
                e["frequency"]: e["amount"] for e in params["allowance_amounts_per_period"]
            }
        if params.get("allowance_cliff_annual_wages") is not None:
            out["allowance_cliff_annual_wages"] = params["allowance_cliff_annual_wages"]
        if params.get("credit_per_allowance") is not None:
            out["credit_per_allowance"] = params["credit_per_allowance"]
        if params.get("elected_amount_treatment") is not None:
            out["elected_amount_treatment"] = params["elected_amount_treatment"]
        out["brackets"] = {
            e["frequency"]: _bracket_map(e["tables"]) for e in params["frequencies"]
        }
        return out
    if method == "federal_percentage_2020":
        return {
            "wage_adjustment": _status_map(params["wage_adjustment"]),
            "brackets": {
                "standard": _bracket_map(params["brackets_standard"]),
                "step2_checkbox": _bracket_map(params["brackets_step2_checkbox"]),
            },
        }
    raise ValueError(f"no transform for method {method!r}")


def assemble_parameter_file(
    *,
    jurisdiction: str,
    tax: str,
    method: str,
    extraction: dict,
    source: dict,
    schema_version: str = "0.1",
    supersedes: str | None = None,
) -> dict:
    """Build the full parameter-file mapping ready for validation and YAML dump.

    `source` must already carry document/url/retrieved/sha256 from the
    retrieval step — provenance never comes from the model."""
    rounding = dict(extraction["rounding"])
    if rounding.get("intermediate_to") is None:
        rounding.pop("intermediate_to", None)
    if method.startswith("custom/"):
        method_field = {"method": "custom", "custom_implementation": method}
    else:
        method_field = {"method": method}
    provenance = (
        {"sources": source["sources"]} if "sources" in source else {"source": source}
    )
    if "sources" in source:
        schema_version = "0.2"  # multi-document citation is a v0.2 feature
    return {
        "schema_version": schema_version,
        "jurisdiction": jurisdiction,
        "tax": tax,
        "effective_from": extraction["effective_from"],
        "effective_to": None,
        **({"supersedes": supersedes} if supersedes else {}),
        **provenance,
        **method_field,
        "rounding": rounding,
        "params": _transform_params(method, extraction["params"]),
    }


def _money(value, default: str = "0") -> str:
    return default if value is None else value


def assemble_golden_case(
    *,
    jurisdiction: str,
    tax: str,
    example: dict,
    as_of: str,
    document: str,
) -> dict:
    """One verification-pass worked example -> one golden case mapping."""
    record: dict = {
        "pay_frequency": example["pay_frequency"],
        "gross_wages": example["gross_wages"],
    }
    if example.get("period_federal_income_withholding") is not None:
        record["period_federal_income_withholding"] = example["period_federal_income_withholding"]
    if tax == "federal_income_withholding":
        record["federal"] = {
            "w4_version": 2020,
            "filing_status": snake(example["filing_status"]),
            "step2_checkbox": bool(example.get("step2_checkbox")),
            "step3_credits": _money(example.get("step3_credits")),
            "step4a_other_income": _money(example.get("step4a_other_income")),
            "step4b_deductions": _money(example.get("step4b_deductions")),
            "step4c_extra": _money(example.get("step4c_extra")),
        }
        expect_key = "federal_withholding"
    elif tax == "state_income_withholding":
        election = {
            "jurisdiction": jurisdiction,
            "filing_status": snake(example["filing_status"]),
            "allowances": example.get("allowances") or 0,
            "additional_withholding": _money(example.get("additional_withholding")),
        }
        if example.get("secondary_allowances"):
            election["secondary_allowances"] = example["secondary_allowances"]
        if example.get("elected_annual_amount") is not None:
            election["elected_annual_amount"] = example["elected_annual_amount"]
        record["state"] = [election]
        expect_key = "state_withholding"
    elif tax == "local_income_withholding":
        record["locals"] = [{"jurisdiction": jurisdiction, "resident": True}]
        expect_key = "local_withholding"
    else:
        raise ValueError(f"no golden mapping for tax {tax!r}")

    return {
        "source": {
            "document": document,
            "page": example["page"],
            "example": example["description"],
        },
        "as_of": as_of,
        "input": record,
        "expect": {expect_key: example["expected_withholding"]},
    }


def default_as_of(effective_from: str) -> str:
    """Mid-effective-year date used to select the candidate file in goldens."""
    start = dt.date.fromisoformat(str(effective_from))
    return dt.date(start.year, 6, 15).isoformat() if start.month == 1 else str(effective_from)


def build_pr_body(
    *,
    source_id: str,
    jurisdiction: str,
    tax: str,
    method: str,
    source: dict,
    extraction: dict,
    verification: dict,
    golden_paths: list[str],
    golden_ok: bool,
    prev_path: str | None,
) -> str:
    checks = verification.get("checks", [])
    confirmed = sum(1 for c in checks if c["confirmed"])
    unconfirmed = [c for c in checks if not c["confirmed"]]
    lines = [
        f"## `{source_id}`: {jurisdiction} {tax.replace('_', ' ')}",
        "",
        f"- **Method:** `{method}`",
        f"- **Classification:** {extraction['classification']}",
        f"- **Effective from:** {extraction['effective_from']}",
        *(
            [
                line
                for block in source["sources"]
                for line in (
                    f"- **Source:** [{block['document']}]({block['url']}) — retrieved {block['retrieved']}",
                    f"- **Archived sha256:** `{block['sha256']}`",
                )
            ]
            if "sources" in source
            else [
                f"- **Source:** [{source['document']}]({source['url']}) — retrieved {source['retrieved']}",
                f"- **Archived PDF sha256:** `{source['sha256']}`",
            ]
        ),
        f"- **Supersedes:** `{prev_path}`" if prev_path else "- **Supersedes:** none (first edition in repo)",
        "",
        "### Extraction citations",
        "",
        *(f"- {c['what']} — p.{c['page']}" for c in extraction.get("citations", [])),
        "",
        "### Independent verification (separate context)",
        "",
        f"- {confirmed}/{len(checks)} values confirmed against the document",
    ]
    for c in unconfirmed:
        lines.append(f"- ⚠️ **UNCONFIRMED** `{c['path']}` = `{c['candidate_value']}` — {c['note'] or 'no note'}")
    lines += ["", "### Golden tests", ""]
    if golden_paths:
        lines += [
            "Transcribed from this document's worked examples:",
            "",
            *(f"- `{p}`" for p in golden_paths),
            "",
            f"- Engine reproduces every example: **{'PASS' if golden_ok else 'FAIL'}**",
        ]
    else:
        lines += [
            "⚠️ **This publication prints no applicable worked examples.** "
            "Maintainer-constructed golden cases (noted as such in their `source`) are "
            "required before merge; the data-golden-guard CI job enforces this.",
        ]
    lines += [
        "",
        "### Extractor notes",
        "",
        extraction.get("notes", "").strip() or "(none)",
        "",
        "### Reviewer checklist",
        "",
        "- [ ] Spot-checked 2–3 parameter values against the linked PDF pages",
        "- [ ] Golden tests are transcribed from THIS edition (source document/year matches)",
        "- [ ] Rounding block matches what the worked examples actually do",
        "- [ ] `supersedes` / `effective_to` handled on the prior file if this is a revision",
        "",
        "🤖 Extracted by the pipeline; every number above requires human review before merge.",
    ]
    return "\n".join(lines)
