#!/usr/bin/env python3
"""LLM-assisted extraction: government PDF -> candidate data PR (DESIGN.md §8.2).

Drive it manually per document while seeding; the watcher will enqueue the
same command once it exists. The flow never merges anything: it writes a
candidate parameter file + golden fixtures into the working tree and a PR
body under pipeline/out/, and the human takes it from there.

    python pipeline/extract.py us-federal-p15t --year 2026
    python pipeline/extract.py us-co-dr1098 --year 2026 --pdf ~/Downloads/DR1098_2026.pdf

Stages: fetch+archive -> extract (LLM) -> independently verify (separate LLM
context) -> mechanical validation (schema, brackets, golden tests against the
reference engine) -> write candidate + PR body. Any failure writes a triage
report instead of candidate files.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from engine.errors import EngineError  # noqa: E402
from engine.golden import GoldenCase, run_golden_case  # noqa: E402
from engine.loader import load_parameter_dict  # noqa: E402
from engine.taxability import TaxabilityMatrix  # noqa: E402
from pipeline import assemble, discover  # noqa: E402
from pipeline.schemas import VERIFICATION_SCHEMA, extraction_schema  # noqa: E402

ARCHIVE_DIR = REPO_ROOT / "archive"
OUT_DIR = REPO_ROOT / "pipeline" / "out"
SOURCES = REPO_ROOT / "pipeline" / "sources.yaml"

EXTRACTION_SYSTEM = """\
You transcribe payroll tax parameters from official government publications
into machine-readable form for an open, citation-backed dataset. Accuracy is
the entire point of the project: a plausible-but-wrong number is the worst
possible outcome, far worse than flagging uncertainty in `notes`.

Rules:
- Every number comes from the attached document only. Never fill gaps from
  memory of other years or other states.
- Reproduce values exactly as printed, as decimal strings ("0.0440", not
  0.044). Rates are decimal fractions of 1.
- Bracket rows carry `over` = the row's LOWER bound; the first row's over is
  "0". If the document prints cumulative base tax amounts, transcribe them
  into `base`; otherwise set base to null.
- The `rounding` block must describe what the document's worked examples
  actually do, not what seems reasonable.
- Filing-status keys are machine identifiers: concise lower_snake_case
  (e.g. single, married_spouse_works, head_of_household), never the
  document's prose labels. When a prior edition's parameter file is
  provided, reuse its filing-status keys VERBATIM — key stability across
  years is part of the dataset's contract.
- Cite the page for every parameter group you transcribe.
"""

VERIFICATION_SYSTEM = """\
You are an independent verifier for a payroll tax dataset. You receive an
official government publication and a candidate parameter file that someone
else transcribed from it. Your job is adversarial: assume the candidate may
contain transcription errors and confirm or refute every numeric value
against the document, citing the page for each.

Also transcribe EVERY worked example in the document that exercises this
withholding method (percentage/formula method for the stated filing statuses)
into the structured worked_examples format — these become the dataset's
golden tests. Copy the example's inputs and final withholding amount exactly
as printed — expected_withholding is the example's FINAL total (including any
additional withholding it adds), never an intermediate line. When a state's
certificate combines a status code with a count (Alabama's "M-2" = married
with 2 dependents; Missouri-style "M-1"), split it: the letter is the
filing_status and the NUMBER goes in `allowances` — never leave the count
null when the example states one. For each
example's filing_status, use EXACTLY the filing-status
key spelled in the candidate parameter file (not the document's prose). If
an example states only annual wages, divide by the pay periods to per-period
wages (rounded to the cent). Skip an example and mention it in a check note
when it uses a mechanism outside the schema (supplemental wages, nonresident
aliens, pre-2020 W-4s for a federal_percentage_2020 candidate) — or when it
is computed by LOOKING UP a wage-bracket table instead of the formula:
table lookups embed bracket-midpoint rounding that the formula parameters
cannot and should not reproduce. Only formula/percentage-method computations
become golden tests.
"""


class ExtractionFailure(Exception):
    pass


def load_source(source_id: str) -> dict:
    for entry in yaml.safe_load(SOURCES.read_text()):
        if entry["id"] == source_id:
            return entry
    raise SystemExit(f"source id {source_id!r} not in pipeline/sources.yaml")


def _substitute_year(pattern: str, year: int) -> str:
    """{year} -> 2026, {yy} -> 26 (LA's 1306-1-{yy}.pdf, ME's {yy}_wh_tab_instr.pdf)."""
    return pattern.replace("{year}", str(year)).replace("{yy}", f"{year % 100:02d}")


def html_to_text(data: bytes, url: str) -> str:
    """Strip an HTML page to readable text for the model. Crude but
    sufficient: agencies' formula pages are simple documents."""
    import re

    html = data.decode("utf-8", errors="replace")
    html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    html = re.sub(r"<br[^>]*>|</(p|div|tr|li|h[1-6])>", "\n", html, flags=re.I)
    html = re.sub(r"</t[dh]>", "\t", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    import html as h

    text = h.unescape(html)
    # Collapse space runs but keep the tabs that mark table-cell boundaries.
    text = re.sub(r" +", " ", text)
    text = re.sub(r" ?\t[ \t]*", "\t", text)
    text = re.sub(r"\n[ \t]*(?=\n)|\t+(?=\n)", "", text)
    text = re.sub(r"\n\n+", "\n\n", text)
    return f"[HTML source: {url}]\n\n" + text.strip()


def stamp_edition_year(source_block: dict, effective_year: int) -> None:
    """Suffix the edition year onto a single-source citation's document name.
    Multi-source citations keep their registry names verbatim — each already
    identifies its own document (some carry their own years); the parameter
    file's effective_from carries the edition."""
    if "sources" not in source_block:
        source_block["document"] = f"{source_block['document']} ({effective_year})"


def fetch_documents(source: dict, year: int) -> list[dict]:
    """Multi-document sources: fetch every entry in `documents`. Returns
    [{name, kind, url, data, text?}] — PDFs keep bytes, HTML becomes text."""
    out = []
    for doc in source["documents"]:
        url = _substitute_year(doc["url"], year)
        data = discover.fetch(url, insecure=source.get("insecure_tls", False))
        kind = doc.get("kind", "pdf")
        if kind == "pdf" and not data.startswith(b"%PDF"):
            raise ExtractionFailure(f"{url}: expected PDF, got other bytes")
        entry = {"name": doc["name"], "kind": kind, "url": url, "data": data}
        if kind == "html":
            entry["text"] = html_to_text(data, url)
        out.append(entry)
    return out


def fetch_pdf(source: dict, year: int, pdf_path: str | None) -> tuple[bytes, str]:
    """Returns (pdf bytes, the URL they came from)."""
    if pdf_path:
        data = Path(pdf_path).expanduser().read_bytes()
        url = _substitute_year(source.get("document_url_pattern", source["landing"]), year)
    elif source.get("document_url_pattern"):
        url = _substitute_year(source["document_url_pattern"], year)
        data = discover.fetch(url, insecure=source.get("insecure_tls", False))
    elif source.get("discovery") == "link_scan":
        url = discover.discover_document_url(
            source["landing"], source["link_pattern"], year,
            insecure=source.get("insecure_tls", False),
        )
        print(f"      discovered {url}")
        data = discover.fetch(url, insecure=source.get("insecure_tls", False))
    else:
        raise SystemExit(f"{source['id']} has neither document_url_pattern nor link_scan discovery")
    if not data.startswith(b"%PDF"):
        raise ExtractionFailure(f"{url}: retrieved bytes are not a PDF (content_type_anomaly)")
    return data, url


def archive_pdf(data: bytes, source: dict, year: int, url: str) -> str:
    sha = hashlib.sha256(data).hexdigest()
    ARCHIVE_DIR.mkdir(exist_ok=True)
    (ARCHIVE_DIR / f"{sha}.pdf").write_bytes(data)
    (ARCHIVE_DIR / f"{sha}.json").write_text(
        json.dumps(
            {
                "source_id": source["id"],
                "year": year,
                "url": url,
                "retrieved": dt.date.today().isoformat(),
                "sha256": sha,
            },
            indent=2,
        )
    )
    return sha


def call_model(client, model: str, system: str, content: list, schema: dict) -> dict:
    with client.messages.stream(
        model=model,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise ExtractionFailure("model refused the request")
    if message.stop_reason == "max_tokens":
        raise ExtractionFailure("output truncated at max_tokens; raise the limit")
    text = next(b.text for b in message.content if b.type == "text")
    return json.loads(text)


def pdf_block(data: bytes) -> dict:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(data).decode(),
        },
    }


def find_prev_file(jurisdiction: str, tax: str) -> Path | None:
    candidates = []
    for path in (REPO_ROOT / "data").rglob("*.yaml"):
        raw = yaml.safe_load(path.read_text())
        if isinstance(raw, dict) and raw.get("jurisdiction") == jurisdiction and raw.get("tax") == tax:
            candidates.append((str(raw["effective_from"]), path))
    return max(candidates)[1] if candidates else None


def dump_yaml(mapping: dict) -> str:
    return yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True, width=100)


def run_mechanical_validation(param_dict: dict, golden_dicts: list[dict], taxability) -> list:
    """Schema + bracket validation, then run every transcribed example
    against the reference engine. Raises on any failure."""
    pf = load_parameter_dict(param_dict)
    if not golden_dicts:
        raise ExtractionFailure(
            "verification pass transcribed no worked examples; "
            "no worked example -> not mergeable (DESIGN.md §7)"
        )
    failures = []
    for g in golden_dicts:
        case = GoldenCase(
            path=Path("<candidate>"),
            source=g["source"],
            as_of=dt.date.fromisoformat(g["as_of"]),
            input_record=g["input"],
            expect=g["expect"],
        )
        for result in run_golden_case(case, [pf], taxability):
            if not result.ok:
                failures.append(
                    f"{g['source']['example']!r} (p.{g['source']['page']}): "
                    f"expected {result.expected}, engine produced {result.actual}"
                )
    if failures:
        raise ExtractionFailure("golden tests failed:\n  " + "\n  ".join(failures))
    return golden_dicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--pdf", help="Use a local PDF instead of downloading")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument(
        "--dry-run", action="store_true", help="Write candidates to pipeline/out/ only"
    )
    parser.add_argument(
        "--no-examples-ok",
        action="store_true",
        help="Accept a publication that prints no applicable worked examples: write the "
        "candidate without golden fixtures. The data-golden-guard CI job still blocks the "
        "PR until maintainer-constructed cases (noted as such) are added.",
    )
    args = parser.parse_args()

    import anthropic

    source = load_source(args.source_id)
    jurisdiction, tax, method = source["jurisdiction"], source["tax"], source["method"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] fetching + archiving {args.source_id} ...")
    documents = None
    if source.get("documents"):
        documents = fetch_documents(source, args.year)
        source_blocks = []
        for doc in documents:
            sha = hashlib.sha256(doc["data"]).hexdigest()
            ARCHIVE_DIR.mkdir(exist_ok=True)
            ext = "pdf" if doc["kind"] == "pdf" else "html"
            (ARCHIVE_DIR / f"{sha}.{ext}").write_bytes(doc["data"])
            doc["sha256"] = sha
            source_blocks.append({
                "document": doc["name"],
                "url": doc["url"],
                "retrieved": dt.date.today().isoformat(),
                "sha256": sha,
            })
            print(f"      archived {doc['name']} ({doc['kind']}, {len(doc['data'])//1024} KiB) {sha[:12]}...")
        source_block = {"sources": source_blocks}
    else:
        pdf, pdf_url = fetch_pdf(source, args.year, args.pdf)
        sha = archive_pdf(pdf, source, args.year, pdf_url)
        source_block = {
            "document": source["document"],
            "url": pdf_url,
            "retrieved": dt.date.today().isoformat(),
            "sha256": sha,
        }
        print(f"      archived archive/{sha}.pdf ({len(pdf)//1024} KiB)")

    method_spec = (REPO_ROOT / "methods" / f"{method}.md").read_text()
    prev_path = find_prev_file(jurisdiction, tax)
    if prev_path:
        prev_note = (
            "\n\nThe prior edition's parameter file (for shape reference only — every "
            "number must come from the attached document). Classify parameter_change or "
            "cosmetic_reissue RELATIVE TO THIS FILE:\n\n" + prev_path.read_text()
        )
    else:
        prev_note = (
            "\n\nThere is no prior edition in the dataset — this is the first import of "
            "this source, so classify it new_year_edition regardless of the document's "
            "own revision date."
        )

    client = anthropic.Anthropic()

    # Maintainer guidance from the registry: WHERE to read each value when
    # documents overlap or supersede each other — never the values themselves.
    hint = source.get("extraction_hint", "")
    hint_note = f"\n\nMaintainer notes on this source's documents:\n{hint}" if hint else ""

    print(f"[2/5] extraction pass ({args.model}) ...")
    extraction = call_model(
        client,
        args.model,
        EXTRACTION_SYSTEM,
        [
            *(
                [pdf_block(d["data"]) if d["kind"] == "pdf"
                 else {"type": "text", "text": d["text"]}
                 for d in documents]
                if documents else [pdf_block(pdf)]
            ),
            {
                "type": "text",
                "text": f"Jurisdiction: {jurisdiction}\nTax: {tax}\nMethod: {method}\n"
                f"Expected year: {args.year}\n\nThe normative method spec:\n\n{method_spec}"
                f"{prev_note}{hint_note}\n\nTranscribe this document's parameters for the method above.",
            },
        ],
        extraction_schema(method),
    )
    print(f"      classification: {extraction['classification']}")
    if extraction["classification"] == "cosmetic_reissue" and prev_path is None:
        # A first import can't be cosmetic — there's nothing to be identical to.
        print("      overriding to new_year_edition: no prior edition exists in the dataset")
        extraction["classification"] = "new_year_edition"
    if extraction["classification"] == "cosmetic_reissue":
        (OUT_DIR / f"{args.source_id}-{args.year}-cosmetic.json").write_text(json.dumps(extraction, indent=2))
        print("      cosmetic re-issue — no parameter change; nothing to PR. Details in pipeline/out/.")
        return 0

    # Layout follows the document's own effective date, not the requested
    # year: agencies don't reissue when nothing changed (CO's current DR 1098
    # is the 2024 edition), and effective-dating resolves later paychecks.
    effective_year = int(str(extraction["effective_from"])[:4])
    if effective_year != args.year:
        print(f"      note: document is effective {extraction['effective_from']} — "
              f"filing under {effective_year}, not {args.year}")
    stamp_edition_year(source_block, effective_year)

    param_dict = assemble.assemble_parameter_file(
        jurisdiction=jurisdiction,
        tax=tax,
        method=method,
        extraction=extraction,
        source=(
            source_block
            if "sources" in source_block
            else {**source_block, "notes": "Extracted by pipeline; pages per PR body"}
        ),
        supersedes=str(prev_path.relative_to(REPO_ROOT)) if prev_path else None,
    )
    candidate_yaml = dump_yaml(param_dict)

    print(f"[3/5] independent verification pass (separate context) ...")
    verification = call_model(
        client,
        args.model,
        VERIFICATION_SYSTEM,
        [
            *(
                [pdf_block(d["data"]) if d["kind"] == "pdf"
                 else {"type": "text", "text": d["text"]}
                 for d in documents]
                if documents else [pdf_block(pdf)]
            ),
            {
                "type": "text",
                "text": "The candidate parameter file to verify:\n\n```yaml\n"
                + candidate_yaml
                + "```\n\nConfirm every number against the document and transcribe all "
                "applicable worked examples." + hint_note,
            },
        ],
        VERIFICATION_SCHEMA,
    )
    unconfirmed = [c for c in verification["checks"] if not c["confirmed"]]

    # Maintainer-adjudicated print-defect corrections (registry `adjudications`).
    # Applied AFTER verification — the verifier must confirm the transcription
    # against the document as printed — and before validation, which checks the
    # corrected arithmetic. assemble.apply_adjudications guards that each
    # correction matches the transcribed printed value.
    applied_adjudications: list[dict] = []
    if source.get("adjudications"):
        try:
            applied_adjudications = assemble.apply_adjudications(
                param_dict["params"], source["adjudications"]
            )
        except ValueError as exc:
            (OUT_DIR / f"{args.source_id}-{args.year}-triage.md").write_text(
                f"# Triage: {args.source_id} {args.year}\n\n**Failure:** {exc}\n\n"
                f"## Candidate\n\n```yaml\n{candidate_yaml}```\n"
            )
            print(f"      FAILED — {exc}")
            return 1
        n_applied = sum(1 for a in applied_adjudications if a["status"] == "applied")
        if "source" in param_dict:
            param_dict["source"]["notes"] = (
                param_dict["source"].get("notes", "").rstrip() + "; "
                f"{n_applied} print-defect correction(s) adjudicated by maintainer "
                "(see PR / registry adjudications)"
            ).lstrip("; ")
        candidate_yaml = dump_yaml(param_dict)
        print(f"      applied {n_applied} maintainer adjudication(s) "
              f"({len(applied_adjudications) - n_applied} already correct in transcription)")

    print(f"[4/5] mechanical validation ...")
    as_of = assemble.default_as_of(extraction["effective_from"])
    golden_dicts = [
        assemble.assemble_golden_case(
            jurisdiction=jurisdiction,
            tax=tax,
            example=ex,
            as_of=as_of,
            # Multi-source blocks have no single name; cite the registry
            # entry's summary (e.g. "NJ-WT + Rate Tables A-E").
            document=source_block.get("document", source["document"]),
        )
        for ex in verification["worked_examples"]
    ]
    taxability = TaxabilityMatrix.from_file(REPO_ROOT / "taxability" / "us.yaml")
    try:
        if unconfirmed:
            raise ExtractionFailure(
                "verification could not confirm: "
                + "; ".join(f"{c['path']}={c['candidate_value']} ({c['note']})" for c in unconfirmed)
            )
        if not golden_dicts and args.no_examples_ok:
            load_parameter_dict(param_dict)  # schema + bracket validation still gates
            print("      schema OK; no worked examples in publication (--no-examples-ok); "
                  "maintainer-constructed golden cases required before merge")
        else:
            run_mechanical_validation(param_dict, golden_dicts, taxability)
            print(f"      schema OK; {len(golden_dicts)} golden case(s) reproduced by the engine")
    except (ExtractionFailure, EngineError) as exc:
        triage = OUT_DIR / f"{args.source_id}-{args.year}-triage.md"
        triage.write_text(
            f"# Triage: {args.source_id} {args.year}\n\n**Failure:** {exc}\n\n"
            f"## Candidate\n\n```yaml\n{candidate_yaml}```\n\n"
            f"## Extraction\n\n```json\n{json.dumps(extraction, indent=2)}\n```\n\n"
            f"## Verification\n\n```json\n{json.dumps(verification, indent=2)}\n```\n"
        )
        print(f"      FAILED — triage report written to {triage.relative_to(REPO_ROOT)}")
        print(f"      {exc}")
        return 1

    print(f"[5/5] writing candidate files ...")
    slug = assemble.golden_slug(jurisdiction)
    data_file = assemble.data_path(jurisdiction, effective_year)
    golden_paths = [
        f"tests/golden/{slug}-{effective_year}-{i + 1}.yaml" for i in range(len(golden_dicts))
    ]
    target_root = OUT_DIR / f"{args.source_id}-{args.year}" if args.dry_run else REPO_ROOT
    (target_root / data_file).parent.mkdir(parents=True, exist_ok=True)
    (target_root / data_file).write_text(candidate_yaml)
    for rel, g in zip(golden_paths, golden_dicts):
        (target_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (target_root / rel).write_text(dump_yaml(g))

    pr_body = assemble.build_pr_body(
        source_id=args.source_id,
        jurisdiction=jurisdiction,
        tax=tax,
        method=method,
        source=source_block,
        extraction=extraction,
        verification=verification,
        golden_paths=golden_paths,
        golden_ok=True,
        prev_path=str(prev_path.relative_to(REPO_ROOT)) if prev_path else None,
        adjudications=applied_adjudications,
    )
    pr_file = OUT_DIR / f"{args.source_id}-{args.year}-pr.md"
    pr_file.write_text(pr_body + "\n")

    print(f"      {data_file}")
    for rel in golden_paths:
        print(f"      {rel}")
    print(f"      PR body: {pr_file.relative_to(REPO_ROOT)}")
    branch = f"data/{slug}-{effective_year}"
    print(
        f"\nNext (human): review the diff, then:\n"
        f"  git checkout -b {branch} && git add data tests/golden && "
        f"git commit && gh pr create --body-file {pr_file.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
