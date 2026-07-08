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
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from engine.errors import EngineError  # noqa: E402
from engine.golden import GoldenCase, run_golden_case  # noqa: E402
from engine.loader import load_parameter_dict  # noqa: E402
from engine.taxability import TaxabilityMatrix  # noqa: E402
from pipeline import assemble  # noqa: E402
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
as printed. If an example uses a mechanism outside the schema (supplemental
wages, nonresident aliens, pre-2020 W-4s for a federal_percentage_2020
candidate), skip it and mention that in a check note.
"""


class ExtractionFailure(Exception):
    pass


def load_source(source_id: str) -> dict:
    for entry in yaml.safe_load(SOURCES.read_text()):
        if entry["id"] == source_id:
            return entry
    raise SystemExit(f"source id {source_id!r} not in pipeline/sources.yaml")


def fetch_pdf(source: dict, year: int, pdf_path: str | None) -> bytes:
    if pdf_path:
        data = Path(pdf_path).expanduser().read_bytes()
    else:
        url = source.get("document_url_pattern")
        if not url:
            raise SystemExit(
                f"{source['id']} has no document_url_pattern (link_scan discovery is not "
                f"implemented yet) — download the PDF and pass --pdf"
            )
        url = url.replace("{year}", str(year))
        request = urllib.request.Request(url, headers={"User-Agent": "open-withholding/0.1"})
        with urllib.request.urlopen(request, timeout=120) as resp:
            data = resp.read()
    if not data.startswith(b"%PDF"):
        raise ExtractionFailure("retrieved bytes are not a PDF (content_type_anomaly)")
    return data


def archive_pdf(data: bytes, source: dict, year: int) -> str:
    sha = hashlib.sha256(data).hexdigest()
    ARCHIVE_DIR.mkdir(exist_ok=True)
    (ARCHIVE_DIR / f"{sha}.pdf").write_bytes(data)
    (ARCHIVE_DIR / f"{sha}.json").write_text(
        json.dumps(
            {
                "source_id": source["id"],
                "year": year,
                "url": source.get("document_url_pattern", source["landing"]),
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
        max_tokens=32000,
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
    args = parser.parse_args()

    import anthropic

    source = load_source(args.source_id)
    jurisdiction, tax, method = source["jurisdiction"], source["tax"], source["method"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] fetching + archiving {args.source_id} ...")
    pdf = fetch_pdf(source, args.year, args.pdf)
    sha = archive_pdf(pdf, source, args.year)
    source_block = {
        "document": f"{source['document']} ({args.year})",
        "url": source.get("document_url_pattern", source["landing"]).replace("{year}", str(args.year)),
        "retrieved": dt.date.today().isoformat(),
        "sha256": sha,
    }
    print(f"      archived archive/{sha}.pdf ({len(pdf)//1024} KiB)")

    method_spec = (REPO_ROOT / "methods" / f"{method}.md").read_text()
    prev_path = find_prev_file(jurisdiction, tax)
    prev_note = ""
    if prev_path:
        prev_note = (
            "\n\nThe prior edition's parameter file (for shape reference only — every "
            "number must come from the attached document):\n\n" + prev_path.read_text()
        )

    client = anthropic.Anthropic()

    print(f"[2/5] extraction pass ({args.model}) ...")
    extraction = call_model(
        client,
        args.model,
        EXTRACTION_SYSTEM,
        [
            pdf_block(pdf),
            {
                "type": "text",
                "text": f"Jurisdiction: {jurisdiction}\nTax: {tax}\nMethod: {method}\n"
                f"Expected year: {args.year}\n\nThe normative method spec:\n\n{method_spec}"
                f"{prev_note}\n\nTranscribe this document's parameters for the method above.",
            },
        ],
        extraction_schema(method),
    )
    print(f"      classification: {extraction['classification']}")
    if extraction["classification"] == "cosmetic_reissue":
        (OUT_DIR / f"{args.source_id}-{args.year}-cosmetic.json").write_text(json.dumps(extraction, indent=2))
        print("      cosmetic re-issue — no parameter change; nothing to PR. Details in pipeline/out/.")
        return 0

    param_dict = assemble.assemble_parameter_file(
        jurisdiction=jurisdiction,
        tax=tax,
        method=method,
        extraction=extraction,
        source={**source_block, "notes": "Extracted by pipeline; pages per PR body"},
        supersedes=str(prev_path.relative_to(REPO_ROOT)) if prev_path else None,
    )
    candidate_yaml = dump_yaml(param_dict)

    print(f"[3/5] independent verification pass (separate context) ...")
    verification = call_model(
        client,
        args.model,
        VERIFICATION_SYSTEM,
        [
            pdf_block(pdf),
            {
                "type": "text",
                "text": "The candidate parameter file to verify:\n\n```yaml\n"
                + candidate_yaml
                + "```\n\nConfirm every number against the document and transcribe all "
                "applicable worked examples.",
            },
        ],
        VERIFICATION_SCHEMA,
    )
    unconfirmed = [c for c in verification["checks"] if not c["confirmed"]]

    print(f"[4/5] mechanical validation ...")
    as_of = assemble.default_as_of(extraction["effective_from"])
    golden_dicts = [
        assemble.assemble_golden_case(
            jurisdiction=jurisdiction,
            tax=tax,
            example=ex,
            as_of=as_of,
            document=source_block["document"],
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
        run_mechanical_validation(param_dict, golden_dicts, taxability)
    except (ExtractionFailure, EngineError) as exc:
        triage = OUT_DIR / f"{args.source_id}-{args.year}-triage.md"
        triage.write_text(
            f"# Triage: {args.source_id} {args.year}\n\n**Failure:** {exc}\n\n"
            f"## Candidate\n\n```yaml\n{candidate_yaml}```\n\n"
            f"## Verification\n\n```json\n{json.dumps(verification, indent=2)}\n```\n"
        )
        print(f"      FAILED — triage report written to {triage.relative_to(REPO_ROOT)}")
        print(f"      {exc}")
        return 1
    print(f"      schema OK; {len(golden_dicts)} golden case(s) reproduced by the engine")

    print(f"[5/5] writing candidate files ...")
    slug = assemble.golden_slug(jurisdiction)
    data_file = assemble.data_path(jurisdiction, args.year)
    golden_paths = [
        f"tests/golden/{slug}-{args.year}-{i + 1}.yaml" for i in range(len(golden_dicts))
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
    )
    pr_file = OUT_DIR / f"{args.source_id}-{args.year}-pr.md"
    pr_file.write_text(pr_body + "\n")

    print(f"      {data_file}")
    for rel in golden_paths:
        print(f"      {rel}")
    print(f"      PR body: {pr_file.relative_to(REPO_ROOT)}")
    branch = f"data/{slug}-{args.year}"
    print(
        f"\nNext (human): review the diff, then:\n"
        f"  git checkout -b {branch} && git add data tests/golden && "
        f"git commit && gh pr create --body-file {pr_file.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
